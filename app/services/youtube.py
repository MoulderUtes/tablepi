"""YouTube playback service using mpv + yt-dlp."""

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from threading import Thread, Event
from typing import Optional

from app.shared_state import SharedState, Queues, shutdown_event


class YouTubeService(Thread):
    """Background thread that manages mpv for YouTube playback."""

    IPC_SOCKET_PATH = "/tmp/mpv-socket"

    def __init__(self, state: SharedState, queues: Queues):
        super().__init__(daemon=True)
        self.state = state
        self.queues = queues

        self._mpv_process: Optional[subprocess.Popen] = None
        self._command_event = Event()
        self._pending_command: Optional[dict] = None

    def run(self):
        """Main thread loop."""
        self.queues.log_info('YouTube service started')

        while not shutdown_event.is_set():
            # Check for pending commands
            if self._command_event.wait(timeout=0.5):
                self._command_event.clear()
                if self._pending_command:
                    self._handle_command(self._pending_command)
                    self._pending_command = None

            # Monitor mpv process
            if self._mpv_process:
                if self._mpv_process.poll() is not None:
                    # mpv has exited
                    self._on_playback_ended()
                else:
                    # Update playback position
                    self._update_status()

    def send_command(self, cmd: dict):
        """Send a command to the YouTube service."""
        self._pending_command = cmd
        self._command_event.set()

    def _handle_command(self, cmd: dict):
        """Handle a command from the web UI."""
        cmd_type = cmd.get('type')

        if cmd_type == 'youtube_play':
            url = cmd.get('url', '')
            self._start_playback(url)

        elif cmd_type == 'youtube_pause':
            self._send_mpv_command(['set_property', 'pause', True])

        elif cmd_type == 'youtube_resume':
            self._send_mpv_command(['set_property', 'pause', False])

        elif cmd_type == 'youtube_stop':
            self._stop_playback()

        elif cmd_type == 'youtube_volume_up':
            self._send_mpv_command(['add', 'volume', 5])

        elif cmd_type == 'youtube_volume_down':
            self._send_mpv_command(['add', 'volume', -5])

    def _validate_youtube_url(self, url: str) -> Optional[str]:
        """Validate and extract video ID from YouTube URL."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def _start_playback(self, url: str):
        """Start playing a YouTube video."""
        video_id = self._validate_youtube_url(url)
        if not video_id:
            self.queues.log_error(f'Invalid YouTube URL: {url}')
            return

        # Stop any existing playback
        if self._mpv_process:
            self._stop_playback()

        # Get config settings
        config = self.state.get_config()
        youtube_config = config.get('youtube', {})
        audio_config = config.get('audio', {})

        max_resolution = youtube_config.get('max_resolution', 480)
        audio_device = audio_config.get('output_device', 'default')

        # Clean up old socket
        if os.path.exists(self.IPC_SOCKET_PATH):
            try:
                os.remove(self.IPC_SOCKET_PATH)
            except OSError:
                pass

        # Build mpv command
        # Use a more permissive format string that falls back gracefully
        format_str = f'bestvideo[height<={max_resolution}]+bestaudio/best[height<={max_resolution}]/best'

        cmd = [
            'mpv',
            '--fullscreen',
            '--osc=yes',
            '--script-opts=osc-layout=bottombar,osc-scalewindowed=2,osc-scalefullscreen=2',
            f'--ytdl-format={format_str}',
            f'--input-ipc-server={self.IPC_SOCKET_PATH}',
            '--no-terminal',  # Don't require a terminal
        ]

        # Add audio device if not default
        if audio_device and audio_device != 'default':
            cmd.append(f'--audio-device=pulse/{audio_device}')

        cmd.append(url)

        # Set up environment with display access
        env = os.environ.copy()
        env['DISPLAY'] = ':0'

        try:
            self.queues.log_action(f'Starting YouTube playback: {video_id}')
            self.queues.log_info(f'mpv command: {" ".join(cmd)}')

            # Start mpv process
            self._mpv_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env
            )

            # Update state
            self.state.set_youtube_playing(True, video_id=video_id)

            # Wait a moment for mpv to start and create socket
            time.sleep(2)

            # Check if process is still running
            if self._mpv_process.poll() is not None:
                # Process exited immediately - read stderr for error
                stderr = self._mpv_process.stderr.read().decode() if self._mpv_process.stderr else ''
                self.queues.log_error(f'mpv exited immediately: {stderr[:500]}')
                self.state.set_youtube_playing(False)
                self._mpv_process = None
                return

            # Try to get video title
            title = self._get_property('media-title')
            if title:
                self.state.set_youtube_playing(True, video_id=video_id, title=title)
                self.queues.log_info(f'Playing: {title}')

        except FileNotFoundError:
            self.queues.log_error('mpv not found. Install with: sudo apt install mpv')
            self.state.set_youtube_playing(False)

        except Exception as e:
            self.queues.log_error(f'Failed to start mpv: {e}')
            self.state.set_youtube_playing(False)

    def _stop_playback(self):
        """Stop current playback."""
        if self._mpv_process:
            # Try graceful quit first
            self._send_mpv_command(['quit'])

            # Give it a moment to exit
            try:
                self._mpv_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill
                self._mpv_process.kill()
                self._mpv_process.wait()

            self._mpv_process = None

        self._on_playback_ended()

    def _on_playback_ended(self):
        """Handle playback ending."""
        self._mpv_process = None

        # Clean up socket
        if os.path.exists(self.IPC_SOCKET_PATH):
            try:
                os.remove(self.IPC_SOCKET_PATH)
            except OSError:
                pass

        # Update state
        self.state.set_youtube_playing(False)
        self.queues.log_action('YouTube playback ended')

    def _send_mpv_command(self, command: list) -> Optional[dict]:
        """Send a command to mpv via IPC socket."""
        if not os.path.exists(self.IPC_SOCKET_PATH):
            return None

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(self.IPC_SOCKET_PATH)

            msg = json.dumps({'command': command}) + '\n'
            sock.send(msg.encode())

            response = sock.recv(4096).decode()
            sock.close()

            return json.loads(response)

        except (socket.error, json.JSONDecodeError, OSError):
            return None

    def _get_property(self, prop: str) -> Optional[any]:
        """Get a property from mpv."""
        result = self._send_mpv_command(['get_property', prop])
        if result and 'data' in result:
            return result['data']
        return None

    def _update_status(self):
        """Update playback status from mpv."""
        if not self._mpv_process or not os.path.exists(self.IPC_SOCKET_PATH):
            return

        try:
            position = self._get_property('time-pos') or 0.0
            duration = self._get_property('duration') or 0.0
            paused = self._get_property('pause') or False

            self.state.update_youtube_position(position, duration, paused)

        except Exception:
            pass

    def is_playing(self) -> bool:
        """Check if a video is currently playing."""
        return self._mpv_process is not None and self._mpv_process.poll() is None
