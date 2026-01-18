"""Flask web server for TablePi control panel."""

import re
import time
from pathlib import Path
from threading import Thread
from typing import Optional, Any, Tuple

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

from app.shared_state import SharedState, Queues, shutdown_event, LogEntry
from app.services.config import (
    load_config, save_config, load_theme, save_theme,
    list_themes, get_default_theme
)


# ============ Input Validation Helpers ============

def sanitize_string(value: Any, max_length: int = 255, allow_empty: bool = False) -> Tuple[bool, str]:
    """
    Sanitize a string input.
    Returns (is_valid, sanitized_value or error_message).
    """
    if value is None:
        if allow_empty:
            return True, ""
        return False, "Value cannot be empty"

    if not isinstance(value, str):
        return False, "Value must be a string"

    # Strip whitespace
    value = value.strip()

    if not allow_empty and len(value) == 0:
        return False, "Value cannot be empty"

    if len(value) > max_length:
        return False, f"Value exceeds maximum length of {max_length}"

    return True, value


def validate_theme_name(name: str) -> Tuple[bool, str]:
    """
    Validate a theme name.
    Only allows alphanumeric, hyphens, and underscores.
    """
    if not name:
        return False, "Theme name cannot be empty"

    if not isinstance(name, str):
        return False, "Theme name must be a string"

    name = name.strip()

    if len(name) > 64:
        return False, "Theme name too long (max 64 characters)"

    # Only allow safe characters for filenames
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return False, "Theme name can only contain letters, numbers, hyphens, and underscores"

    return True, name


def validate_mac_address(mac: str) -> Tuple[bool, str]:
    """
    Validate a Bluetooth MAC address.
    Accepts formats: XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX
    """
    if not mac:
        return False, "MAC address cannot be empty"

    if not isinstance(mac, str):
        return False, "MAC address must be a string"

    mac = mac.strip().upper()

    # Allow both : and - separators
    mac_pattern = r'^([0-9A-F]{2}[:-]){5}[0-9A-F]{2}$'
    if not re.match(mac_pattern, mac):
        return False, "Invalid MAC address format (expected XX:XX:XX:XX:XX:XX)"

    # Normalize to colon separator
    mac = mac.replace('-', ':')

    return True, mac


def validate_volume(volume: Any) -> Tuple[bool, int]:
    """
    Validate and clamp volume to 0-100.
    """
    if volume is None:
        return True, 80  # Default

    try:
        volume = int(volume)
    except (ValueError, TypeError):
        return False, "Volume must be a number"

    # Clamp to valid range
    volume = max(0, min(100, volume))
    return True, volume


def validate_color_hex(color: str) -> Tuple[bool, str]:
    """
    Validate a hex color code.
    """
    if not color:
        return False, "Color cannot be empty"

    if not isinstance(color, str):
        return False, "Color must be a string"

    color = color.strip()

    # Accept with or without #
    if not color.startswith('#'):
        color = '#' + color

    # Validate hex color format
    if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
        return False, "Invalid color format (expected #RRGGBB)"

    return True, color.lower()


def validate_coordinates(lat: Any, lon: Any) -> Tuple[bool, str]:
    """
    Validate latitude and longitude coordinates.
    """
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return False, "Coordinates must be numbers"

    if lat < -90 or lat > 90:
        return False, "Latitude must be between -90 and 90"

    if lon < -180 or lon > 180:
        return False, "Longitude must be between -180 and 180"

    return True, ""


def validate_timezone(tz: str) -> Tuple[bool, str]:
    """
    Validate a timezone string.
    """
    if not tz:
        return False, "Timezone cannot be empty"

    if not isinstance(tz, str):
        return False, "Timezone must be a string"

    tz = tz.strip()

    # Basic format check (Area/Location or UTC)
    if not re.match(r'^[A-Za-z_]+(/[A-Za-z_]+)?$', tz) and tz != 'UTC':
        return False, "Invalid timezone format"

    if len(tz) > 64:
        return False, "Timezone name too long"

    return True, tz


