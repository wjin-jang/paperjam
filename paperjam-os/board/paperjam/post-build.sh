#!/bin/bash
# PaperJam OS - Post-build script
# Runs after rootfs is built, before image creation

set -e

BOARD_DIR="$(dirname "$0")"
TARGET_DIR="$1"

echo "=== PaperJam OS Post-Build ==="

# Copy cmdline.txt to staging area for genimage
mkdir -p "${BINARIES_DIR}/rpi-firmware"
cp "${BOARD_DIR}/cmdline.txt" "${BINARIES_DIR}/rpi-firmware/"
cp "${BOARD_DIR}/config.txt" "${BINARIES_DIR}/rpi-firmware/"

# Set init scripts as executable
chmod +x "${TARGET_DIR}/etc/init.d/"* 2>/dev/null || true

# Create symbolic links for compatibility
mkdir -p "${TARGET_DIR}/var/log"
mkdir -p "${TARGET_DIR}/var/run"
mkdir -p "${TARGET_DIR}/var/tmp"

# Create device nodes (mdev will handle most, but ensure critical ones exist)
mkdir -p "${TARGET_DIR}/dev"

# Set correct permissions on user directories
if [ -d "${TARGET_DIR}/home/paperjam" ]; then
    # Will be properly set by Buildroot user management, but ensure directories exist
    mkdir -p "${TARGET_DIR}/home/paperjam/.config/paperjam"
    mkdir -p "${TARGET_DIR}/home/paperjam/.cache/paperjam"
fi

# Remove unnecessary files to reduce image size
rm -rf "${TARGET_DIR}/usr/share/doc" 2>/dev/null || true
rm -rf "${TARGET_DIR}/usr/share/man" 2>/dev/null || true
rm -rf "${TARGET_DIR}/usr/share/info" 2>/dev/null || true
rm -rf "${TARGET_DIR}/usr/share/locale" 2>/dev/null || true

# Keep only required locales for paperjam
mkdir -p "${TARGET_DIR}/usr/share/locale"

# Remove Python bytecode cache (will be regenerated at runtime)
find "${TARGET_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "${TARGET_DIR}" -name "*.pyc" -delete 2>/dev/null || true

# Strip binaries for smaller image (Buildroot usually handles this)
# But ensure Python libraries aren't stripped
find "${TARGET_DIR}/usr/bin" -type f -executable -exec strip --strip-unneeded {} 2>/dev/null \; || true

# Create VERSION file
echo "PaperJam OS v1.0.0" > "${TARGET_DIR}/etc/paperjam-version"
echo "Built: $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "${TARGET_DIR}/etc/paperjam-version"

# Ensure /etc/shadow has correct permissions
chmod 600 "${TARGET_DIR}/etc/shadow" 2>/dev/null || true

# Create music directory mount point
mkdir -p "${TARGET_DIR}/mnt/music"

echo "=== Post-Build Complete ==="
