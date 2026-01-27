#!/bin/bash
# PiSugar 3 double-tap: Skip to next track
# Configure in PiSugar web interface or /etc/pisugar-server/config.json

# Find the user running paperjam and send D-Bus command as that user
for uid in $(ls /run/user/ 2>/dev/null); do
    user=$(getent passwd "$uid" | cut -d: -f1)
    [ -z "$user" ] && continue
    runuser -u "$user" -- env DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        dbus-send --print-reply --dest=org.mpris.MediaPlayer2.paperjam \
        /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Next 2>/dev/null && exit 0
done
