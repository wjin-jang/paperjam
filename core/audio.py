"""
Audio playback engine using VLC.

Provides simple audio playback with:
- Automatic output detection (PulseAudio, ALSA, default)
- Play, pause, stop controls
- State querying (playing, paused, ended)

VLC was chosen for robust codec support and simple Python bindings.
"""
import logging
import os
import subprocess

import vlc

logger = logging.getLogger(__name__)


class AudioEngine:
    def __init__(self):
        # Try audio outputs in order of preference
        self.instance = None

        # Try PulseAudio first
        if self._check_pulseaudio():
            try:
                self.instance = vlc.Instance('--aout=pulse')
                logger.info("Audio: PulseAudio selected")
            except Exception:
                pass

        # Try ALSA if PulseAudio failed
        if self.instance is None:
            try:
                self.instance = vlc.Instance('--aout=alsa')
                logger.info("Audio: ALSA selected")
            except Exception:
                pass

        # Fall back to default
        if self.instance is None:
            self.instance = vlc.Instance()
            logger.info("Audio: Default output selected")

        self.player = self.instance.media_player_new()
        self.current_media_path = None

    def _check_pulseaudio(self):
        """Check if PulseAudio is available and running."""
        try:
            result = subprocess.run(
                ["pactl", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
            return result.returncode == 0
        except Exception:
            return False

    def play(self, path):
        self.current_media_path = path
        media = self.instance.media_new(str(path))
        self.player.set_media(media)
        self.player.play()

    def toggle_pause(self):
        if self.player.is_playing():
            self.player.pause()
            return False 
        else:
            self.player.play()
            return True 

    def stop(self):
        self.player.stop()

    def is_playing(self):
        return self.player.is_playing()

    def has_ended(self):
        return self.player.get_state() == vlc.State.Ended

    def is_paused(self):
        return self.player.get_state() == vlc.State.Paused

    def is_stopped(self):
        state = self.player.get_state()
        return state in (vlc.State.Stopped, vlc.State.NothingSpecial, vlc.State.Ended)

    def get_state(self):
        """Return the current playback state as a string."""
        state = self.player.get_state()
        state_map = {
            vlc.State.NothingSpecial: 'stopped',
            vlc.State.Opening: 'loading',
            vlc.State.Buffering: 'loading',
            vlc.State.Playing: 'playing',
            vlc.State.Paused: 'paused',
            vlc.State.Stopped: 'stopped',
            vlc.State.Ended: 'ended',
            vlc.State.Error: 'error'
        }
        return state_map.get(state, 'unknown')
