"""Dynamic color functions for weather-based coloring."""

from typing import Tuple


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color."""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)


def lerp_color(color1: str, color2: str, t: float) -> str:
    """Linear interpolation between two hex colors."""
    t = max(0, min(1, t))
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)

    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)

    return rgb_to_hex((r, g, b))


def get_temperature_color(temp_f: float) -> str:
    """
    Get color for temperature value (Fahrenheit).

    Scale:
    - < 32°F: Deep blue (#0066FF)
    - 32-50°F: Light blue (#66B2FF)
    - 50-65°F: Green (#66CC66)
    - 65-80°F: Yellow/Orange (#FFCC00)
    - 80-90°F: Orange (#FF9933)
    - > 90°F: Red (#FF3333)
    """
    if temp_f < 32:
        return "#0066FF"  # Deep blue
    elif temp_f < 50:
        t = (temp_f - 32) / 18
        return lerp_color("#0066FF", "#66B2FF", t)
    elif temp_f < 65:
        t = (temp_f - 50) / 15
        return lerp_color("#66B2FF", "#66CC66", t)
    elif temp_f < 80:
        t = (temp_f - 65) / 15
        return lerp_color("#66CC66", "#FFCC00", t)
    elif temp_f < 90:
        t = (temp_f - 80) / 10
        return lerp_color("#FFCC00", "#FF9933", t)
    else:
        t = min((temp_f - 90) / 10, 1)
        return lerp_color("#FF9933", "#FF3333", t)


def get_temperature_color_celsius(temp_c: float) -> str:
    """Get color for temperature value (Celsius)."""
    temp_f = temp_c * 9 / 5 + 32
    return get_temperature_color(temp_f)


def get_precipitation_color(percent: float) -> str:
    """
    Get color for precipitation chance.

    Scale:
    - 0-20%: Gray (#888888)
    - 20-50%: Light blue (#66B2FF)
    - 50-80%: Blue (#3399FF)
    - 80-100%: Dark blue/purple (#6633FF)
    """
    if percent < 20:
        t = percent / 20
        return lerp_color("#888888", "#66B2FF", t)
    elif percent < 50:
        t = (percent - 20) / 30
        return lerp_color("#66B2FF", "#3399FF", t)
    elif percent < 80:
        t = (percent - 50) / 30
        return lerp_color("#3399FF", "#6633FF", t)
    else:
        return "#6633FF"


def get_uv_color(uv_index: float) -> Tuple[str, str]:
    """
    Get color and label for UV index.

    Returns: (color, label)

    Scale:
    - 0-2: Green (Low)
    - 3-5: Yellow (Moderate)
    - 6-7: Orange (High)
    - 8-10: Red (Very High)
    - 11+: Purple (Extreme)
    """
    if uv_index <= 2:
        return "#66CC66", "Low"
    elif uv_index <= 5:
        return "#FFCC00", "Moderate"
    elif uv_index <= 7:
        return "#FF9933", "High"
    elif uv_index <= 10:
        return "#FF3333", "Very High"
    else:
        return "#9933FF", "Extreme"


def get_wind_color(speed_mph: float) -> Tuple[str, str]:
    """
    Get color and label for wind speed (mph).

    Returns: (color, label)

    Scale:
    - 0-10 mph: Gray (Calm)
    - 10-20 mph: Light blue (Breezy)
    - 20-30 mph: Yellow (Windy)
    - 30+ mph: Orange/Red (Strong)
    """
    if speed_mph < 10:
        return "#888888", "Calm"
    elif speed_mph < 20:
        return "#66B2FF", "Breezy"
    elif speed_mph < 30:
        return "#FFCC00", "Windy"
    else:
        return "#FF6633", "Strong"


def get_humidity_color(percent: float) -> Tuple[str, str]:
    """
    Get color and label for humidity.

    Returns: (color, label)

    Scale:
    - 0-30%: Orange (Dry)
    - 30-60%: Green (Comfortable)
    - 60-80%: Light blue (Humid)
    - 80-100%: Blue (Very humid)
    """
    if percent < 30:
        return "#FF9933", "Dry"
    elif percent < 60:
        return "#66CC66", "Comfortable"
    elif percent < 80:
        return "#66B2FF", "Humid"
    else:
        return "#3399FF", "Very Humid"


def get_moon_phase_icon(phase: float) -> Tuple[str, str]:
    """
    Get emoji and name for moon phase.

    Phase is 0-1 from OpenWeatherMap:
    - 0 or 1: New Moon
    - 0.25: First Quarter
    - 0.5: Full Moon
    - 0.75: Last Quarter

    Returns: (emoji, name)
    """
    if phase == 0 or phase == 1:
        return "🌑", "New Moon"
    elif phase < 0.25:
        return "🌒", "Waxing Crescent"
    elif phase == 0.25:
        return "🌓", "First Quarter"
    elif phase < 0.5:
        return "🌔", "Waxing Gibbous"
    elif phase == 0.5:
        return "🌕", "Full Moon"
    elif phase < 0.75:
        return "🌖", "Waning Gibbous"
    elif phase == 0.75:
        return "🌗", "Last Quarter"
    else:
        return "🌘", "Waning Crescent"


def get_weather_icon(icon_code: str) -> str:
    """
    Get emoji for OpenWeatherMap icon code.

    Codes: https://openweathermap.org/weather-conditions
    """
    icon_map = {
        '01d': '☀️',   # Clear day
        '01n': '🌙',   # Clear night
        '02d': '⛅',   # Few clouds day
        '02n': '☁️',   # Few clouds night
        '03d': '☁️',   # Scattered clouds
        '03n': '☁️',
        '04d': '☁️',   # Broken clouds
        '04n': '☁️',
        '09d': '🌧️',  # Shower rain
        '09n': '🌧️',
        '10d': '🌧️',  # Rain
        '10n': '🌧️',
        '11d': '⛈️',  # Thunderstorm
        '11n': '⛈️',
        '13d': '❄️',   # Snow
        '13n': '❄️',
        '50d': '🌫️',  # Mist
        '50n': '🌫️',
    }
    return icon_map.get(icon_code, '🌡️')
