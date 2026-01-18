"""Thread-safe shared state for inter-thread communication."""

import time
from threading import Lock, Event
from queue import Queue
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class LogEntry:
    """A single log entry."""
    timestamp: float
    category: str  # 'API', 'Action', 'Error', 'Info'
    message: str

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'category': self.category,
            'message': self.message
        }


class SharedState:
    """Thread-safe shared state container."""

    def __init__(self):
        self._lock = Lock()

        # Weather data
        self._weather_data: Optional[dict] = None
        self._weather_last_fetch: Optional[float] = None

        # YouTube state
        self._youtube_playing: bool = False
        self._youtube_video_id: Optional[str] = None
        self._youtube_title: Optional[str] = None
        self._youtube_position: float = 0.0
        self._youtube_duration: float = 0.0
        self._youtube_paused: bool = False

        # Bluetooth state
        self._bluetooth_connected: bool = False
        self._bluetooth_device_name: Optional[str] = None
        self._bluetooth_device_mac: Optional[str] = None

        # Audio state
        self._audio_device: str = "default"
        self._audio_volume: int = 80
        self._audio_devices: list = []

        # Network state
        self._ip_address: Optional[str] = None

        # Config
        self._config: dict = {}

        # Current theme
        self._theme: dict = {}

    # Weather methods
    def update_weather(self, data: dict) -> None:
        with self._lock:
            self._weather_data = data
            self._weather_last_fetch = time.time()

    def get_weather(self) -> tuple[Optional[dict], Optional[float]]:
        with self._lock:
            return self._weather_data, self._weather_last_fetch

    # YouTube methods
    def set_youtube_playing(self, playing: bool, video_id: str = None,
                            title: str = None) -> None:
        with self._lock:
            self._youtube_playing = playing
            self._youtube_video_id = video_id
            self._youtube_title = title
            if not playing:
                self._youtube_position = 0.0
                self._youtube_duration = 0.0
                self._youtube_paused = False

    def update_youtube_position(self, position: float, duration: float,
                                 paused: bool) -> None:
        with self._lock:
            self._youtube_position = position
            self._youtube_duration = duration
            self._youtube_paused = paused

    def get_youtube_status(self) -> dict:
        with self._lock:
            return {
                'playing': self._youtube_playing,
                'video_id': self._youtube_video_id,
                'title': self._youtube_title,
                'position': self._youtube_position,
                'duration': self._youtube_duration,
                'paused': self._youtube_paused
            }

    # Bluetooth methods
    def set_bluetooth_status(self, connected: bool, device_name: str = None,
                              device_mac: str = None) -> None:
        with self._lock:
            self._bluetooth_connected = connected
            self._bluetooth_device_name = device_name
            self._bluetooth_device_mac = device_mac

    def get_bluetooth_status(self) -> dict:
        with self._lock:
            return {
                'connected': self._bluetooth_connected,
                'device_name': self._bluetooth_device_name,
                'device_mac': self._bluetooth_device_mac
            }

    # Audio methods
    def set_audio_device(self, device: str) -> None:
        with self._lock:
            self._audio_device = device

    def set_audio_volume(self, volume: int) -> None:
        with self._lock:
            self._audio_volume = max(0, min(100, volume))

    def set_audio_devices(self, devices: list) -> None:
        with self._lock:
            self._audio_devices = devices

    def get_audio_status(self) -> dict:
        with self._lock:
            return {
                'device': self._audio_device,
                'volume': self._audio_volume,
                'devices': self._audio_devices.copy()
            }

    # Network methods
    def set_ip_address(self, ip: str) -> None:
        with self._lock:
            self._ip_address = ip

    def get_ip_address(self) -> Optional[str]:
        with self._lock:
            return self._ip_address

    # Config methods
    def set_config(self, config: dict) -> None:
        with self._lock:
            self._config = config.copy()

    def get_config(self) -> dict:
        with self._lock:
            return self._config.copy()

    # Theme methods
    def set_theme(self, theme: dict) -> None:
        with self._lock:
            self._theme = theme.copy()

    def get_theme(self) -> dict:
        with self._lock:
            return self._theme.copy()


class Queues:
    """Container for all inter-thread queues."""

    def __init__(self):
        self.weather = Queue()   # Weather data updates
        self.config = Queue()    # Config change notifications
        self.command = Queue()   # Commands from web UI
        self.log = Queue()       # Log entries from all threads

    def log_message(self, category: str, message: str) -> None:
        """Convenience method to log a message."""
        entry = LogEntry(
            timestamp=time.time(),
            category=category,
            message=message
        )
        self.log.put(entry)

    def log_api(self, message: str) -> None:
        self.log_message('API', message)

    def log_action(self, message: str) -> None:
        self.log_message('Action', message)

    def log_error(self, message: str) -> None:
        self.log_message('Error', message)

    def log_info(self, message: str) -> None:
        self.log_message('Info', message)


# Global shutdown event
shutdown_event = Event()
