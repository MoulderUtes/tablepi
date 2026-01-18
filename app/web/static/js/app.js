// TablePi Control Panel JavaScript

// WebSocket connection
let socket = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSocket();
    loadSettings();
    loadThemes();
    loadLogs();
    loadWeatherStatus();
    loadAudioDevices();
    loadDimmingSettings();
    initEventListeners();

    // Periodically update weather status
    setInterval(loadWeatherStatus, 30000);
});

// Sidebar Navigation
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const contents = document.querySelectorAll('.tab-content');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.dataset.tab;

            navItems.forEach(n => n.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            item.classList.add('active');
            document.getElementById(targetId).classList.add('active');
        });
    });
}

// WebSocket
function initSocket() {
    socket = io();

    socket.on('connect', () => {
        const badge = document.getElementById('connection-status');
        badge.innerHTML = '<i class="fas fa-circle"></i><span>Connected</span>';
        badge.classList.add('connected');
    });

    socket.on('disconnect', () => {
        const badge = document.getElementById('connection-status');
        badge.innerHTML = '<i class="fas fa-circle"></i><span>Disconnected</span>';
        badge.classList.remove('connected');
    });

    socket.on('log', (data) => {
        addLogEntry(data);
    });
}

// Settings
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();

        // Populate form
        document.getElementById('weather-api-key').value = settings.weather?.api_key || '';
        document.getElementById('weather-lat').value = settings.weather?.lat || '';
        document.getElementById('weather-lon').value = settings.weather?.lon || '';
        document.getElementById('timezone').value = settings.clock?.timezone || 'America/New_York';
        document.getElementById('units').value = settings.weather?.units || 'imperial';
        document.getElementById('clock-format').value = settings.clock?.format_24h ? '24' : '12';
        document.getElementById('update-interval').value = settings.weather?.update_interval_minutes || 30;

        // Audio
        document.getElementById('audio-volume').value = settings.audio?.volume || 80;
        document.getElementById('volume-value').textContent = (settings.audio?.volume || 80) + '%';

        // Bluetooth
        document.getElementById('bt-auto-connect').checked = settings.bluetooth?.auto_connect !== false;

    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

// Weather Status
async function loadWeatherStatus() {
    try {
        const response = await fetch('/api/weather/status');
        const data = await response.json();

        const statusText = document.getElementById('weather-status-text');
        const lastUpdate = document.getElementById('weather-last-update');
        const statusIcon = document.getElementById('weather-status-icon');

        // Update status text and styling
        statusText.textContent = data.status_text;
        statusText.className = 'status-value';

        if (statusIcon) {
            statusIcon.className = 'status-icon';
        }

        if (data.status === 'ok') {
            statusText.classList.add('status-ok');
            if (statusIcon) {
                statusIcon.classList.add('status-ok');
                statusIcon.innerHTML = '<i class="fas fa-check-circle"></i>';
            }
        } else if (data.status === 'error') {
            statusText.classList.add('status-error');
            if (statusIcon) {
                statusIcon.classList.add('status-error');
                statusIcon.innerHTML = '<i class="fas fa-exclamation-circle"></i>';
            }
        } else {
            statusText.classList.add('status-loading');
            if (statusIcon) {
                statusIcon.innerHTML = '<i class="fas fa-circle-question"></i>';
            }
        }

        // Update last fetch time
        if (data.last_fetch) {
            const fetchTime = new Date(data.last_fetch * 1000);
            const now = new Date();
            const diffMs = now - fetchTime;
            const diffMins = Math.floor(diffMs / 60000);

            if (diffMins < 1) {
                lastUpdate.textContent = 'Just now';
            } else if (diffMins < 60) {
                lastUpdate.textContent = `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
            } else {
                const diffHours = Math.floor(diffMins / 60);
                lastUpdate.textContent = `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
            }
        } else {
            lastUpdate.textContent = 'Never';
        }

        // Enable/disable refresh button based on API key
        const refreshBtn = document.getElementById('refresh-weather');
        if (refreshBtn) {
            refreshBtn.disabled = !data.has_api_key;
        }

    } catch (error) {
        console.error('Failed to load weather status:', error);
    }
}

