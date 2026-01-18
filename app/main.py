"""TablePi main application entry point."""

import os
import sys
import signal
import socket
from threading import Thread
from queue import Empty

import pygame

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.shared_state import SharedState, Queues, shutdown_event
from app.services.config import (
    load_config, load_theme, ConfigWatcher, get_default_theme
)
from app.display.themes import Theme
from app.display.clock import ClockWidget
from app.display.weather import WeatherWidget, ForecastGraphWidget, StatusBarWidget


class TablePiApp:
    """Main application class."""

    def __init__(self, state: SharedState, queues: Queues):
        self.state = state
        self.queues = queues

        self.screen = None
        self.clock = None
        self.running = False

        # Display widgets
        self.clock_widget = None
        self.weather_widget = None
        self.forecast_widget = None
        self.status_bar = None

        # Current theme
        self.theme = None

        # View state
        self.current_view = 'main'  # 'main' or 'hourly'
        self.selected_day = None

    def init_display(self):
        """Initialize PyGame and display."""
        pygame.init()
        pygame.font.init()

        config = self.state.get_config()
        display_config = config.get('display', {})

        width = display_config.get('width', 800)
        height = display_config.get('height', 480)
        fullscreen = display_config.get('fullscreen', True)

        flags = pygame.DOUBLEBUF
        if fullscreen:
            flags |= pygame.FULLSCREEN

        # Try to create display
        try:
            self.screen = pygame.display.set_mode((width, height), flags)
        except pygame.error:
            # Fallback to windowed mode
            self.screen = pygame.display.set_mode((width, height))

        pygame.display.set_caption('TablePi')
        pygame.mouse.set_visible(False)

        self.clock = pygame.time.Clock()

        # Initialize theme
        theme_name = config.get('theme', 'dark')
        theme_data = load_theme(theme_name)
        self.theme = Theme(theme_data)
        self.state.set_theme(theme_data)

        # Initialize widgets
        self.clock_widget = ClockWidget(self.screen, self.theme, config)
        self.weather_widget = WeatherWidget(self.screen, self.theme, config)
        self.forecast_widget = ForecastGraphWidget(self.screen, self.theme, config)
        self.status_bar = StatusBarWidget(self.screen, self.theme)

        # Get initial IP address
        self._update_ip_address()

        self.queues.log_info('Display initialized')

    def _update_ip_address(self):
        """Update the IP address."""
        ip = self._get_ip_address()
        self.state.set_ip_address(ip)
        self.status_bar.set_ip_address(ip)

    def _get_ip_address(self) -> str:
        """Get the device's IP address."""
        try:
            # Connect to a remote address to find our IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "No network"

    def _process_queues(self):
        """Process messages from queues (non-blocking)."""
        # Config changes
        try:
            msg = self.queues.config.get_nowait()
            if msg.get('type') == 'reload':
                self._reload_config()
        except Empty:
            pass

        # Weather updates
        try:
            msg = self.queues.weather.get_nowait()
            if msg.get('type') == 'update':
                self._update_weather(msg.get('data'))
        except Empty:
            pass

        # Commands from web UI
        try:
            msg = self.queues.command.get_nowait()
            self._handle_command(msg)
        except Empty:
            pass

    def _reload_config(self):
        """Reload configuration and theme."""
        config = load_config()
        self.state.set_config(config)

        # Reload theme
        theme_name = config.get('theme', 'dark')
        theme_data = load_theme(theme_name)
        self.theme = Theme(theme_data)
        self.state.set_theme(theme_data)

        # Update widgets
        self.clock_widget.update_theme(self.theme)
        self.clock_widget.update_config(config)
        self.weather_widget.update_theme(self.theme)
        self.weather_widget.update_config(config)
        self.forecast_widget.update_theme(self.theme)
        self.forecast_widget.update_config(config)
        self.status_bar.update_theme(self.theme)

    def _update_weather(self, data: dict):
        """Update weather data on widgets."""
        self.weather_widget.set_weather_data(data)
        self.forecast_widget.set_weather_data(data)

        # Update last fetch time on status bar
        _, last_fetch = self.state.get_weather()
        self.status_bar.set_last_update(last_fetch)

    def _handle_command(self, cmd: dict):
        """Handle a command from the web UI."""
        cmd_type = cmd.get('type')

        if cmd_type == 'youtube_play':
            # TODO: Implement YouTube playback
            self.queues.log_action(f"YouTube play: {cmd.get('video_id')}")

        elif cmd_type == 'theme_change':
            theme_name = cmd.get('theme')
            config = self.state.get_config()
            config['theme'] = theme_name
            self.state.set_config(config)
            self._reload_config()
            self.queues.log_action(f"Theme changed to {theme_name}")

    def _handle_events(self):
        """Handle PyGame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_q:
                    self.running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_touch(event.pos)

    def _handle_touch(self, pos):
        """Handle touch/click event."""
        config = self.state.get_config()
        display_config = config.get('display', {})
        width = display_config.get('width', 800)
        height = display_config.get('height', 480)

        if self.current_view == 'main':
            # Check if touch is on forecast graph
            graph_rect = pygame.Rect(0, 250, width, 200)
            day_idx = self.forecast_widget.handle_touch(pos, graph_rect)
            if day_idx is not None:
                self.selected_day = day_idx
                self.current_view = 'hourly'
                self.queues.log_action(f"Selected day {day_idx} for hourly view")

        elif self.current_view == 'hourly':
            # Check for back button (top-left area)
            back_rect = pygame.Rect(0, 0, 100, 50)
            if back_rect.collidepoint(pos):
                self.current_view = 'main'
                self.selected_day = None

    def _render(self):
        """Render the display."""
        config = self.state.get_config()
        display_config = config.get('display', {})
        width = display_config.get('width', 800)
        height = display_config.get('height', 480)

        # Clear screen
        self.screen.fill(self.theme.background_rgb)

        if self.current_view == 'main':
            self._render_main_view(width, height)
        elif self.current_view == 'hourly':
            self._render_hourly_view(width, height)

        pygame.display.flip()

    def _render_main_view(self, width: int, height: int):
        """Render the main view with clock, weather, and graph."""
        # Layout regions
        clock_rect = pygame.Rect(0, 0, width, 80)
        weather_rect = pygame.Rect(0, 80, width, 120)
        graph_rect = pygame.Rect(0, 200, width, height - 230)
        status_rect = pygame.Rect(0, height - 30, width, 30)

        # Render widgets
        self.clock_widget.render(clock_rect)
        self.weather_widget.render(weather_rect)
        self.forecast_widget.render(graph_rect)

        # Update status bar with latest info
        _, last_fetch = self.state.get_weather()
        self.status_bar.set_last_update(last_fetch)
        self.status_bar.render(status_rect)

    def _render_hourly_view(self, width: int, height: int):
        """Render the hourly detail view."""
        # Draw back button
        back_font = pygame.font.SysFont('DejaVu Sans', 24)
        back_text = "← Back"
        back_surface = back_font.render(back_text, True, self.theme.clock_color_rgb)
        self.screen.blit(back_surface, (10, 10))

        # TODO: Implement full hourly view
        # For now, show placeholder
        placeholder_font = pygame.font.SysFont('DejaVu Sans', 20)
        text = f"Hourly view for day {self.selected_day} (Coming soon)"
        surface = placeholder_font.render(text, True, self.theme.weather_value_color_rgb)
        rect = surface.get_rect(center=(width // 2, height // 2))
        self.screen.blit(surface, rect)

    def run(self):
        """Main application loop."""
        self.running = True
        config = self.state.get_config()
        fps = config.get('display', {}).get('fps', 30)

        # Periodically update IP (every 60 seconds)
        ip_update_counter = 0
        ip_update_interval = fps * 60

        while self.running and not shutdown_event.is_set():
            self._process_queues()
            self._handle_events()
            self._render()

            # Update IP periodically
            ip_update_counter += 1
            if ip_update_counter >= ip_update_interval:
                self._update_ip_address()
                ip_update_counter = 0

            self.clock.tick(fps)

        pygame.quit()


def run_app(state: SharedState, queues: Queues):
    """Run the main application."""
    app = TablePiApp(state, queues)
    app.init_display()
    app.run()


def main():
    """Main entry point."""
    # Set up signal handlers
    def signal_handler(sig, frame):
        print("\nShutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize shared state and queues
    state = SharedState()
    queues = Queues()

    # Load initial configuration
    config = load_config()
    state.set_config(config)

    # Load initial theme
    theme_name = config.get('theme', 'dark')
    theme_data = load_theme(theme_name)
    if not theme_data:
        theme_data = get_default_theme()
    state.set_theme(theme_data)

    queues.log_info('TablePi starting')

    # Start background threads
    threads = []

    # Config watcher
    config_watcher = ConfigWatcher(state, queues)
    config_watcher.start()
    threads.append(config_watcher)

    # Import and start other services
    weather_service = None
    try:
        from app.services.weather import WeatherService
        weather_service = WeatherService(state, queues)
        weather_service.start()
        threads.append(weather_service)
    except ImportError:
        queues.log_info('Weather service not available')

    try:
        from app.services.log import LogService
        log_service = LogService(queues)
        log_service.start()
        threads.append(log_service)
    except ImportError:
        queues.log_info('Log service not available')

    try:
        from app.web.server import run_flask_thread
        flask_thread = Thread(target=run_flask_thread, args=(state, queues, weather_service), daemon=True)
        flask_thread.start()
        threads.append(flask_thread)
    except ImportError:
        queues.log_info('Web server not available')

    # Run main display
    run_app(state, queues)

    # Cleanup
    shutdown_event.set()
    for t in threads:
        if hasattr(t, 'join'):
            t.join(timeout=2)

    print("TablePi stopped")


if __name__ == '__main__':
    main()
