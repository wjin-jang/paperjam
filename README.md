# PaperJam

E-ink music player for Raspberry Pi Zero 2 W.

## Hardware

- Raspberry Pi Zero 2 W
- Waveshare 2.13" e-Paper display (V4)
- PiSugar 3 battery module

## Features

- **Music Player** - Browse by artist, album, track, or file. Favorites, playlists, shuffle, loop, and endless playback modes.
- **Library** - Auto-scanning with metadata extraction. Supports MP3, FLAC, WAV, M4A.
- **Audio** - VLC engine with PulseAudio. Bluetooth and wired audio output.
- **Display** - 1-bit e-paper with partial refresh. Album art, status icons, screensaver.
- **Input** - Keyboard, IR remote, media keys, and PiSugar button. Long-press for context menus.

## Quick Start

```bash
# Install (fresh Raspberry Pi)
curl -fsSL https://raw.githubusercontent.com/wjin-jang/paperjam/main/install.sh | bash

# Or run manually
cd ~/paperjam
source venv/bin/activate
python main.py
```

## Service

```bash
systemctl --user start paperjam     # Start
systemctl --user stop paperjam      # Stop
systemctl --user status paperjam    # Status
```

## Logs

```bash
tail -f ~/.cache/paperjam/paperjam.log
```

## Update

```bash
cd ~/paperjam && ./update.sh
```

## Configuration

Config file: `~/.config/paperjam/config.json`

```json
{
    "music_path": "/home/pi/Music",
    "screensaver_timeout": 60,
    "invert_colors": false
}
```

## Documentation

- [Installation Guide](INSTALL.md)
- [Architecture](ARCHITECTURE.md)
