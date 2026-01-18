"""Flask web server for TablePi control panel."""

import re
import time
from pathlib import Path
from threading import Thread
from typing import Optional

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

from app.shared_state import SharedState, Queues, shutdown_event, LogEntry
from app.services.config import (
    load_config, save_config, load_theme, save_theme,
    list_themes, get_default_theme
)


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

    config = _state.get_config()
    config.update(data)

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
    theme_data = load_theme(name)
    if theme_data:
        return jsonify(theme_data)
    return jsonify({'error': 'Theme not found'}), 404


@app.route('/api/theme/<name>', methods=['POST'])
def save_theme_endpoint(name):
    """Save a theme."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if save_theme(name, data):
        _queues.log_action(f'Theme "{name}" saved')
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to save theme'}), 500


@app.route('/api/theme/select/<name>', methods=['POST'])
def select_theme(name):
    """Select a theme."""
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
    device = data.get('device', 'default')

    _state.set_audio_device(device)

    config = _state.get_config()
    config['audio']['output_device'] = device
    save_config(config)

    _queues.log_action(f'Audio device changed to "{device}"')
    return jsonify({'success': True})


@app.route('/api/audio/volume', methods=['POST'])
def set_volume():
    """Set the audio volume."""
    data = request.get_json()
    volume = data.get('volume', 80)

    _state.set_audio_volume(volume)

    config = _state.get_config()
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
    mac = data.get('mac', '')

    if not mac:
        return jsonify({'error': 'No MAC address provided'}), 400

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
        logs = [l for l in logs if l['category'] == category]

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
