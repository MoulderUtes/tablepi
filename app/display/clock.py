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
            self._date_font = pygame.font.SysFont('DejaVu Sans', 16)
        except:
            self._time_font = pygame.font.Font(None, font_size)
            self._date_font = pygame.font.Font(None, 16)

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

        # Create a subtle card background for the clock area
        card_margin = 15
        card_padding_top = 12
        card_padding_bottom = 10
        card_rect = pygame.Rect(
            rect.left + card_margin,
            rect.top + card_padding_top,
            rect.width - card_margin * 2,
            rect.height - card_padding_top - card_padding_bottom
        )
        card_bg = self._darken_color(self.theme.background_rgb, 0.1)
        draw_rounded_rect(self.screen, card_bg, card_rect, 12)

        # Render the time text
        time_surface = self._time_font.render(
            time_str,
            True,
            self.theme.clock_color_rgb
        )

        # Calculate centered position
        total_width = time_surface.get_width()

        # Add AM/PM if present
        ampm_surface = None
        if ampm:
            ampm_surface = self._date_font.render(
                ampm,
                True,
                self._lighten_color(self.theme.clock_color_rgb, -0.3)
            )
            total_width += ampm_surface.get_width() + 8

        # Center everything vertically with space for date below
        date_surface = self._date_font.render(
            date_str,
            True,
            self.theme.weather_label_color_rgb
        )
        total_height = time_surface.get_height() + date_surface.get_height() + 8
        start_y = card_rect.centery - total_height // 2

        start_x = card_rect.centerx - total_width // 2
        time_y = start_y

        # Draw time
        self.screen.blit(time_surface, (start_x, time_y))

        # Draw AM/PM next to time
        if ampm_surface:
            ampm_x = start_x + time_surface.get_width() + 8
            ampm_y = time_y + time_surface.get_height() - ampm_surface.get_height() - 5
            self.screen.blit(ampm_surface, (ampm_x, ampm_y))

        # Render the date below the time with padding
        date_rect = date_surface.get_rect(
            centerx=card_rect.centerx,
            top=time_y + time_surface.get_height() + 8
        )
        self.screen.blit(date_surface, date_rect)

        self._last_time_str = time_str

    def _darken_color(self, color, amount):
        """Darken a color by a percentage."""
        return (
            max(0, int(color[0] * (1 - amount))),
            max(0, int(color[1] * (1 - amount))),
            max(0, int(color[2] * (1 - amount)))
        )

    def _lighten_color(self, color, amount):
        """Lighten a color by a percentage."""
        return (
            min(255, int(color[0] + (255 - color[0]) * amount)),
            min(255, int(color[1] + (255 - color[1]) * amount)),
            min(255, int(color[2] + (255 - color[2]) * amount))
        )
