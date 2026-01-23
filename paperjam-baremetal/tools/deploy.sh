#!/bin/bash
# PaperJam Bare-Metal OS - SD Card Deployment Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BOOT_DIR="$PROJECT_DIR/boot"

# Default mount point (Linux)
MOUNT_POINT="${1:-/media/$USER/boot}"

echo "PaperJam Bare-Metal OS Deployment"
echo "=================================="
echo ""

# Check if kernel exists
if [ ! -f "$BOOT_DIR/kernel8.img" ]; then
    echo "Error: kernel8.img not found. Run 'make' first."
    exit 1
fi

# Check mount point
if [ ! -d "$MOUNT_POINT" ]; then
    echo "Error: Mount point '$MOUNT_POINT' not found."
    echo "Usage: $0 [mount_point]"
    echo ""
    echo "Insert SD card and provide mount point."
    exit 1
fi

echo "Deploying to: $MOUNT_POINT"
echo ""

# Check for existing Raspberry Pi boot files
if [ -f "$MOUNT_POINT/bootcode.bin" ]; then
    echo "Found existing Raspberry Pi boot files."
else
    echo "Warning: No existing boot files found."
    echo "You may need to copy bootcode.bin, start.elf, fixup.dat from"
    echo "https://github.com/raspberrypi/firmware/tree/master/boot"
    echo ""
fi

# Copy boot files
echo "Copying boot files..."
cp -v "$BOOT_DIR/config.txt" "$MOUNT_POINT/"
cp -v "$BOOT_DIR/kernel8.img" "$MOUNT_POINT/"

# Create directories
echo "Creating directories..."
mkdir -p "$MOUNT_POINT/music"
mkdir -p "$MOUNT_POINT/data"

# Sync
echo "Syncing..."
sync

echo ""
echo "Deployment complete!"
echo ""
echo "Don't forget to:"
echo "1. Copy bootcode.bin, start.elf, fixup.dat if not present"
echo "2. Add music files to /music directory"
echo "3. Safely eject the SD card"
