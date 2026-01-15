# PaperJam Installation Guide

Installation guide for Raspberry Pi Zero 2 W running Debian Bookworm or Trixie.

## Quick Install (Recommended)

For a fresh Raspberry Pi, use the automated install script:

```bash
curl -fsSL https://raw.githubusercontent.com/wjin-jang/paperjam/main/install.sh | bash
```

Or review before running:

```bash
curl -fsSL https://raw.githubusercontent.com/wjin-jang/paperjam/main/install.sh -o install.sh
nano install.sh
chmod +x install.sh && ./install.sh
```

The script handles everything automatically. A reboot is required after installation.

---

## Manual Installation

### 1. System Packages

```bash
sudo apt update && sudo apt upgrade -y
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
```

### 2. Enable Interfaces

Run `sudo raspi-config` and enable under **Interface Options**:
- **I2C** - Battery monitoring (PiSugar 3)
- **SPI** - E-Paper display

Or add directly to config:
```bash
# Determine config location (Bookworm uses /boot/firmware/, older uses /boot/)
BOOT_CONFIG="/boot/firmware/config.txt"
[ ! -f "$BOOT_CONFIG" ] && BOOT_CONFIG="/boot/config.txt"

# Enable I2C and SPI
sudo bash -c "grep -q '^dtparam=i2c_arm=on' $BOOT_CONFIG || echo 'dtparam=i2c_arm=on' >> $BOOT_CONFIG"
sudo bash -c "grep -q '^dtparam=spi=on' $BOOT_CONFIG || echo 'dtparam=spi=on' >> $BOOT_CONFIG"
```

### 3. Enable Bluetooth

```bash
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
sudo rfkill unblock bluetooth
```

### 4. User Permissions

```bash
sudo usermod -aG i2c,gpio,spi,bluetooth,audio $USER
sudo reboot
```

### 5. Verify Hardware

After reboot:
```bash
# I2C - should show device at 0x57 (PiSugar 3)
sudo i2cdetect -y 1

# SPI - should show /dev/spidev0.0 and /dev/spidev0.1
ls /dev/spidev*

# Bluetooth
bluetoothctl show
```

### 6. Clone Repository

```bash
cd ~
git clone https://github.com/wjin-jang/paperjam.git
cd paperjam
```

### 7. Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install pillow mutagen python-vlc smbus2 evdev numpy spidev RPi.GPIO gpiozero pykakasi korean_romanizer

# Symlink system lgpio into venv (can't be pip installed)
# Get the exact Python version for the correct site-packages path
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
VENV_SITE="$HOME/paperjam/venv/lib/python$PYTHON_VERSION/site-packages"
ln -sf /usr/lib/python3/dist-packages/lgpio.py "$VENV_SITE/"
ln -sf /usr/lib/python3/dist-packages/_lgpio*.so "$VENV_SITE/" 2>/dev/null || true
```

Dependencies:
- **pillow** - Image processing for display rendering
- **mutagen** - Audio metadata extraction (MP3, FLAC, etc.)
- **python-vlc** - VLC media player bindings
- **smbus2** - I2C for battery monitoring
- **evdev** - Input device handling
- **numpy** - Image dithering
- **spidev** - SPI communication for e-paper display
- **RPi.GPIO** - GPIO access for Raspberry Pi
- **gpiozero** - GPIO interface (required by Waveshare driver)
- **lgpio** - GPIO backend for gpiozero (system package, symlinked)
- **pykakasi** - Japanese text romanization (optional, for Japanese metadata)
- **korean_romanizer** - Korean text romanization (optional, for Korean metadata)

### 8. Waveshare e-Paper Driver

Install from source (recommended):
```bash
mkdir -p lib
git clone https://github.com/waveshare/e-Paper.git lib/waveshare
pip install lib/waveshare/RaspberryPi_JetsonNano/python/
```

**Note:** Installing from source is recommended as it ensures compatibility with your specific display model.

### 9. Configure PaperJam

Create the config directory and configuration file:

```bash
mkdir -p ~/.config/paperjam
```

For manual configuration, create `~/.config/paperjam/config.json`:

```json
{
    "music_path": "/home/YOUR_USERNAME/Music",
    "screensaver_timeout": 60,
    "long_press_duration": 0.5,
    "recents_limit": 50,
    "invert_colors": false
}
```

Replace `YOUR_USERNAME` with your actual username (run `whoami` to check). The font settings are optional and use built-in defaults.

### 10. Run Manually

```bash
cd ~/paperjam
source venv/bin/activate
python main.py
```

---

## Auto-Start Service

PaperJam should run as a user service to access PulseAudio:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/paperjam.service << 'EOF'
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
sudo loginctl enable-linger $USER
```

Service commands:
```bash
systemctl --user start paperjam      # Start
systemctl --user stop paperjam       # Stop
systemctl --user status paperjam     # Status
journalctl --user -u paperjam -f     # Logs
```

---

## Troubleshooting

### I2C Not Working
```bash
ls /dev/i2c*              # Check device exists
sudo i2cdetect -y 1       # Scan for devices
sudo raspi-config         # Enable I2C if missing
```

### SPI/Display Not Working
```bash
ls /dev/spidev*           # Check SPI devices exist
# Verify wiring and display model (epd2in13_V4)
```

### Bluetooth Issues
```bash
systemctl status bluetooth
sudo systemctl restart bluetooth
rfkill list               # Check if blocked
sudo rfkill unblock bluetooth
```

### Permission Denied
```bash
sudo usermod -aG i2c,gpio,spi,bluetooth,audio $USER
sudo reboot
```

### No Audio
```bash
pactl info                # Check PulseAudio
systemctl --user status pulseaudio
systemctl --user start pulseaudio
```
