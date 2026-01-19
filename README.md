# paperjam

E-ink music player for Raspberry Pi Zero 2 W.

## Hardware

- Raspberry Pi Zero 2 W
- Waveshare 2.13" e-Paper display (V4)
- SugarPi 3 battery module

## Features

### Music Player
- Browse by Artists, Albums, Tracks, or Files
- Favorite Artists and Albums with quick access
- User playlists with add/remove functionality
- Recently played tracks history
- Shuffle and loop modes (off, all, one)
- Album art display with dithered rendering
- Screensaver with random album art
- Endless playback mode - automatically plays random albums

### Library Management
- Automatic library scanning and caching
- Support for MP3, FLAC, WAV, M4A formats
- Track metadata extraction (title, artist, album, year, track number, disc number)
- Multi-disc album support with disc headings
- Alphabetical artist organization with quick-jump headings

### Audio
- VLC-based audio engine with PulseAudio support
- Audio output device switching (cycles through available devices)
- Volume control with on-screen display
- Bluetooth audio device pairing and management

### Connectivity
- WiFi status display and network switching
- Bluetooth device scanning, pairing, and management
- Status icons for connected devices (headphones, WiFi, Bluetooth)

### Display
- 1-bit monochrome e-paper display
- Partial refresh for smooth navigation
- Color inversion option
- Configurable screensaver timeout
- Battery level indicator with charging status
- Low battery auto-shutdown protection

### Settings
- Audio output selection
- Endless playback toggle
- Volume control
- Library rescan
- Recent tracks limit
- Color inversion
- Screensaver timeout
- WiFi toggle
- Bluetooth toggle
- CPU power mode (normal/powersave)
- Long press duration
- Screen clear shutdown (for screen removal)
- System restart

### Input
- Multi-device support (keyboard, remote, media keys)
- Long press detection for context menus
- Debounced input handling

## Logs

Application logs are stored at:
```
~/.cache/paperjam/paperjam.log
```

To view logs in real-time:
```bash
tail -f ~/.cache/paperjam/paperjam.log
```

## Installation

See [INSTALL.md](INSTALL.md) for complete setup instructions including:
- System configuration (I2C, SPI, Bluetooth)
- User permissions
- PulseAudio setup
- Virtual environment setup
- Auto-start on boot

## Version

1.0
