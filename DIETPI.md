# DietPi Headless Installation Guide

Complete headless setup for PaperJam on Raspberry Pi Zero 2 W using DietPi.
No monitor, no keyboard, no SSH required.

## Requirements

- Raspberry Pi Zero 2 W
- microSD card (8GB+)
- Computer with SD card reader
- WiFi network (for initial setup)

## Step 1: Download DietPi

Download the **ARMv8 64-bit** image for Raspberry Pi Zero 2 W:

```
https://dietpi.com/downloads/images/DietPi_RPi-ARMv8-Bookworm.img.xz
```

## Step 2: Flash to SD Card

Use one of these tools:
- **Raspberry Pi Imager** (easiest)
- **balenaEtcher**
- **Win32DiskImager** (Windows)

Flash the `.img.xz` file directly (no need to extract).

## Step 3: Configure Boot Files

After flashing, the SD card will have a `boot` partition. Open it and edit these files:

### 3a. Edit `dietpi.txt`

Find and change these lines:

```ini
# Auto-setup without prompts
AUTO_SETUP_AUTOMATED=1
AUTO_SETUP_ACCEPT_LICENSE=1

# Locale (change if needed)
AUTO_SETUP_LOCALE=en_US.UTF-8
AUTO_SETUP_KEYBOARD_LAYOUT=us
AUTO_SETUP_TIMEZONE=America/New_York

# WiFi (your network)
AUTO_SETUP_NET_WIFI_ENABLED=1
AUTO_SETUP_NET_WIFI_COUNTRY_CODE=US

# Hostname
AUTO_SETUP_NET_HOSTNAME=paperjam

# Disable serial console (we use GPIO)
AUTO_SETUP_ENABLE_SERIAL_CONSOLE=0

# Skip SSH server (saves power)
AUTO_SETUP_SSH_SERVER_INDEX=0

# No desktop
AUTO_SETUP_AUTOMATED_BOOT_INDEX=0

# Default passwords (change these!)
AUTO_SETUP_GLOBAL_PASSWORD=paperjam
SOFTWARE_DISABLE_SSH_PASSWORD_LOGINS=0

# Auto-install software IDs:
#   5=ALSA, 17=Git, 130=Python3
AUTO_SETUP_INSTALL_SOFTWARE_ID=5
AUTO_SETUP_INSTALL_SOFTWARE_ID=17
AUTO_SETUP_INSTALL_SOFTWARE_ID=130

# Run custom script after setup
AUTO_SETUP_CUSTOM_SCRIPT_EXEC=1
```

### 3b. Edit `dietpi-wifi.txt`

Add your WiFi credentials:

```ini
aWIFI_SSID[0]='YourWiFiName'
aWIFI_KEY[0]='YourWiFiPassword'
```

### 3c. Create `Automation_Custom_Script.sh`

Create this new file in the boot partition (same folder as `dietpi.txt`):

```bash
#!/bin/bash
# PaperJam auto-installer for DietPi

# Download and run the install script
curl -fsSL https://raw.githubusercontent.com/wjin-jang/paperjam/main/install-dietpi.sh | bash
```

Make sure to save with Unix line endings (LF, not CRLF).

## Step 4: Copy Music (Optional)

Create a `Music` folder on the boot partition and add some music files.
The installer will move them to the correct location.

Or skip this and copy music later via USB drive.

## Step 5: First Boot

1. Insert SD card into Pi Zero 2 W
2. Connect power
3. Wait 10-15 minutes for:
   - DietPi first-boot setup
   - Package installation
   - PaperJam installation
   - Automatic reboot

The e-ink display will show the UI once everything is ready.

## Step 6: Add Music

### Option A: USB Drive
1. Format USB drive as FAT32 or exFAT
2. Create a `Music` folder with your files
3. Plug into Pi Zero 2 W
4. In PaperJam settings, select "Rescan Library"

### Option B: Copy via Network (if WiFi connected)
```bash
# From another computer on same network:
scp -r ~/Music/* dietpi@paperjam.local:/home/dietpi/Music/
```

### Option C: Direct SD Card Access
1. Power off Pi
2. Remove SD card
3. On computer, copy files to `/home/dietpi/Music/` (ext4 partition)
4. Re-insert and boot

## Troubleshooting

### Display not working
- Check SPI wiring
- Verify `/dev/spidev0.0` exists: `ls /dev/spi*`
- Check logs: `journalctl -u paperjam`

### No audio
- Check 3.5mm jack connection
- Test: `aplay /usr/share/sounds/alsa/Front_Center.wav`

### Check service status
```bash
sudo systemctl status paperjam
journalctl -u paperjam -f
```

### Manual start for debugging
```bash
sudo systemctl stop paperjam
cd /home/dietpi/paperjam
source venv/bin/activate
python main.py
```

## Power Consumption

DietPi with PaperJam optimizations:

| State | Current Draw |
|-------|-------------|
| Idle (display sleeping) | ~80mA |
| Menu browsing | ~120mA |
| Music playback | ~150mA |
| WiFi active | ~180mA |

With 1200mAh PiSugar battery:
- ~8 hours playback
- ~15 hours idle

## Updating PaperJam

```bash
cd /home/dietpi/paperjam
git pull
sudo systemctl restart paperjam
```

## Factory Reset

Reflash the SD card and repeat setup.
