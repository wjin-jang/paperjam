#!/bin/bash
# PiSugar 3 double-tap: Skip to next track
# Configure in PiSugar web interface or /etc/pisugar-server/config.json

# Find the user running paperjam and their D-Bus session
for uid in $(ls /run/user/ 2>/dev/null); do
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus"
    dbus-send --print-reply --dest=org.mpris.MediaPlayer2.paperjam \
        /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Next 2>/dev/null && exit 0
done