async function refreshWeather() {
    const refreshBtn = document.getElementById('refresh-weather');
    const statusText = document.getElementById('weather-status-text');
    const originalContent = refreshBtn.innerHTML;

    // Update UI to show loading
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
    statusText.textContent = 'Refreshing...';
    statusText.className = 'status-value status-loading';

    try {
        const response = await fetch('/api/weather/refresh', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            // Wait a moment for the refresh to complete, then reload status
            setTimeout(() => {
                loadWeatherStatus();
                refreshBtn.innerHTML = originalContent;
                refreshBtn.disabled = false;
            }, 2000);
        } else {
            statusText.textContent = data.error || 'Refresh failed';
            statusText.className = 'status-value status-error';
            refreshBtn.innerHTML = originalContent;
            refreshBtn.disabled = false;
        }
    } catch (error) {
        console.error('Failed to refresh weather:', error);
        statusText.textContent = 'Refresh failed';
        statusText.className = 'status-value status-error';
        refreshBtn.innerHTML = originalContent;
        refreshBtn.disabled = false;
    }
}

async function saveSettings() {
    const saveBtn = document.getElementById('save-settings');
    const originalContent = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    saveBtn.disabled = true;

    const settings = {
        weather: {
            api_key: document.getElementById('weather-api-key').value,
            lat: parseFloat(document.getElementById('weather-lat').value) || 0,
            lon: parseFloat(document.getElementById('weather-lon').value) || 0,
            units: document.getElementById('units').value,
            update_interval_minutes: parseInt(document.getElementById('update-interval').value) || 30
        },
        clock: {
            timezone: document.getElementById('timezone').value,
            format_24h: document.getElementById('clock-format').value === '24'
        },
        bluetooth: {
            auto_connect: document.getElementById('bt-auto-connect').checked
        }
    };

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Saved!';
            setTimeout(() => {
                saveBtn.innerHTML = originalContent;
                saveBtn.disabled = false;
            }, 2000);
        } else {
            saveBtn.innerHTML = '<i class="fas fa-times"></i> Failed';
            setTimeout(() => {
                saveBtn.innerHTML = originalContent;
                saveBtn.disabled = false;
            }, 2000);
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
        saveBtn.innerHTML = '<i class="fas fa-times"></i> Failed';
        setTimeout(() => {
            saveBtn.innerHTML = originalContent;
            saveBtn.disabled = false;
        }, 2000);
    }
}

// Themes
async function loadThemes() {
    try {
        const response = await fetch('/api/themes');
        const data = await response.json();

        const select = document.getElementById('theme-select');
        select.innerHTML = '';

        data.themes.forEach(theme => {
            const option = document.createElement('option');
            option.value = theme;
            option.textContent = theme.charAt(0).toUpperCase() + theme.slice(1);
            if (theme === data.current) {
                option.selected = true;
            }
            select.appendChild(option);
        });

        // Load current theme colors
        loadThemeColors(data.current);

    } catch (error) {
        console.error('Failed to load themes:', error);
    }
}

async function loadThemeColors(themeName) {
    try {
        const response = await fetch(`/api/theme/${themeName}`);
        const theme = await response.json();

        const bgInput = document.getElementById('color-background');
        const clockInput = document.getElementById('color-clock');
        const highInput = document.getElementById('color-high-line');
        const lowInput = document.getElementById('color-low-line');
        const accentInput = document.getElementById('color-accent');

        bgInput.value = theme.background || '#1a1a2e';
        clockInput.value = theme.clock?.color || '#ffffff';
        highInput.value = theme.graph?.high_line || '#ff6b6b';
        lowInput.value = theme.graph?.low_line || '#4ecdc4';
        accentInput.value = theme.accents?.primary || '#e94560';
        document.getElementById('dynamic-colors').checked = theme.weather?.use_dynamic_colors !== false;

        // Update color value displays
        updateColorValue(bgInput);
        updateColorValue(clockInput);
        updateColorValue(highInput);
        updateColorValue(lowInput);
        updateColorValue(accentInput);

    } catch (error) {
        console.error('Failed to load theme colors:', error);
    }
}

function updateColorValue(input) {
    const valueSpan = input.nextElementSibling;
    if (valueSpan && valueSpan.classList.contains('color-value')) {
        valueSpan.textContent = input.value;
    }
}

