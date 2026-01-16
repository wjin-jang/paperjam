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
        self.target_queue_index: Optional[int] = None  # Index in queue for queue items
        self.layer = 0
        self._in_queue_view = False

    def open(self, item: dict, in_queue_view: bool = False, queue_index: int = None):
        """
        Open context menu for an item.

        Args:
            item: Item dict to show context menu for
            in_queue_view: Whether the item is in queue view
            queue_index: Index of the item in the queue (for queue management)
        """
        self.active = True
        self.index = 0
        self.target_item = item
        self.target_queue_index = queue_index
        self.layer = 0
        self._in_queue_view = in_queue_view
        self.options = self._get_options_for_item(item)

    def close(self):
        """Close the context menu."""
        self.active = False
        self.options = []
        self.index = 0
        self.target_item = None
        self.target_queue_index = None
        self.layer = 0
        self._in_queue_view = False

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
        # Queue view has special options for queue management
        if self._in_queue_view and item.get('type') == 'file':
            opts = ["Remove from Queue", "Send to Top", "Move Up", "Move Down"]
            if item.get('artist'):
                opts.append("Go to Artist")
            if item.get('album'):
                opts.append("Go to Album")
            opts.append("Cancel")
            return opts

        if item.get('type') == 'playlist':
            return ["Add to Queue", "Delete Playlist", "Cancel"]
        elif item.get('type') == 'artist':
            return ["Add to Queue", "Favourite Artist", "Cancel"]
        elif item.get('type') == 'album':
            return ["Add to Queue", "Favourite Album", "Cancel"]
        elif item.get('type') == 'heading':
            # Check if this is an alphabetical heading (single char like A, B, #)
            # vs album/disc heading (longer name like "Album Name" or "Disc 1")
            name = item.get('name', '')
            if len(name) <= 1 or name.startswith('Disc '):
                # Alphabetical or disc heading - no context menu options
                return ["Cancel"]
            # Album heading in artist view
            return ["Go to Album", "Add to Queue", "Favourite Album", "Cancel"]
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

            # Queue management options (for QUEUE_VIEW)
            elif opt == "Remove from Queue":
                if self.target_queue_index is not None:
                    self.playlist.remove_from_queue(self.target_queue_index)
                self.close()
                on_refresh()
                return None

            elif opt == "Send to Top":
                if self.target_queue_index is not None:
                    self.playlist.move_in_queue(self.target_queue_index, 0)
                self.close()
                on_refresh()
                return None

            elif opt == "Move Up":
                if self.target_queue_index is not None and self.target_queue_index > 0:
                    self.playlist.move_in_queue(self.target_queue_index, self.target_queue_index - 1)
                self.close()
                on_refresh()
                return None

            elif opt == "Move Down":
                if self.target_queue_index is not None:
                    self.playlist.move_in_queue(self.target_queue_index, self.target_queue_index + 1)
                self.close()
                on_refresh()
                return None

            elif opt == "Add to Queue":
                if target['type'] == 'file':
                    self.playlist.add_to_manual_queue(str(target['path']))

                elif target['type'] == 'album':
                    tracks = self.lib.get_album_tracks(target['name'])
                    for t in tracks:
                        self.playlist.add_to_manual_queue(str(t['path']))

                elif target['type'] == 'heading':
                    # Headings represent albums in artist view
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
                # Works for both album and heading types
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
                # For file items, album is in 'album' field; for headings, it's in 'name'
                album_name = target.get('album') or target.get('name')
                return {
                    'mode': 'ALBUM_VIEW',
                    'path': album_name
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
