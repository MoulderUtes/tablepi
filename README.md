# TablePi

A Raspberry Pi-powered tabletop display featuring a clock, weather information, and YouTube playback with a web-based control panel.

> **Note:** This project was developed with the assistance of AI (Claude by Anthropic).

## Features

- **Clock Display** - Large digital clock with seconds, configurable 12/24 hour format
- **Weather Dashboard** - Current conditions, 7-day forecast graph, hourly details (tap to drill down)
- **YouTube Playback** - Play videos via web UI with touch-friendly on-screen controls
- **Web Control Panel** - Configure settings, themes, audio, and Bluetooth from any device on your network
- **Dynamic Theming** - Multiple themes with weather-reactive colors (hot = red, cold = blue, etc.)
- **Bluetooth Audio** - Connect to Bluetooth speakers with auto-reconnect
- **Activity Logging** - View API requests and user actions in the web UI

## Hardware Requirements

- Raspberry Pi 3B (or newer)
- 7" touchscreen display (480p)
- MicroSD card (16GB+)
- Power supply (2.5A recommended)
- Optional: Bluetooth speaker

## Quick Start

1. Flash Raspberry Pi OS Lite (64-bit) to your SD card
2. Clone this repository to `/home/pi/tablepi`
3. Run `./install.sh`
4. Access the web UI at `http://tablepi.local:5000`

See [PI_SETUP.md](PI_SETUP.md) for detailed Raspberry Pi setup instructions.

## Documentation

- [PI_SETUP.md](PI_SETUP.md) - Raspberry Pi installation and setup guide
- [PLANNING_MAIN.md](PLANNING_MAIN.md) - Core architecture and configuration
- [PLANNING_WEATHER.md](PLANNING_WEATHER.md) - Weather module details
- [PLANNING_YOUTUBE.md](PLANNING_YOUTUBE.md) - YouTube playback details

## Tech Stack

- **Display:** Python + PyGame
- **Web UI:** Flask + Flask-SocketIO
- **Video:** mpv + yt-dlp
- **Weather:** OpenWeatherMap One Call API 3.0

## Changelog

### v0.1.0 (Initial Release)
- Clock display with configurable 12/24h format and timezone
- Weather widget with current conditions display
- 7-day forecast graph (touch to view details)
- Dynamic weather-based colors (temp, humidity, UV, wind, rain)
- Web control panel with settings, themes, YouTube, audio, Bluetooth tabs
- Theme system with 5 built-in themes (Dark, Light, Neon, Minimal, Default)
- Theme editor in web UI
- Activity logging with filtering and export
- Multi-threaded architecture for responsive UI
- Config hot-reload via file watcher

### Planned
- Full YouTube playback via mpv
- Hourly forecast detail view
- Bluetooth device scanning and pairing
- Audio device enumeration and switching

## License

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute this software, either in source code form or as a compiled binary, for any purpose, commercial or non-commercial, and by any means.

In jurisdictions that recognize copyright laws, the author or authors of this software dedicate any and all copyright interest in the software to the public domain. We make this dedication for the benefit of the public at large and to the detriment of our heirs and successors. We intend this dedication to be an overt act of relinquishment in perpetuity of all present and future rights to this software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org>
