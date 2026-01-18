"""Auto-dimming service for display brightness control."""

import os
import subprocess
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from threading import Thread, Event
from typing import Optional

from app.shared_state import SharedState, Queues, shutdown_event


class DimmingService(Thread):
    """Background thread that manages display brightness based on time of day."""

    # Raspberry Pi backlight sysfs paths
    RPI_BACKLIGHT_PATH = Path("/sys/class/backlight/rpi_backlight/brightness")
    RPI_BACKLIGHT_MAX_PATH = Path("/sys/class/backlight/rpi_backlight/max_brightness")

    # Alternative paths for different setups
    BACKLIGHT_PATHS = [
        Path("/sys/class/backlight/rpi_backlight/brightness"),
        Path("/sys/class/backlight/10-0045/brightness"),
        Path("/sys/class/backlight/backlight/brightness"),
    ]

    def __init__(self, state: SharedState, queues: Queues):
        super().__init__(daemon=True)
        self.state = state
        self.queues = queues

        self._command_event = Event()
        self._pending_command: Optional[dict] = None
        self._backlight_path: Optional[Path] = None
        self._max_brightness: int = 255
        self._current_brightness: int = 255
        self._manual_override: bool = False

    def run(self):
        """Main thread loop."""
        self.queues.log_info('Dimming service started')

        # Find working backlight path
        self._find_backlight_path()

        last_check = time.time()
        last_minute = -1

        while not shutdown_event.is_set():
            # Check for pending commands
            if self._command_event.wait(timeout=10):
                self._command_event.clear()
                if self._pending_command:
                    self._handle_command(self._pending_command)
                    self._pending_command = None

            # Check if minute changed (only adjust on minute boundaries)
            now = datetime.now()
            if now.minute != last_minute:
                last_minute = now.minute
                if not self._manual_override:
                    self._auto_adjust_brightness()

    def send_command(self, cmd: dict):
        """Send a command to the dimming service."""
        self._pending_command = cmd
        self._command_event.set()

    def _handle_command(self, cmd: dict):
        """Handle a command from the web UI."""
        cmd_type = cmd.get('type')

        if cmd_type == 'dimming_set_brightness':
            brightness = cmd.get('brightness', 100)
            self._set_brightness_percent(brightness)
            self._manual_override = True
            self.queues.log_action(f'Brightness manually set to {brightness}%')

        elif cmd_type == 'dimming_auto':
            self._manual_override = False
            self._auto_adjust_brightness()
            self.queues.log_action('Auto-dimming enabled')

    def _find_backlight_path(self):
        """Find a working backlight sysfs path."""
        for path in self.BACKLIGHT_PATHS:
            if path.exists():
                self._backlight_path = path
                self._get_max_brightness()
                self.queues.log_info(f'Using backlight: {path}')
                return

        # No sysfs backlight found, will try xrandr
        self.queues.log_info('No sysfs backlight found, will use xrandr')

    def _get_max_brightness(self):
        """Get the maximum brightness value."""
        if self._backlight_path:
            max_path = self._backlight_path.parent / "max_brightness"
            if max_path.exists():
                try:
                    with open(max_path, 'r') as f:
                        self._max_brightness = int(f.read().strip())
                except Exception:
                    self._max_brightness = 255

    def _set_brightness_percent(self, percent: int):
        """Set brightness as a percentage (0-100)."""
        percent = max(10, min(100, percent))  # Minimum 10% to prevent complete darkness
        self._current_brightness = percent

        if self._backlight_path:
            self._set_sysfs_brightness(percent)
        else:
            self._set_xrandr_brightness(percent)

    def _set_sysfs_brightness(self, percent: int):
        """Set brightness via sysfs (Raspberry Pi)."""
        if not self._backlight_path or not self._backlight_path.exists():
            return

        value = int(self._max_brightness * percent / 100)

        try:
            with open(self._backlight_path, 'w') as f:
                f.write(str(value))
        except PermissionError:
            # Try with sudo
            try:
                subprocess.run(
                    ['sudo', 'tee', str(self._backlight_path)],
                    input=str(value).encode(),
                    capture_output=True,
                    timeout=5
                )
            except Exception as e:
                self.queues.log_error(f'Failed to set brightness: {e}')
        except Exception as e:
            self.queues.log_error(f'Failed to set brightness: {e}')

    def _set_xrandr_brightness(self, percent: int):
        """Set brightness via xrandr (fallback for non-RPi)."""
        brightness = percent / 100.0

        try:
            # Get connected displays
            result = subprocess.run(
                ['xrandr', '--query'],
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, 'DISPLAY': ':0'}
            )

            if result.returncode != 0:
                return

            # Find connected outputs
            for line in result.stdout.split('\n'):
                if ' connected' in line:
                    output = line.split()[0]
                    subprocess.run(
                        ['xrandr', '--output', output, '--brightness', str(brightness)],
                        capture_output=True,
                        timeout=5,
                        env={**os.environ, 'DISPLAY': ':0'}
                    )

        except FileNotFoundError:
            self.queues.log_error('xrandr not found')
        except Exception as e:
            self.queues.log_error(f'Failed to set xrandr brightness: {e}')

    def _auto_adjust_brightness(self):
        """Automatically adjust brightness based on time of day."""
        config = self.state.get_config()
        dimming_config = config.get('dimming', {})

        if not dimming_config.get('enabled', True):
            return

        # Get schedule settings
        day_start = dimming_config.get('day_start', '07:00')
        night_start = dimming_config.get('night_start', '21:00')
        day_brightness = dimming_config.get('day_brightness', 100)
        night_brightness = dimming_config.get('night_brightness', 30)
        transition_minutes = dimming_config.get('transition_minutes', 30)

        # Parse times
        try:
            day_time = datetime.strptime(day_start, '%H:%M').time()
            night_time = datetime.strptime(night_start, '%H:%M').time()
        except ValueError:
            # Default to 7am/9pm if parsing fails
            day_time = dt_time(7, 0)
            night_time = dt_time(21, 0)

        now = datetime.now().time()

        # Determine target brightness based on time
        if self._is_time_between(now, day_time, night_time):
            # Daytime
            target = day_brightness

            # Check if in morning transition
            morning_transition_end = self._add_minutes(day_time, transition_minutes)
            if self._is_time_between(now, day_time, morning_transition_end):
                # Calculate transition progress
                progress = self._time_diff_minutes(day_time, now) / transition_minutes
                target = int(night_brightness + (day_brightness - night_brightness) * progress)
        else:
            # Nighttime
            target = night_brightness

            # Check if in evening transition
            evening_transition_end = self._add_minutes(night_time, transition_minutes)
            if self._is_time_between(now, night_time, evening_transition_end):
                # Calculate transition progress
                progress = self._time_diff_minutes(night_time, now) / transition_minutes
                target = int(day_brightness + (night_brightness - day_brightness) * progress)

        # Only update if significantly different
        if abs(target - self._current_brightness) >= 5:
            self._set_brightness_percent(target)

    def _is_time_between(self, check: dt_time, start: dt_time, end: dt_time) -> bool:
        """Check if a time is between start and end (handles midnight crossing)."""
        if start <= end:
            return start <= check <= end
        else:
            return check >= start or check <= end

    def _add_minutes(self, t: dt_time, minutes: int) -> dt_time:
        """Add minutes to a time."""
        total_minutes = t.hour * 60 + t.minute + minutes
        total_minutes = total_minutes % (24 * 60)
        return dt_time(total_minutes // 60, total_minutes % 60)

    def _time_diff_minutes(self, start: dt_time, end: dt_time) -> float:
        """Get difference in minutes between two times."""
        start_mins = start.hour * 60 + start.minute
        end_mins = end.hour * 60 + end.minute

        diff = end_mins - start_mins
        if diff < 0:
            diff += 24 * 60

        return diff

    def get_current_brightness(self) -> int:
        """Get current brightness percentage."""
        return self._current_brightness

    def is_manual_override(self) -> bool:
        """Check if manual override is active."""
        return self._manual_override