async function applyTheme() {
    const themeName = document.getElementById('theme-select').value;
    const btn = document.getElementById('apply-theme');
    const originalContent = btn.innerHTML;

    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Applying...';
    btn.disabled = true;

    try {
        const response = await fetch(`/api/theme/select/${themeName}`, {
            method: 'POST'
        });

        if (response.ok) {
            btn.innerHTML = '<i class="fas fa-check"></i> Applied!';
            setTimeout(() => {
                btn.innerHTML = originalContent;
                btn.disabled = false;
            }, 2000);
        }
    } catch (error) {
        console.error('Failed to apply theme:', error);
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

async function saveTheme() {
    const themeName = document.getElementById('theme-select').value;
    await saveThemeAs(themeName);
}

async function saveThemeAs(name = null) {
    if (!name) {
        name = prompt('Enter theme name:');
        if (!name) return;
    }

    const theme = {
        name: name.charAt(0).toUpperCase() + name.slice(1),
        background: document.getElementById('color-background').value,
        clock: {
            color: document.getElementById('color-clock').value,
            font_size: 72
        },
        weather: {
            label_color: '#888888',
            use_dynamic_colors: document.getElementById('dynamic-colors').checked,
            static_value_color: '#ffffff'
        },
        graph: {
            background: '#16213e',
            high_line: document.getElementById('color-high-line').value,
            low_line: document.getElementById('color-low-line').value,
            grid_color: '#333333',
            label_color: '#888888'
        },
        status_bar: {
            background: '#0f0f1a',
            text_color: '#666666'
        },
        accents: {
            primary: document.getElementById('color-accent').value,
            secondary: '#0f3460'
        }
    };

    try {
        const response = await fetch(`/api/theme/${name.toLowerCase()}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(theme)
        });

        if (response.ok) {
            alert(`Theme "${name}" saved!`);
            loadThemes();
        }
    } catch (error) {
        console.error('Failed to save theme:', error);
    }
}

// YouTube
async function playYouTube() {
    const url = document.getElementById('youtube-url').value;
    const btn = document.getElementById('youtube-play');

    if (!url) {
        alert('Please enter a YouTube URL');
        return;
    }

    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    btn.disabled = true;

    try {
        const response = await fetch('/api/youtube/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById('yt-status-text').textContent = 'Playing';
            document.getElementById('youtube-controls').style.display = 'block';
        } else {
            alert(data.error || 'Failed to play video');
        }
    } catch (error) {
        console.error('Failed to play YouTube:', error);
        alert('Failed to play video');
    }

    btn.innerHTML = originalContent;
    btn.disabled = false;
}

async function youtubeControl(command) {
    try {
        await fetch('/api/youtube/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });

        // Update status based on command
        const statusText = document.getElementById('yt-status-text');
        if (command === 'pause') statusText.textContent = 'Paused';
        else if (command === 'resume') statusText.textContent = 'Playing';
        else if (command === 'stop') {
            statusText.textContent = 'Stopped';
            document.getElementById('youtube-controls').style.display = 'none';
        }
    } catch (error) {
        console.error('YouTube control failed:', error);
    }
}

// Audio
async function loadAudioDevices() {
    try {
        const response = await fetch('/api/audio/devices');
        const data = await response.json();

        const select = document.getElementById('audio-device');
        select.innerHTML = '';

        if (data.devices && data.devices.length > 0) {
            data.devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.id;
                option.textContent = device.name;
                if (device.id === data.device) {
                    option.selected = true;
                }
                select.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.value = 'default';
            option.textContent = 'Default System Output';
            select.appendChild(option);
        }

        // Update volume slider
        if (data.volume !== undefined) {
            document.getElementById('audio-volume').value = data.volume;
            document.getElementById('volume-value').textContent = data.volume + '%';
        }
    } catch (error) {
        console.error('Failed to load audio devices:', error);
    }
}

async function setAudioDevice(deviceId) {
    try {
        await fetch('/api/audio/device', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device: deviceId })
        });
    } catch (error) {
        console.error('Failed to set audio device:', error);
    }
}

async function setVolume(value) {
    document.getElementById('volume-value').textContent = value + '%';

    try {
        await fetch('/api/audio/volume', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ volume: parseInt(value) })
        });
    } catch (error) {
        console.error('Failed to set volume:', error);
    }
}

// Bluetooth
async function bluetoothScan() {
    const btn = document.getElementById('bt-scan');
    const originalContent = btn.innerHTML;

    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scanning...';
    btn.disabled = true;

    try {
        await fetch('/api/bluetooth/scan', { method: 'POST' });
        setTimeout(() => {
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }, 5000);
    } catch (error) {
        console.error('Bluetooth scan failed:', error);
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

async function bluetoothDisconnect() {
    try {
        await fetch('/api/bluetooth/disconnect', { method: 'POST' });
        document.getElementById('bt-status').textContent = 'Disconnected';
        document.getElementById('bt-device').textContent = 'None';
    } catch (error) {
        console.error('Bluetooth disconnect failed:', error);
    }
}

// Logs
async function loadLogs() {
    try {
        const filter = document.getElementById('log-filter').value;
        let url = '/api/logs';
        if (filter) {
            url += `?category=${filter}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        const container = document.getElementById('log-entries');

        if (data.logs.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-scroll"></i>
                    <p>No log entries yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';
        data.logs.forEach(log => {
            addLogEntry(log, false);
        });

        // Scroll to bottom
        document.getElementById('log-container').scrollTop =
            document.getElementById('log-container').scrollHeight;

    } catch (error) {
        console.error('Failed to load logs:', error);
    }
}

function addLogEntry(log, scroll = true) {
    const container = document.getElementById('log-entries');

    // Remove empty state if present
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    const entry = document.createElement('div');
    entry.className = 'log-entry';

    const time = new Date(log.timestamp * 1000).toLocaleTimeString();

    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-category ${log.category}">${log.category}</span>
        <span class="log-message">${log.message}</span>
    `;

    container.appendChild(entry);

    // Limit entries
    const entries = container.querySelectorAll('.log-entry');
    while (entries.length > 500) {
        container.removeChild(container.firstChild);
    }

    // Auto-scroll
    if (scroll) {
        document.getElementById('log-container').scrollTop =
            document.getElementById('log-container').scrollHeight;
    }
}

async function clearLogs() {
    if (!confirm('Clear all logs?')) return;

    try {
        await fetch('/api/logs/clear', { method: 'POST' });
        document.getElementById('log-entries').innerHTML = `
            <div class="empty-state">
                <i class="fas fa-scroll"></i>
                <p>No log entries yet</p>
            </div>
        `;
    } catch (error) {
        console.error('Failed to clear logs:', error);
    }
}

function exportLogs() {
    const entries = document.querySelectorAll('.log-entry');
    if (entries.length === 0) {
        alert('No logs to export');
        return;
    }

    let text = 'TablePi Logs\n' + '='.repeat(50) + '\n\n';

    entries.forEach(entry => {
        const time = entry.querySelector('.log-time').textContent;
        const category = entry.querySelector('.log-category').textContent;
        const message = entry.querySelector('.log-message').textContent;
        text += `${time}  [${category}]  ${message}\n`;
    });

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tablepi-logs-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}

// Dimming
async function loadDimmingSettings() {
    try {
        const response = await fetch('/api/dimming/settings');
        const settings = await response.json();

        document.getElementById('dimming-enabled').checked = settings.enabled !== false;
        document.getElementById('dimming-day-start').value = settings.day_start || '07:00';
        document.getElementById('dimming-night-start').value = settings.night_start || '21:00';
        document.getElementById('dimming-transition').value = settings.transition_minutes || 30;

        const dayBrightness = settings.day_brightness || 100;
        const nightBrightness = settings.night_brightness || 30;

        document.getElementById('dimming-day-brightness').value = dayBrightness;
        document.getElementById('day-brightness-value').textContent = dayBrightness + '%';

        document.getElementById('dimming-night-brightness').value = nightBrightness;
        document.getElementById('night-brightness-value').textContent = nightBrightness + '%';

    } catch (error) {
        console.error('Failed to load dimming settings:', error);
    }
}

async function saveDimmingSettings() {
    const saveBtn = document.getElementById('save-dimming');
    const originalContent = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    saveBtn.disabled = true;

    const settings = {
        enabled: document.getElementById('dimming-enabled').checked,
        day_start: document.getElementById('dimming-day-start').value,
        night_start: document.getElementById('dimming-night-start').value,
        transition_minutes: parseInt(document.getElementById('dimming-transition').value) || 30,
        day_brightness: parseInt(document.getElementById('dimming-day-brightness').value) || 100,
        night_brightness: parseInt(document.getElementById('dimming-night-brightness').value) || 30
    };

    try {
        const response = await fetch('/api/dimming/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            saveBtn.innerHTML = '<i class="fas fa-check"></i> Saved!';
            setTimeout(() => {
                saveBtn.innerHTML = originalContent;
                saveBtn.disabled = false;
            }, 2000);
        } else {
            saveBtn.innerHTML = '<i class="fas fa-times"></i> Failed';
            setTimeout(() => {
                saveBtn.innerHTML = originalContent;
                saveBtn.disabled = false;
            }, 2000);
        }
    } catch (error) {
        console.error('Failed to save dimming settings:', error);
        saveBtn.innerHTML = '<i class="fas fa-times"></i> Failed';
        setTimeout(() => {
            saveBtn.innerHTML = originalContent;
            saveBtn.disabled = false;
        }, 2000);
    }
}

async function applyManualBrightness() {
    const brightness = document.getElementById('dimming-manual').value;

    try {
        await fetch('/api/dimming/brightness', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ brightness: parseInt(brightness) })
        });
    } catch (error) {
        console.error('Failed to set manual brightness:', error);
    }
}

async function restoreAutoDimming() {
    try {
        await fetch('/api/dimming/auto', { method: 'POST' });
    } catch (error) {
        console.error('Failed to restore auto-dimming:', error);
    }
}

// Event listeners
function initEventListeners() {
    // Settings
    document.getElementById('save-settings').addEventListener('click', saveSettings);
    document.getElementById('refresh-weather').addEventListener('click', refreshWeather);

    // Themes
    document.getElementById('theme-select').addEventListener('change', (e) => {
        loadThemeColors(e.target.value);
    });
    document.getElementById('apply-theme').addEventListener('click', applyTheme);
    document.getElementById('save-theme').addEventListener('click', saveTheme);
    document.getElementById('save-theme-as').addEventListener('click', () => saveThemeAs());

    // YouTube
    document.getElementById('youtube-play').addEventListener('click', playYouTube);
    document.getElementById('yt-pause').addEventListener('click', () => youtubeControl('pause'));
    document.getElementById('yt-resume').addEventListener('click', () => youtubeControl('resume'));
    document.getElementById('yt-stop').addEventListener('click', () => youtubeControl('stop'));
    document.getElementById('yt-vol-up').addEventListener('click', () => youtubeControl('volume_up'));
    document.getElementById('yt-vol-down').addEventListener('click', () => youtubeControl('volume_down'));

    // Audio
    document.getElementById('audio-device').addEventListener('change', (e) => {
        setAudioDevice(e.target.value);
    });
    document.getElementById('audio-volume').addEventListener('input', (e) => {
        setVolume(e.target.value);
    });

    // Bluetooth
    document.getElementById('bt-scan').addEventListener('click', bluetoothScan);
    document.getElementById('bt-disconnect').addEventListener('click', bluetoothDisconnect);

    // Dimming
    document.getElementById('save-dimming').addEventListener('click', saveDimmingSettings);
    document.getElementById('dimming-apply-manual').addEventListener('click', applyManualBrightness);
    document.getElementById('dimming-restore-auto').addEventListener('click', restoreAutoDimming);

    // Dimming slider value updates
    document.getElementById('dimming-day-brightness').addEventListener('input', (e) => {
        document.getElementById('day-brightness-value').textContent = e.target.value + '%';
    });
    document.getElementById('dimming-night-brightness').addEventListener('input', (e) => {
        document.getElementById('night-brightness-value').textContent = e.target.value + '%';
    });
    document.getElementById('dimming-manual').addEventListener('input', (e) => {
        document.getElementById('manual-brightness-value').textContent = e.target.value + '%';
    });

    // Logs
    document.getElementById('log-filter').addEventListener('change', loadLogs);
    document.getElementById('clear-logs').addEventListener('click', clearLogs);
    document.getElementById('export-logs').addEventListener('click', exportLogs);

    // Color inputs - update value display
    document.querySelectorAll('.color-item input[type="color"]').forEach(input => {
        input.addEventListener('input', () => updateColorValue(input));
    });
}
