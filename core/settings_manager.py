"""
Settings manager for centralized configuration management.
Replaces direct mutation of config.py globals with a cleaner abstraction.
"""
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

import config as cfg


@dataclass
class SettingDefinition:
    """Definition of a setting with validation and options."""
    key: str
    default: Any
    options: Optional[List[Any]] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None


def format_duration(seconds: int) -> str:
    """Format seconds as human-readable duration."""
    if seconds == 0:
        return "OFF"
    elif seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins}m"
    else:
        hours = seconds // 3600
        return f"{hours}h"


class SettingsManager:
    """
    Centralized settings management with persistence, validation, and observers.

    Replaces the pattern of directly mutating config.py globals,
    providing a cleaner interface for settings management.
    """

    # Define all settings with their defaults and constraints
    SETTING_DEFINITIONS = {
        'screensaver_timeout': SettingDefinition(
            key='screensaver_timeout',
            default=cfg.SCREENSAVER_TIMEOUT,
            options=cfg.SCREENSAVER_OPTIONS
        ),
        'long_press_duration': SettingDefinition(
            key='long_press_duration',
            default=cfg.LONG_PRESS_DURATION,
            options=cfg.LONG_PRESS_OPTIONS
        ),
        'recents_limit': SettingDefinition(
            key='recents_limit',
            default=cfg.RECENTS_LIMIT,
            options=cfg.RECENTS_LIMIT_OPTIONS
        ),
        'invert_colors': SettingDefinition(
            key='invert_colors',
            default=False
        ),
        'audio_output': SettingDefinition(
            key='audio_output',
            default='Auto',
            options=['Auto', 'Headphones', 'HDMI', 'USB']
        ),
        'endless_playback': SettingDefinition(
            key='endless_playback',
            default=False
        )
    }

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize settings manager.

        Args:
            data_dir: Directory for settings file. Defaults to ./data
        """
        if data_dir is None:
            data_dir = Path("data")
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._settings_file = self._data_dir / "settings.json"
        self._settings: Dict[str, Any] = {}
        self._listeners: List[Callable[[str, Any], None]] = []

        self._load_defaults()
        self._load()

    def _load_defaults(self):
        """Load default values for all settings."""
        for key, definition in self.SETTING_DEFINITIONS.items():
            self._settings[key] = definition.default

    def _load(self):
        """Load settings from file."""
        if self._settings_file.exists():
            try:
                with open(self._settings_file, 'r') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if key in self.SETTING_DEFINITIONS:
                            self._settings[key] = value
            except Exception as e:
                print(f"Error loading settings: {e}")

    def _save(self):
        """Save settings to file."""
        try:
            with open(self._settings_file, 'w') as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def _validate(self, key: str, value: Any) -> bool:
        """Validate a setting value against its definition."""
        if key not in self.SETTING_DEFINITIONS:
            return False

        definition = self.SETTING_DEFINITIONS[key]

        if definition.options is not None:
            return value in definition.options

        if definition.min_val is not None and value < definition.min_val:
            return False

        if definition.max_val is not None and value > definition.max_val:
            return False

        return True

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: New value
            save: Whether to persist immediately

        Returns:
            True if successful, False if validation failed
        """
        if key in self.SETTING_DEFINITIONS and not self._validate(key, value):
            print(f"Invalid value for {key}: {value}")
            return False

        old_value = self._settings.get(key)
        self._settings[key] = value

        if save:
            self._save()

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(key, value)
            except Exception as e:
                print(f"Error notifying listener: {e}")

        return True

    def cycle(self, key: str) -> Any:
        """
        Cycle a setting through its available options.

        Args:
            key: Setting key

        Returns:
            New value after cycling, or current value if not cycleable
        """
        if key not in self.SETTING_DEFINITIONS:
            return self._settings.get(key)

        definition = self.SETTING_DEFINITIONS[key]
        if definition.options is None:
            return self._settings.get(key)

        current = self._settings.get(key, definition.default)
        try:
            idx = definition.options.index(current)
            new_idx = (idx + 1) % len(definition.options)
            new_value = definition.options[new_idx]
            self.set(key, new_value)
            return new_value
        except ValueError:
            # Current value not in options, reset to first option
            new_value = definition.options[0]
            self.set(key, new_value)
            return new_value

    def toggle(self, key: str) -> bool:
        """
        Toggle a boolean setting.

        Args:
            key: Setting key

        Returns:
            New value after toggle
        """
        current = self._settings.get(key, False)
        new_value = not current
        self.set(key, new_value)
        return new_value

    def subscribe(self, callback: Callable[[str, Any], None]):
        """
        Subscribe to setting changes.

        Args:
            callback: Function to call when any setting changes.
                     Receives (key, new_value) arguments.
        """
        self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[str, Any], None]):
        """Unsubscribe from setting changes."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def get_options(self, key: str) -> Optional[List[Any]]:
        """Get available options for a setting."""
        if key in self.SETTING_DEFINITIONS:
            return self.SETTING_DEFINITIONS[key].options
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Export all settings as dictionary."""
        return self._settings.copy()

    def sync_to_config(self):
        """
        Sync settings to config.py globals for backward compatibility.
        This is a transitional method during refactoring.
        """
        import config as cfg
        cfg.SCREENSAVER_TIMEOUT = self.get('screensaver_timeout', 60)
        cfg.LONG_PRESS_DURATION = self.get('long_press_duration', 0.5)
        cfg.RECENTS_LIMIT = self.get('recents_limit', 50)


# Global instance for backward compatibility
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get or create the global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
