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

See [PLANNING_MAIN.md](PLANNING_MAIN.md) for detailed setup instructions.

## Documentation

- [PLANNING_MAIN.md](PLANNING_MAIN.md) - Core architecture, setup, and configuration
- [PLANNING_WEATHER.md](PLANNING_WEATHER.md) - Weather module details
- [PLANNING_YOUTUBE.md](PLANNING_YOUTUBE.md) - YouTube playback details

## Tech Stack

- **Display:** Python + PyGame
- **Web UI:** Flask + Flask-SocketIO
- **Video:** mpv + yt-dlp
- **Weather:** OpenWeatherMap One Call API 3.0

## License

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute this software, either in source code form or as a compiled binary, for any purpose, commercial or non-commercial, and by any means.

In jurisdictions that recognize copyright laws, the author or authors of this software dedicate any and all copyright interest in the software to the public domain. We make this dedication for the benefit of the public at large and to the detriment of our heirs and successors. We intend this dedication to be an overt act of relinquishment in perpetuity of all present and future rights to this software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org>
