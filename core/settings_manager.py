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
            options=['Auto', 'Headphones', 'USB']
        ),
        'endless_playback': SettingDefinition(
            key='endless_playback',
            default=False
        ),
        'auto_update': SettingDefinition(
            key='auto_update',
            default=False
        )
    }

    def __init__(self):
        """
        Initialize settings manager.
        """
        self._settings: Dict[str, Any] = {}
        self._listeners: List[Callable[[str, Any], None]] = []

        self._load_defaults()
        # Load values from config.py's loaded config
        self._load_from_config()

    def _load_defaults(self):
        """Load default values for all settings."""
        for key, definition in self.SETTING_DEFINITIONS.items():
            self._settings[key] = definition.default

    def _load_from_config(self):
        """Load settings from global config."""
        # _config is internal to config.py, but we can re-load or access exported vars.
        # However, config.py loads into variables.
        # Better: use the exposed dictionary if possible, but config.py exposes variables.
        # Actually config.py has `_config` and `load_config`.
        # Let's verify config.py again. It exposes `save_config`.
        # It has `_config = load_config()`.
        # But `_config` is not exported.
        # We should use `cfg.load_config()` (which re-reads file) or rely on the variables.
        # But config.py variables are constants initialized at module load.
        # To support runtime updates, config.py should probably expose the dict or getters.
        
        # NOTE: config.py exposes _config as a module-level variable but it is not in __all__?
        # Python modules export everything by default.
        
        # Let's assume we can access cfg._config or we should have exposed it.
        # config.py does: `_config = load_config()`
        
        if hasattr(cfg, '_config'):
            for key, value in cfg._config.items():
                if key in self.SETTING_DEFINITIONS:
                    self._settings[key] = value

    def _save(self):
        """Save settings to file via config module."""
        # We only save keys that are in our definitions and valid
        updates = {k: v for k, v in self._settings.items() if k in self.SETTING_DEFINITIONS}
        cfg.save_config(updates)

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