def validate_api_key(key: str) -> Tuple[bool, str]:
    """
    Validate an API key (basic sanitization).
    """
    if not key:
        return True, ""  # Empty is allowed

    if not isinstance(key, str):
        return False, "API key must be a string"

    key = key.strip()

    if len(key) > 128:
        return False, "API key too long"

    # Only allow alphanumeric characters
    if not re.match(r'^[a-zA-Z0-9]+$', key):
        return False, "API key contains invalid characters"

    return True, key


def validate_settings(data: dict) -> Tuple[bool, str, dict]:
    """
    Validate and sanitize the full settings object.
    Returns (is_valid, error_message, sanitized_data).
    """
    if not isinstance(data, dict):
        return False, "Settings must be an object", {}

    sanitized = {}

    # Validate display settings
    if 'display' in data:
        display = data['display']
        if not isinstance(display, dict):
            return False, "Display settings must be an object", {}

        sanitized['display'] = {}

        if 'width' in display:
            try:
                w = int(display['width'])
                if w < 320 or w > 4096:
                    return False, "Display width must be between 320 and 4096", {}
                sanitized['display']['width'] = w
            except (ValueError, TypeError):
                return False, "Display width must be a number", {}

        if 'height' in display:
            try:
                h = int(display['height'])
                if h < 240 or h > 2160:
                    return False, "Display height must be between 240 and 2160", {}
                sanitized['display']['height'] = h
            except (ValueError, TypeError):
                return False, "Display height must be a number", {}

        if 'fullscreen' in display:
            sanitized['display']['fullscreen'] = bool(display['fullscreen'])

        if 'fps' in display:
            try:
                fps = int(display['fps'])
                if fps < 1 or fps > 120:
                    return False, "FPS must be between 1 and 120", {}
                sanitized['display']['fps'] = fps
            except (ValueError, TypeError):
                return False, "FPS must be a number", {}

    # Validate clock settings
    if 'clock' in data:
        clock = data['clock']
        if not isinstance(clock, dict):
            return False, "Clock settings must be an object", {}

        sanitized['clock'] = {}

        if 'format_24h' in clock:
            sanitized['clock']['format_24h'] = bool(clock['format_24h'])

        if 'show_seconds' in clock:
            sanitized['clock']['show_seconds'] = bool(clock['show_seconds'])

        if 'timezone' in clock:
            valid, result = validate_timezone(clock['timezone'])
            if not valid:
                return False, result, {}
            sanitized['clock']['timezone'] = result

    # Validate weather settings
    if 'weather' in data:
        weather = data['weather']
        if not isinstance(weather, dict):
            return False, "Weather settings must be an object", {}

        sanitized['weather'] = {}

        if 'api_key' in weather:
            valid, result = validate_api_key(weather['api_key'])
            if not valid:
                return False, result, {}
            sanitized['weather']['api_key'] = result

        if 'lat' in weather and 'lon' in weather:
            valid, result = validate_coordinates(weather['lat'], weather['lon'])
            if not valid:
                return False, result, {}
            sanitized['weather']['lat'] = float(weather['lat'])
            sanitized['weather']['lon'] = float(weather['lon'])
        elif 'lat' in weather or 'lon' in weather:
            return False, "Both latitude and longitude must be provided", {}

        if 'units' in weather:
            units = weather['units']
            if units not in ['imperial', 'metric']:
                return False, "Units must be 'imperial' or 'metric'", {}
            sanitized['weather']['units'] = units

        if 'update_interval_minutes' in weather:
            try:
                interval = int(weather['update_interval_minutes'])
                if interval < 1 or interval > 1440:
                    return False, "Update interval must be between 1 and 1440 minutes", {}
                sanitized['weather']['update_interval_minutes'] = interval
            except (ValueError, TypeError):
                return False, "Update interval must be a number", {}

    # Validate theme selection
    if 'theme' in data:
        valid, result = validate_theme_name(data['theme'])
        if not valid:
            return False, result, {}
        sanitized['theme'] = result

    # Validate audio settings
    if 'audio' in data:
        audio = data['audio']
        if not isinstance(audio, dict):
            return False, "Audio settings must be an object", {}

        sanitized['audio'] = {}

        if 'output_device' in audio:
            valid, result = sanitize_string(audio['output_device'], max_length=128, allow_empty=False)
            if not valid:
                return False, f"Audio device: {result}", {}
            sanitized['audio']['output_device'] = result

        if 'volume' in audio:
            valid, result = validate_volume(audio['volume'])
            if not valid:
                return False, result, {}
            sanitized['audio']['volume'] = result

    # Validate bluetooth settings
    if 'bluetooth' in data:
        bt = data['bluetooth']
        if not isinstance(bt, dict):
            return False, "Bluetooth settings must be an object", {}

        sanitized['bluetooth'] = {}

        if 'speaker_mac' in bt:
            if bt['speaker_mac']:  # Allow empty
                valid, result = validate_mac_address(bt['speaker_mac'])
                if not valid:
                    return False, result, {}
                sanitized['bluetooth']['speaker_mac'] = result
            else:
                sanitized['bluetooth']['speaker_mac'] = ""

        if 'auto_connect' in bt:
            sanitized['bluetooth']['auto_connect'] = bool(bt['auto_connect'])

    # Validate web settings
    if 'web' in data:
        web = data['web']
        if not isinstance(web, dict):
            return False, "Web settings must be an object", {}

        sanitized['web'] = {}

        if 'port' in web:
            try:
                port = int(web['port'])
                if port < 1 or port > 65535:
                    return False, "Port must be between 1 and 65535", {}
                sanitized['web']['port'] = port
            except (ValueError, TypeError):
                return False, "Port must be a number", {}

        if 'host' in web:
            valid, result = sanitize_string(web['host'], max_length=64, allow_empty=False)
            if not valid:
                return False, f"Host: {result}", {}
            # Basic host validation
            if not re.match(r'^[0-9A-Za-z.\-]+$', result):
                return False, "Invalid host format", {}
            sanitized['web']['host'] = result

    # Validate youtube settings
    if 'youtube' in data:
        yt = data['youtube']
        if not isinstance(yt, dict):
            return False, "YouTube settings must be an object", {}

        sanitized['youtube'] = {}

        if 'max_resolution' in yt:
            try:
                res = int(yt['max_resolution'])
                if res not in [144, 240, 360, 480, 720, 1080]:
                    return False, "Invalid resolution (use 144, 240, 360, 480, 720, or 1080)", {}
                sanitized['youtube']['max_resolution'] = res
            except (ValueError, TypeError):
                return False, "Resolution must be a number", {}

        if 'default_volume' in yt:
            valid, result = validate_volume(yt['default_volume'])
            if not valid:
                return False, result, {}
            sanitized['youtube']['default_volume'] = result

    return True, "", sanitized


