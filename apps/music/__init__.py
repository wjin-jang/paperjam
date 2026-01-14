"""
Music player application package.

This package provides a modular music player with:
- Browse modes (artists, albums, playlists, files, recents)
- Playlist/queue management with shuffle and loop
- Context menus for track operations
- Screensaver support
"""
from apps.music.player import MusicPlayerApp
from apps.music.state import PlayerState
from apps.music.playlist import PlaylistManager
from apps.music.browse import BrowseHandler
from apps.music.context_menu import ContextMenuHandler

__all__ = [
    'MusicPlayerApp',
    'PlayerState',
    'PlaylistManager',
    'BrowseHandler',
    'ContextMenuHandler'
]
