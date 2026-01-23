# Installation Guide

This guide covers building and deploying PaperJam Bare-Metal OS to your Raspberry Pi Zero 2 W.

## Prerequisites

### Hardware

- Raspberry Pi Zero 2 W
- Waveshare 2.13" e-paper display (V4)
- PiSugar 3 battery module
- MicroSD card (8GB+ recommended, FAT32)
- Push buttons (9x) with pull-up resistors or internal pull-ups
- 3.5mm audio jack or speaker connected to GPIO 18

### Software

- ARM AArch64 bare-metal toolchain
- GNU Make
- Python 3 (for font tools)

## Toolchain Setup

### Windows

1. Download the ARM GNU Toolchain from [ARM Developer](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)
2. Select "AArch64 bare-metal target (aarch64-none-elf)"
3. Install and add to PATH

```cmd
# Verify installation
aarch64-none-elf-gcc --version
```

### Linux (Ubuntu/Debian)

```bash
# Option 1: Install Linux cross-compiler (easiest, works for bare-metal)
sudo apt update
sudo apt install gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu

# Option 2: Download ARM's official bare-metal toolchain
cd /tmp
wget https://developer.arm.com/-/media/Files/downloads/gnu/13.2.rel1/binrel/arm-gnu-toolchain-13.2.rel1-x86_64-aarch64-none-elf.tar.xz
sudo tar -xf arm-gnu-toolchain-13.2.rel1-x86_64-aarch64-none-elf.tar.xz -C /opt/
echo 'export PATH=$PATH:/opt/arm-gnu-toolchain-13.2.Rel1-x86_64-aarch64-none-elf/bin' >> ~/.bashrc
source ~/.bashrc

# If using Option 2, build with:
make CROSS=aarch64-none-elf-
```

### macOS

```bash
# Using Homebrew
brew install --cask gcc-aarch64-embedded

# Or download from ARM website
```

## Building

### Clone Repository

```bash
git clone https://github.com/yourusername/paperjam.git
cd paperjam/paperjam-baremetal
```

### Download Dependencies

#### FatFS (Required)

