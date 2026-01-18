"""Log service thread for aggregating and persisting logs."""

import json
import time
from datetime import datetime
from pathlib import Path
from queue import Empty
from threading import Thread
from typing import List

from app.shared_state import Queues, shutdown_event, LogEntry


class LogService(Thread):
    """Background thread that aggregates logs and writes to file."""

    def __init__(self, queues: Queues, max_file_size: int = 5 * 1024 * 1024):
        super().__init__(daemon=True)
        self.queues = queues
        self.max_file_size = max_file_size  # 5MB default
        self._log_dir = Path(__file__).parent.parent.parent / "logs"
        self._current_log_file: Path = None
        self._buffer: List[dict] = []
        self._buffer_size = 100  # Flush after this many entries

    def run(self):
        """Main thread loop."""
        # Ensure log directory exists
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # Create initial log file
        self._rotate_log_file()

        # Process logs
        while not shutdown_event.is_set():
            try:
                # Get log entry with timeout
                entry = self.queues.log.get(timeout=0.5)

                # Convert to dict if needed
                if isinstance(entry, LogEntry):
                    log_dict = entry.to_dict()
                elif isinstance(entry, dict):
                    log_dict = entry
                    # Ensure timestamp exists
                    if 'timestamp' not in log_dict:
                        log_dict['timestamp'] = time.time()
                else:
                    continue

                # Add to buffer
                self._buffer.append(log_dict)

                # Flush if buffer is full
                if len(self._buffer) >= self._buffer_size:
                    self._flush_buffer()

            except Empty:
                # Flush any pending logs on timeout
                if self._buffer:
                    self._flush_buffer()

        # Final flush on shutdown
        if self._buffer:
            self._flush_buffer()

    def _rotate_log_file(self):
        """Create a new log file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._current_log_file = self._log_dir / f"tablepi_{timestamp}.log"

    def _flush_buffer(self):
        """Write buffered logs to file."""
        if not self._buffer:
            return

        try:
            # Check if rotation needed
            if self._current_log_file.exists():
                if self._current_log_file.stat().st_size > self.max_file_size:
                    self._rotate_log_file()

            # Write logs
            with open(self._current_log_file, 'a') as f:
                for log in self._buffer:
                    # Format: timestamp | category | message
                    ts = datetime.fromtimestamp(log['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                    category = log.get('category', 'Info')
                    message = log.get('message', '')
                    f.write(f"{ts} | {category:8} | {message}\n")

            self._buffer = []

        except Exception as e:
            print(f"Failed to write logs: {e}")
            # Don't lose logs, keep in buffer (but limit size)
            if len(self._buffer) > 1000:
                self._buffer = self._buffer[-500:]

    def _cleanup_old_logs(self, max_files: int = 10):
        """Remove old log files, keeping only the most recent."""
        try:
            log_files = sorted(self._log_dir.glob("tablepi_*.log"))
            if len(log_files) > max_files:
                for old_file in log_files[:-max_files]:
                    old_file.unlink()
        except Exception as e:
            print(f"Failed to cleanup old logs: {e}")