def validate_theme_data(data: dict) -> Tuple[bool, str, dict]:
    """
    Validate and sanitize theme data.
    Returns (is_valid, error_message, sanitized_data).
    """
    if not isinstance(data, dict):
        return False, "Theme must be an object", {}

    sanitized = {}

    # Validate name
    if 'name' in data:
        valid, result = sanitize_string(data['name'], max_length=64, allow_empty=False)
        if not valid:
            return False, f"Theme name: {result}", {}
        sanitized['name'] = result

    # Validate background color
    if 'background' in data:
        valid, result = validate_color_hex(data['background'])
        if not valid:
            return False, f"Background color: {result}", {}
        sanitized['background'] = result

    # Validate clock settings
    if 'clock' in data:
        clock = data['clock']
        if not isinstance(clock, dict):
            return False, "Clock settings must be an object", {}

        sanitized['clock'] = {}

        if 'color' in clock:
            valid, result = validate_color_hex(clock['color'])
            if not valid:
                return False, f"Clock color: {result}", {}
            sanitized['clock']['color'] = result

        if 'font_size' in clock:
            try:
                size = int(clock['font_size'])
                if size < 12 or size > 200:
                    return False, "Font size must be between 12 and 200", {}
                sanitized['clock']['font_size'] = size
            except (ValueError, TypeError):
                return False, "Font size must be a number", {}

    # Validate weather settings
    if 'weather' in data:
        weather = data['weather']
        if not isinstance(weather, dict):
            return False, "Weather settings must be an object", {}

        sanitized['weather'] = {}

        for key in ['label_color', 'static_value_color']:
            if key in weather:
                valid, result = validate_color_hex(weather[key])
                if not valid:
                    return False, f"Weather {key}: {result}", {}
                sanitized['weather'][key] = result

        if 'use_dynamic_colors' in weather:
            sanitized['weather']['use_dynamic_colors'] = bool(weather['use_dynamic_colors'])

    # Validate graph settings
    if 'graph' in data:
        graph = data['graph']
        if not isinstance(graph, dict):
            return False, "Graph settings must be an object", {}

        sanitized['graph'] = {}

        for key in ['background', 'high_line', 'low_line', 'grid_color', 'label_color']:
            if key in graph:
                valid, result = validate_color_hex(graph[key])
                if not valid:
                    return False, f"Graph {key}: {result}", {}
                sanitized['graph'][key] = result

    # Validate status_bar settings
    if 'status_bar' in data:
        sb = data['status_bar']
        if not isinstance(sb, dict):
            return False, "Status bar settings must be an object", {}

        sanitized['status_bar'] = {}

        for key in ['background', 'text_color']:
            if key in sb:
                valid, result = validate_color_hex(sb[key])
                if not valid:
                    return False, f"Status bar {key}: {result}", {}
                sanitized['status_bar'][key] = result

    # Validate accents
    if 'accents' in data:
        accents = data['accents']
        if not isinstance(accents, dict):
            return False, "Accents must be an object", {}

        sanitized['accents'] = {}

        for key in ['primary', 'secondary']:
            if key in accents:
                valid, result = validate_color_hex(accents[key])
                if not valid:
                    return False, f"Accent {key}: {result}", {}
                sanitized['accents'][key] = result

    return True, "", sanitized


