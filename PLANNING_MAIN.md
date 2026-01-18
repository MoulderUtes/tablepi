# TablePi - Main Planning Document

## Project Overview

A 7-inch tabletop display running on a Raspberry Pi 3B that shows:
- Clock with seconds
- Weather information (see [PLANNING_WEATHER.md](PLANNING_WEATHER.md))
- YouTube video playback (see [PLANNING_YOUTUBE.md](PLANNING_YOUTUBE.md))

With a web-based control panel for configuration.

---

## Architecture

### Hybrid Python + Lightweight Web Approach

Given the RPi 3B's limited resources (1GB RAM, older CPU) and the 480p display:

```
┌─────────────────────────────────────────────────────────┐
│                    Raspberry Pi 3B                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐    ┌────────────────────────────┐ │
│  │  Python Display  │    │    Flask Web Server        │ │
│  │  (PyGame)        │◄───│    (Control Panel)         │ │
│  │                  │    │    Port 5000               │ │
│  │  - Clock         │    └────────────────────────────┘ │
│  │  - Weather       │                                   │
│  │  - YouTube       │    ┌────────────────────────────┐ │
│  │    (via mpv)     │    │  Background Services       │ │
│  │                  │    │  - Weather API fetcher     │ │
│  └──────────────────┘    │  - Bluetooth manager       │ │
│                          │  - Audio device manager    │ │
│                          └────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Why this approach:**
- PyGame is much lighter than Chromium
- mpv handles YouTube efficiently (with yt-dlp)
- Flask is lightweight for the admin web UI
- Accessible from phone/laptop on same network

---

## Multi-Threading Architecture

The application uses multiple threads to keep the UI responsive while handling background tasks.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Main Process                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Main Thread (PyGame)                         │ │
│  │  - Display rendering (clock, weather, graphs)                   │ │
│  │  - Touch event handling                                         │ │
│  │  - UI state management                                          │ │
│  │  - 30 FPS render loop                                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│            ▲                    ▲                    ▲               │
│            │ Queue              │ Queue              │ Queue         │
│            ▼                    ▼                    ▼               │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐ │
│  │  Weather Thread  │ │   Flask Thread   │ │  Bluetooth Thread    │ │
│  │                  │ │                  │ │                      │ │
│  │  - API polling   │ │  - Web server    │ │  - Device monitoring │ │
│  │  - Data parsing  │ │  - REST endpoints│ │  - Auto-reconnect    │ │
│  │  - Caching       │ │  - WebSocket     │ │  - Status updates    │ │
│  └──────────────────┘ └──────────────────┘ └──────────────────────┘ │
│                                                                      │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐ │
│  │  Config Thread   │ │   Audio Thread   │ │    Log Thread        │ │
│  │                  │ │                  │ │                      │ │
│  │  - File watcher  │ │  - Device enum   │ │  - Log aggregation   │ │
│  │  - Hot reload    │ │  - Sink switching│ │  - File writing      │ │
│  └──────────────────┘ └──────────────────┘ └──────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Thread Communication

**Thread-Safe Queues:**
```python
from queue import Queue
from threading import Thread, Event

# Shared queues for inter-thread communication
weather_queue = Queue()      # Weather data updates
config_queue = Queue()       # Config change notifications
command_queue = Queue()      # Commands from web UI
log_queue = Queue()          # Log entries from all threads
```

**Shared State with Locks:**
```python
from threading import Lock

class SharedState:
    def __init__(self):
        self._lock = Lock()
        self._weather_data = None
        self._last_fetch = None

    def update_weather(self, data):
        with self._lock:
            self._weather_data = data
            self._last_fetch = time.time()

    def get_weather(self):
        with self._lock:
            return self._weather_data, self._last_fetch
