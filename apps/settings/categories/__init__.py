"""
Settings category modules.

This package contains individual settings categories, each in its own module.
Categories are organized by functionality:

- audio: Volume, output device, endless playback, Bluetooth audio
- library: Library stats, rescanning, recents limit
- display: Colors, screensaver, language, weather location
- network: WiFi and Bluetooth management
- system: Disk, version, power mode, updates, restart/shutdown
"""
from .base import SettingsCategory
from .audio import AudioCategory
from .library import LibraryCategory
from .display import DisplayCategory
from .network import NetworkCategory
from .system import SystemCategory

__all__ = [
    'SettingsCategory',
    'AudioCategory',
    'LibraryCategory',
    'DisplayCategory',
    'NetworkCategory',
    'SystemCategory',
]