# Flask app
app = Flask(__name__,
            template_folder=str(Path(__file__).parent / 'templates'),
            static_folder=str(Path(__file__).parent / 'static'))
app.config['SECRET_KEY'] = 'tablepi-secret-key'

socketio = SocketIO(app, cors_allowed_origins="*")

# Global references (set when server starts)
_state: Optional[SharedState] = None
_queues: Optional[Queues] = None
_weather_service = None  # Reference to weather service for refresh

# In-memory log buffer
_log_buffer = []
_log_buffer_max = 500


def init_server(state: SharedState, queues: Queues, weather_service=None):
    """Initialize the server with shared state and queues."""
    global _state, _queues, _weather_service
    _state = state
    _queues = queues
    _weather_service = weather_service


# ============ Routes ============

@app.route('/')
def index():
    """Serve the main control panel page."""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Get overall system status."""
    config = _state.get_config()
    weather_data, last_fetch = _state.get_weather()
    youtube_status = _state.get_youtube_status()
    bluetooth_status = _state.get_bluetooth_status()
    audio_status = _state.get_audio_status()

    return jsonify({
        'ip': _state.get_ip_address(),
        'theme': config.get('theme', 'dark'),
        'weather_last_fetch': last_fetch,
        'youtube': youtube_status,
        'bluetooth': bluetooth_status,
        'audio': audio_status
    })


# ============ Settings API ============

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings."""
    config = _state.get_config()
    return jsonify(config)


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update settings."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate and sanitize input
    valid, error, sanitized = validate_settings(data)
    if not valid:
        _queues.log_error(f'Settings validation failed: {error}')
        return jsonify({'error': error}), 400

    # Merge sanitized data with existing config
    config = _state.get_config()

    # Deep merge the sanitized settings
    for key, value in sanitized.items():
        if isinstance(value, dict) and key in config and isinstance(config[key], dict):
            config[key].update(value)
        else:
            config[key] = value

    if save_config(config):
        _state.set_config(config)
        _queues.config.put({'type': 'reload'})
        _queues.log_action('Settings updated')
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to save settings'}), 500


# ============ Weather API ============

@app.route('/api/weather/status', methods=['GET'])
def weather_status():
    """Get weather status including last fetch time."""
    weather_data, last_fetch = _state.get_weather()
    config = _state.get_config()

    has_api_key = bool(config.get('weather', {}).get('api_key'))
    has_data = weather_data is not None

    if has_data:
        status = 'ok'
        status_text = 'Connected'
    elif not has_api_key:
        status = 'error'
        status_text = 'API key not configured'
    else:
        status = 'unknown'
        status_text = 'Waiting for data'

    return jsonify({
        'status': status,
        'status_text': status_text,
        'last_fetch': last_fetch,
        'has_data': has_data,
        'has_api_key': has_api_key
    })


