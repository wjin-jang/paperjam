#!/bin/bash
# PiSugar 3 soft shutdown: Gracefully stop PaperJam and power off PiSugar
# Configure as soft_poweroff_shell in PiSugar web interface or config.json
#
# This script runs when PiSugar triggers a shutdown (long-press or low battery).
# It stops the PaperJam service, then tells PiSugar to fully power off.

# Stop PaperJam service - try system service first (DietPi), then user service
systemctl stop paperjam 2>/dev/null || true
for uid in $(ls /run/user/ 2>/dev/null); do
    sudo -u "#$uid" XDG_RUNTIME_DIR="/run/user/$uid" systemctl --user stop paperjam 2>/dev/null || true
done

# Tell PiSugar to power off after Pi shuts down (turns off blue LED)
# Try nc (netcat), then ncat, then bash tcp
if command -v nc &>/dev/null; then
    echo "set_battery_power_off" | nc -q 0 127.0.0.1 8423 2>/dev/null || true
elif command -v ncat &>/dev/null; then
    echo "set_battery_power_off" | ncat 127.0.0.1 8423 2>/dev/null || true
else
    exec 3<>/dev/tcp/127.0.0.1/8423 && echo "set_battery_power_off" >&3 && exec 3<&-
fi
