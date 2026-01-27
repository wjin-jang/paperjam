#!/bin/bash
# PiSugar 3 single-tap: Toggle play/pause
# Configure in PiSugar web interface or /etc/pisugar-server/config.json

dbus-send --print-reply --dest=org.mpris.MediaPlayer2.paperjam \
    /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.PlayPause
