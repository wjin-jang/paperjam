#!/bin/bash
# PiSugar 3 soft shutdown: Gracefully stop PaperJam and power off PiSugar
# Configure as soft_poweroff_shell in PiSugar web interface or config.json
#
# This script runs when PiSugar triggers a shutdown (long-press or low battery).
# It stops the PaperJam service, then tells PiSugar to fully power off.

# Stop PaperJam service (try user service first, then system service)
systemctl --user stop paperjam 2>/dev/null || systemctl stop paperjam 2>/dev/null || true

# Tell PiSugar to power off after Pi shuts down (turns off blue LED)
echo "set_battery_power_off" | nc -q 0 127.0.0.1 8423 2>/dev/null || true
