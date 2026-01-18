"""Audio device management service using PulseAudio."""

import re
import subprocess
import time
from threading import Thread, Event
from typing import Optional, List, Dict

from app.shared_state import SharedState, Queues, shutdown_event


class AudioService(Thread):
    """Background thread that manages PulseAudio devices."""

    def __init__(self, state: SharedState, queues: Queues):
        super().__init__(daemon=True)
        self.state = state
        self.queues = queues

        self._command_event = Event()
        self._pending_command: Optional[dict] = None

    def run(self):
        """Main thread loop."""
        self.queues.log_info('Audio service started')

        # Initial device enumeration
        self._enumerate_devices()

        # Set initial device from config
        config = self.state.get_config()
        audio_config = config.get('audio', {})
        device = audio_config.get('output_device', 'default')
        volume = audio_config.get('volume', 80)

        if device != 'default':
            self._set_device(device)
        self._set_volume(volume)

        last_enum = time.time()

        while not shutdown_event.is_set():
            # Check for pending commands
            if self._command_event.wait(timeout=1):
                self._command_event.clear()
                if self._pending_command:
                    self._handle_command(self._pending_command)
                    self._pending_command = None

            # Re-enumerate devices every 30 seconds
            if time.time() - last_enum > 30:
                self._enumerate_devices()
                last_enum = time.time()

    def send_command(self, cmd: dict):
        """Send a command to the audio service."""
        self._pending_command = cmd
        self._command_event.set()

    def _handle_command(self, cmd: dict):
        """Handle a command from the web UI."""
        cmd_type = cmd.get('type')

        if cmd_type == 'audio_set_device':
            device = cmd.get('device', 'default')
            self._set_device(device)

        elif cmd_type == 'audio_set_volume':
            volume = cmd.get('volume', 80)
            self._set_volume(volume)

        elif cmd_type == 'audio_refresh':
            self._enumerate_devices()

    def _enumerate_devices(self):
        """Enumerate available PulseAudio sinks."""
        try:
            result = subprocess.run(
                ['pactl', 'list', 'short', 'sinks'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                self.queues.log_error(f'pactl error: {result.stderr}')
                return

            devices = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 2:
                    # Format: ID\tNAME\tDRIVER\tSAMPLE_SPEC\tSTATE
                    sink_name = parts[1]
                    devices.append({
                        'id': sink_name,
                        'name': self._get_friendly_name(sink_name)
                    })

            # Add default option
            devices.insert(0, {'id': 'default', 'name': 'Default'})

            self.state.set_audio_devices(devices)

        except subprocess.TimeoutExpired:
            self.queues.log_error('pactl timeout enumerating devices')
        except FileNotFoundError:
            self.queues.log_error('pactl not found. Install pulseaudio-utils.')
        except Exception as e:
            self.queues.log_error(f'Failed to enumerate audio devices: {e}')

    def _get_friendly_name(self, sink_name: str) -> str:
        """Convert PulseAudio sink name to friendly name."""
        # Try to get description from pactl
        try:
            result = subprocess.run(
                ['pactl', 'list', 'sinks'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Parse output to find matching sink
                current_sink = None
                for line in result.stdout.split('\n'):
                    if 'Name:' in line:
                        current_sink = line.split('Name:')[1].strip()
                    elif 'Description:' in line and current_sink == sink_name:
                        return line.split('Description:')[1].strip()

        except Exception:
            pass

        # Fallback: clean up the sink name
        name = sink_name.replace('alsa_output.', '')
        name = name.replace('bluez_sink.', 'Bluetooth: ')
        name = name.replace('.analog-stereo', '')
        name = name.replace('.a2dp_sink', '')
        name = name.replace('_', ' ')
        return name

    def _set_device(self, device: str):
        """Set the default audio output device."""
        if device == 'default':
            self.queues.log_action('Audio device set to default')
            self.state.set_audio_device('default')
            return

        try:
            result = subprocess.run(
                ['pactl', 'set-default-sink', device],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                self.state.set_audio_device(device)
                self.queues.log_action(f'Audio device set to {device}')
            else:
                self.queues.log_error(f'Failed to set audio device: {result.stderr}')

        except subprocess.TimeoutExpired:
            self.queues.log_error('pactl timeout setting device')
        except FileNotFoundError:
            self.queues.log_error('pactl not found')
        except Exception as e:
            self.queues.log_error(f'Failed to set audio device: {e}')

    def _set_volume(self, volume: int):
        """Set the audio volume."""
        volume = max(0, min(100, volume))

        try:
            # Set volume on default sink
            result = subprocess.run(
                ['pactl', 'set-sink-volume', '@DEFAULT_SINK@', f'{volume}%'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                self.state.set_audio_volume(volume)
            else:
                self.queues.log_error(f'Failed to set volume: {result.stderr}')

        except subprocess.TimeoutExpired:
            self.queues.log_error('pactl timeout setting volume')
        except FileNotFoundError:
            self.queues.log_error('pactl not found')
        except Exception as e:
            self.queues.log_error(f'Failed to set volume: {e}')

    def get_current_volume(self) -> int:
        """Get the current volume level."""
        try:
            result = subprocess.run(
                ['pactl', 'get-sink-volume', '@DEFAULT_SINK@'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Parse output like "Volume: front-left: 52428 /  80% / -5.81 dB"
                match = re.search(r'(\d+)%', result.stdout)
                if match:
                    return int(match.group(1))

        except Exception:
            pass

        return 80  # Default
