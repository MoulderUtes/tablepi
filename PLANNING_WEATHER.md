# TablePi - Weather Module Planning

## Overview

Full weather display using OpenWeatherMap One Call API 3.0, featuring:
- Current conditions with dynamic colored values
- 7-day forecast graph with touch interaction
- Hourly detail view for selected days

---

## API: OpenWeatherMap One Call 3.0

**Endpoint:** `https://api.openweathermap.org/data/3.0/onecall`

**Required Parameters:**
- `lat`, `lon` - Location coordinates
- `appid` - API key
- `units` - `imperial` or `metric`

**Response includes:**
- `current` - Current weather
- `hourly` - 48-hour forecast
- `daily` - 8-day forecast
- Moon phase data in daily

**Free Tier:** 1,000 calls/day (plenty for 15-30 min updates)

**Sign up:** https://openweathermap.org/api/one-call-3

---

## Main Display - Current Weather Section

```
┌─────────────────────────────────────────────────────────┐
│  ☀️ 72°F  Feels like 75°F                               │
│  Humidity: 45%  Wind: 8 mph NW                          │
│  Rain: 10%  UV: 6                                       │
│  ☀ 6:32 AM  ☽ 8:15 PM  🌙 Waxing Gibbous               │
└─────────────────────────────────────────────────────────┘
```

### Data Displayed

| Field | Source | Dynamic Color |
|-------|--------|---------------|
| Current temp | `current.temp` | Yes - temp scale |
| Feels like | `current.feels_like` | Yes - temp scale |
| Weather icon | `current.weather[0].icon` | N/A |
| Humidity | `current.humidity` | Yes - humidity scale |
| Wind speed | `current.wind_speed` | Yes - wind scale |
| Wind direction | `current.wind_deg` | No |
| Rain chance | `daily[0].pop` * 100 | Yes - precipitation scale |
| UV index | `current.uvi` | Yes - UV scale |
| Sunrise | `current.sunrise` | No |
| Sunset | `current.sunset` | No |
| Moon phase | `daily[0].moon_phase` | No |

### Moon Phase Display

| Value Range | Phase Name | Icon |
|-------------|------------|------|
| 0 or 1 | New Moon | 🌑 |
| 0.01-0.24 | Waxing Crescent | 🌒 |
| 0.25 | First Quarter | 🌓 |
| 0.26-0.49 | Waxing Gibbous | 🌔 |
| 0.5 | Full Moon | 🌕 |
| 0.51-0.74 | Waning Gibbous | 🌖 |
| 0.75 | Last Quarter | 🌗 |
| 0.76-0.99 | Waning Crescent | 🌘 |

### Weather Condition Icons

Map OpenWeatherMap icon codes to display icons:

| Code | Condition | Icon |
|------|-----------|------|
| 01d/01n | Clear | ☀️/🌙 |
| 02d/02n | Few clouds | ⛅/☁️ |
| 03d/03n | Scattered clouds | ☁️ |
| 04d/04n | Broken clouds | ☁️ |
| 09d/09n | Shower rain | 🌧️ |
| 10d/10n | Rain | 🌧️ |
| 11d/11n | Thunderstorm | ⛈️ |
| 13d/13n | Snow | ❄️ |
| 50d/50n | Mist | 🌫️ |

---

## 7-Day Forecast Graph

```
┌─────────────────────────────────────────────────────────┐
│  7-Day Forecast                                         │
│                                                         │
│  80°─        ╭─╮                                        │
│  70°─    ╭──╯   ╰──╮         ← Highs line (red/orange) │
│  60°─╭──╯           ╰──╮                                │
│  50°─╰─╮         ╭──╯  ╰─   ← Lows line (blue/teal)    │
│  40°─   ╰───────╯                                       │
│     Mon Tue Wed Thu Fri Sat Sun                         │
│      ▲                                                  │
│   [Tap a day to see hourly details]                     │
└─────────────────────────────────────────────────────────┘
```

### Graph Specifications

