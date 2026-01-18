"""Theme management for the display."""

from typing import Tuple
from app.display.colors import hex_to_rgb


class Theme:
    """Theme wrapper with convenient accessors."""

    def __init__(self, theme_data: dict):
        self._data = theme_data

    @property
    def name(self) -> str:
        return self._data.get('name', 'Unknown')

    @property
    def background(self) -> str:
        return self._data.get('background', '#1a1a2e')

    @property
    def background_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.background)

    # Clock properties
    @property
    def clock_color(self) -> str:
        return self._data.get('clock', {}).get('color', '#ffffff')

    @property
    def clock_color_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.clock_color)

    @property
    def clock_font_size(self) -> int:
        return self._data.get('clock', {}).get('font_size', 72)

    # Weather properties
    @property
    def weather_label_color(self) -> str:
        return self._data.get('weather', {}).get('label_color', '#888888')

    @property
    def weather_label_color_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.weather_label_color)

    @property
    def use_dynamic_colors(self) -> bool:
        return self._data.get('weather', {}).get('use_dynamic_colors', True)

    @property
    def weather_value_color(self) -> str:
        return self._data.get('weather', {}).get('static_value_color', '#ffffff')

    @property
    def weather_value_color_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.weather_value_color)

    # Graph properties
    @property
    def graph_background(self) -> str:
        return self._data.get('graph', {}).get('background', '#16213e')

    @property
    def graph_background_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.graph_background)

    @property
    def graph_high_line(self) -> str:
        return self._data.get('graph', {}).get('high_line', '#ff6b6b')

    @property
    def graph_high_line_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.graph_high_line)

    @property
    def graph_low_line(self) -> str:
        return self._data.get('graph', {}).get('low_line', '#4ecdc4')

    @property
    def graph_low_line_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.graph_low_line)

    @property
    def graph_grid_color(self) -> str:
        return self._data.get('graph', {}).get('grid_color', '#333333')

    @property
    def graph_grid_color_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.graph_grid_color)

    @property
    def graph_label_color(self) -> str:
        return self._data.get('graph', {}).get('label_color', '#888888')

    @property
    def graph_label_color_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.graph_label_color)

    # Status bar properties
    @property
    def status_bar_background(self) -> str:
        return self._data.get('status_bar', {}).get('background', '#0f0f1a')

    @property
    def status_bar_background_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.status_bar_background)

    @property
    def status_bar_text_color(self) -> str:
        return self._data.get('status_bar', {}).get('text_color', '#666666')

    @property
    def status_bar_text_color_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.status_bar_text_color)

    # Accent properties
    @property
    def accent_primary(self) -> str:
        return self._data.get('accents', {}).get('primary', '#e94560')

    @property
    def accent_primary_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.accent_primary)

    @property
    def accent_secondary(self) -> str:
        return self._data.get('accents', {}).get('secondary', '#0f3460')

    @property
    def accent_secondary_rgb(self) -> Tuple[int, int, int]:
        return hex_to_rgb(self.accent_secondary)

    def to_dict(self) -> dict:
        return self._data.copy()
