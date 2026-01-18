"""Weather display widget with modern UI."""

import time
from datetime import datetime
from typing import Optional, Tuple

import pygame
import pytz

from app.display.themes import Theme
from app.display.drawing import draw_rounded_rect, draw_smooth_line
from app.display.colors import (
    get_temperature_color, get_precipitation_color, get_uv_color,
    get_wind_color, get_humidity_color, get_moon_phase_icon,
    get_weather_icon, hex_to_rgb
)


class WeatherWidget:
    """Displays current weather conditions in a modern card layout."""

    def __init__(self, screen: pygame.Surface, theme: Theme, config: dict):
        self.screen = screen
        self.theme = theme
        self.config = config

        self._label_font: Optional[pygame.font.Font] = None
        self._value_font: Optional[pygame.font.Font] = None
        self._large_font: Optional[pygame.font.Font] = None
        self._icon_font: Optional[pygame.font.Font] = None
        self._small_font: Optional[pygame.font.Font] = None

        self._weather_data: Optional[dict] = None

        self._init_fonts()

    def _init_fonts(self):
        """Initialize fonts."""
        try:
            self._label_font = pygame.font.SysFont('DejaVu Sans', 14)
            self._value_font = pygame.font.SysFont('DejaVu Sans', 18)
            self._large_font = pygame.font.SysFont('DejaVu Sans', 48)
            self._small_font = pygame.font.SysFont('DejaVu Sans', 12)
            self._icon_font = pygame.font.SysFont('Segoe UI Emoji', 32)
        except:
            self._label_font = pygame.font.Font(None, 14)
            self._value_font = pygame.font.Font(None, 18)
            self._large_font = pygame.font.Font(None, 48)
            self._small_font = pygame.font.Font(None, 12)
            self._icon_font = pygame.font.Font(None, 32)

    def update_theme(self, theme: Theme):
        """Update the theme."""
        self.theme = theme

    def update_config(self, config: dict):
        """Update the configuration."""
        self.config = config

    def set_weather_data(self, data: dict):
        """Set the weather data to display."""
        self._weather_data = data

    def _get_color(self, color_func, value, *args) -> Tuple[int, int, int]:
        """Get color based on dynamic colors setting."""
        if self.theme.use_dynamic_colors:
            result = color_func(value, *args) if args else color_func(value)
            if isinstance(result, tuple):
                color = result[0]
            else:
                color = result
            return hex_to_rgb(color)
        return self.theme.weather_value_color_rgb

    def render(self, rect: pygame.Rect) -> None:
        """Render the weather widget in the given rectangle."""
        if not self._weather_data:
            self._render_no_data(rect)
            return

        current = self._weather_data.get('current', {})
        daily = self._weather_data.get('daily', [{}])[0] if self._weather_data.get('daily') else {}

        # Extract weather values
        temp = current.get('temp', 0)
        feels_like = current.get('feels_like', 0)
        humidity = current.get('humidity', 0)
        wind_speed = current.get('wind_speed', 0)
        wind_deg = current.get('wind_deg', 0)
        uvi = current.get('uvi', 0)
        weather_icon = current.get('weather', [{}])[0].get('icon', '01d') if current.get('weather') else '01d'
        weather_desc = current.get('weather', [{}])[0].get('description', '') if current.get('weather') else ''

        # Precipitation (include rain and snow amounts)
        pop = daily.get('pop', 0) * 100
        rain_amount = current.get('rain', {}).get('1h', 0) if isinstance(current.get('rain'), dict) else 0
        snow_amount = current.get('snow', {}).get('1h', 0) if isinstance(current.get('snow'), dict) else 0
        precip_total = rain_amount + snow_amount
        sunrise = current.get('sunrise', 0)
        sunset = current.get('sunset', 0)
        moon_phase = daily.get('moon_phase', 0)

        # Get units
        units = self.config.get('weather', {}).get('units', 'imperial')
        temp_unit = '°F' if units == 'imperial' else '°C'
        speed_unit = 'mph' if units == 'imperial' else 'm/s'

        # Card styling
        padding = 15
        card_margin = 8
        card_radius = 12
        card_bg = self._darken_color(self.theme.background_rgb, 0.15)

        # Calculate card dimensions - horizontal layout
        card_height = rect.height - padding * 2
        main_card_width = rect.width * 0.35
        stats_card_width = rect.width * 0.35
        sun_card_width = rect.width * 0.25

        # Main temperature card (left)
        main_rect = pygame.Rect(
            rect.left + padding,
            rect.top + padding,
            main_card_width - card_margin,
            card_height
        )
        self._render_main_temp_card(main_rect, temp, feels_like, weather_icon, weather_desc, temp_unit, card_bg, card_radius)

        # Stats card (middle)
        stats_rect = pygame.Rect(
            main_rect.right + card_margin * 2,
            rect.top + padding,
            stats_card_width - card_margin,
            card_height
        )
        self._render_stats_card(stats_rect, humidity, wind_speed, wind_deg, pop, uvi, speed_unit, card_bg, card_radius, precip_total, rain_amount, snow_amount)

        # Sun/Moon card (right)
        sun_rect = pygame.Rect(
            stats_rect.right + card_margin * 2,
            rect.top + padding,
            sun_card_width - card_margin - padding,
            card_height
        )
        self._render_sun_card(sun_rect, sunrise, sunset, moon_phase, card_bg, card_radius)

    def _render_main_temp_card(self, rect, temp, feels_like, icon, desc, unit, bg_color, radius):
        """Render the main temperature card."""
        draw_rounded_rect(self.screen, bg_color, rect, radius)

        padding = 6
        max_width = rect.width - padding * 2

        # Weather emoji
        weather_emoji = get_weather_icon(icon)
        try:
            emoji_surface = self._icon_font.render(weather_emoji, True, self.theme.weather_value_color_rgb)
        except:
            emoji_surface = self._icon_font.render("☀", True, self.theme.weather_value_color_rgb)
        emoji_rect = emoji_surface.get_rect(centerx=rect.centerx, top=rect.top + 6)
        self.screen.blit(emoji_surface, emoji_rect)

        # Temperature
        temp_color = self._get_color(get_temperature_color, temp)
        temp_str = f"{temp:.0f}{unit}"
        temp_surface = self._large_font.render(temp_str, True, temp_color)
        # Ensure temperature fits
        temp_x = max(rect.left + padding, rect.centerx - temp_surface.get_width() // 2)
        temp_rect = temp_surface.get_rect(left=temp_x, top=emoji_rect.bottom + 1)
        self.screen.blit(temp_surface, temp_rect)

        # Feels like
        feels_color = self._get_color(get_temperature_color, feels_like)
        feels_str = f"Feels {feels_like:.0f}{unit}"
        feels_surface = self._small_font.render(feels_str, True, feels_color)
        feels_rect = feels_surface.get_rect(centerx=rect.centerx, top=temp_rect.bottom + 1)
        self.screen.blit(feels_surface, feels_rect)

        # Description - truncate if too long
        if desc:
            desc_text = desc.title()
            desc_surface = self._small_font.render(desc_text, True, self.theme.weather_label_color_rgb)
            # Truncate if needed
            while desc_surface.get_width() > max_width and len(desc_text) > 3:
                desc_text = desc_text[:-1]
                desc_surface = self._small_font.render(desc_text + "..", True, self.theme.weather_label_color_rgb)
            desc_rect = desc_surface.get_rect(centerx=rect.centerx, bottom=rect.bottom - 6)
            self.screen.blit(desc_surface, desc_rect)

    def _render_stats_card(self, rect, humidity, wind, wind_deg, rain_chance, uvi, speed_unit, bg_color, radius, precip_total=0, rain_amount=0, snow_amount=0):
        """Render the stats card with grid layout."""
        draw_rounded_rect(self.screen, bg_color, rect, radius)

        # 2x2 grid layout
        cell_width = rect.width // 2
        cell_height = rect.height // 2
        padding = 6
        icon_width = 22

        # Build precipitation label with rain/snow amounts
        if precip_total > 0:
            units = self.config.get('weather', {}).get('units', 'imperial')
            precip_unit = 'in' if units == 'imperial' else 'mm'
            if snow_amount > 0 and rain_amount > 0:
                precip_label = f"R+S:{precip_total:.1f}{precip_unit}"
            elif snow_amount > 0:
                precip_label = f"Snow:{snow_amount:.1f}{precip_unit}"
            else:
                precip_label = f"Rain:{rain_amount:.1f}{precip_unit}"
        else:
            precip_label = "Precip"

        stats = [
            ("💧", f"{humidity:.0f}%", "Humidity", self._get_color(get_humidity_color, humidity)),
            ("💨", f"{wind:.0f}{speed_unit}", self._wind_direction(wind_deg), self._get_color(get_wind_color, wind)),
            ("🌧", f"{rain_chance:.0f}%", precip_label, self._get_color(get_precipitation_color, rain_chance)),
            ("☀", f"UV {uvi:.0f}", "Index", self._get_uv_display_color(uvi)),
        ]

        for i, (icon, value, label, color) in enumerate(stats):
            col = i % 2
            row = i // 2
            cell_x = rect.left + col * cell_width
            cell_y = rect.top + row * cell_height
            max_text_width = cell_width - padding * 2 - icon_width

            # Icon
            try:
                icon_surface = self._value_font.render(icon, True, color)
            except:
                icon_surface = self._value_font.render("*", True, color)
            icon_rect = icon_surface.get_rect(left=cell_x + padding, top=cell_y + padding)
            self.screen.blit(icon_surface, icon_rect)

            # Value - truncate if needed
            value_surface = self._value_font.render(value, True, color)
            value_x = icon_rect.right + 2
            # Ensure value fits within cell
            if value_surface.get_width() > max_text_width:
                # Truncate value
                truncated = value
                while value_surface.get_width() > max_text_width and len(truncated) > 2:
                    truncated = truncated[:-1]
                    value_surface = self._value_font.render(truncated, True, color)
            self.screen.blit(value_surface, (value_x, icon_rect.top))

            # Label - truncate if needed
            label_surface = self._small_font.render(label, True, self.theme.weather_label_color_rgb)
            if label_surface.get_width() > max_text_width:
                truncated = label
                while label_surface.get_width() > max_text_width and len(truncated) > 2:
                    truncated = truncated[:-1]
                    label_surface = self._small_font.render(truncated, True, self.theme.weather_label_color_rgb)
            self.screen.blit(label_surface, (cell_x + padding, icon_rect.bottom + 1))

    def _render_sun_card(self, rect, sunrise, sunset, moon_phase, bg_color, radius):
        """Render the sunrise/sunset card."""
        draw_rounded_rect(self.screen, bg_color, rect, radius)

        tz_name = self.config.get('clock', {}).get('timezone', 'America/New_York')
        try:
            tz = pytz.timezone(tz_name)
        except:
            tz = pytz.UTC

        sunrise_dt = datetime.fromtimestamp(sunrise, tz) if sunrise else None
        sunset_dt = datetime.fromtimestamp(sunset, tz) if sunset else None
        sunrise_str = sunrise_dt.strftime('%I:%M') if sunrise_dt else '--:--'
        sunset_str = sunset_dt.strftime('%I:%M') if sunset_dt else '--:--'

        moon_emoji, moon_name = get_moon_phase_icon(moon_phase)

        padding = 8
        icon_width = 28
        available_width = rect.width - padding * 2
        y = rect.top + padding

        # Sunrise
        sun_up = "☀↑"
        try:
            icon_surface = self._value_font.render(sun_up, True, (255, 200, 100))
        except:
            icon_surface = self._value_font.render("↑", True, (255, 200, 100))
        self.screen.blit(icon_surface, (rect.left + padding, y))

        time_surface = self._value_font.render(sunrise_str, True, self.theme.weather_value_color_rgb)
        # Ensure time fits within card
        time_x = min(rect.left + padding + icon_width, rect.right - time_surface.get_width() - padding)
        self.screen.blit(time_surface, (time_x, y))
        y += 26

        # Sunset
        sun_down = "☀↓"
        try:
            icon_surface = self._value_font.render(sun_down, True, (255, 150, 100))
        except:
            icon_surface = self._value_font.render("↓", True, (255, 150, 100))
        self.screen.blit(icon_surface, (rect.left + padding, y))

        time_surface = self._value_font.render(sunset_str, True, self.theme.weather_value_color_rgb)
        time_x = min(rect.left + padding + icon_width, rect.right - time_surface.get_width() - padding)
        self.screen.blit(time_surface, (time_x, y))
        y += 26

        # Moon phase
        try:
            moon_surface = self._value_font.render(moon_emoji, True, (200, 200, 220))
        except:
            moon_surface = self._value_font.render("🌙", True, (200, 200, 220))
        self.screen.blit(moon_surface, (rect.left + padding, y))

        # Moon name - truncate to fit within card
        max_name_width = available_width - icon_width - 4
        moon_abbrev = moon_name
        name_surface = self._small_font.render(moon_abbrev, True, self.theme.weather_label_color_rgb)
        # Truncate if needed
        while name_surface.get_width() > max_name_width and len(moon_abbrev) > 3:
            moon_abbrev = moon_abbrev[:-1]
            name_surface = self._small_font.render(moon_abbrev + "..", True, self.theme.weather_label_color_rgb)
        self.screen.blit(name_surface, (rect.left + padding + icon_width, y + 3))

    def _get_uv_display_color(self, uvi):
        """Get UV color for display."""
        if self.theme.use_dynamic_colors:
            color, _ = get_uv_color(uvi)
            return hex_to_rgb(color)
        return self.theme.weather_value_color_rgb

    def _render_no_data(self, rect: pygame.Rect):
        """Render placeholder when no weather data."""
        card_bg = self._darken_color(self.theme.background_rgb, 0.15)
        card_rect = pygame.Rect(rect.left + 15, rect.top + 15, rect.width - 30, rect.height - 30)
        draw_rounded_rect(self.screen, card_bg, card_rect, 12)

        text = "Weather data loading..."
        surface = self._value_font.render(text, True, self.theme.weather_label_color_rgb)
        text_rect = surface.get_rect(center=card_rect.center)
        self.screen.blit(surface, text_rect)

    def _wind_direction(self, degrees: float) -> str:
        """Convert wind degrees to compass direction."""
        directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                      'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        idx = round(degrees / 22.5) % 16
        return directions[idx]

    def _darken_color(self, color, amount):
        """Darken a color by a percentage."""
        return (
            max(0, int(color[0] * (1 - amount))),
            max(0, int(color[1] * (1 - amount))),
            max(0, int(color[2] * (1 - amount)))
        )


class ForecastGraphWidget:
    """Displays 7-day forecast as a smooth graph with modern styling."""

    def __init__(self, screen: pygame.Surface, theme: Theme, config: dict):
        self.screen = screen
        self.theme = theme
        self.config = config

        self._label_font: Optional[pygame.font.Font] = None
        self._value_font: Optional[pygame.font.Font] = None
        self._weather_data: Optional[dict] = None
        self._selected_day: Optional[int] = None

        self._init_fonts()

    def _init_fonts(self):
        """Initialize fonts."""
        try:
            self._label_font = pygame.font.SysFont('DejaVu Sans', 13)
            self._value_font = pygame.font.SysFont('DejaVu Sans', 11)
        except:
            self._label_font = pygame.font.Font(None, 13)
            self._value_font = pygame.font.Font(None, 11)

    def update_theme(self, theme: Theme):
        """Update the theme."""
        self.theme = theme

    def update_config(self, config: dict):
        """Update the configuration."""
        self.config = config

    def set_weather_data(self, data: dict):
        """Set the weather data to display."""
        self._weather_data = data

    def handle_touch(self, pos: Tuple[int, int], rect: pygame.Rect) -> Optional[int]:
        """Handle touch event and return selected day index if any."""
        if not rect.collidepoint(pos):
            return None

        if not self._weather_data or not self._weather_data.get('daily'):
            return None

        daily = self._weather_data['daily'][:7]
        if not daily:
            return None

        padding = 50
        graph_left = rect.left + padding
        graph_width = rect.width - padding - 20
        day_width = graph_width / len(daily)

        x = pos[0] - graph_left
        if x < 0 or x > graph_width:
            return None

        day_idx = int(x / day_width)
        if 0 <= day_idx < len(daily):
            self._selected_day = day_idx
            return day_idx

        return None

    def render(self, rect: pygame.Rect) -> None:
        """Render the forecast graph in the given rectangle."""
        if not self._weather_data or not self._weather_data.get('daily'):
            self._render_no_data(rect)
            return

        daily = self._weather_data['daily'][:7]
        if not daily:
            self._render_no_data(rect)
            return

        # Card background with rounded corners
        card_margin = 15
        card_rect = pygame.Rect(
            rect.left + card_margin,
            rect.top + card_margin // 2,
            rect.width - card_margin * 2,
            rect.height - card_margin
        )
        card_bg = self._darken_color(self.theme.background_rgb, 0.15)
        draw_rounded_rect(self.screen, card_bg, card_rect, 12)

        # Calculate bounds
        padding_left = 45
        padding_right = 15
        padding_top = 25
        padding_bottom = 45

        graph_left = card_rect.left + padding_left
        graph_right = card_rect.right - padding_right
        graph_top = card_rect.top + padding_top
        graph_bottom = card_rect.bottom - padding_bottom
        graph_width = graph_right - graph_left
        graph_height = graph_bottom - graph_top

        # Get temperature range
        highs = [d['temp']['max'] for d in daily]
        lows = [d['temp']['min'] for d in daily]
        temp_min = min(lows) - 5
        temp_max = max(highs) + 5
        temp_range = max(temp_max - temp_min, 1)

        # Draw subtle grid lines
        grid_color = self._lighten_color(card_bg, 0.15)
        for i in range(5):
            y = graph_top + (graph_height * i / 4)
            pygame.draw.line(self.screen, grid_color, (graph_left, int(y)), (graph_right, int(y)), 1)

            # Temperature labels
            temp_label = temp_max - (temp_range * i / 4)
            label_surface = self._value_font.render(f"{temp_label:.0f}°", True, self.theme.graph_label_color_rgb)
            self.screen.blit(label_surface, (card_rect.left + 8, int(y) - 6))

        # Calculate points
        day_width = graph_width / len(daily)
        high_points = []
        low_points = []

        for i, day in enumerate(daily):
            x = graph_left + day_width * i + day_width / 2

            high_y = graph_top + graph_height * (1 - (day['temp']['max'] - temp_min) / temp_range)
            low_y = graph_top + graph_height * (1 - (day['temp']['min'] - temp_min) / temp_range)

            high_points.append((x, high_y))
            low_points.append((x, low_y))

            # Day label with weather icon
            dt = datetime.fromtimestamp(day['dt'])
            day_name = dt.strftime('%a')

            # Highlight selected day
            if self._selected_day == i:
                highlight_rect = pygame.Rect(
                    graph_left + day_width * i + 2,
                    graph_top,
                    day_width - 4,
                    graph_height
                )
                # Draw semi-transparent highlight
                s = pygame.Surface((highlight_rect.width, highlight_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(s, (self.theme.accent_secondary_rgb[0], self.theme.accent_secondary_rgb[1], self.theme.accent_secondary_rgb[2], 40), s.get_rect(), border_radius=6)
                self.screen.blit(s, highlight_rect.topleft)

            # Day name
            label_surface = self._label_font.render(day_name, True, self.theme.graph_label_color_rgb)
            label_rect = label_surface.get_rect(centerx=int(x), top=graph_bottom + 8)
            self.screen.blit(label_surface, label_rect)

            # Weather icon for the day
            if day.get('weather'):
                icon_code = day['weather'][0].get('icon', '01d')
                weather_emoji = get_weather_icon(icon_code)
                try:
                    icon_surface = self._value_font.render(weather_emoji, True, self.theme.weather_value_color_rgb)
                    icon_rect = icon_surface.get_rect(centerx=int(x), top=label_rect.bottom + 1)
                    self.screen.blit(icon_surface, icon_rect)
                except:
                    pass

        # Draw smooth lines using Catmull-Rom spline
        if len(high_points) > 1:
            draw_smooth_line(self.screen, self.theme.graph_high_line_rgb, high_points, 3)
            draw_smooth_line(self.screen, self.theme.graph_low_line_rgb, low_points, 3)

        # Draw points with glow effect
        for i, (high_pt, low_pt) in enumerate(zip(high_points, low_points)):
            # High point
            pygame.draw.circle(self.screen, self._darken_color(self.theme.graph_high_line_rgb, 0.3), (int(high_pt[0]), int(high_pt[1])), 7)
            pygame.draw.circle(self.screen, self.theme.graph_high_line_rgb, (int(high_pt[0]), int(high_pt[1])), 5)
            pygame.draw.circle(self.screen, (255, 255, 255), (int(high_pt[0]), int(high_pt[1])), 2)

            # Low point
            pygame.draw.circle(self.screen, self._darken_color(self.theme.graph_low_line_rgb, 0.3), (int(low_pt[0]), int(low_pt[1])), 7)
            pygame.draw.circle(self.screen, self.theme.graph_low_line_rgb, (int(low_pt[0]), int(low_pt[1])), 5)
            pygame.draw.circle(self.screen, (255, 255, 255), (int(low_pt[0]), int(low_pt[1])), 2)

            # Temperature values near points
            high_temp = daily[i]['temp']['max']
            low_temp = daily[i]['temp']['min']

            high_label = self._value_font.render(f"{high_temp:.0f}°", True, self.theme.graph_high_line_rgb)
            low_label = self._value_font.render(f"{low_temp:.0f}°", True, self.theme.graph_low_line_rgb)

            self.screen.blit(high_label, (int(high_pt[0]) - high_label.get_width() // 2, int(high_pt[1]) - 18))
            self.screen.blit(low_label, (int(low_pt[0]) - low_label.get_width() // 2, int(low_pt[1]) + 8))

        # Title
        title_surface = self._label_font.render("7-Day Forecast", True, self.theme.weather_value_color_rgb)
        title_rect = title_surface.get_rect(left=card_rect.left + 15, top=card_rect.top + 6)
        self.screen.blit(title_surface, title_rect)

    def _render_no_data(self, rect: pygame.Rect):
        """Render placeholder when no weather data."""
        card_margin = 15
        card_rect = pygame.Rect(rect.left + card_margin, rect.top + card_margin // 2, rect.width - card_margin * 2, rect.height - card_margin)
        card_bg = self._darken_color(self.theme.background_rgb, 0.15)
        draw_rounded_rect(self.screen, card_bg, card_rect, 12)

        text = "Forecast data loading..."
        surface = self._label_font.render(text, True, self.theme.graph_label_color_rgb)
        text_rect = surface.get_rect(center=card_rect.center)
        self.screen.blit(surface, text_rect)

    def _darken_color(self, color, amount):
        """Darken a color."""
        return (
            max(0, int(color[0] * (1 - amount))),
            max(0, int(color[1] * (1 - amount))),
            max(0, int(color[2] * (1 - amount)))
        )

    def _lighten_color(self, color, amount):
        """Lighten a color."""
        return (
            min(255, int(color[0] + (255 - color[0]) * amount)),
            min(255, int(color[1] + (255 - color[1]) * amount)),
            min(255, int(color[2] + (255 - color[2]) * amount))
        )


class StatusBarWidget:
    """Displays IP address and last update time with modern styling."""

    def __init__(self, screen: pygame.Surface, theme: Theme):
        self.screen = screen
        self.theme = theme

        self._font: Optional[pygame.font.Font] = None
        self._ip_address: str = "..."
        self._last_update: Optional[float] = None

        self._init_font()

    def _init_font(self):
        """Initialize the font."""
        try:
            self._font = pygame.font.SysFont('DejaVu Sans', 12)
        except:
            self._font = pygame.font.Font(None, 12)

    def update_theme(self, theme: Theme):
        """Update the theme."""
        self.theme = theme

    def set_ip_address(self, ip: str):
        """Set the IP address to display."""
        self._ip_address = ip or "No network"

    def set_last_update(self, timestamp: Optional[float]):
        """Set the last API update timestamp."""
        self._last_update = timestamp

    def _format_time_ago(self, timestamp: float) -> str:
        """Format a timestamp as time ago string."""
        if timestamp is None:
            return "Never"

        elapsed = time.time() - timestamp
        if elapsed < 60:
            return "Just now"
        elif elapsed < 3600:
            mins = int(elapsed / 60)
            return f"{mins}m ago"
        elif elapsed < 86400:
            hours = int(elapsed / 3600)
            return f"{hours}h ago"
        else:
            days = int(elapsed / 86400)
            return f"{days}d ago"

    def render(self, rect: pygame.Rect) -> None:
        """Render the status bar in the given rectangle."""
        # Draw subtle background
        bar_color = self._darken_color(self.theme.background_rgb, 0.2)
        pygame.draw.rect(self.screen, bar_color, rect)

        # Draw top border line
        border_color = self._lighten_color(bar_color, 0.1)
        pygame.draw.line(self.screen, border_color, (rect.left, rect.top), (rect.right, rect.top), 1)

        padding = 15
        text_color = self.theme.status_bar_text_color_rgb

        # IP address on left with icon
        ip_text = f"IP: {self._ip_address}"
        ip_surface = self._font.render(ip_text, True, text_color)
        self.screen.blit(ip_surface, (rect.left + padding, rect.centery - ip_surface.get_height() // 2))

        # Web UI hint in center
        web_text = f"Web UI: http://{self._ip_address}:5000"
        web_surface = self._font.render(web_text, True, self._lighten_color(text_color, 0.3))
        web_rect = web_surface.get_rect(center=(rect.centerx, rect.centery))
        self.screen.blit(web_surface, web_rect)

        # Last update on right
        update_text = f"Updated: {self._format_time_ago(self._last_update)}"
        update_surface = self._font.render(update_text, True, text_color)
        self.screen.blit(
            update_surface,
            (rect.right - update_surface.get_width() - padding,
             rect.centery - update_surface.get_height() // 2)
        )

    def _darken_color(self, color, amount):
        """Darken a color."""
        return (
            max(0, int(color[0] * (1 - amount))),
            max(0, int(color[1] * (1 - amount))),
            max(0, int(color[2] * (1 - amount)))
        )

    def _lighten_color(self, color, amount):
        """Lighten a color."""
        return (
            min(255, int(color[0] + (255 - color[0]) * amount)),
            min(255, int(color[1] + (255 - color[1]) * amount)),
            min(255, int(color[2] + (255 - color[2]) * amount))
        )