- **X-axis:** 7 days (today + 6 days), labeled with day abbreviation
- **Y-axis:** Temperature scale, auto-scaled to data range with padding
- **High line:** Connects daily high temps, colored from theme `graph.high_line`
- **Low line:** Connects daily low temps, colored from theme `graph.low_line`
- **Data points:** Small circles at each day's high/low
- **Grid:** Horizontal lines at major temp intervals

### Touch Interaction

- Each day is a touch target (vertical column)
- Touch target width: ~100px (800px / 7 days ≈ 114px each)
- Highlight touched day briefly
- Transition to hourly detail view

### Data Source

```python
for day in response['daily'][:7]:
    date = datetime.fromtimestamp(day['dt'])
    high = day['temp']['max']
    low = day['temp']['min']
    icon = day['weather'][0]['icon']
    pop = day['pop']  # Probability of precipitation
```

---

## Hourly Detail View

Shown when user taps a day on the graph.

```
┌─────────────────────────────────────────────────────────┐
│  ← Back                Wednesday, Jan 22                │
├─────────────────────────────────────────────────────────┤
│  High: 75°F  Low: 52°F  Rain: 30%                       │
│  Sunrise: 6:32 AM  Sunset: 5:45 PM                      │
├─────────────────────────────────────────────────────────┤
│  Hourly Forecast:                                       │
│                                                         │
│  6AM   8AM   10AM  12PM  2PM   4PM   6PM   8PM         │
│  48°   52°   61°   68°   73°   75°   70°   62°         │
│  ☁️    ⛅    ☀️    ☀️    ⛅    🌧️    ☁️    ☁️          │
│  0%    0%    5%    10%   20%   40%   30%   15%         │
│                                                         │
│  Wind: 5-12 mph NW                                      │
│  Humidity: 45-65%                                       │
│  UV Index: 6 (High)                                     │
└─────────────────────────────────────────────────────────┘
```

### Layout Sections

**Header:**
- Back button (touch target ~60x40px)
- Day and date

**Daily Summary:**
- High/Low temps (dynamic colors)
- Overall rain chance
- Sunrise/sunset for that day

**Hourly Grid:**
- Show 8 time slots (every 2 hours, or every 3 hours to fit)
- For each slot:
  - Time label
  - Temperature (dynamic color)
  - Weather icon
  - Rain percentage (dynamic color)

**Daily Ranges:**
- Wind speed range for the day
- Humidity range
- Max UV index with label

### Data Source

```python
# For today: use hourly[0:24]
# For future days: hourly data may not be available
# OpenWeatherMap provides 48 hours of hourly data

# Get hourly data for selected day
day_start = selected_date.replace(hour=0, minute=0)
day_end = day_start + timedelta(days=1)

hourly_data = [
    h for h in response['hourly']
    if day_start <= datetime.fromtimestamp(h['dt']) < day_end
]
```

**Note:** Hourly data is only available for ~48 hours. Days beyond that will show:
- Daily high/low/summary only
- Message: "Hourly forecast not available for this day"

### Touch Interactions

- **Back button:** Return to main display
- **Swipe right:** Return to main display
- Auto-return after 30 seconds of inactivity

---

## Weather Service (Thread)

Background thread that fetches and caches weather data without blocking the main display.

### Threading Architecture

