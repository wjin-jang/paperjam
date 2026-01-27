#!/bin/bash
# PaperJam DietPi Installation Script
# Optimized for power efficiency on Raspberry Pi Zero 2 W
#
# For headless install, place this script at:
#   /boot/Automation_Custom_Script.sh
# DietPi will run it automatically after first-boot setup.

set -e

# Must run as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

echo "=========================================="
echo "  PaperJam DietPi Installer"
echo "  E-ink Music Player for Raspberry Pi"
echo "=========================================="
echo

# Get username and paths (dietpi user by default)
if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    USER_NAME="$SUDO_USER"
else
    USER_NAME="dietpi"
fi

# Verify user exists
if ! id "$USER_NAME" &>/dev/null; then
    echo "Error: User '$USER_NAME' does not exist"
    exit 1
fi

HOME_DIR=$(getent passwd "$USER_NAME" | cut -d: -f6)
if [ -z "$HOME_DIR" ] || [ ! -d "$HOME_DIR" ]; then
    echo "Error: Home directory for '$USER_NAME' not found"
    exit 1
fi

INSTALL_DIR="$HOME_DIR/paperjam"

echo "Installing for user: $USER_NAME"
echo "Install directory: $INSTALL_DIR"
echo

# --- Install Software via DietPi ---
echo "[1/9] Installing software..."

# Update package list
apt-get update

# Install core packages via apt (works on DietPi and Raspberry Pi OS)
apt-get install -y vlc-nox git i2c-tools python3-pip python3-venv python3-dev \
    libjpeg-dev zlib1g-dev libfreetype6-dev alsa-utils

# Install Python GPIO/system packages (may vary by distro)
apt-get install -y python3-lgpio python3-dbus python3-gi python3-gpiozero 2>/dev/null || true

echo "  Core packages installed"

# --- Enable Interfaces via DietPi ---
echo
echo "[2/9] Enabling I2C and SPI..."

# Find config.txt location (Bookworm uses /boot/firmware/, older uses /boot/)
if [ -f /boot/firmware/config.txt ]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    BOOT_CONFIG="/boot/config.txt"
else
    echo "Warning: config.txt not found, skipping I2C/SPI setup"
    BOOT_CONFIG=""
fi

if [ -n "$BOOT_CONFIG" ]; then
    # Enable I2C
    grep -q "^dtparam=i2c_arm=on" "$BOOT_CONFIG" || echo "dtparam=i2c_arm=on" >> "$BOOT_CONFIG"

    # Enable SPI
    grep -q "^dtparam=spi=on" "$BOOT_CONFIG" || echo "dtparam=spi=on" >> "$BOOT_CONFIG"

    echo "  I2C and SPI enabled in $BOOT_CONFIG"
fi

# Load i2c-dev module
grep -q "^i2c-dev" /etc/modules 2>/dev/null || echo "i2c-dev" >> /etc/modules

# --- User Permissions ---
echo
echo "[3/9] Setting up user permissions..."
for group in i2c gpio spi audio video input; do
    usermod -aG "$group" "$USER_NAME" 2>/dev/null || true
done
echo "  Added $USER_NAME to hardware groups"

# --- Power Optimization ---
echo
echo "[4/9] Optimizing for power efficiency..."

# Disable WiFi power management (if NetworkManager is used)
if [ -f /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf ]; then
    sed -i 's/wifi.powersave = 3/wifi.powersave = 2/' /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf 2>/dev/null || true
fi

# Disable HDMI (saves ~25mA) - use vcgencmd on 64-bit, tvservice on 32-bit
if command -v vcgencmd &>/dev/null; then
    vcgencmd display_power 0 2>/dev/null || true
elif command -v tvservice &>/dev/null; then
    tvservice -o 2>/dev/null || true
fi

# Create systemd service to disable HDMI on boot
cat > /etc/systemd/system/disable-hdmi.service << 'HDMIEOF'
[Unit]
Description=Disable HDMI output to save power
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'vcgencmd display_power 0 2>/dev/null || tvservice -o 2>/dev/null || true'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
HDMIEOF
systemctl daemon-reload
systemctl enable disable-hdmi 2>/dev/null || true

echo "  Power optimizations applied"

