"""Configuration management service."""

import json
import os
from pathlib import Path
from threading import Thread
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from app.shared_state import SharedState, Queues, shutdown_event


# Default configuration
DEFAULT_CONFIG = {
    "display": {
        "width": 800,
        "height": 480,
        "fullscreen": True,
        "fps": 30
    },
    "clock": {
        "format_24h": False,
        "show_seconds": True,
        "timezone": "America/New_York"
    },
    "weather": {
        "api_key": "",
        "lat": 40.7128,
        "lon": -74.0060,
        "units": "imperial",
        "update_interval_minutes": 30
    },
    "theme": "dark",
    "audio": {
        "output_device": "default",
        "volume": 80
    },
    "bluetooth": {
        "speaker_mac": "",
        "auto_connect": True
    },
    "web": {
        "port": 5000,
        "host": "0.0.0.0"
    },
    "youtube": {
        "max_resolution": 480,
        "default_volume": 80
    }
}


def get_config_path() -> Path:
    """Get the path to the config file."""
    base_dir = Path(__file__).parent.parent.parent
    return base_dir / "config" / "settings.json"


def get_themes_dir() -> Path:
    """Get the path to the themes directory."""
    base_dir = Path(__file__).parent.parent.parent
    return base_dir / "themes"


def load_config() -> dict:
    """Load configuration from file, creating default if needed."""
    config_path = get_config_path()

    if not config_path.exists():
        # Create default config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG.copy()

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Merge with defaults for any missing keys
        merged = DEFAULT_CONFIG.copy()
        _deep_merge(merged, config)
        return merged

    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Save configuration to file."""
    config_path = get_config_path()

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving config: {e}")
        return False


def load_theme(theme_name: str) -> dict:
    """Load a theme by name."""
    themes_dir = get_themes_dir()
    theme_path = themes_dir / f"{theme_name}.json"

    if not theme_path.exists():
        # Return default dark theme
        return get_default_theme()

    try:
        with open(theme_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading theme {theme_name}: {e}")
        return get_default_theme()


def save_theme(theme_name: str, theme_data: dict) -> bool:
    """Save a theme to file."""
    themes_dir = get_themes_dir()
    theme_path = themes_dir / f"{theme_name}.json"

    try:
        themes_dir.mkdir(parents=True, exist_ok=True)
        with open(theme_path, 'w') as f:
            json.dump(theme_data, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving theme {theme_name}: {e}")
        return False


def list_themes() -> list[str]:
    """List all available theme names."""
    themes_dir = get_themes_dir()

    if not themes_dir.exists():
        return ["dark"]

    themes = []
    for f in themes_dir.glob("*.json"):
        themes.append(f.stem)

    return themes if themes else ["dark"]


def get_default_theme() -> dict:
    """Get the default dark theme."""
    return {
        "name": "Dark",
        "background": "#1a1a2e",
        "clock": {
            "color": "#ffffff",
            "font_size": 72
        },
        "weather": {
            "label_color": "#888888",
            "use_dynamic_colors": True,
            "static_value_color": "#ffffff"
        },
        "graph": {
            "background": "#16213e",
            "high_line": "#ff6b6b",
            "low_line": "#4ecdc4",
            "grid_color": "#333333",
            "label_color": "#888888"
        },
        "status_bar": {
            "background": "#0f0f1a",
            "text_color": "#666666"
        },
        "accents": {
            "primary": "#e94560",
            "secondary": "#0f3460"
        }
    }


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


class ConfigFileHandler(FileSystemEventHandler):
    """Watches for config file changes."""

    def __init__(self, state: SharedState, queues: Queues):
        self.state = state
        self.queues = queues
        self._last_modified = 0

    def on_modified(self, event):
        if not isinstance(event, FileModifiedEvent):
            return

        if not event.src_path.endswith('settings.json'):
            return

        # Debounce - ignore if modified within last second
        import time
        now = time.time()
        if now - self._last_modified < 1:
            return
        self._last_modified = now

        # Reload config
        config = load_config()
        self.state.set_config(config)

        # Load new theme if changed
        theme = load_theme(config.get('theme', 'dark'))
        self.state.set_theme(theme)

        # Notify main thread
        self.queues.config.put({'type': 'reload'})
        self.queues.log_action('Configuration reloaded')


class ConfigWatcher(Thread):
    """Thread that watches for config file changes."""

    def __init__(self, state: SharedState, queues: Queues):
        super().__init__(daemon=True)
        self.state = state
        self.queues = queues
        self.observer: Optional[Observer] = None

    def run(self):
        config_path = get_config_path()
        config_dir = str(config_path.parent)

        handler = ConfigFileHandler(self.state, self.queues)
        self.observer = Observer()
        self.observer.schedule(handler, config_dir, recursive=False)
        self.observer.start()

        self.queues.log_info('Config watcher started')

        # Wait for shutdown
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1)

        self.observer.stop()
        self.observer.join()