```

### Thread Descriptions

| Thread | Purpose | Update Frequency |
|--------|---------|------------------|
| **Main (PyGame)** | Render display, handle touch | 30 FPS |
| **Weather** | Fetch API, parse, cache | Every 15-30 min |
| **Flask** | Serve web UI, handle API | On request |
| **Bluetooth** | Monitor connection, reconnect | Every 5 sec |
| **Config** | Watch settings file | On file change |
| **Audio** | Enumerate devices, switch sinks | On demand |
| **Log** | Aggregate logs, write to file | Continuous |

### Startup Sequence

```python
def main():
    # 1. Initialize shared state
    state = SharedState()
    queues = {
        'weather': Queue(),
        'config': Queue(),
        'command': Queue(),
        'log': Queue()
    }

    # 2. Start background threads
    threads = [
        Thread(target=weather_service, args=(state, queues), daemon=True),
        Thread(target=flask_server, args=(state, queues), daemon=True),
        Thread(target=bluetooth_service, args=(state, queues), daemon=True),
        Thread(target=config_watcher, args=(state, queues), daemon=True),
        Thread(target=log_service, args=(queues,), daemon=True),
    ]

    for t in threads:
        t.start()

    # 3. Run main display loop (blocks)
    run_display(state, queues)
```

### Graceful Shutdown

```python
shutdown_event = Event()

def signal_handler(sig, frame):
    shutdown_event.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# In each thread:
while not shutdown_event.is_set():
    # ... do work ...
    shutdown_event.wait(timeout=interval)
```

---

## Project Structure

```
tablepi/
├── app/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── display/
│   │   ├── __init__.py
│   │   ├── clock.py         # Clock widget
│   │   ├── weather.py       # Weather widget
│   │   ├── youtube.py       # YouTube player (mpv wrapper)
│   │   ├── themes.py        # Theme management
│   │   └── colors.py        # Dynamic color functions
│   ├── services/
│   │   ├── __init__.py
│   │   ├── weather_api.py   # Weather API client
│   │   ├── bluetooth.py     # Bluetooth speaker manager
│   │   ├── audio.py         # Audio device manager
│   │   ├── network.py       # IP address detection
│   │   └── config.py        # Configuration manager
│   └── web/
│       ├── __init__.py
│       ├── server.py        # Flask web server
│       ├── templates/
│       │   └── index.html   # Control panel UI
│       └── static/
│           ├── css/
│           └── js/
├── config/
│   └── settings.json        # User configuration
├── themes/
│   ├── default.json
│   ├── dark.json
│   ├── light.json
│   ├── neon.json
│   └── minimal.json
├── requirements.txt
├── install.sh               # Installation script
└── tablepi.service          # Systemd service file
```

---

## Main Display Layout

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│                    12:34:56 PM                          │  ← Large clock with seconds
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│           [Weather Section - see WEATHER doc]           │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│          [7-Day Graph - see WEATHER doc]                │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  IP: 192.168.1.42          Last update: 5 min ago       │  ← Status bar
└─────────────────────────────────────────────────────────┘
```

### Status Bar (Bottom of Screen)
- **IP Address:** Shows current device IP for easy web UI access
- **Last API Update:** Time since last weather API call (e.g., "2 min ago", "Just now")
- Small, unobtrusive text at bottom of display

---

## Clock Module

- Large digital clock with seconds
- Updates every second
- Configurable 12/24 hour format
- Timezone support via `pytz`
- Centered at top of display

---

## Theme System

### Multiple Selectable Themes
- Default, Dark, Light, Neon, Minimal (pre-built)
- Each theme stored as editable JSON
- User can create custom themes via web UI

### Dynamic Color Coding (Weather Values)

Weather stats automatically color based on data:

**Temperature Colors:**
| Range | Color | Hex |
|-------|-------|-----|
| < 32°F | Deep blue | #0066FF |
| 32-50°F | Light blue | #66B2FF |
| 50-65°F | Green | #66CC66 |
| 65-80°F | Yellow | #FFCC00 |
| 80-90°F | Orange | #FF9933 |
| > 90°F | Red | #FF3333 |