@app.route('/api/weather/refresh', methods=['POST'])
def weather_refresh():
    """Force a weather data refresh."""
    config = _state.get_config()

    if not config.get('weather', {}).get('api_key'):
        return jsonify({
            'success': False,
            'error': 'API key not configured'
        }), 400

    # Trigger refresh on weather service directly if available
    if _weather_service is not None:
        _weather_service.trigger_refresh()
        _queues.log_action('Weather refresh requested')
        return jsonify({'success': True, 'message': 'Refresh triggered'})
    else:
        return jsonify({
            'success': False,
            'error': 'Weather service not available'
        }), 503


# ============ Theme API ============

@app.route('/api/themes', methods=['GET'])
def get_themes():
    """Get list of available themes."""
    themes = list_themes()
    current_config = _state.get_config()
    return jsonify({
        'themes': themes,
        'current': current_config.get('theme', 'dark')
    })


@app.route('/api/theme/<name>', methods=['GET'])
def get_theme(name):
    """Get a specific theme."""
    # Validate theme name
    valid, result = validate_theme_name(name)
    if not valid:
        return jsonify({'error': result}), 400

    theme_data = load_theme(result)
    if theme_data:
        return jsonify(theme_data)
    return jsonify({'error': 'Theme not found'}), 404


@app.route('/api/theme/<name>', methods=['POST'])
def save_theme_endpoint(name):
    """Save a theme."""
    # Validate theme name
    valid, result = validate_theme_name(name)
    if not valid:
        return jsonify({'error': result}), 400
    name = result

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate and sanitize theme data
    valid, error, sanitized = validate_theme_data(data)
    if not valid:
        _queues.log_error(f'Theme data validation failed: {error}')
        return jsonify({'error': error}), 400

    if save_theme(name, sanitized):
        _queues.log_action(f'Theme "{name}" saved')
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to save theme'}), 500


@app.route('/api/theme/select/<name>', methods=['POST'])
def select_theme(name):
    """Select a theme."""
    # Validate theme name
    valid, result = validate_theme_name(name)
    if not valid:
        return jsonify({'error': result}), 400
    name = result

    # Verify theme exists
    available_themes = list_themes()
    if name not in available_themes:
        return jsonify({'error': f'Theme "{name}" not found'}), 404

    config = _state.get_config()
    config['theme'] = name

    if save_config(config):
        _state.set_config(config)
        _queues.config.put({'type': 'reload'})
        _queues.log_action(f'Theme changed to "{name}"')
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to select theme'}), 500


# ============ YouTube API ============

@app.route('/api/youtube/play', methods=['POST'])
def youtube_play():
    """Play a YouTube video."""
    data = request.get_json()
    url = data.get('url', '')

    # Validate YouTube URL
    youtube_regex = r'(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([\w-]+)'
    match = re.search(youtube_regex, url)

    if not match:
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    video_id = match.group(1)

    # Send command to main thread
    _queues.command.put({
        'type': 'youtube_play',
        'url': url,
        'video_id': video_id
    })

    _queues.log_action(f'YouTube play: {video_id}')
    return jsonify({'success': True, 'video_id': video_id})


@app.route('/api/youtube/control', methods=['POST'])
def youtube_control():
    """Control YouTube playback."""
    data = request.get_json()
    command = data.get('command', '')

    valid_commands = ['pause', 'resume', 'stop', 'volume_up', 'volume_down']
    if command not in valid_commands:
        return jsonify({'error': 'Invalid command'}), 400

    _queues.command.put({
        'type': f'youtube_{command}'
    })

    _queues.log_action(f'YouTube {command}')
    return jsonify({'success': True})


@app.route('/api/youtube/status', methods=['GET'])
def youtube_status():
    """Get YouTube playback status."""
    status = _state.get_youtube_status()
    return jsonify(status)


# ============ Audio API ============

@app.route('/api/audio/devices', methods=['GET'])
def get_audio_devices():
    """Get available audio devices."""
    status = _state.get_audio_status()
    return jsonify(status)


