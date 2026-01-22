#!/bin/bash
# PaperJam OS - Post-image script
# Runs after all filesystem images are built, creates final SD card image

set -e

BOARD_DIR="$(dirname "$0")"
GENIMAGE_CFG="${BOARD_DIR}/genimage.cfg"
GENIMAGE_TMP="${BUILD_DIR}/genimage.tmp"

echo "=== PaperJam OS Post-Image ==="

# Remove old genimage temp directory
rm -rf "${GENIMAGE_TMP}"

# Generate SD card image
genimage \
    --rootpath "${TARGET_DIR}" \
    --tmppath "${GENIMAGE_TMP}" \
    --inputpath "${BINARIES_DIR}" \
    --outputpath "${BINARIES_DIR}" \
    --config "${GENIMAGE_CFG}"

# Compress the image for distribution
if [ -f "${BINARIES_DIR}/sdcard.img" ]; then
    echo "Compressing SD card image..."
    gzip -9 -k -f "${BINARIES_DIR}/sdcard.img"

    # Calculate checksums
    cd "${BINARIES_DIR}"
    sha256sum sdcard.img > sdcard.img.sha256
    sha256sum sdcard.img.gz > sdcard.img.gz.sha256

    # Print image info
    echo ""
    echo "=== Build Complete ==="
    echo "Image: ${BINARIES_DIR}/sdcard.img"
    echo "Compressed: ${BINARIES_DIR}/sdcard.img.gz"
    echo "Size: $(du -h sdcard.img | cut -f1)"
    echo "Compressed size: $(du -h sdcard.img.gz | cut -f1)"
    echo ""
    echo "Flash with:"
    echo "  gunzip -c sdcard.img.gz | sudo dd of=/dev/sdX bs=4M status=progress"
    echo "  sync"
fi

echo "=== Post-Image Complete ==="
