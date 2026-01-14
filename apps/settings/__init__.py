"""
Settings application package.

Provides modular settings management with category handlers for:
- Audio settings (output, volume, Bluetooth)
- Library settings (reload, limits)
- Display settings (invert colors, screensaver)
- Network information (WiFi status)
- System settings (long press, restart)
"""
from apps.settings.app import SettingsApp
from apps.settings.categories import (
    SettingsCategory,
    AudioCategory,
    LibraryCategory,
    DisplayCategory,
    NetworkCategory,
    SystemCategory
)

__all__ = [
    'SettingsApp',
    'SettingsCategory',
    'AudioCategory',
    'LibraryCategory',
    'DisplayCategory',
    'NetworkCategory',
    'SystemCategory'
]
