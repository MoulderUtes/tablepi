#!/bin/bash
# TablePi Installation Script

set -e

echo "================================"
echo "  TablePi Installation Script"
echo "================================"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    echo "Installation will continue, but some features may not work."
    echo ""
fi

# Update system
echo "[1/7] Updating system packages..."
sudo apt update

# Install system dependencies
echo "[2/7] Installing system dependencies..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-pygame \
    mpv \
    fonts-dejavu \
    fonts-liberation

# Create virtual environment
echo "[3/7] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "[4/7] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install yt-dlp
echo "[5/7] Installing yt-dlp..."
pip install yt-dlp

# Create necessary directories
echo "[6/7] Creating directories..."
mkdir -p cache logs

# Copy default config if not exists
if [ ! -f config/settings.json ]; then
    echo "[6/7] Creating default configuration..."
    cp config/settings.json.example config/settings.json 2>/dev/null || true
fi

# Install systemd service (optional)
echo "[7/7] Installing systemd service..."
if [ -f tablepi.service ]; then
    sudo cp tablepi.service /etc/systemd/system/
    sudo systemctl daemon-reload
    echo "  Service installed. Enable with: sudo systemctl enable tablepi"
fi

echo ""
echo "================================"
echo "  Installation Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Edit config/settings.json with your OpenWeatherMap API key"
echo "2. Set your location (latitude/longitude)"
echo "3. Run: source venv/bin/activate && python -m app.main"
echo ""
echo "Or enable the service to start on boot:"
echo "  sudo systemctl enable tablepi"
echo "  sudo systemctl start tablepi"
echo ""
echo "Web UI will be available at: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
