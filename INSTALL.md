# PaperJam Installation Guide

Complete installation guide for Raspberry Pi Zero 2 W running Debian Trixie (or Bookworm).

## Quick Install (Recommended)

For a fresh Raspberry Pi, use the automated install script:

```bash
# Download and run the install script
curl -fsSL https://raw.githubusercontent.com/wjin-jang/paperjam/main/install.sh | bash
```

Or if you prefer to review the script first:

```bash
# Download the script
curl -fsSL https://raw.githubusercontent.com/wjin-jang/paperjam/main/install.sh -o install.sh

# Review it
nano install.sh

# Make executable and run
chmod +x install.sh && ./install.sh
```

The script handles all system packages, permissions, Python environment, and service setup automatically. A reboot is required after installation.

---

## Manual Installation

Follow the steps below if you prefer manual installation or need to troubleshoot.

### 1. System Setup

#### Update System
```bash
sudo apt update && sudo apt upgrade -y
```

#### Install System Dependencies
```bash
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
```

#### PulseAudio Setup

PulseAudio is required for audio output switching and Bluetooth audio support.

```bash
# Enable and start PulseAudio as user service
systemctl --user enable pulseaudio
systemctl --user start pulseaudio

# Verify PulseAudio is running
pactl info
```

For Bluetooth audio support, ensure the bluetooth module is loaded:
```bash
# Check if bluetooth module is loaded
pactl list modules | grep bluetooth

# If not present, add to PulseAudio config
echo "load-module module-bluetooth-discover" >> ~/.config/pulse/default.pa
echo "load-module module-bluetooth-policy" >> ~/.config/pulse/default.pa

# Restart PulseAudio
pulseaudio -k
pulseaudio --start
```

For auto-start on login (if not using systemd user service):
```bash
# Add to ~/.bashrc or ~/.profile
echo "pulseaudio --start" >> ~/.bashrc
```

### 2. Enable Interfaces

##### Run raspi-config
```bash
sudo raspi-config
```

Enable the following under **Interface Options**:
- **I2C** - For battery monitoring (SugarPi 3)
- **SPI** - For e-Paper display

#### Enable and Unblock Bluetooth
```bash
# Enable bluetooth service
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Unblock bluetooth
sudo rfkill unblock bluetooth

# Verify bluetooth is up
rfkill list
```

#### Reboot
```bash
sudo reboot
```

### 3. User Permissions

Add your user to required groups for hardware access:

```bash
# I2C access (battery monitoring)
sudo usermod -aG i2c $USER

# GPIO access (buttons, display)
sudo usermod -aG gpio $USER

# SPI access (e-Paper display)
sudo usermod -aG spi $USER

# Bluetooth access
sudo usermod -aG bluetooth $USER

# Audio access
sudo usermod -aG audio $USER
```

Log out and back in (or reboot) for group changes to take effect:
```bash
sudo reboot
```

### 4. Verify Hardware

#### Check I2C
```bash
sudo i2cdetect -y 1
```
You should see `75` or similar where the SugarPi 3 is detected.

#### Check Bluetooth
```bash
bluetoothctl
# Type 'show' to see adapter info
# Type 'exit' to quit
```

#### Check SPI
```bash
ls /dev/spidev*
```
Should show `/dev/spidev0.0` and `/dev/spidev0.1`.

### 5. Python Virtual Environment

Debian Trixie requires virtual environments for pip packages.

#### Create Virtual Environment
```bash
cd ~
git clone https://github.com/wjin-jang/paperjam.git
cd paperjam

python3 -m venv venv
source venv/bin/activate
```

#### Install Python Dependencies
```bash
pip install --upgrade pip
pip install pillow mutagen python-vlc smbus2 evdev numpy
```

Dependencies overview:
- **pillow** - Image processing for album art and display rendering
- **mutagen** - Audio file metadata extraction (MP3, FLAC, etc.)
- **python-vlc** - VLC media player bindings for audio playback
- **smbus2** - I2C communication for battery monitoring (SugarPi 3)
- **evdev** - Linux input device handling (keyboard, remote, buttons)
- **numpy** - Numerical operations for image dithering

#### Install Waveshare e-Paper Driver
```bash
pip install waveshare-epd
```

Or install from source:
```bash
git clone https://github.com/waveshare/e-Paper.git
pip install e-Paper/RaspberryPi_JetsonNano/python/
```

### 6. Configure Music Directory

Edit `config.py` and set your music path:
```python
MUSIC_PATH = Path("/home/yourusername/Music")
```

Or create a symlink:
```bash
ln -s /path/to/your/music ~/paperjam/music
```

### 7. Running PaperJam

#### Activate Virtual Environment
```bash
cd ~/paperjam
source venv/bin/activate
```

#### Run
```bash
python main.py
```

### 8. Auto-Start on Boot (Optional)

#### Option A: User Service (Recommended for PulseAudio)

PulseAudio runs as a user service, so paperjam should also run as a user service to access audio:

```bash
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/paperjam.service
```

Add the following:
```ini
[Unit]
Description=PaperJam Music Player
After=pulseaudio.service

[Service]
Type=simple
WorkingDirectory=/home/yourusername/paperjam
ExecStart=/home/yourusername/paperjam/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable paperjam
systemctl --user start paperjam

# Enable user services to start at boot (without login)
sudo loginctl enable-linger yourusername
```

#### Option B: System Service (Uses ALSA fallback)

If PulseAudio isn't required, you can run as a system service. Audio will fall back to ALSA:

```bash
sudo nano /etc/systemd/system/paperjam.service
```

Add the following:
```ini
[Unit]
Description=PaperJam Music Player
After=multi-user.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/home/yourusername/paperjam
ExecStart=/home/yourusername/paperjam/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable paperjam
sudo systemctl start paperjam
```

#### Check Status
```bash
sudo systemctl status paperjam
```

#### View Logs
```bash
journalctl -u paperjam -f
```

### Troubleshooting

#### I2C Not Working
```bash
# Check if I2C is enabled
ls /dev/i2c*

# If not present, enable in raspi-config
sudo raspi-config
```

#### Bluetooth Not Finding Devices
```bash
# Check bluetooth status
systemctl status bluetooth

# Restart bluetooth
sudo systemctl restart bluetooth

# Check if blocked
rfkill list
sudo rfkill unblock bluetooth
```

#### Permission Denied Errors
```bash
# Re-add to groups
sudo usermod -aG i2c,gpio,spi,bluetooth,audio $USER

# Reboot
sudo reboot
```

### Display Not Working
```bash
# Check SPI is enabled
ls /dev/spidev*

# Check wiring connections
# Ensure correct Waveshare model in code (epd2in13_V4)
```