**Precipitation Colors:**
| Range | Color |
|-------|-------|
| 0-20% | Gray |
| 20-50% | Light blue |
| 50-80% | Blue |
| 80-100% | Dark blue/purple |

**UV Index Colors:**
| Range | Label | Color |
|-------|-------|-------|
| 0-2 | Low | Green |
| 3-5 | Moderate | Yellow |
| 6-7 | High | Orange |
| 8-10 | Very High | Red |
| 11+ | Extreme | Purple |

**Wind Speed Colors:**
| Range | Label | Color |
|-------|-------|-------|
| 0-10 mph | Calm | Gray |
| 10-20 mph | Breezy | Light blue |
| 20-30 mph | Windy | Yellow |
| 30+ mph | Strong | Orange/Red |

**Humidity Colors:**
| Range | Label | Color |
|-------|-------|-------|
| 0-30% | Dry | Orange |
| 30-60% | Comfortable | Green |
| 60-80% | Humid | Light blue |
| 80-100% | Very humid | Blue |

### Theme JSON Structure

```json
{
  "name": "Dark",
  "background": "#1a1a2e",
  "clock": {
    "color": "#ffffff",
    "font_size": 72
  },
  "weather": {
    "label_color": "#888888",
    "use_dynamic_colors": true,
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
```

---

## Web Control Panel (Flask)

Accessible at `http://<pi-ip>:5000`

### Settings Page
- Weather API key input
- Weather location (city or coordinates)
- Timezone selector
- 12/24 hour format toggle
- Theme selector dropdown

### Theme Editor
- Color pickers for all theme colors
- Live preview
- Save as new theme / overwrite existing
- Import/export theme JSON
- Toggle dynamic weather colors on/off

### Audio Settings
- **Sound output device selector**
  - List available audio outputs (HDMI, headphone jack, Bluetooth speakers)
  - Select active output device
  - Test audio button
- Volume control slider

### Bluetooth Settings
- Scan for devices
- Pair/Connect to speakers
- Show connected device
- Disconnect button
- Auto-reconnect toggle

### Log Tab
View system activity and debug information:

**API Request Log:**
- Weather API calls (timestamp, status, response time)
- YouTube URL fetches

**User Action Log:**
- Theme changes
- Settings updates
- YouTube play/stop commands
- Bluetooth connect/disconnect
- Audio device changes

