# Raspberry Pi Setup Guide

This guide covers setting up a Raspberry Pi 3B with the official 7" touchscreen display to run TablePi.

## Hardware Requirements

- Raspberry Pi 3B (or newer)
- 7" Official RPi Display (480p touchscreen)
- MicroSD card (16GB+ recommended)
- Power supply (2.5A recommended)
- Optional: Bluetooth speaker

## Step 1: Flash Raspberry Pi OS

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Flash **Raspberry Pi OS Lite (64-bit)** to SD card
3. In imager settings (gear icon):
   - Enable SSH
   - Set username/password (remember this for later)
   - Configure WiFi
   - Set hostname: `tablepi`

## Step 2: Initial Boot

```bash
# SSH into the Pi (replace YOUR_USERNAME with what you set in imager)
ssh YOUR_USERNAME@tablepi.local
```

---

# Choose Your Installation Method

## Option 1: Automated Installation (Recommended)

The install script handles everything automatically:

```bash
# Clone the repository
cd ~
git clone <your-repo-url> tablepi
cd tablepi

# Run the installer
./install.sh
```

The script will:
- Update system packages
- Install X11, Python, audio, and Bluetooth packages
- Create Python virtual environment and install dependencies
- Expand filesystem to use full SD card
- Enable console auto-login
- Enable SSH
- Configure auto-start on boot (.xinitrc and .bash_profile)
- Enable Bluetooth and PulseAudio services

After the script completes:

```bash
# Edit the config to add your API key and location
nano config/settings.json
```

Required config changes:
- `weather.api_key` - Your OpenWeatherMap API key (get one at https://openweathermap.org/api)
- `weather.lat` - Your latitude (e.g., 40.7128)
- `weather.lon` - Your longitude (e.g., -74.0060)
- `clock.timezone` - Your timezone (e.g., "America/New_York")

Optional:
```bash
# Set your timezone
sudo raspi-config
# → Localisation Options → Timezone → Select yours
```

Then reboot:
```bash
sudo reboot
```

**That's it!** TablePi will start automatically after reboot.

---

## Option 2: Manual Installation

If you prefer to install manually or need to troubleshoot, follow these steps.

### 2a: Update System

```bash
sudo apt update && sudo apt upgrade -y

# Set timezone
sudo raspi-config
# → Localisation Options → Timezone → Select yours
```

### 2b: Install X11 and Display Dependencies

We use X11 without a full desktop environment - just enough to run PyGame:

```bash
# Install X server and minimal window manager
sudo apt install -y xserver-xorg x11-xserver-utils xinit openbox

# Install Python and development tools
sudo apt install -y python3 python3-pip python3-venv python3-pygame

# Install mpv and yt-dlp for YouTube
sudo apt install -y mpv

# Install fonts (for emoji and text rendering)
sudo apt install -y fonts-dejavu fonts-liberation fonts-noto-color-emoji

# Install audio tools
sudo apt install -y pulseaudio pulseaudio-utils alsa-utils

# Install Bluetooth tools
sudo apt install -y bluez pulseaudio-module-bluetooth
```

### 2c: Install TablePi Application

```bash
# Clone repository
cd ~
git clone <your-repo-url> tablepi
cd tablepi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install yt-dlp

# Create directories
mkdir -p cache logs

# Copy default config
cp config/settings.example.json config/settings.json

# Edit settings (add your OpenWeatherMap API key, location, etc.)
nano config/settings.json
```

### 2d: Configure System Settings

```bash
# Expand filesystem, enable auto-login, and enable SSH
sudo raspi-config nonint do_expand_rootfs
sudo raspi-config nonint do_boot_behaviour B2
sudo raspi-config nonint do_ssh 0

# Add user to bluetooth group
sudo usermod -aG bluetooth $(whoami)

# Enable services
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
systemctl --user enable pulseaudio
```

### 2e: Configure Auto-Start on Boot

This is how TablePi starts automatically:
1. Pi boots → auto-login to console
2. `.bash_profile` runs → starts X11
3. `.xinitrc` runs → launches TablePi

**Create the X startup script (.xinitrc):**

```bash
cat << 'EOF' > ~/.xinitrc
#!/bin/bash
# Disable screen saver and power management
xset s off
xset -dpms
xset s noblank

# Start minimal window manager in background
openbox-session &

# Launch TablePi
cd ~/tablepi
source venv/bin/activate
python3 app/main.py
EOF

chmod +x ~/.xinitrc
```

**Configure auto-start X11 on login (.bash_profile):**

```bash
echo '[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx' >> ~/.bash_profile
```

What this does:
- `[[ -z $DISPLAY ]]` - Only run if no display is set (not already in X)
- `$XDG_VTNR -eq 1` - Only run on virtual terminal 1 (the main console, not SSH)
- `startx` - Starts X11, which then runs `.xinitrc`

### 2f: Reboot and Test

```bash
sudo reboot
```

After reboot, the Pi should:
1. Auto-login to the console
2. Automatically start X11
3. Launch TablePi on the display

**Note:** If you SSH in, X won't start (that's by design). The display only runs when booted normally.

