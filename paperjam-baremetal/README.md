# PaperJam Bare-Metal OS

A bare-metal music player operating system for Raspberry Pi Zero 2 W with e-paper display. No Linux, no dependencies - just pure C running directly on the hardware.

## Features

- **Music Playback**: MP3, FLAC, and WAV audio formats
- **E-Paper Display**: 250x122 1-bit display with partial refresh for responsive UI
- **Battery Powered**: PiSugar 3 integration with low-battery shutdown
- **Physical Controls**: 9 GPIO buttons with long-press actions
- **Library Management**: Automatic music scanning with metadata extraction
- **Queue & Playlists**: Full queue management with shuffle and repeat modes
- **Favorites**: Mark and quickly access favorite tracks
- **Settings Persistence**: User preferences saved to SD card
- **Power Efficient**: WFI sleep, display sleep, cooperative scheduling

## Hardware Requirements

| Component | Specification |
|-----------|---------------|
| Board | Raspberry Pi Zero 2 W |
| CPU | BCM2710, ARM Cortex-A53 (quad-core) |
| RAM | 512 MB |
| Display | Waveshare 2.13" e-paper (250x122, SPI) |
| Battery | PiSugar 3 (1200mAh, I2C) |
| Storage | MicroSD card (FAT32) |
| Audio | PWM output on GPIO 18 |

### Pin Connections

**E-Paper Display (SPI)**
| Pin | GPIO | Function |
|-----|------|----------|
| RST | 17 | Reset |
| DC | 25 | Data/Command |
| CS | 8 | Chip Select (CE0) |
| BUSY | 24 | Busy signal |
| CLK | 11 | SPI Clock |
| DIN | 10 | SPI MOSI |

**PiSugar 3 Battery**
| Bus | Address | Function |
|-----|---------|----------|
| I2C1 | 0x57 | Battery monitor (IP5312) |

**Buttons (Active Low, Internal Pull-up)**
| GPIO | Button | Short Press | Long Press |
|------|--------|-------------|------------|
| 4 | Play | Play/Pause | Show Queue |
| 5 | Prev | Seek -10s | Settings |
| 6 | Next | Seek +10s | Browse |
| 12 | Up | Navigate Up | - |
| 13 | Down | Navigate Down | - |
| 16 | Enter | Select | Context Menu |
| 19 | Back | Go Back | Home |
| 20 | Vol+ | Volume Up | - (repeat) |
| 21 | Vol- | Volume Down | - (repeat) |

## Project Structure

```
paperjam-baremetal/
├── boot/                   # Boot files for SD card
│   ├── config.txt          # RPi boot configuration
│   └── kernel8.img         # Compiled kernel (output)
├── src/
│   ├── boot/               # Startup assembly code
│   │   ├── start.S         # Entry point, vector table
│   │   └── exceptions.S    # IRQ/exception handlers
│   ├── hal/                # Hardware Abstraction Layer
│   │   ├── bcm2837.h       # BCM2837 register definitions
│   │   ├── gpio.c          # GPIO driver
│   │   ├── timer.c         # System timer
│   │   ├── uart.c          # Mini UART (debug)
│   │   ├── spi.c           # SPI master
│   │   ├── i2c.c           # I2C (BSC)
│   │   ├── pwm.c           # PWM audio
│   │   ├── irq.c           # Interrupt controller
│   │   └── mmc.c           # SD/MMC driver
│   ├── drivers/            # Device drivers
│   │   ├── epd_2in13_v4.c  # E-paper display
│   │   ├── pisugar3.c      # Battery monitor
│   │   ├── buttons.c       # GPIO buttons
│   │   └── audio.c         # Audio output
│   ├── fs/                 # Filesystem
│   │   └── diskio.c        # FatFS disk I/O
│   ├── audio/              # Audio subsystem
│   │   ├── playback.c      # Playback engine
│   │   ├── mp3_decoder.c   # MP3 decoder (libmad)
│   │   ├── flac_decoder.c  # FLAC decoder (dr_flac)
│   │   ├── wav_decoder.c   # WAV decoder (dr_wav)
│   │   ├── id3.c           # ID3 tag parser
│   │   └── flac_meta.c     # FLAC metadata parser
│   ├── gfx/                # Graphics
│   │   ├── framebuffer.c   # 1-bit framebuffer
│   │   ├── fonts.c         # Bitmap fonts
│   │   ├── text.c          # Text rendering
│   │   ├── dither.c        # Image dithering
│   │   ├── icons.c         # UI icons
│   │   └── jpeg.c          # JPEG decoder
│   ├── ui/                 # User interface
│   │   ├── renderer.c      # Main UI renderer
│   │   ├── menu.c          # Menu system
│   │   ├── music_view.c    # Now playing view
│   │   ├── browse_view.c   # File browser
│   │   ├── settings_view.c # Settings screen
│   │   ├── context_menu.c  # Popup menus
│   │   ├── volume_overlay.c# Volume popup
│   │   └── screensaver.c   # Screensaver
│   ├── app/                # Application logic
│   │   ├── player.c        # Music player
│   │   ├── library.c       # Library scanner
│   │   ├── playlist.c      # Queue management
│   │   ├── favorites.c     # Favorites system
│   │   └── settings.c      # Settings persistence
│   ├── sys/                # System services
│   │   ├── heap.c          # Memory allocator
│   │   ├── scheduler.c     # Cooperative scheduler
│   │   └── power.c         # Power management
│   └── main.c              # Kernel entry point
├── lib/                    # Third-party libraries
│   ├── fatfs/              # FatFS filesystem
│   ├── libmad/             # MP3 decoder (optional)
│   └── dr_libs/            # dr_flac, dr_wav headers
├── tools/                  # Build tools
│   ├── mkfont.py           # Font compiler
│   └── deploy.sh           # SD card deploy script
├── Makefile
├── linker.ld
├── README.md
├── INSTALL.md
└── TODO.md
```