# --- Clone Repository ---
echo
echo "[5/9] Cloning PaperJam repository..."
if [ -d "$INSTALL_DIR" ]; then
    echo "  Directory exists, pulling latest..."
    cd "$INSTALL_DIR"
    git pull origin main || true
else
    git clone https://github.com/wjin-jang/paperjam.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi
chown -R $USER_NAME:$USER_NAME "$INSTALL_DIR"

# --- Python Virtual Environment ---
echo
echo "[6/9] Setting up Python environment..."
sudo -u $USER_NAME python3 -m venv "$INSTALL_DIR/venv"
sudo -u $USER_NAME "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo -u $USER_NAME "$INSTALL_DIR/venv/bin/pip" install \
    pillow mutagen python-vlc smbus2 evdev numpy spidev RPi.GPIO gpiozero pyyaml

# Symlink system packages into venv
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
VENV_SITE="$INSTALL_DIR/venv/lib/python$PYTHON_VERSION/site-packages"
ln -sf /usr/lib/python3/dist-packages/lgpio.py "$VENV_SITE/" 2>/dev/null || true
ln -sf /usr/lib/python3/dist-packages/_lgpio*.so "$VENV_SITE/" 2>/dev/null || true
ln -sf /usr/lib/python3/dist-packages/dbus "$VENV_SITE/" 2>/dev/null || true
ln -sf /usr/lib/python3/dist-packages/_dbus*.so "$VENV_SITE/" 2>/dev/null || true
ln -sf /usr/lib/python3/dist-packages/gi "$VENV_SITE/" 2>/dev/null || true

echo "  Python dependencies installed"

# --- Configuration ---
echo
echo "[7/9] Configuring PaperJam..."
CONFIG_DIR="$HOME_DIR/.config/paperjam"
mkdir -p "$CONFIG_DIR"
chown -R $USER_NAME:$USER_NAME "$HOME_DIR/.config"
CONFIG_FILE="$CONFIG_DIR/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    # Default config for headless install
    MUSIC_PATH="${MUSIC_PATH:-$HOME_DIR/Music}"

    cat > "$CONFIG_FILE" << EOFCONFIG
{
    "music_path": "$MUSIC_PATH",
    "screensaver_timeout": 45,
    "long_press_duration": 0.5,
    "recents_limit": 50,
    "invert_colors": false
}
EOFCONFIG
    chown $USER_NAME:$USER_NAME "$CONFIG_FILE"
    echo "  Configuration created at $CONFIG_FILE"
else
    echo "  Configuration already exists"
fi

# Create Music directory
mkdir -p "$HOME_DIR/Music"
chown $USER_NAME:$USER_NAME "$HOME_DIR/Music"

# --- Waveshare EPD Library ---
echo
echo "[8/9] Installing Waveshare e-Paper driver..."
cd "$INSTALL_DIR"
if [ ! -d "lib/waveshare" ]; then
    mkdir -p lib
    git clone https://github.com/waveshare/e-Paper.git "lib/waveshare"
fi
sudo -u $USER_NAME "$INSTALL_DIR/venv/bin/pip" install lib/waveshare/RaspberryPi_JetsonNano/python/
chown -R $USER_NAME:$USER_NAME "$INSTALL_DIR/lib"
echo "  Waveshare driver installed"

# --- Systemd Service ---
echo
echo "[9/9] Setting up auto-start service..."

# Get user ID for XDG_RUNTIME_DIR
USER_ID=$(id -u "$USER_NAME")

# Create system-level service (works without user login)
cat > /etc/systemd/system/paperjam.service << EOF
[Unit]
Description=PaperJam Music Player
After=local-fs.target sound.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=on-failure
RestartSec=5
Environment=HOME=$HOME_DIR
Environment=XDG_RUNTIME_DIR=/run/user/$USER_ID
Environment=DISPLAY=

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable paperjam

echo "  Service configured"

# --- Done ---
echo
echo "=========================================="
echo "  DietPi Installation Complete!"
echo "=========================================="
echo
echo "Music directory: $HOME_DIR/Music"
echo "Config file:     $CONFIG_FILE"
echo
echo "Commands:"
echo "  Start:   sudo systemctl start paperjam"
echo "  Stop:    sudo systemctl stop paperjam"
echo "  Logs:    journalctl -u paperjam -f"
echo "  Status:  sudo systemctl status paperjam"
echo
echo "Rebooting in 5 seconds to apply changes..."
sleep 5
reboot
