"""Bluetooth device management service using bluetoothctl."""

import re
import subprocess
import time
from threading import Thread, Event
from typing import Optional, List, Dict

from app.shared_state import SharedState, Queues, shutdown_event


class BluetoothService(Thread):
    """Background thread that manages Bluetooth connections."""

    def __init__(self, state: SharedState, queues: Queues):
        super().__init__(daemon=True)
        self.state = state
        self.queues = queues

        self._command_event = Event()
        self._pending_command: Optional[dict] = None
        self._discovered_devices: List[Dict] = []
        self._scanning = False

    def run(self):
        """Main thread loop."""
        self.queues.log_info('Bluetooth service started')

        # Try auto-connect on startup
        self._auto_connect()

        last_status_check = time.time()

        while not shutdown_event.is_set():
            # Check for pending commands
            if self._command_event.wait(timeout=2):
                self._command_event.clear()
                if self._pending_command:
                    self._handle_command(self._pending_command)
                    self._pending_command = None

            # Check connection status every 10 seconds
            if time.time() - last_status_check > 10:
                self._check_connection_status()
                last_status_check = time.time()

    def send_command(self, cmd: dict):
        """Send a command to the Bluetooth service."""
        self._pending_command = cmd
        self._command_event.set()

    def get_discovered_devices(self) -> List[Dict]:
        """Get the list of discovered devices."""
        return self._discovered_devices.copy()

    def is_scanning(self) -> bool:
        """Check if currently scanning."""
        return self._scanning

    def _handle_command(self, cmd: dict):
        """Handle a command from the web UI."""
        cmd_type = cmd.get('type')

        if cmd_type == 'bluetooth_scan':
            self._scan_devices()

        elif cmd_type == 'bluetooth_connect':
            mac = cmd.get('mac', '')
            self._connect_device(mac)

        elif cmd_type == 'bluetooth_disconnect':
            self._disconnect_device()

        elif cmd_type == 'bluetooth_pair':
            mac = cmd.get('mac', '')
            self._pair_device(mac)

        elif cmd_type == 'bluetooth_remove':
            mac = cmd.get('mac', '')
            self._remove_device(mac)

    def _auto_connect(self):
        """Try to auto-connect to configured device on startup."""
        config = self.state.get_config()
        bt_config = config.get('bluetooth', {})

        if not bt_config.get('auto_connect', True):
            return

        mac = bt_config.get('speaker_mac', '')
        if not mac:
            return

        self.queues.log_info(f'Attempting auto-connect to {mac}')
        self._connect_device(mac)

    def _scan_devices(self, duration: int = 10):
        """Scan for nearby Bluetooth devices."""
        self._scanning = True
        self._discovered_devices = []

        try:
            self.queues.log_action('Starting Bluetooth scan')

            # Start scan
            subprocess.run(
                ['bluetoothctl', 'scan', 'on'],
                capture_output=True,
                timeout=2
            )

            # Wait for scan duration
            time.sleep(duration)

            # Stop scan
            subprocess.run(
                ['bluetoothctl', 'scan', 'off'],
                capture_output=True,
                timeout=2
            )

            # Get list of devices
            result = subprocess.run(
                ['bluetoothctl', 'devices'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                self._discovered_devices = self._parse_devices(result.stdout)
                self.queues.log_action(f'Found {len(self._discovered_devices)} Bluetooth devices')

        except subprocess.TimeoutExpired:
            self.queues.log_error('Bluetooth scan timeout')
        except FileNotFoundError:
            self.queues.log_error('bluetoothctl not found')
        except Exception as e:
            self.queues.log_error(f'Bluetooth scan failed: {e}')

        self._scanning = False

    def _parse_devices(self, output: str) -> List[Dict]:
        """Parse bluetoothctl devices output."""
        devices = []

        for line in output.strip().split('\n'):
            if not line:
                continue

            # Format: Device XX:XX:XX:XX:XX:XX Device Name
            match = re.match(r'Device\s+([0-9A-Fa-f:]{17})\s+(.+)', line)
            if match:
                mac = match.group(1)
                name = match.group(2)

                # Check if device is paired/connected
                info = self._get_device_info(mac)

                devices.append({
                    'mac': mac,
                    'name': name,
                    'paired': info.get('paired', False),
                    'connected': info.get('connected', False),
                    'trusted': info.get('trusted', False)
                })

        return devices

    def _get_device_info(self, mac: str) -> Dict:
        """Get info about a specific device."""
        info = {'paired': False, 'connected': False, 'trusted': False}

        try:
            result = subprocess.run(
                ['bluetoothctl', 'info', mac],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                output = result.stdout
                info['paired'] = 'Paired: yes' in output
                info['connected'] = 'Connected: yes' in output
                info['trusted'] = 'Trusted: yes' in output

        except Exception:
            pass

        return info

    def _connect_device(self, mac: str):
        """Connect to a Bluetooth device."""
        if not mac:
            return

        try:
            self.queues.log_action(f'Connecting to Bluetooth device {mac}')

            # Make sure the device is trusted (for auto-reconnect)
            subprocess.run(
                ['bluetoothctl', 'trust', mac],
                capture_output=True,
                timeout=5
            )

            # Connect
            result = subprocess.run(
                ['bluetoothctl', 'connect', mac],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0 and 'Connection successful' in result.stdout:
                # Get device name
                name = self._get_device_name(mac)
                self.state.set_bluetooth_status(True, device_name=name, device_mac=mac)
                self.queues.log_action(f'Connected to {name}')
            else:
                self.queues.log_error(f'Failed to connect: {result.stderr or result.stdout}')
                self.state.set_bluetooth_status(False)

        except subprocess.TimeoutExpired:
            self.queues.log_error('Bluetooth connect timeout')
            self.state.set_bluetooth_status(False)
        except Exception as e:
            self.queues.log_error(f'Bluetooth connect failed: {e}')
            self.state.set_bluetooth_status(False)

    def _disconnect_device(self):
        """Disconnect from current Bluetooth device."""
        status = self.state.get_bluetooth_status()
        mac = status.get('device_mac')

        if not mac:
            return

        try:
            self.queues.log_action(f'Disconnecting Bluetooth device {mac}')

            result = subprocess.run(
                ['bluetoothctl', 'disconnect', mac],
                capture_output=True,
                text=True,
                timeout=10
            )

            self.state.set_bluetooth_status(False)
            self.queues.log_action('Bluetooth disconnected')

        except Exception as e:
            self.queues.log_error(f'Bluetooth disconnect failed: {e}')

    def _pair_device(self, mac: str):
        """Pair with a Bluetooth device."""
        if not mac:
            return

        try:
            self.queues.log_action(f'Pairing with Bluetooth device {mac}')

            result = subprocess.run(
                ['bluetoothctl', 'pair', mac],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                self.queues.log_action(f'Paired with {mac}')
            else:
                self.queues.log_error(f'Failed to pair: {result.stderr or result.stdout}')

        except subprocess.TimeoutExpired:
            self.queues.log_error('Bluetooth pair timeout')
        except Exception as e:
            self.queues.log_error(f'Bluetooth pair failed: {e}')

    def _remove_device(self, mac: str):
        """Remove/unpair a Bluetooth device."""
        if not mac:
            return

        try:
            self.queues.log_action(f'Removing Bluetooth device {mac}')

            result = subprocess.run(
                ['bluetoothctl', 'remove', mac],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                self.queues.log_action(f'Removed device {mac}')

                # Update status if this was connected device
                status = self.state.get_bluetooth_status()
                if status.get('device_mac') == mac:
                    self.state.set_bluetooth_status(False)
            else:
                self.queues.log_error(f'Failed to remove: {result.stderr}')

        except Exception as e:
            self.queues.log_error(f'Bluetooth remove failed: {e}')

    def _check_connection_status(self):
        """Check if Bluetooth device is still connected."""
        status = self.state.get_bluetooth_status()
        mac = status.get('device_mac')

        if not mac:
            return

        info = self._get_device_info(mac)

        if not info.get('connected'):
            # Device disconnected
            if status.get('connected'):
                self.state.set_bluetooth_status(False)
                self.queues.log_action(f'Bluetooth device {mac} disconnected')

    def _get_device_name(self, mac: str) -> str:
        """Get the name of a Bluetooth device."""
        try:
            result = subprocess.run(
                ['bluetoothctl', 'info', mac],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                match = re.search(r'Name:\s+(.+)', result.stdout)
                if match:
                    return match.group(1)

        except Exception:
            pass

        return mac  # Return MAC as fallback