## Building

### Prerequisites

- ARM AArch64 bare-metal toolchain (`aarch64-none-elf-gcc`)
- GNU Make

### Compile

```bash
make clean
make
```

This produces `boot/kernel8.img`.

### Deploy

See [INSTALL.md](INSTALL.md) for detailed deployment instructions.

## Usage

### Controls

| Action | Button |
|--------|--------|
| Play/Pause | PLAY |
| Previous/Seek Back | PREV |
| Next/Seek Forward | NEXT |
| Navigate | UP / DOWN |
| Select | ENTER |
| Go Back | BACK |
| Volume | VOL+ / VOL- |

### Long Press Actions

| Action | Button (hold 500ms) |
|--------|---------------------|
| Show Queue | PLAY |
| Open Settings | PREV |
| Browse Files | NEXT |
| Context Menu | ENTER |
| Return Home | BACK |

### File Organization

Place music files on the SD card:
```
/music/
├── Artist 1/
│   ├── Album 1/
│   │   ├── 01 Track.mp3
│   │   └── 02 Track.flac
│   └── Album 2/
└── Artist 2/
```

Supported formats: `.mp3`, `.flac`, `.wav`

## Architecture

### Memory Map

| Address | Size | Description |
|---------|------|-------------|
| 0x00000000 | 256 KB | GPU/VC memory |
| 0x00080000 | ~2 MB | Kernel code & data |
| 0x00280000 | ~1 MB | Heap |
| 0x00380000 | 64 KB | Stack |
| 0x3F000000 | 16 MB | Peripheral registers |

### Boot Sequence

1. GPU loads `kernel8.img` to 0x80000
2. `start.S` initializes CPU, transitions EL2 -> EL1
3. BSS cleared, stack set up
4. `kernel_main()` called
5. Hardware initialized (GPIO, SPI, I2C, PWM, MMC)
6. Filesystem mounted
7. Application initialized (library scan, settings load)
8. Main loop via cooperative scheduler

### Scheduler

Cooperative multitasking with prioritized tasks:
- Audio playback (5ms interval) - highest priority
- Button polling (10ms interval)
- UI update (50ms interval)

CPU enters WFI (Wait For Interrupt) when idle for power saving.

## Power Consumption

| State | Current | Battery Life* |
|-------|---------|---------------|
| Active playback | ~160mA | ~7.5 hours |
| Idle (display on) | ~120mA | ~10 hours |
| Screensaver | ~60mA | ~20 hours |

*Estimated with 1200mAh PiSugar 3 battery

## Documentation

- [README.md](README.md) - This file
- [INSTALL.md](INSTALL.md) - Build and installation guide
- [TODO.md](TODO.md) - Development roadmap and known issues

## License

MIT License - See LICENSE file for details.

## Credits

- [FatFS](http://elm-chan.org/fsw/ff/) - FAT filesystem by ChaN
- [libmad](https://www.underbit.com/products/mad/) - MPEG audio decoder
- [dr_libs](https://github.com/mackron/dr_libs) - Single-file audio decoders
- Raspberry Pi Foundation - Hardware documentation
