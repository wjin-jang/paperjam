#!/bin/bash
# PiSugar 3 soft shutdown: Gracefully stop PaperJam before system shutdown
# Configure in PiSugar web interface or /etc/pisugar-server/config.json
#
# This script runs when PiSugar triggers a shutdown (long-press or low battery).
# It stops the PaperJam service gracefully, then allows the system to shut down.

# Try user service first (Raspberry Pi OS), then system service (DietPi)
systemctl --user stop paperjam 2>/dev/null || systemctl stop paperjam 2>/dev/null || true

# Brief delay to allow graceful cleanup
sleep 1
