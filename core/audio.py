"""
Audio playback engine using VLC.

This module provides a simplified interface to VLC for audio playback,
optimized for headless Raspberry Pi operation. It handles:

- Automatic audio output detection (PulseAudio → ALSA → default fallback)
- Basic playback controls (play, pause, stop)
- State querying (playing, paused, ended, error)
- Resource cleanup on shutdown

VLC was chosen for its robust codec support (MP3, FLAC, WAV, M4A) and
reliable Python bindings. The engine disables all video/GUI features
to minimize resource usage on the Pi Zero.

Example:
    >>> engine = AudioEngine()
    >>> engine.play("/path/to/song.mp3")
    >>> if engine.has_ended():
    ...     engine.play("/path/to/next.mp3")
    >>> engine.cleanup()
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Literal

import vlc

logger = logging.getLogger(__name__)

# Type alias for playback state strings
PlaybackState = Literal['stopped', 'loading', 'playing', 'paused', 'ended', 'error', 'unknown']


class AudioEngine:
    """VLC-based audio playback engine for headless operation.

    Automatically detects and configures the best available audio output
    (PulseAudio, ALSA, or system default). All video and GUI features
    are disabled to minimize resource usage.

    Attributes:
        instance: VLC instance with configured audio output.
        player: VLC media player for playback control.
        current_media_path: Path of the currently loaded media file.
    """

    def __init__(self) -> None:
        """Initialize the audio engine with automatic output detection."""
        self.instance: vlc.Instance | None = None
        self.player: vlc.MediaPlayer | None = None
        self.current_media_path: str | Path | None = None

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

        # Try audio outputs in order of preference: PulseAudio → ALSA → default
        if self._check_pulseaudio():
            try:
                self.instance = vlc.Instance(*base_opts, '--aout=pulse')
                logger.info("Audio: PulseAudio selected")
            except vlc.VLCException as e:
                logger.warning(f"PulseAudio init failed: {e}")

        if self.instance is None:
            try:
                self.instance = vlc.Instance(*base_opts, '--aout=alsa')
                logger.info("Audio: ALSA selected")
            except vlc.VLCException as e:
                logger.warning(f"ALSA init failed: {e}")

        if self.instance is None:
            self.instance = vlc.Instance(*base_opts)
            logger.info("Audio: Default output selected")

        self.player = self.instance.media_player_new()
        self.player.audio_set_volume(100)  # VLC internal volume at max (system volume controls actual level)

    def _check_pulseaudio(self) -> bool:
        """Check if PulseAudio is available and running.

        Returns:
            True if PulseAudio is available and responding, False otherwise.
        """
        try:
            result = subprocess.run(
                ["pactl", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False

    def load(self, path: str | Path) -> bool:
        """Load media without starting playback.

        Args:
            path: Path to the audio file to load.

        Returns:
            True if media was loaded successfully, False on error.
        """
        self.current_media_path = path
        logger.info(f"Loading: {path}")
        media = self.instance.media_new(str(path))
        if media is None:
            logger.error(f"Failed to create media for: {path}")
            return False
        self.player.set_media(media)
        self.player.audio_set_volume(100)
        return True

    def play(self, path: str | Path) -> None:
        """Load and start playing an audio file.

        Args:
            path: Path to the audio file to play.
        """
        import time

        self.current_media_path = path
        logger.info(f"Playing: {path}")
        media = self.instance.media_new(str(path))
        if media is None:
            logger.error(f"Failed to create media for: {path}")
            return
        self.player.set_media(media)
        self.player.audio_set_volume(100)
        result = self.player.play()

        # Brief delay to allow VLC to initialize playback
        time.sleep(0.1)
        state = self.get_state()
        logger.info(f"Play result: {result}, state: {state}")

        if state == 'error':
            logger.error(f"VLC error playing: {path}")
        elif state == 'stopped':
            logger.warning(f"VLC stopped immediately - possible codec/file issue: {path}")

    def toggle_pause(self) -> bool:
        """Toggle between play and pause states.

        Returns:
            True if now playing, False if now paused.
        """
        if self.player.is_playing():
            self.player.pause()
            return False
        else:
            self.player.play()
            return True

    def stop(self) -> None:
        """Stop playback completely."""
        self.player.stop()

    def is_playing(self) -> bool:
        """Check if audio is currently playing.

        Returns:
            True if actively playing audio.
        """
        return self.player.is_playing()

    def has_ended(self) -> bool:
        """Check if playback has reached the end of the track.

        Returns:
            True if the current track has finished playing.
        """
        return self.player.get_state() == vlc.State.Ended

    def is_paused(self) -> bool:
        """Check if playback is paused.

        Returns:
            True if paused.
        """
        return self.player.get_state() == vlc.State.Paused

    def is_stopped(self) -> bool:
        """Check if playback is stopped (not playing or paused).

        Returns:
            True if stopped, nothing loaded, or playback ended.
        """
        state = self.player.get_state()
        return state in (vlc.State.Stopped, vlc.State.NothingSpecial, vlc.State.Ended)

    def get_state(self) -> PlaybackState:
        """Get the current playback state as a human-readable string.

        Returns:
            One of: 'stopped', 'loading', 'playing', 'paused', 'ended', 'error', 'unknown'.
        """
        state = self.player.get_state()
        state_map: dict[vlc.State, PlaybackState] = {
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

    def cleanup(self) -> None:
        """Release VLC resources.

        Should be called on application shutdown to ensure proper cleanup.
        Safe to call multiple times.
        """
        try:
            if self.player:
                self.player.stop()
                self.player.release()
                self.player = None
            if self.instance:
                self.instance.release()
                self.instance = None
            logger.info("Audio engine cleaned up")
        except vlc.VLCException as e:
            logger.error(f"Error cleaning up audio engine: {e}")

    def __del__(self) -> None:
        """Destructor to ensure cleanup on garbage collection."""
        self.cleanup()
