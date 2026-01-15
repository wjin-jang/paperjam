#!/bin/bash
# PaperJam Installation Script
# Run: curl -fsSL https://raw.githubusercontent.com/wjin-jang/paperjam/main/install.sh | bash

set -e

echo "=========================================="
echo "  PaperJam Installer"
echo "  E-ink Music Player for Raspberry Pi"
echo "=========================================="
echo

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: This doesn't appear to be a Raspberry Pi."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

# Get username and paths
USER_NAME=$(whoami)
HOME_DIR=$(eval echo ~$USER_NAME)
INSTALL_DIR="$HOME_DIR/paperjam"

echo "Installing for user: $USER_NAME"
echo "Install directory: $INSTALL_DIR"
echo

# Determine config.txt location (Bookworm uses /boot/firmware/, older uses /boot/)
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
else
    CONFIG_FILE="/boot/config.txt"
fi

# --- System Packages ---
echo "[1/8] Installing system packages..."
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    i2c-tools \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    vlc \
    git \
    pulseaudio \
    pulseaudio-module-bluetooth \
    alsa-utils \
    wireless-tools \
    swig \
    python3-lgpio

# --- Enable Interfaces ---
echo
echo "[2/8] Enabling I2C and SPI..."

# Enable I2C
if ! grep -q "^dtparam=i2c_arm=on" "$CONFIG_FILE" 2>/dev/null; then
    sudo bash -c "echo 'dtparam=i2c_arm=on' >> $CONFIG_FILE"
    echo "  I2C enabled"
else
    echo "  I2C already enabled"
fi

# Enable SPI
if ! grep -q "^dtparam=spi=on" "$CONFIG_FILE" 2>/dev/null; then
    sudo bash -c "echo 'dtparam=spi=on' >> $CONFIG_FILE"
    echo "  SPI enabled"
else
    echo "  SPI already enabled"
fi

# --- User Permissions ---
echo
echo "[3/8] Setting up user permissions..."
sudo usermod -aG i2c,gpio,spi,bluetooth,audio $USER_NAME 2>/dev/null || true
echo "  Added $USER_NAME to hardware groups"

# --- Bluetooth ---
echo
echo "[4/8] Configuring Bluetooth..."
sudo systemctl enable bluetooth 2>/dev/null || true
sudo systemctl start bluetooth 2>/dev/null || true
sudo rfkill unblock bluetooth 2>/dev/null || true
echo "  Bluetooth enabled"

# --- Clone Repository ---
echo
echo "[5/8] Cloning PaperJam repository..."
if [ -d "$INSTALL_DIR" ]; then
    echo "  Directory exists, pulling latest..."
    cd "$INSTALL_DIR"
    git pull origin main || true
else
    git clone https://github.com/wjin-jang/paperjam.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# --- Python Virtual Environment ---
echo
echo "[6/8] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install pillow mutagen python-vlc smbus2 evdev numpy spidev RPi.GPIO gpiozero pykakasi korean_romanizer

# Symlink system lgpio into venv (can't be pip installed)
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
VENV_SITE="$INSTALL_DIR/venv/lib/python$PYTHON_VERSION/site-packages"
ln -sf /usr/lib/python3/dist-packages/lgpio.py "$VENV_SITE/"
ln -sf /usr/lib/python3/dist-packages/_lgpio*.so "$VENV_SITE/" 2>/dev/null || true
echo "  Python dependencies installed"

# --- Configuration ---
echo
echo "[7/8] Configuring PaperJam..."
CONFIG_DIR="$HOME_DIR/.config/paperjam"
mkdir -p "$CONFIG_DIR"
CONFIG_FILE="$CONFIG_DIR/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating configuration..."
    
    # Prompt for Music Path
    read -p "Enter path to music directory (default: $HOME_DIR/Music): " INPUT_PATH
    MUSIC_PATH=${INPUT_PATH:-"$HOME_DIR/Music"}
    
    # Create Python script to write JSON
    $INSTALL_DIR/venv/bin/python3 -c "
import json
import os
from pathlib import Path

config = {
    'music_path': '$MUSIC_PATH',
    'screensaver_timeout': 60,
    'long_press_duration': 0.5,
    'recents_limit': 50,
    'invert_colors': False
}

config_path = Path('$CONFIG_FILE')
with open(config_path, 'w') as f:
    json.dump(config, f, indent=4)

print(f'Configuration saved to {config_path}')
"
else
    echo "  Configuration already exists at $CONFIG_FILE"
fi

# --- Waveshare EPD Library ---
echo
echo "[8/9] Installing Waveshare e-Paper driver..."
if [ -d "lib/waveshare" ]; then
    echo "  Directory exists, pulling latest..."
    cd "lib/waveshare"
    git pull origin master || true
    cd "$INSTALL_DIR"
else
    mkdir -p lib
    git clone https://github.com/waveshare/e-Paper.git "lib/waveshare"
fi
pip install lib/waveshare/RaspberryPi_JetsonNano/python/
echo "  Waveshare driver installed"

# --- Systemd Service ---
echo
echo "[9/9] Setting up auto-start service..."

mkdir -p "$HOME_DIR/.config/systemd/user"

cat > "$HOME_DIR/.config/systemd/user/paperjam.service" << 'EOF'
[Unit]
Description=PaperJam Music Player
After=pulseaudio.service

[Service]
Type=simple
WorkingDirectory=%h/paperjam
ExecStart=%h/paperjam/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable paperjam

# Enable linger for auto-start without login
sudo loginctl enable-linger $USER_NAME 2>/dev/null || true

echo "  Service configured"

# --- Done ---
echo
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo
echo "A reboot is required for I2C/SPI changes to take effect."
echo
echo "After reboot:"
echo "  - Edit music path: nano $INSTALL_DIR/config.py"
echo "  - Start service:   systemctl --user start paperjam"
echo "  - View logs:       journalctl --user -u paperjam -f"
echo "  - Run manually:    cd $INSTALL_DIR && source venv/bin/activate && python main.py"
echo
read -p "Reboot now? (y/n) " -n 1 -r REPLY </dev/tty
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
fi
