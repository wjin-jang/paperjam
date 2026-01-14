"""
View rendering components for the UI.

This package provides modular renderers for different views:
- MusicViewRenderer: Music player browsing and playback
- MenuViewRenderer: Settings and navigation menus
- ScreensaverRenderer: Screensaver and shutdown screens
"""
from ui.views.common import RenderBase
from ui.views.music_view import MusicViewRenderer
from ui.views.menu_view import MenuViewRenderer
from ui.views.screensaver_view import ScreensaverRenderer

__all__ = [
    'RenderBase',
    'MusicViewRenderer',
    'MenuViewRenderer',
    'ScreensaverRenderer'
]
