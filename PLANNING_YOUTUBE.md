# TablePi - YouTube Module Planning

## Overview

YouTube video playback using mpv + yt-dlp with touch-friendly on-screen controls.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  Web UI                           │
│  [Enter YouTube URL] [Play]                       │
└──────────────────┬───────────────────────────────┘
                   │ HTTP POST /api/youtube/play
                   ▼
┌──────────────────────────────────────────────────┐
│              Flask Server                         │
│  - Validates URL                                  │
│  - Sends command to display service              │
└──────────────────┬───────────────────────────────┘
                   │ IPC / shared state
                   ▼
┌──────────────────────────────────────────────────┐
│            Display Application                    │
│  1. Hide PyGame window                           │
│  2. Launch mpv with yt-dlp                       │
│  3. Wait for mpv to exit                         │
│  4. Restore PyGame window                        │
└──────────────────────────────────────────────────┘
```

---

## mpv + yt-dlp

### How It Works

1. **yt-dlp** extracts the direct video stream URL from YouTube
2. **mpv** plays the stream directly (no download to disk)
3. Streams in real-time from YouTube's servers

### Benefits

- No storage space used
- Fast startup (no waiting for download)
- Works with live streams
- Low memory footprint

---

## mpv Configuration for Touch

### Command Line Flags

```bash
mpv \
  --fullscreen \
  --osc=yes \
  --script-opts=osc-layout=bottombar,osc-scalewindowed=2,osc-scalefullscreen=2 \
  --ytdl-format="bestvideo[height<=480]+bestaudio/best[height<=480]" \
  --audio-device="pulse/DEVICE_NAME" \
  --input-ipc-server=/tmp/mpv-socket \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Flag Explanations

| Flag | Purpose |
|------|---------|
| `--fullscreen` | Launch in fullscreen mode |
| `--osc=yes` | Enable on-screen controller |
| `--script-opts=osc-layout=bottombar` | Put controls at bottom |
| `--script-opts=osc-scalewindowed=2` | 2x scale for touch targets |
| `--script-opts=osc-scalefullscreen=2` | 2x scale in fullscreen |
| `--ytdl-format="..."` | Limit to 480p for Pi 3B performance |
| `--audio-device="pulse/..."` | Route to selected audio output |
| `--input-ipc-server=/tmp/mpv-socket` | Enable IPC for remote control |

### On-Screen Controller (OSC)

mpv's built-in OSC provides touch-friendly controls:

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│                                                         │
│                    VIDEO CONTENT                        │
│                                                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│   advancement          00:00:00                          │
│  [◄◄] [▶/❚❚] [►►]  ──●────────────────  [🔊] [✕]       │
│              seek bar              volume  close         │
└─────────────────────────────────────────────────────────┘
```

**OSC Controls:**
- Play/Pause toggle
- Seek backward/forward buttons
- Seek bar (drag to position)
- Volume control
- Fullscreen toggle
- Close button (exits mpv)

The `osc-scale*=2` options make these buttons larger for the 7" touchscreen.

---

## Playback Flow

### Threading Model

YouTube playback uses a subprocess (mpv) managed from the main thread, with commands coming from the Flask thread via queue.

```
┌─────────────────┐         ┌─────────────────┐
│   Flask Thread  │         │   Main Thread   │
│                 │         │    (PyGame)     │
│  POST /youtube  │────────▶│                 │
│     /play       │ command │  command_queue  │
│                 │  queue  │       │         │
└─────────────────┘         │       ▼         │
                            │  ┌───────────┐  │
                            │  │  Process  │  │
                            │  │  mpv      │  │
                            │  │  subprocess│ │
                            │  └───────────┘  │
                            │       │         │
                            │       ▼         │
                            │  IPC socket     │
                            │  /tmp/mpv-socket│
                            └─────────────────┘
```

### Starting Video

1. User enters YouTube URL in web UI
2. Flask thread receives POST to `/api/youtube/play`
3. Flask validates URL format
4. Flask pushes command to `command_queue`:
   ```python
   command_queue.put({
       'type': 'youtube_play',
       'url': url,
       'video_id': video_id
   })
   ```
5. Main thread picks up command (non-blocking check each frame)
6. Main thread:
   - Saves current state
   - Hides PyGame window
   - Spawns mpv subprocess with URL
   - Logs playback start via `log_queue`
7. mpv plays video with touch OSC

### During Playback

```python
# Main thread monitors mpv process
class YouTubePlayer:
    def __init__(self, queues):
        self.command_queue = queues['command']
        self.log_queue = queues['log']
        self.mpv_process = None
        self.ipc_socket = None

    def update(self):
        # Check for commands from web UI
        try:
            cmd = self.command_queue.get_nowait()
            self._handle_command(cmd)
        except queue.Empty:
            pass

        # Check if mpv still running
        if self.mpv_process and self.mpv_process.poll() is not None:
            self._on_playback_ended()

    def _handle_command(self, cmd):
        if cmd['type'] == 'youtube_play':
            self._start_playback(cmd['url'])
        elif cmd['type'] == 'youtube_pause':
            self._send_mpv_command(['set_property', 'pause', True])
        elif cmd['type'] == 'youtube_resume':
            self._send_mpv_command(['set_property', 'pause', False])
        elif cmd['type'] == 'youtube_stop':
            self._send_mpv_command(['quit'])
