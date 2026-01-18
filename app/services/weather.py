"""Weather service thread for fetching OpenWeatherMap data."""

import json
import time
from pathlib import Path
from threading import Thread, Event
from queue import Empty
from typing import Optional

import requests

from app.shared_state import SharedState, Queues, shutdown_event


class WeatherService(Thread):
    """Background thread that fetches weather data from OpenWeatherMap."""

    API_URL = "https://api.openweathermap.org/data/3.0/onecall"

    def __init__(self, state: SharedState, queues: Queues):
        super().__init__(daemon=True)
        self.state = state
        self.queues = queues
        self._cache_path = Path(__file__).parent.parent.parent / "cache" / "weather.json"
        self._refresh_event = Event()

    def run(self):
        """Main thread loop."""
        self.queues.log_info('Weather service started')

        # Load cached data on startup
        self._load_cache()

        # Initial fetch
        self._fetch_weather()

        # Main loop - check every 10 seconds for config changes or if interval has passed
        while not shutdown_event.is_set():
            # Wait for refresh event or timeout (check every 10 seconds)
            if self._refresh_event.wait(timeout=10):
                # Refresh was requested manually
                self._refresh_event.clear()
                self._fetch_weather()
            elif not shutdown_event.is_set():
                # Get current interval from config (re-read each time to catch changes)
                config = self.state.get_config()
                interval_minutes = config.get('weather', {}).get('update_interval_minutes', 30)
                interval_seconds = interval_minutes * 60

                # Check if enough time has passed since last fetch
                weather_data, last_fetch = self.state.get_weather()
                if last_fetch is None or (time.time() - last_fetch) >= interval_seconds:
                    self._fetch_weather()

    def trigger_refresh(self):
        """Trigger an immediate weather refresh."""
        self._refresh_event.set()

    def _fetch_weather(self):
        """Fetch weather data from API."""
        config = self.state.get_config()
        weather_config = config.get('weather', {})

        api_key = weather_config.get('api_key', '')
        if not api_key:
            self.queues.log_error('Weather API key not configured')
            return

        lat = weather_config.get('lat', 0)
        lon = weather_config.get('lon', 0)
        units = weather_config.get('units', 'imperial')

        if lat == 0 and lon == 0:
            self.queues.log_error('Weather location not configured')
            return

        try:
            start_time = time.time()

            params = {
                'lat': lat,
                'lon': lon,
                'appid': api_key,
                'units': units,
                'exclude': 'minutely,alerts'  # We don't need these
            }

            response = requests.get(self.API_URL, params=params, timeout=30)
            elapsed_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                data = response.json()

                # Update shared state
                self.state.update_weather(data)

                # Notify main thread
                self.queues.weather.put({
                    'type': 'update',
                    'data': data
                })

                # Cache the data
                self._save_cache(data)

                self.queues.log_api(f'Weather fetch OK ({elapsed_ms:.0f}ms)')

            elif response.status_code == 401:
                self.queues.log_error('Weather API: Invalid API key')

            elif response.status_code == 429:
                self.queues.log_error('Weather API: Rate limit exceeded')

            else:
                self.queues.log_error(f'Weather API: HTTP {response.status_code}')

        except requests.exceptions.Timeout:
            self.queues.log_error('Weather API: Request timeout')
            self._load_cache()  # Use cached data

        except requests.exceptions.ConnectionError:
            self.queues.log_error('Weather API: Connection error')
            self._load_cache()  # Use cached data

        except Exception as e:
            self.queues.log_error(f'Weather fetch failed: {str(e)}')
            self._load_cache()  # Use cached data

    def _save_cache(self, data: dict):
        """Save weather data to cache file."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)

            cache_data = {
                'fetched_at': time.time(),
                'data': data
            }

            with open(self._cache_path, 'w') as f:
                json.dump(cache_data, f)

        except Exception as e:
            self.queues.log_error(f'Failed to save weather cache: {e}')

    def _load_cache(self):
        """Load weather data from cache file."""
        try:
            if not self._cache_path.exists():
                return

            with open(self._cache_path, 'r') as f:
                cache_data = json.load(f)

            data = cache_data.get('data')
            if data:
                self.state.update_weather(data)
                self.queues.weather.put({
                    'type': 'update',
                    'data': data
                })
                self.queues.log_info('Loaded weather from cache')

        except Exception as e:
            self.queues.log_error(f'Failed to load weather cache: {e}')
