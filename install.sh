#!/bin/bash
# PaperJam Installation Script
# Copy this entire script and paste into: nano install.sh
# Then run: chmod +x install.sh && ./install.sh

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

# Get username
USER_NAME=$(whoami)
HOME_DIR=$(eval echo ~$USER_NAME)
INSTALL_DIR="$HOME_DIR/paperjam"

echo "Installing for user: $USER_NAME"
echo "Install directory: $INSTALL_DIR"
echo

# --- System Packages ---
echo "[1/7] Installing system packages..."
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
    alsa-utils

# --- Enable Interfaces ---
echo
echo "[2/7] Enabling I2C and SPI..."

# Enable I2C
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
    if [ -f /boot/firmware/config.txt ]; then
        sudo bash -c 'echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt'
    else
        sudo bash -c 'echo "dtparam=i2c_arm=on" >> /boot/config.txt'
    fi
    echo "  I2C enabled"
else
    echo "  I2C already enabled"
fi

# Enable SPI
if ! grep -q "^dtparam=spi=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null; then
    if [ -f /boot/firmware/config.txt ]; then
        sudo bash -c 'echo "dtparam=spi=on" >> /boot/firmware/config.txt'
    else
        sudo bash -c 'echo "dtparam=spi=on" >> /boot/config.txt'
    fi
    echo "  SPI enabled"
else
    echo "  SPI already enabled"
fi

# --- User Permissions ---
echo
echo "[3/7] Setting up user permissions..."
sudo usermod -aG i2c,gpio,spi,bluetooth,audio $USER_NAME 2>/dev/null || true
echo "  Added $USER_NAME to hardware groups"

# --- Bluetooth ---
echo
echo "[4/7] Configuring Bluetooth..."
sudo systemctl enable bluetooth 2>/dev/null || true
sudo systemctl start bluetooth 2>/dev/null || true
sudo rfkill unblock bluetooth 2>/dev/null || true
echo "  Bluetooth enabled"

# --- Clone Repository ---
echo
echo "[5/7] Cloning PaperJam repository..."
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
echo "[6/7] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install pillow mutagen python-vlc smbus2 evdev numpy epd-library
echo "  Python dependencies installed"

# --- Systemd Service ---
echo
echo "[7/7] Setting up auto-start service..."

mkdir -p "$HOME_DIR/.config/systemd/user"

cat > "$HOME_DIR/.config/systemd/user/paperjam.service" << EOF
[Unit]
Description=PaperJam Music Player
After=pulseaudio.service

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python main.py
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
echo "IMPORTANT: A reboot is required for I2C/SPI changes."
echo
echo "After reboot:"
echo "  - Edit music path: nano $INSTALL_DIR/config.py"
echo "  - Start service:   systemctl --user start paperjam"
echo "  - View logs:       journalctl --user -u paperjam -f"
echo "  - Run manually:    cd $INSTALL_DIR && source venv/bin/activate && python main.py"
echo
read -p "Reboot now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
fi