Download FatFS from [elm-chan.org](http://elm-chan.org/fsw/ff/00index_e.html):

```bash
cd lib/fatfs
# Download and extract ff15.zip (or latest)
# Copy ff.c, ff.h, diskio.h to this directory
# ffconf.h is already configured
```

#### libmad (Optional, for MP3)

For full MP3 support, integrate libmad:

```bash
cd lib/libmad
# Download from https://www.underbit.com/products/mad/
# Configure for bare-metal ARM
```

### Compile

```bash
make clean
make
```

Successful build outputs:
```
Built boot/kernel8.img - 245760 bytes
```

### Build Options

```bash
# Debug build with UART output
make DEBUG=1

# Release build (optimized)
make RELEASE=1

# Generate disassembly
make disasm
```

## SD Card Preparation

### 1. Format SD Card

Format as FAT32 with MBR partition table:

**Windows:**
- Use SD Card Formatter or Disk Management
- Select FAT32, default allocation unit size

**Linux:**
```bash
# Replace /dev/sdX with your SD card
sudo fdisk /dev/sdX
# Create new MBR partition table (o)
# Create new primary partition (n, p, 1, enter, enter)
# Set type to FAT32 (t, c)
# Write (w)

sudo mkfs.vfat -F 32 /dev/sdX1
```

**macOS:**
```bash
diskutil eraseDisk FAT32 BOOT MBRFormat /dev/diskN
```

### 2. Copy Boot Files

Download Raspberry Pi firmware files:

```bash
# Download from https://github.com/raspberrypi/firmware/tree/master/boot
# Required files:
# - bootcode.bin
# - start.elf
# - fixup.dat
```

Copy to SD card root:
```
/bootcode.bin
/start.elf
/fixup.dat
/config.txt      (from boot/ directory)
/kernel8.img     (compiled kernel)
```

### 3. Create Directory Structure

```bash
mkdir /media/BOOT/music
mkdir /media/BOOT/data
```

### 4. Copy Music Files

```bash
cp -r ~/Music/* /media/BOOT/music/
```

Recommended organization:
```
/music/
├── Artist Name/
│   ├── Album Name/
│   │   ├── 01 - Track.mp3
│   │   ├── 02 - Track.flac
│   │   └── cover.jpg
```

## Configuration

### config.txt

The `boot/config.txt` file configures the Raspberry Pi:

```ini
# 64-bit mode
arm_64bit=1

# Our kernel
kernel=kernel8.img

# Minimal GPU memory (we don't use GPU)
gpu_mem=16

# Enable required interfaces
dtparam=i2c_arm=on
dtparam=spi=on

# Disable unused features for power saving
dtoverlay=disable-bt
dtoverlay=disable-wifi

# Audio output via PWM
dtparam=audio=off
```

### Hardware Wiring

#### E-Paper Display

Connect to SPI0:
| E-Paper | RPi GPIO | Pin |
|---------|----------|-----|
| VCC | 3.3V | 1 |
| GND | GND | 6 |
| DIN | GPIO 10 (MOSI) | 19 |
| CLK | GPIO 11 (SCLK) | 23 |
| CS | GPIO 8 (CE0) | 24 |
| DC | GPIO 25 | 22 |
| RST | GPIO 17 | 11 |
| BUSY | GPIO 24 | 18 |

#### Buttons

Connect buttons between GPIO and GND (internal pull-ups enabled):
| Function | GPIO | Pin |
|----------|------|-----|
| Play/Pause | 4 | 7 |
| Previous | 5 | 29 |
| Next | 6 | 31 |
| Up | 12 | 32 |
| Down | 13 | 33 |
| Enter | 16 | 36 |
| Back | 19 | 35 |
| Volume Up | 20 | 38 |
| Volume Down | 21 | 40 |

#### Audio Output

Connect to GPIO 18 (Pin 12):
- Use a low-pass filter (RC circuit) for cleaner audio
- Recommended: 1K resistor + 100nF capacitor to ground
- Connect to amplifier or powered speakers

#### PiSugar 3

The PiSugar 3 connects via the pogo pins to the RPi's I2C and power pins. No additional wiring needed if using the standard PiSugar 3 board.

## First Boot

1. Insert SD card into Raspberry Pi
2. Connect display and buttons
3. Power on via PiSugar or USB

### Boot Sequence

1. **GPU LED blinks** - Firmware loading
2. **Display initializes** - "PaperJam v1.0" splash
3. **Library scan** - Scans /music directory
4. **Ready** - Now playing screen appears

### Debugging

Connect a USB-to-Serial adapter for UART output:
| UART | RPi GPIO | Pin |
|------|----------|-----|
| TX | GPIO 14 | 8 |
| RX | GPIO 15 | 10 |
| GND | GND | 6 |

Serial settings: 115200 baud, 8N1

```bash
# Linux
screen /dev/ttyUSB0 115200

# Windows
# Use PuTTY or similar
```

## Troubleshooting

### Display Not Working

1. Check SPI connections
2. Verify config.txt has `dtparam=spi=on`
3. Check BUSY pin - should go LOW when ready

### No Audio

1. Check GPIO 18 connection
2. Verify audio files are valid MP3/FLAC/WAV
3. Check volume setting (not muted)

### SD Card Not Detected

1. Ensure FAT32 format
2. Check card is properly seated
3. Try a different SD card (some have compatibility issues)

### Buttons Not Responding

1. Check GPIO connections
2. Verify buttons connect to GND when pressed
3. Internal pull-ups should be enabled automatically

### Battery Not Detected

1. Check PiSugar 3 is properly connected
2. I2C address should be 0x57
3. Verify config.txt has `dtparam=i2c_arm=on`

## Updating

To update the kernel:

1. Build new kernel: `make`
2. Copy `boot/kernel8.img` to SD card
3. Reboot

Settings and favorites are preserved in `/data/`.

## Uninstalling

Simply format the SD card or use it for another purpose. PaperJam makes no permanent changes to the Raspberry Pi hardware.
