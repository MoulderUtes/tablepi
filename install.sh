#!/bin/bash
# TablePi Installation Script
# Run this after a fresh Raspberry Pi OS Lite (64-bit) install

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "     TablePi Installation Script"
echo "========================================"
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model)
    echo "Detected: $PI_MODEL"
else
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    echo "Some features (auto-start, display config) may not work."
fi
echo ""

# Get current user
CURRENT_USER=$(whoami)
HOME_DIR=$(eval echo ~$CURRENT_USER)
echo "Installing for user: $CURRENT_USER"
echo "Home directory: $HOME_DIR"
echo ""

# Confirm installation
read -p "Continue with installation? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "Installation cancelled."
    exit 1
fi

echo ""
echo "[1/10] Updating system packages..."
sudo apt update && sudo apt upgrade -y

echo ""
echo "[2/10] Installing X11 and display dependencies..."
sudo apt install -y \
    xserver-xorg \
    x11-xserver-utils \
    xinit \
    openbox

echo ""
echo "[3/10] Installing Python and development tools..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-pygame

echo ""
echo "[4/10] Installing media and font packages..."
sudo apt install -y \
    mpv \
    fonts-dejavu \
    fonts-liberation \
    fonts-noto-color-emoji

echo ""
echo "[5/10] Installing audio tools..."
sudo apt install -y \
    pulseaudio \
    pulseaudio-utils \
    alsa-utils \
    bluez \
    pulseaudio-module-bluetooth

# Add user to bluetooth group
sudo usermod -aG bluetooth $CURRENT_USER

echo ""
echo "[6/10] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo ""
echo "[7/10] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install yt-dlp

echo ""
echo "[8/10] Creating directories and config..."
mkdir -p cache logs

# Copy default config if not exists
if [ ! -f config/settings.json ]; then
    if [ -f config/settings.json.example ]; then
        cp config/settings.json.example config/settings.json
        echo "Created config/settings.json from example"
    elif [ -f config/settings.example.json ]; then
        cp config/settings.example.json config/settings.json
        echo "Created config/settings.json from example"
    else
        echo "Warning: No example config found. You'll need to create config/settings.json manually."
    fi
fi

echo ""
echo "[9/10] Configuring auto-start on boot..."

# Configure via raspi-config noninteractive mode
if command -v raspi-config &> /dev/null; then
    echo "  Expanding filesystem..."
    sudo raspi-config nonint do_expand_rootfs

    echo "  Enabling console auto-login..."
    sudo raspi-config nonint do_boot_behaviour B2

    echo "  Ensuring SSH is enabled..."
    sudo raspi-config nonint do_ssh 0
else
    echo "  Warning: raspi-config not found. You'll need to configure auto-login, SSH, and filesystem expansion manually."
fi

# Create .xinitrc with error logging (exits to TTY on crash for debugging)
echo "  Creating ~/.xinitrc..."
cat << 'EOF' > "$HOME_DIR/.xinitrc"
#!/bin/bash
# TablePi X startup script

# Log file for debugging
LOGFILE=~/tablepi/logs/startup.log
mkdir -p ~/tablepi/logs

echo "=== TablePi starting at $(date) ===" >> "$LOGFILE"

# Disable screen saver and power management
xset s off
xset -dpms
xset s noblank

# Start minimal window manager in background
openbox-session &

# Launch TablePi
cd ~/tablepi
source venv/bin/activate

echo "Starting TablePi at $(date)" >> "$LOGFILE"
python3 app/main.py 2>&1 | tee -a "$LOGFILE"
EXIT_CODE=$?
echo "TablePi exited with code $EXIT_CODE at $(date)" >> "$LOGFILE"

# Exit to TTY for debugging - check ~/tablepi/logs/startup.log for errors
EOF
chmod +x "$HOME_DIR/.xinitrc"

# Add auto-startx to .bash_profile (if not already present)
echo "  Configuring ~/.bash_profile..."
STARTX_LINE='[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx'
if [ -f "$HOME_DIR/.bash_profile" ]; then
    if ! grep -q "startx" "$HOME_DIR/.bash_profile"; then
        echo "$STARTX_LINE" >> "$HOME_DIR/.bash_profile"
    else
        echo "  .bash_profile already has startx configured"
    fi
else
    echo "$STARTX_LINE" > "$HOME_DIR/.bash_profile"
fi

echo ""
echo "[10/10] Enabling services..."

# Enable bluetooth
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Enable PulseAudio for user
systemctl --user enable pulseaudio 2>/dev/null || true

echo ""
echo "========================================"
echo "     Installation Complete!"
echo "========================================"
echo ""
echo "IMPORTANT: You still need to:"
echo ""
echo "1. Edit config/settings.json and add:"
echo "   - Your OpenWeatherMap API key"
echo "   - Your location (latitude/longitude)"
echo ""
echo "   Run: nano config/settings.json"
echo ""
echo "2. (Optional) Set your timezone:"
echo "   Run: sudo raspi-config"
echo "   Navigate to: Localisation Options -> Timezone"
echo ""
echo "3. Reboot to start TablePi:"
echo "   Run: sudo reboot"
echo ""
echo "After reboot, TablePi will start automatically."
echo ""
echo "Web UI will be available at:"
echo "   http://$(hostname).local:5000"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "To pair Bluetooth speakers:"
echo "   Run: bluetoothctl"
echo "   Then: power on, scan on, pair XX:XX:XX, trust XX:XX:XX, connect XX:XX:XX"
echo ""