**Display:**
```
┌─────────────────────────────────────────────────────────┐
│  Logs                            [Clear] [Export]       │
├─────────────────────────────────────────────────────────┤
│  Filter: [All ▼]  [API] [Actions] [Errors]             │
├─────────────────────────────────────────────────────────┤
│  14:32:05  API      Weather fetch OK (234ms)           │
│  14:31:42  Action   Theme changed to "Dark"            │
│  14:30:15  Action   YouTube play: dQw4w9WgXcQ          │
│  14:02:11  API      Weather fetch OK (198ms)           │
│  14:00:00  Info     Service started                    │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- Real-time log updates (WebSocket or polling)
- Filter by log type
- Clear logs button
- Export logs to file
- Auto-scroll with pause on hover
- Timestamp + category + message format

---

## Background Services (Threads)

### Weather Thread
See [PLANNING_WEATHER.md](PLANNING_WEATHER.md) for details.
- Runs in dedicated thread
- Fetches API on interval (configurable)
- Updates shared state with lock
- Pushes to weather_queue for display notification
- Handles errors without crashing main thread

### Flask Thread
- Runs Flask in separate thread (`threaded=True`)
- Handles all web UI requests
- Pushes commands to command_queue
- Reads from shared state for status endpoints
- WebSocket for real-time log streaming

### Bluetooth Thread
- Monitors Bluetooth connection status
- Polls every 5 seconds
- Auto-reconnects if configured
- Updates shared state with connection status
- Pushes status changes to log_queue

### Audio Thread
- Enumerates available audio devices via PulseAudio/ALSA
- Sets default audio sink on demand
- Routes mpv audio to selected device
- Runs on-demand (not continuously polling)

### Network Service (in Main Thread)
- Detects current IP address
- Updates display when IP changes
- Handles multiple interfaces (WiFi, Ethernet)
- Checked periodically in main loop

### Config Watcher Thread
- Uses `watchdog` library to monitor settings.json
- Hot-reloads configuration without restart
- Pushes changes to config_queue
- Main thread applies changes on next frame

### Log Thread
- Aggregates log entries from all threads via log_queue
- Writes to rotating log file
- Maintains in-memory buffer for web UI
- Thread-safe log collection

---

## Configuration File

`config/settings.json`:

```json
{
  "display": {
    "width": 800,
    "height": 480,
    "fullscreen": true,
    "fps": 30
  },
  "clock": {
    "format_24h": true,
    "show_seconds": true,
    "timezone": "America/New_York"
  },
  "weather": {
    "api_key": "YOUR_API_KEY",
    "provider": "openweathermap",
    "location": "New York,US",
    "lat": 40.7128,
    "lon": -74.0060,
    "units": "imperial",
    "update_interval_minutes": 30
  },
  "theme": "default",
  "audio": {
    "output_device": "default",
    "volume": 80
  },
  "bluetooth": {
    "speaker_mac": "",
    "auto_connect": true
  },
  "web": {
    "port": 5000,
    "host": "0.0.0.0"
  }
}
```

---

## Dependencies

`requirements.txt`:

```
pygame>=2.5.0
flask>=3.0.0
yt-dlp>=2024.1.0
python-mpv>=1.0.0
requests>=2.31.0
pytz>=2024.1
pulsectl>=23.5.0
netifaces>=0.11.0
watchdog>=3.0.0
flask-socketio>=5.3.0
```

---

## Raspberry Pi Setup

See [PI_SETUP.md](PI_SETUP.md) for detailed Raspberry Pi installation and configuration instructions.

---

## Development Phases

### Phase 1: Core Display & Threading
- [ ] Set up PyGame window
- [ ] Implement clock widget
- [ ] Theme system with JSON loading
- [ ] Dynamic color functions (temp→color, uv→color, etc.)
- [ ] Configuration loading
- [ ] Status bar with IP address
- [ ] Status bar with last API update time
- [ ] Thread-safe shared state class
- [ ] Queue-based inter-thread communication
- [ ] Graceful shutdown handling

### Phase 2: Weather Integration
See [PLANNING_WEATHER.md](PLANNING_WEATHER.md)

### Phase 3: Web Control Panel
- [ ] Flask server setup
- [ ] Settings page (weather, timezone, clock format)
- [ ] Theme selector and editor
- [ ] Audio device selector
- [ ] Bluetooth pairing UI
- [ ] Real-time config updates
- [ ] Log tab with filtering
- [ ] Log export functionality

### Phase 4: YouTube Player
See [PLANNING_YOUTUBE.md](PLANNING_YOUTUBE.md)

### Phase 5: Audio & Bluetooth
- [ ] Audio device enumeration
- [ ] Audio output switching via PulseAudio
- [ ] Bluetooth service
- [ ] Web UI for pairing
- [ ] Auto-reconnect

### Phase 6: Themes & Polish
- [ ] Create default themes (Dark, Light, Neon, Minimal)
- [ ] Web UI theme editor with color pickers
- [ ] Theme import/export
- [ ] Error handling
- [ ] Installation script
- [ ] Documentation

---

## Notes

- **Performance:** PyGame should run smoothly at 30 FPS for clock updates
- **Memory:** Expect ~150-200MB RAM usage, leaving headroom on the 1GB Pi 3B
- **Network:** Web UI only accessible on local network by default
- **Audio:** PulseAudio handles routing to Bluetooth/HDMI/analog seamlessly
