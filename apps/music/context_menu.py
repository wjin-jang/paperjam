"""
Context menu handling for the music player.
"""
from typing import List, Optional, Callable
from pathlib import Path

import config as cfg


class ContextMenuHandler:
    """Handles context menu display and actions."""

    def __init__(self, library_manager, playlist_manager, on_navigate: Optional[Callable] = None):
        """
        Initialize context menu handler.

        Args:
            library_manager: Library manager instance
            playlist_manager: Playlist manager instance
            on_navigate: Callback for navigation actions
        """
        self.lib = library_manager
        self.playlist = playlist_manager
        self._on_navigate = on_navigate

        self.active = False
        self.options: List[str] = []
        self.index = 0
        self.target_item: Optional[dict] = None
        self.layer = 0

    def open(self, item: dict):
        """
        Open context menu for an item.

        Args:
            item: Item dict to show context menu for
        """
        self.active = True
        self.index = 0
        self.target_item = item
        self.layer = 0
        self.options = self._get_options_for_item(item)

    def close(self):
        """Close the context menu."""
        self.active = False
        self.options = []
        self.index = 0
        self.target_item = None
        self.layer = 0

    def go_back(self):
        """Handle back action in context menu."""
        if self.layer == 1:
            # Return to main context menu
            self.layer = 0
            self.index = 0
            self.options = self._get_options_for_item(self.target_item)
        else:
            self.close()

    def _get_options_for_item(self, item: dict) -> List[str]:
        """Get context menu options based on item type."""
        if item.get('type') == 'playlist':
            return ["Add to Queue", "Delete Playlist", "Cancel"]
        elif item.get('type') == 'artist':
            return ["Add to Queue", "Favourite Artist", "Cancel"]
        elif item.get('type') == 'album':
            return ["Add to Queue", "Favourite Album", "Cancel"]
        elif item.get('type') == 'file':
            opts = ["Add to Queue", "Favourite Song", "Add to Playlist"]
            if item.get('artist'):
                opts.append("Go to Artist")
            if item.get('album'):
                opts.append("Go to Album")
            opts.append("Cancel")
            return opts
        return ["Cancel"]

    def select_up(self):
        """Move selection up."""
        if self.options:
            self.index = (self.index - 1) % len(self.options)

    def select_down(self):
        """Move selection down."""
        if self.options:
            self.index = (self.index + 1) % len(self.options)

    def execute_action(self, current_mode: str, on_refresh: Callable) -> Optional[dict]:
        """
        Execute the selected action.

        Args:
            current_mode: Current browse mode
            on_refresh: Callback to refresh the list

        Returns:
            Navigation info dict if navigation required, None otherwise
        """
        if not self.options:
            return None

        opt = self.options[self.index]
        target = self.target_item

        if self.layer == 0:
            if opt == "Cancel":
                self.close()
                return None

            elif opt == "Add to Queue":
                if target['type'] == 'file':
                    self.playlist.add_to_manual_queue(str(target['path']))
                
                elif target['type'] == 'album':
                    tracks = self.lib.get_album_tracks(target['name'])
                    for t in tracks:
                        self.playlist.add_to_manual_queue(str(t['path']))
                        
                elif target['type'] == 'artist':
                    tracks = self.lib.get_artist_tracks(target['name'])
                    for t in tracks:
                        self.playlist.add_to_manual_queue(str(t['path']))
                        
                elif target['type'] == 'playlist':
                    tracks = self.lib.get_playlist_tracks(Path(target['path']))
                    for t in tracks:
                        self.playlist.add_to_manual_queue(str(t['path']))
                        
                self.close()
                return None

            elif opt == "Favourite Song":
                self.lib.toggle_fav_track(str(target['path']))
                self.close()
                if current_mode == 'FAV_TRACKS_VIEW':
                    on_refresh()
                return None

            elif opt == "Favourite Artist":
                self.lib.toggle_fav_artist(target['name'])
                self.close()
                if current_mode == 'FAV_ARTISTS':
                    on_refresh()
                return None

            elif opt == "Favourite Album":
                self.lib.toggle_fav_album(target['name'])
                self.close()
                if current_mode == 'FAV_ALBUMS':
                    on_refresh()
                return None

            elif opt == "Delete Playlist":
                self.lib.delete_playlist(target['path'])
                self.close()
                on_refresh()
                return None

            elif opt == "Add to Playlist":
                self.layer = 1
                self.index = 0
                pl_files = self.lib.get_playlists()
                self.options = ["New Playlist"] + [f"Add to: {p.stem}" for p in pl_files]
                return None

            elif opt == "Go to Artist":
                self.close()
                return {
                    'mode': 'ARTIST_VIEW',
                    'path': target['artist']
                }

            elif opt == "Go to Album":
                self.close()
                return {
                    'mode': 'ALBUM_VIEW',
                    'path': target['album']
                }

        elif self.layer == 1:
            # Playlist selection layer
            if opt == "New Playlist":
                p = self.lib.create_playlist()
                self.lib.add_to_playlist(p, target['path'])
            else:
                pl_name = opt.replace("Add to: ", "")
                p = cfg.PLAYLIST_DIR / f"{pl_name}.json"
                self.lib.add_to_playlist(p, target['path'])
            self.close()
            return None

        return None