@app.route('/api/audio/device', methods=['POST'])
def set_audio_device():
    """Set the audio output device."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    device = data.get('device', 'default')

    # Validate device name
    valid, result = sanitize_string(device, max_length=128, allow_empty=False)
    if not valid:
        return jsonify({'error': f'Invalid device name: {result}'}), 400
    device = result

    _state.set_audio_device(device)

    config = _state.get_config()
    if 'audio' not in config:
        config['audio'] = {}
    config['audio']['output_device'] = device
    save_config(config)

    _queues.log_action(f'Audio device changed to "{device}"')
    return jsonify({'success': True})


@app.route('/api/audio/volume', methods=['POST'])
def set_volume():
    """Set the audio volume."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate and clamp volume
    valid, result = validate_volume(data.get('volume'))
    if not valid:
        return jsonify({'error': result}), 400
    volume = result

    _state.set_audio_volume(volume)

    config = _state.get_config()
    if 'audio' not in config:
        config['audio'] = {}
    config['audio']['volume'] = volume
    save_config(config)

    _queues.log_action(f'Volume set to {volume}')
    return jsonify({'success': True})


# ============ Bluetooth API ============

@app.route('/api/bluetooth/status', methods=['GET'])
def bluetooth_status():
    """Get Bluetooth status."""
    status = _state.get_bluetooth_status()
    return jsonify(status)


@app.route('/api/bluetooth/scan', methods=['POST'])
def bluetooth_scan():
    """Start Bluetooth scan."""
    _queues.command.put({'type': 'bluetooth_scan'})
    _queues.log_action('Bluetooth scan started')
    return jsonify({'success': True, 'message': 'Scan started'})


@app.route('/api/bluetooth/connect', methods=['POST'])
def bluetooth_connect():
    """Connect to a Bluetooth device."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    mac = data.get('mac', '')

    # Validate MAC address
    valid, result = validate_mac_address(mac)
    if not valid:
        return jsonify({'error': result}), 400
    mac = result

    _queues.command.put({
        'type': 'bluetooth_connect',
        'mac': mac
    })

    _queues.log_action(f'Bluetooth connect: {mac}')
    return jsonify({'success': True})


@app.route('/api/bluetooth/disconnect', methods=['POST'])
def bluetooth_disconnect():
    """Disconnect Bluetooth device."""
    _queues.command.put({'type': 'bluetooth_disconnect'})
    _queues.log_action('Bluetooth disconnect')
    return jsonify({'success': True})


# ============ Logs API ============

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get recent logs."""
    category = request.args.get('category', None)

    logs = _log_buffer.copy()
    if category:
        # Validate category - only allow known categories
        valid_categories = ['info', 'error', 'action', 'debug']
        if category not in valid_categories:
            return jsonify({'error': f'Invalid category. Must be one of: {", ".join(valid_categories)}'}), 400
        logs = [l for l in logs if l.get('category') == category]

    return jsonify({'logs': logs})


@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Clear the log buffer."""
    global _log_buffer
    _log_buffer = []
    _queues.log_action('Logs cleared')
    return jsonify({'success': True})


# ============ WebSocket events ============

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection."""
    pass


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    pass


# ============ Log processing ============

def process_log_queue():
    """Process log entries from the queue and broadcast via WebSocket."""
    global _log_buffer

    while not shutdown_event.is_set():
        try:
            # Get log entries from queue (with timeout)
            from queue import Empty
            try:
                entry = _queues.log.get(timeout=0.5)

                if isinstance(entry, LogEntry):
                    log_dict = entry.to_dict()
                else:
                    log_dict = entry

                # Add to buffer
                _log_buffer.append(log_dict)
                if len(_log_buffer) > _log_buffer_max:
                    _log_buffer = _log_buffer[-_log_buffer_max:]

                # Broadcast to connected clients
                socketio.emit('log', log_dict)

            except Empty:
                pass

        except Exception as e:
            print(f"Log processing error: {e}")


def run_flask_thread(state: SharedState, queues: Queues, weather_service=None):
    """Run Flask server in a thread."""
    init_server(state, queues, weather_service)

    config = state.get_config()
    web_config = config.get('web', {})
    host = web_config.get('host', '0.0.0.0')
    port = web_config.get('port', 5000)

    queues.log_info(f'Web server starting on {host}:{port}')

    # Start log processor thread
    log_processor = Thread(target=process_log_queue, daemon=True)
    log_processor.start()

    # Run Flask with SocketIO
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False)
