# Raspberry Pi Setup Guide

This guide covers setting up a Raspberry Pi 3B with the official 7" touchscreen display to run TablePi.

## Hardware Requirements

- Raspberry Pi 3B (or newer)
- 7" Official RPi Display (480p touchscreen)
- MicroSD card (16GB+ recommended)
- Power supply (2.5A recommended)
- Optional: Bluetooth speaker

## Step 1: Install Raspberry Pi OS Lite

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Flash **Raspberry Pi OS Lite (64-bit)** to SD card
3. In imager settings (gear icon):
   - Enable SSH
   - Set username/password (remember this username for later steps)
   - Configure WiFi
   - Set hostname: `tablepi`

## Step 2: Initial Boot & Updates

```bash
# SSH into the Pi (replace YOUR_USERNAME with what you set in imager)
ssh YOUR_USERNAME@tablepi.local

# Update system
sudo apt update && sudo apt upgrade -y

# Set timezone
sudo raspi-config
# → Localisation Options → Timezone → Select yours
```

## Step 3: Install X11 and Display Dependencies

We use X11 without a full desktop environment - just enough to run PyGame:

```bash
# Install X server and minimal window manager
sudo apt install -y xserver-xorg x11-xserver-utils xinit openbox

# Install Python and development tools
sudo apt install -y python3 python3-pip python3-venv python3-pygame

# Install mpv and yt-dlp for YouTube
sudo apt install -y mpv
pip3 install yt-dlp

# Install fonts (for emoji and text rendering)
sudo apt install -y fonts-dejavu fonts-liberation fonts-noto-color-emoji

# Install audio tools
sudo apt install -y pulseaudio pulseaudio-utils alsa-utils
```

## Step 4: Install TablePi Application

**Important:** Install TablePi BEFORE configuring auto-start (Step 5), since the auto-start scripts reference the virtual environment.

```bash
# Clone repository (or copy files)
cd ~
git clone <your-repo-url> tablepi
cd tablepi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy default config
cp config/settings.example.json config/settings.json

# Edit settings (add your OpenWeatherMap API key, location, etc.)
nano config/settings.json
```

## Step 5: Configure Auto-Start on Boot

This is the recommended method for running TablePi. The flow is:
1. Pi boots → auto-login to console
2. `.bash_profile` runs → starts X11
3. `.xinitrc` runs → launches TablePi

### 5a: Enable Console Auto-Login

```bash
sudo raspi-config
# Navigate to: System Options → Boot / Auto Login → Console Autologin
# Select it and exit raspi-config
```

### 5b: Create the X Startup Script (.xinitrc)

This script runs when X11 starts. It disables screen blanking and launches TablePi:

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

# Make it executable
chmod +x ~/.xinitrc
```

### 5c: Auto-Start X11 on Login (.bash_profile)

This line starts X automatically when you log in to the console (but not via SSH):

```bash
# Create or append to .bash_profile
echo '[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx' >> ~/.bash_profile
```

**What this does:**
- `[[ -z $DISPLAY ]]` - Only run if no display is set (not already in X)
- `$XDG_VTNR -eq 1` - Only run on virtual terminal 1 (the main console, not SSH)
- `startx` - Starts X11, which then runs `.xinitrc`

### 5d: Reboot and Test

```bash
sudo reboot
```

After reboot, the Pi should:
1. Auto-login to the console
2. Automatically start X11
3. Launch TablePi on the display

**Note:** If you SSH in, X won't start (that's by design). The display will only run when booted normally.

## Step 6: Configure Display (if needed)

```bash
# Edit boot config
sudo nano /boot/firmware/config.txt
# (or /boot/config.txt on older Pi OS versions)

# For 7" official display rotation (if upside down):
lcd_rotate=2

# General rotation (0, 90, 180, 270):
display_rotate=0
```

## Step 7: Configure Touchscreen

The official 7" display should work out of the box. If touch is inverted:

```bash
# Add to /boot/firmware/config.txt:
lcd_rotate=2

# For rotation with touch calibration:
# dtoverlay=rpi-ft5406,touchscreen-inverted-x=1,touchscreen-swapped-x-y=1
```

## Step 8: Systemd Service (Alternative Method)

**Note:** This is an alternative to Step 5. Only use this if you want TablePi to run as a system service. This requires X11 to already be running (e.g., via the auto-start method above, or a display manager).

```bash
# Get your username
whoami

sudo nano /etc/systemd/system/tablepi.service
```

Add (replace `YOUR_USERNAME` with your actual username from `whoami`):

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
# Reload systemd, enable and start
sudo systemctl daemon-reload
sudo systemctl enable tablepi
sudo systemctl start tablepi

# Check status
sudo systemctl status tablepi

# View logs
journalctl -u tablepi -f
```

## Step 9: Configure Bluetooth Audio

```bash
# Install bluetooth tools
sudo apt install -y bluez pulseaudio-module-bluetooth

# Add your user to bluetooth group (replace YOUR_USERNAME)
sudo usermod -aG bluetooth YOUR_USERNAME

# Enable bluetooth service
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Pair manually (first time)
bluetoothctl
# power on
# agent on
# scan on
# pair XX:XX:XX:XX:XX:XX
# connect XX:XX:XX:XX:XX:XX
# trust XX:XX:XX:XX:XX:XX
# quit
```

## Step 10: Configure PulseAudio

```bash
# Ensure PulseAudio starts on login
systemctl --user enable pulseaudio

# List available audio sinks
pactl list short sinks

# Test audio
speaker-test -c 2
```

## Running TablePi

After setup, TablePi will start automatically on boot. You can also run it manually:

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
