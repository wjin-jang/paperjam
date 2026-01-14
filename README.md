# paperjam

E-ink music player for Raspberry Pi Zero 2 W.

## Hardware

- Raspberry Pi Zero 2 W
- Waveshare 2.13" e-Paper display (V4)
- SugarPi 3 battery module

## Quick Start

```bash
# Clone repository
git clone https://github.com/wjin-jang/paperjam.git
cd paperjam

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pillow mutagen python-vlc smbus2 waveshare-epd

# Run
python main.py
```

## Installation

See [INSTALL.md](INSTALL.md) for complete setup instructions including:
- System configuration (I2C, SPI, Bluetooth)
- User permissions
- Virtual environment setup
- Auto-start on boot