---

## Display Configuration (if needed)

```bash
# Edit boot config
sudo nano /boot/firmware/config.txt
# (or /boot/config.txt on older Pi OS versions)

# For 7" official display rotation (if upside down):
lcd_rotate=2

# General rotation (0, 90, 180, 270):
display_rotate=0
```

## Touchscreen Configuration

The official 7" display should work out of the box. If touch is inverted:

```bash
# Add to /boot/firmware/config.txt:
lcd_rotate=2

# For rotation with touch calibration:
# dtoverlay=rpi-ft5406,touchscreen-inverted-x=1,touchscreen-swapped-x-y=1
```

## Bluetooth Audio Setup

```bash
# Pair a Bluetooth speaker (first time)
bluetoothctl
# power on
# agent on
# scan on
# pair XX:XX:XX:XX:XX:XX
# connect XX:XX:XX:XX:XX:XX
# trust XX:XX:XX:XX:XX:XX
# quit
```

## Systemd Service (Alternative Method)

**Note:** This is an alternative to the auto-start method. Only use this if you want TablePi to run as a system service. This requires X11 to already be running.

```bash
# Get your username
whoami

sudo nano /etc/systemd/system/tablepi.service
```

Add (replace `YOUR_USERNAME` with your actual username):

```ini
[Unit]
Description=TablePi Display
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/tablepi
Environment=DISPLAY=:0
Environment=PULSE_RUNTIME_PATH=/run/user/1000/pulse
ExecStartPre=/bin/sleep 5
ExecStart=/home/YOUR_USERNAME/tablepi/venv/bin/python app/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable tablepi
sudo systemctl start tablepi

# Check status
sudo systemctl status tablepi

# View logs
journalctl -u tablepi -f
```

---

## Running TablePi

After setup, TablePi starts automatically on boot. You can also run it manually:

```bash
# If on the Pi console (not SSH), start X and TablePi
startx

# If X is already running, run TablePi directly
cd ~/tablepi
source venv/bin/activate
python3 app/main.py
```

Access the web control panel from any device on your network:
```
http://tablepi.local:5000
```
or
```
http://<pi-ip-address>:5000
```

---

## Troubleshooting

### TablePi doesn't start on boot

1. Verify console auto-login is enabled:
   ```bash
   sudo raspi-config
   # Check: System Options → Boot / Auto Login → Console Autologin
   ```

2. Check that `.bash_profile` exists and has the startx line:
   ```bash
   cat ~/.bash_profile
   # Should contain: [[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx
   ```

3. Check that `.xinitrc` exists and is executable:
   ```bash
   cat ~/.xinitrc
   ls -la ~/.xinitrc
   ```

4. Check X logs for errors:
   ```bash
   cat ~/.local/share/xorg/Xorg.0.log | tail -50
   ```

### X11 won't start

```bash
# Check X logs
cat ~/.local/share/xorg/Xorg.0.log | tail -50

# Try starting manually (must be on console, not SSH)
startx
```

### "Only console users are allowed to run the X server"

You're trying to run `startx` via SSH. X11 can only start from the physical console. Either:
- Plug in a keyboard and run `startx` directly on the Pi
- Reboot and let auto-login + auto-start handle it

### Display not detected

```bash
# Check for framebuffer
ls -la /dev/fb*

# Check DRM devices
ls -la /dev/dri/

# View dmesg for display info
dmesg | grep -i "drm\|display\|dsi\|fb"
```

### Touch not working

```bash
# Check for touch input device
cat /proc/bus/input/devices | grep -A5 "touch"

# Test touch events
sudo apt install evtest
sudo evtest
```

### No audio

```bash
# Restart PulseAudio
pulseaudio -k
pulseaudio --start

# Check sinks
pactl list short sinks
```

### Missing Python modules

If you get "No module named 'pygame'" or similar errors:

```bash
cd ~/tablepi
source venv/bin/activate
pip install -r requirements.txt
```

### Weather not updating

1. Check your API key is correct in `config/settings.json`
2. Verify lat/lon coordinates are correct
3. Check the web UI Activity Log for API errors
4. Test API manually:
   ```bash
   curl "https://api.openweathermap.org/data/3.0/onecall?lat=YOUR_LAT&lon=YOUR_LON&appid=YOUR_API_KEY"
   ```