```

- User controls via mpv's on-screen touch controls
- Web UI can send commands via Flask → command_queue → Main thread → IPC socket:
  - Pause/resume
  - Volume adjustment
  - Stop playback

### Ending Video

When mpv exits (user closes or video ends):

1. Main thread detects `mpv_process.poll() is not None`
2. Cleans up IPC socket
3. Restores PyGame window
4. Resumes clock/weather display
5. Logs playback end via `log_queue`

---

## Web UI - YouTube Section

```
┌─────────────────────────────────────────────────────────┐
│  YouTube Player                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  URL: [https://youtube.com/watch?v=...        ] [Play]  │
│                                                         │
│  Status: Idle / Playing / Error                         │
│                                                         │
│  ─────────────────────────────────────────────────────  │
│                                                         │
│  Remote Controls (while playing):                       │
│  [⏸ Pause] [▶ Resume] [⏹ Stop] [🔊 Vol +] [🔉 Vol -]   │
│                                                         │
│  Now Playing: Video Title Here                          │
│  Duration: 3:45 / 10:23                                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Features

- URL input field with validation
- Play button to start playback
- Status indicator (Idle, Playing, Loading, Error)
- Remote controls (optional, for controlling from phone while video plays)
- Currently playing info (title, duration)

---

## API Endpoints

### POST /api/youtube/play

Start playing a YouTube video.

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Playback started",
  "video_id": "dQw4w9WgXcQ"
}
```

**Errors:**
```json
{
  "success": false,
  "error": "Invalid YouTube URL"
}
```

### POST /api/youtube/control

Send control command to mpv.

**Request:**
```json
{
  "command": "pause"  // pause, resume, stop, volume_up, volume_down
}
```

**Response:**
```json
{
  "success": true
}
```

### GET /api/youtube/status

Get current playback status.

**Response:**
```json
{
  "playing": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "position": 125.5,
  "duration": 623.0,
  "volume": 80,
  "paused": false
}
```

---

## IPC Communication with mpv

mpv can be controlled via JSON IPC over a Unix socket.

### Setup

```bash
mpv --input-ipc-server=/tmp/mpv-socket ...
```

### Python Client

```python
import socket
import json

def send_mpv_command(command):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect('/tmp/mpv-socket')

    msg = json.dumps({"command": command}) + "\n"
    sock.send(msg.encode())

    response = sock.recv(1024).decode()
    sock.close()
    return json.loads(response)

# Examples
send_mpv_command(["set_property", "pause", True])   # Pause
send_mpv_command(["set_property", "pause", False])  # Resume
send_mpv_command(["quit"])                          # Stop
send_mpv_command(["add", "volume", 5])              # Volume +5
send_mpv_command(["add", "volume", -5])             # Volume -5
send_mpv_command(["get_property", "time-pos"])      # Get position
send_mpv_command(["get_property", "duration"])      # Get duration
```

---

## Audio Routing

Video audio should play through the user-selected audio device.

### Getting Selected Device

```python
# From config
audio_device = config['audio']['output_device']

# Pass to mpv
mpv_args.append(f'--audio-device=pulse/{audio_device}')
```

### If Bluetooth Speaker

If user has selected a Bluetooth speaker:
1. Ensure speaker is connected before playback
2. Route audio to Bluetooth sink via PulseAudio
3. Handle disconnection gracefully (fallback to default)

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid URL | Show error in web UI, don't start mpv |
| yt-dlp fails | Show error, log details, return to clock |
| Video unavailable | Show error message, return to clock |
| Network error during playback | mpv shows error, exits, return to clock |
| mpv crashes | Detect exit, log error, return to clock |
| Audio device unavailable | Fallback to default device |

---

## Logging

All YouTube actions logged:

| Event | Logged Data |
|-------|-------------|
| Play request | Timestamp, URL, video ID |
| Playback start | Timestamp, video title, duration |
| Control command | Timestamp, command type |
| Playback end | Timestamp, reason (completed/stopped/error) |
| Error | Timestamp, error type, details |

Logs viewable in web UI log tab.

---

## Development Tasks

### Phase 4: YouTube Player

- [ ] YouTubePlayer class with queue integration
  - [ ] Non-blocking command processing
  - [ ] Process monitoring in main loop
- [ ] mpv subprocess wrapper
  - [ ] Build command with all flags
  - [ ] Handle audio device routing
  - [ ] Process lifecycle management
- [ ] IPC client for mpv control
  - [ ] Pause/resume
  - [ ] Stop
  - [ ] Volume control
  - [ ] Status queries
- [ ] Thread-safe command handling
  - [ ] Flask → command_queue → Main thread
  - [ ] Status updates via shared state
- [ ] PyGame window management
  - [ ] Hide before mpv launch
  - [ ] Restore after mpv exit
  - [ ] Handle edge cases (crash recovery)
- [ ] Web UI YouTube section
  - [ ] URL input with validation
  - [ ] Play button
  - [ ] Status display
  - [ ] Remote controls (pause, stop, volume)
  - [ ] Now playing info
- [ ] API endpoints
  - [ ] POST /api/youtube/play (pushes to command_queue)
  - [ ] POST /api/youtube/control (pushes to command_queue)
  - [ ] GET /api/youtube/status (reads shared state)
- [ ] Logging via log_queue
  - [ ] Log all playback events
  - [ ] Log errors with details
- [ ] Error handling
  - [ ] Invalid URLs
  - [ ] Network errors
  - [ ] yt-dlp failures
  - [ ] mpv crashes

---

## Configuration

In `settings.json`:

```json
{
  "youtube": {
    "max_resolution": 480,
    "default_volume": 80
  },
  "audio": {
    "output_device": "default",
    "volume": 80
  }
}
```

---

## Dependencies

Ensure installed on Pi:

```bash
# mpv video player
sudo apt install -y mpv

# yt-dlp (in Python venv)
pip install yt-dlp

# Keep yt-dlp updated (YouTube changes frequently)
pip install --upgrade yt-dlp
```

**Note:** yt-dlp needs periodic updates as YouTube changes their site. Consider adding an "Update yt-dlp" button in web UI settings.
