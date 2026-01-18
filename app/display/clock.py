"""Clock display widget with modern styling."""

import time
from datetime import datetime
from typing import Optional

import pygame
import pytz

from app.display.themes import Theme
from app.display.drawing import draw_rounded_rect


class ClockWidget:
    """Displays a large digital clock with modern styling."""

    def __init__(self, screen: pygame.Surface, theme: Theme, config: dict):
        self.screen = screen
        self.theme = theme
        self.config = config

        self._time_font: Optional[pygame.font.Font] = None
        self._date_font: Optional[pygame.font.Font] = None
        self._last_time_str: str = ""

        self._init_fonts()

    def _init_fonts(self):
        """Initialize the clock fonts."""
        font_size = self.theme.clock_font_size
        try:
            # Use a clean monospace font for the time
            self._time_font = pygame.font.SysFont('DejaVu Sans Mono', font_size)
            self._date_font = pygame.font.SysFont('DejaVu Sans', 28)  # Bigger date font
            self._ampm_font = pygame.font.SysFont('DejaVu Sans', 18)  # Separate smaller font for AM/PM
        except:
            self._time_font = pygame.font.Font(None, font_size)
            self._date_font = pygame.font.Font(None, 28)
            self._ampm_font = pygame.font.Font(None, 18)

    def update_theme(self, theme: Theme):
        """Update the theme and reinitialize font if needed."""
        if theme.clock_font_size != self.theme.clock_font_size:
            self.theme = theme
            self._init_fonts()
        else:
            self.theme = theme

    def update_config(self, config: dict):
        """Update the configuration."""
        self.config = config

    def get_current_time(self) -> tuple:
        """Get the current time and date strings based on config."""
        clock_config = self.config.get('clock', {})
        tz_name = clock_config.get('timezone', 'America/New_York')
        format_24h = clock_config.get('format_24h', False)
        show_seconds = clock_config.get('show_seconds', True)

        try:
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)
        except:
            now = datetime.now()

        # Time string
        if format_24h:
            if show_seconds:
                time_str = now.strftime('%H:%M:%S')
            else:
                time_str = now.strftime('%H:%M')
        else:
            if show_seconds:
                time_str = now.strftime('%I:%M:%S')
            else:
                time_str = now.strftime('%I:%M')

        # AM/PM indicator (only for 12-hour format)
        ampm = now.strftime('%p') if not format_24h else ""

        # Date string
        date_str = now.strftime('%A, %B %d')

        return time_str, ampm, date_str

    def render(self, rect: pygame.Rect) -> None:
        """
        Render the clock in the given rectangle with modern styling.

        Args:
            rect: The rectangle to render the clock in
        """
        time_str, ampm, date_str = self.get_current_time()

        # Top padding from screen edge
        top_padding = 15

        # Render the time text
        time_surface = self._time_font.render(
            time_str,
            True,
            self.theme.clock_color_rgb
        )

        # Add AM/PM if present
        ampm_surface = None
        if ampm:
            ampm_surface = self._ampm_font.render(
                ampm,
                True,
                self._lighten_color(self.theme.clock_color_rgb, -0.3)
            )

        # Render date
        date_surface = self._date_font.render(
            date_str,
            True,
            self.theme.weather_label_color_rgb
        )

        # Calculate total width: time + AM/PM + gap + date
        gap_between = 20  # Gap between time/ampm and date
        ampm_width = ampm_surface.get_width() + 8 if ampm_surface else 0
        total_width = time_surface.get_width() + ampm_width + gap_between + date_surface.get_width()

        # Center everything horizontally
        start_x = rect.centerx - total_width // 2

        # Position time at top with padding
        time_y = rect.top + top_padding

        # Draw time
        self.screen.blit(time_surface, (start_x, time_y))

        # Track current x position
        current_x = start_x + time_surface.get_width()

        # Draw AM/PM next to time (aligned to bottom of time)
        if ampm_surface:
            ampm_x = current_x + 8
            ampm_y = time_y + time_surface.get_height() - ampm_surface.get_height() - 5
            self.screen.blit(ampm_surface, (ampm_x, ampm_y))
            current_x = ampm_x + ampm_surface.get_width()

        # Draw date to the right, vertically centered with time
        date_x = current_x + gap_between
        date_y = time_y + (time_surface.get_height() - date_surface.get_height()) // 2
        self.screen.blit(date_surface, (date_x, date_y))

        self._last_time_str = time_str

    def _darken_color(self, color, amount):
        """Darken a color by a percentage."""
        return (
            max(0, int(color[0] * (1 - amount))),
            max(0, int(color[1] * (1 - amount))),
            max(0, int(color[2] * (1 - amount)))
        )

    def _lighten_color(self, color, amount):
        """Lighten (positive amount) or darken (negative amount) a color."""
        if amount >= 0:
            return (
                min(255, max(0, int(color[0] + (255 - color[0]) * amount))),
                min(255, max(0, int(color[1] + (255 - color[1]) * amount))),
                min(255, max(0, int(color[2] + (255 - color[2]) * amount)))
            )
        else:
            # Negative amount means darken
            factor = 1 + amount  # e.g., -0.3 becomes 0.7
            return (
                min(255, max(0, int(color[0] * factor))),
                min(255, max(0, int(color[1] * factor))),
                min(255, max(0, int(color[2] * factor)))
            )
