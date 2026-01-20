"""
Audio settings category.

Manages audio-related settings including:
- Volume control with ALSA and PulseAudio support
- Audio output device selection
- Endless playback mode
- Bluetooth audio device management
"""
from __future__ import annotations

import json
import re
import subprocess
from typing import TYPE_CHECKING

import config as cfg
from config import setup_logger
from core.i18n import t
from ui.views.items import Item

from .base import SettingsCategory

if TYPE_CHECKING:
    from core.audio import AudioEngine
    from core.settings_manager import SettingsManager

logger = setup_logger()


class AudioCategory(SettingsCategory):
    """Audio settings category.

    Handles volume control through both ALSA (hardware mixer) and PulseAudio
    (software mixer), audio output device selection, and playback settings.

    Volume is persisted to disk and restored on startup to maintain user
    preferences across reboots.

    Attributes:
        audio: Reference to the AudioEngine.
        volume_level: Current volume level (0-100).
    """

    def __init__(self, settings_manager: "SettingsManager", audio_engine: "AudioEngine") -> None:
        """Initialize audio settings.

        Args:
            settings_manager: Reference to the app's SettingsManager.
            audio_engine: Reference to the AudioEngine for playback control.
        """
        super().__init__(t('settings.categories.audio'), settings_manager)
        self.audio = audio_engine
        self.volume_level: int = cfg.DEFAULT_VOLUME

        # Audio output state
        self._audio_sinks: list[dict[str, str]] = []
        self._current_sink_index: int = 0

        # Find available mixer control (Master, PCM, etc.)
        self._mixer_control: str = self._find_mixer_control()

        # Initialize volume from saved state
        self._load_volume()
        self._refresh_audio_sinks()

    def _load_volume(self) -> None:
        """Load volume from persistent storage or use default."""
        try:
            if cfg.VOLUME_FILE.exists():
                with open(cfg.VOLUME_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.volume_level = data.get('volume', cfg.DEFAULT_VOLUME)
                    self._apply_volume()
                    logger.info(f"Volume loaded: {self.volume_level}%")
                    return
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning(f"Failed to load volume: {e}")

        # Use default and apply it
        self.volume_level = cfg.DEFAULT_VOLUME
        self._apply_volume()

    def save_volume(self) -> None:
        """Save current volume to persistent storage."""
        try:
            with open(cfg.VOLUME_FILE, 'w', encoding='utf-8') as f:
                json.dump({'volume': self.volume_level}, f)
            logger.info(f"Volume saved: {self.volume_level}%")
        except OSError as e:
            logger.error(f"Failed to save volume: {e}")

    def _apply_volume(self) -> None:
        """Apply volume to all audio outputs (ALSA + PulseAudio)."""
        # Set ALSA mixer (hardware level)
        try:
            subprocess.run(
                ["amixer", "set", self._mixer_control, f"{self.volume_level}%"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to set ALSA volume: {e}")

        # Set PulseAudio sink volume (software level)
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{self.volume_level}%"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
            )
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to set PulseAudio volume: {e}")

    def _find_mixer_control(self) -> str:
        """Find an available ALSA mixer control name.

        Tries common control names in order of preference.

        Returns:
            Name of the first available mixer control, or 'Master' as fallback.
        """
        # Common control names in order of preference
        controls = ['Master', 'PCM', 'Speaker', 'Headphone', 'Digital']
        try:
            result = subprocess.check_output(
                ["amixer", "scontrols"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            for ctrl in controls:
                if f"'{ctrl}'" in result:
                    return ctrl
            # If none found, try to extract first available
            if "Simple mixer control" in result:
                match = re.search(r"'([^']+)'", result)
                if match:
                    return match.group(1)
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to find mixer control: {e}")
        return 'Master'

    def _read_system_volume(self) -> int:
        """Read current system volume from ALSA mixer.

        Returns:
            Current volume level (0-100), or cached value on error.
        """
        try:
            result = subprocess.check_output(
                ["amixer", "get", self._mixer_control],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            match = re.search(r'\[(\d+)%\]', result)
            if match:
                return int(match.group(1))
        except (subprocess.SubprocessError, ValueError, OSError) as e:
            logger.debug(f"Failed to read system volume: {e}")
        return self.volume_level

    def _refresh_audio_sinks(self) -> None:
        """Get list of available PulseAudio sinks (audio output devices)."""
        self._audio_sinks = []
        try:
            # Get full sink info including descriptions
            result = subprocess.check_output(
                ["pactl", "list", "sinks"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            )

            current_sink: dict[str, str] = {}
            for line in result.split('\n'):
                line = line.strip()
                if line.startswith('Sink #'):
                    if current_sink.get('name'):
                        self._audio_sinks.append(current_sink)
                    current_sink = {'id': line.split('#')[1]}
                elif line.startswith('Name:'):
                    current_sink['name'] = line.split(':', 1)[1].strip()
                elif line.startswith('Description:'):
                    desc = line.split(':', 1)[1].strip()
                    current_sink['display'] = desc if len(desc) > 20 else desc

            # Don't forget the last sink
            if current_sink.get('name'):
                self._audio_sinks.append(current_sink)

            # Add 'none' option if no sinks found
            if not self._audio_sinks:
                self._audio_sinks = [{'id': 'none', 'name': 'none', 'display': t('settings.bluetooth.none')}]
                self._current_sink_index = 0
                return

            # Find current default sink
            default = subprocess.check_output(
                ["pactl", "get-default-sink"],
                text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            found = False
            for i, sink in enumerate(self._audio_sinks):
                if sink['name'] == default:
                    self._current_sink_index = i
                    found = True
                    break
            # Reset to first sink if default not found
            if not found:
                self._current_sink_index = 0

        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"PulseAudio sinks not available: {e}")
            self._audio_sinks = [{'id': 'none', 'name': 'none', 'display': t('settings.bluetooth.none')}]
            self._current_sink_index = 0

    def _get_current_output_name(self) -> str:
        """Get the display name of the current audio output."""
        if self._audio_sinks and 0 <= self._current_sink_index < len(self._audio_sinks):
            return self._audio_sinks[self._current_sink_index]['display']
        return t('settings.bluetooth.none')

    def _cycle_audio_output(self) -> str:
        """Cycle to the next audio output device.

        Returns:
            Display name of the newly selected output.
        """
        self._refresh_audio_sinks()
        if not self._audio_sinks:
            return t('settings.bluetooth.none')
        if len(self._audio_sinks) == 1:
            return self._audio_sinks[0]['display']

        # Cycle to next sink
        self._current_sink_index = (self._current_sink_index + 1) % len(self._audio_sinks)
        sink = self._audio_sinks[self._current_sink_index]

        # Set as default sink
        if sink['name'] != 'default':
            try:
                subprocess.run(
                    ["pactl", "set-default-sink", sink['name']],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                )
                # Move currently playing streams to new sink
                subprocess.run(
                    f"pactl list short sink-inputs | cut -f1 | xargs -I{{}} pactl move-sink-input {{}} {sink['name']}",
                    shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                )
            except (subprocess.SubprocessError, OSError) as e:
                logger.warning(f"Failed to set default sink: {e}")

        return sink['display']

    def set_volume(self, change: int) -> None:
        """Change volume by given amount and persist.

        Args:
            change: Amount to change volume by (positive or negative).
        """
        self.volume_level = max(0, min(100, self.volume_level + change))
        self._apply_volume()
        self.save_volume()

    def build_menu(self) -> list[Item]:
        """Build the audio settings menu."""
        self._refresh_audio_sinks()
        output_name = self._get_current_output_name()
        endless = self.settings.get('endless_playback', False)
        endless_state = t('general.on') if endless else t('general.off')
        return [
            Item(columns=[t('settings.audio.output'), output_name], selectable=True),
            Item(text=t('settings.audio.volume')),
            Item(columns=[t('settings.audio.endless_play'), endless_state], selectable=True),
            Item(text=t('settings.audio.bluetooth'))
        ]

    def handle_action(self, item_index: int) -> str | None:
        """Handle audio settings menu selection."""
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.audio.bluetooth') in item_text:
            return 'BT_SAVED'
        elif t('settings.audio.volume') in item_text:
            return 'VOLUME'
        elif t('settings.audio.output') in item_text:
            self._cycle_audio_output()
            self.refresh()
            return None
        elif t('settings.audio.endless_play') in item_text:
            self.settings.toggle('endless_playback')
            self.refresh()
            return None

        return None
