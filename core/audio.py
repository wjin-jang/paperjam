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

        # VLC options optimized for headless Raspberry Pi OS Lite
        base_opts = [
            '--no-video',           # Disable video output
            '--no-xlib',            # Disable X11 dependency
            '--no-keyboard-events', # No keyboard input handling
            '--no-mouse-events',    # No mouse input handling
            '--no-disable-screensaver',  # Don't try to manage screensaver
            '--no-snapshot-preview', # Disable snapshot preview
            '--no-osd',             # Disable on-screen display
            '--no-spu',             # Disable subtitles
            '--no-lua',             # Disable Lua scripting
            '--no-plugins-cache',   # Don't use plugin cache (saves memory)
            '--quiet',              # Reduce log verbosity
        ]

        # Try PulseAudio first
        if self._check_pulseaudio():
            try:
                self.instance = vlc.Instance(*base_opts, '--aout=pulse')
                logger.info("Audio: PulseAudio selected")
            except Exception as e:
                logger.warning(f"PulseAudio init failed: {e}")

        # Try ALSA if PulseAudio failed
        if self.instance is None:
            try:
                self.instance = vlc.Instance(*base_opts, '--aout=alsa')
                logger.info("Audio: ALSA selected")
            except Exception as e:
                logger.warning(f"ALSA init failed: {e}")

        # Fall back to default
        if self.instance is None:
            self.instance = vlc.Instance(*base_opts)
            logger.info("Audio: Default output selected")

        self.player = self.instance.media_player_new()
        self.player.audio_set_volume(100)  # Set VLC internal volume to max
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

    def load(self, path):
        """Load media without playing. Returns True if successful."""
        self.current_media_path = path
        logger.info(f"Loading: {path}")
        media = self.instance.media_new(str(path))
        if media is None:
            logger.error(f"Failed to create media for: {path}")
            return False
        self.player.set_media(media)
        self.player.audio_set_volume(100)
        return True

    def play(self, path):
        import time
        self.current_media_path = path
        logger.info(f"Playing: {path}")
        media = self.instance.media_new(str(path))
        if media is None:
            logger.error(f"Failed to create media for: {path}")
            return
        self.player.set_media(media)
        self.player.audio_set_volume(100)  # Ensure volume is set before play
        result = self.player.play()
        # Wait briefly for VLC to start
        time.sleep(0.1)
        state = self.get_state()
        logger.info(f"Play result: {result}, state: {state}")
        if state == 'error':
            logger.error(f"VLC error playing: {path}")
        elif state == 'stopped':
            logger.warning(f"VLC stopped immediately - possible codec/file issue: {path}")

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
