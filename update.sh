#!/bin/bash
# PaperJam Update Script
# Updates from GitHub and restarts the service if running

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== PaperJam Updater ==="

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "Warning: You have uncommitted local changes."
    read -p "Stash changes and continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git stash
        STASHED=1
    else
        echo "Aborted."
        exit 1
    fi
fi

# Pull latest changes
echo "Pulling latest changes..."
git pull origin main

# Update dependencies if requirements changed
if [ -f "venv/bin/pip" ]; then
    echo "Checking dependencies..."
    venv/bin/pip install --quiet --upgrade pillow mutagen python-vlc smbus2 evdev numpy 2>/dev/null || true
fi

# Restore stashed changes if any
if [ "$STASHED" = "1" ]; then
    echo "Restoring local changes..."
    git stash pop || true
fi

# Restart service if running
# Set up environment for user services (needed when running via SSH/script)
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"

if systemctl --user is-active --quiet paperjam 2>/dev/null; then
    echo "Restarting user service..."
    systemctl --user restart paperjam
    echo "Service restarted."
elif systemctl is-active --quiet paperjam 2>/dev/null; then
    echo "Restarting system service..."
    sudo systemctl restart paperjam
    echo "Service restarted."
else
    echo "No service running. Start manually with: python main.py"
fi

echo "=== Update complete ==="