```python
from threading import Thread, Event
from queue import Queue
import time

class WeatherService(Thread):
    def __init__(self, shared_state, queues, shutdown_event):
        super().__init__(daemon=True)
        self.state = shared_state
        self.weather_queue = queues['weather']
        self.log_queue = queues['log']
        self.shutdown = shutdown_event
        self.config = shared_state.get_config()

    def run(self):
        # Initial fetch on startup
        self._fetch_weather()

        # Poll at configured interval
        interval = self.config['weather']['update_interval_minutes'] * 60

        while not self.shutdown.is_set():
            # Wait for interval or shutdown
            self.shutdown.wait(timeout=interval)

            if not self.shutdown.is_set():
                self._fetch_weather()

    def _fetch_weather(self):
        try:
            start_time = time.time()
            data = self._call_api()
            elapsed = (time.time() - start_time) * 1000

            # Update shared state (thread-safe)
            self.state.update_weather(data)

            # Notify main thread via queue
            self.weather_queue.put({'type': 'update', 'data': data})

            # Log success
            self.log_queue.put({
                'type': 'API',
                'message': f'Weather fetch OK ({elapsed:.0f}ms)'
            })

        except Exception as e:
            # Log error, don't crash thread
            self.log_queue.put({
                'type': 'Error',
                'message': f'Weather fetch failed: {str(e)}'
            })

    def _call_api(self):
        # Actual API call implementation
        ...
```

### Behavior

1. Fetch on startup (in thread, non-blocking)
2. Fetch every N minutes (configurable, default 30)
3. Cache response to file for offline/restart
4. Track last fetch timestamp
5. Update shared state with thread lock
6. Notify main thread via queue

### API Request Logging

All API requests logged with:
- Timestamp
- Request URL (API key masked)
- Response status code
- Response time (ms)
- Success/failure

Logs viewable in web UI log tab.

### Error Handling

| Scenario | Behavior |
|----------|----------|
| API key invalid | Show error on display, log error |
| Network error | Use cached data, show "offline" indicator |
| Rate limited | Use cached data, increase interval temporarily |
| Invalid location | Show error on display |

### Cache File

`cache/weather.json`:
```json
{
  "fetched_at": 1705950000,
  "expires_at": 1705951800,
  "data": { /* full API response */ }
}
```

---

### Main Thread Integration

The main PyGame thread reads weather data from shared state:

```python
# In main display loop
def update(self):
    # Check for weather updates (non-blocking)
    try:
        msg = self.weather_queue.get_nowait()
        if msg['type'] == 'update':
            self._refresh_weather_display()
    except queue.Empty:
        pass

    # Get current weather data (thread-safe read)
    weather_data, last_fetch = self.state.get_weather()

    # Update "last updated" display
    if last_fetch:
        elapsed = time.time() - last_fetch
        self._update_status_bar(elapsed)
```

---

## Development Tasks

### Phase 2: Weather Integration

- [ ] WeatherService thread class
- [ ] Thread-safe shared state for weather data
- [ ] Queue-based update notifications
- [ ] OpenWeatherMap One Call API 3.0 client
- [ ] API response parsing
- [ ] Weather data caching (file-based)
- [ ] Last fetch timestamp tracking
- [ ] Current conditions display
  - [ ] Temperature with dynamic color
  - [ ] Feels like with dynamic color
  - [ ] Humidity with dynamic color
  - [ ] Wind speed/direction with dynamic color
  - [ ] Rain chance with dynamic color
  - [ ] UV index with dynamic color
  - [ ] Sunrise/sunset times
  - [ ] Moon phase with icon
  - [ ] Weather condition icon
- [ ] 7-day forecast graph
  - [ ] Auto-scaling Y-axis
  - [ ] High/low line rendering
  - [ ] Day labels on X-axis
  - [ ] Touch target areas per day
- [ ] Hourly detail view
  - [ ] Back button
  - [ ] Daily summary section
  - [ ] Hourly grid (time, temp, icon, rain%)
  - [ ] Daily ranges (wind, humidity, UV)
  - [ ] Handle days without hourly data
- [ ] Error states and offline mode
- [ ] API request logging

---

## Configuration

In `settings.json`:

```json
{
  "weather": {
    "api_key": "YOUR_API_KEY",
    "provider": "openweathermap",
    "location": "New York,US",
    "lat": 40.7128,
    "lon": -74.0060,
    "units": "imperial",
    "update_interval_minutes": 30
  }
}
```

**Note:** `lat` and `lon` are required for One Call API 3.0. The web UI should allow entering a city name and use OpenWeatherMap's geocoding API to convert to coordinates.
