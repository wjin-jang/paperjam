"""
Context menu handling for the music player.
"""
from typing import List, Optional, Callable
from pathlib import Path

import config as cfg
from core.i18n import t
from ui.menu import MenuController


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
        self.target_item: Optional[dict] = None
        self.target_queue_index: Optional[int] = None  # Index in queue for queue items
        self.layer = 0
        self._in_queue_view = False
        
        # Menu controller
        self.menu = MenuController([])

    def open(self, item: dict, in_queue_view: bool = False, queue_index: int = None):
        """
        Open context menu for an item.

        Args:
            item: Item dict to show context menu for
            in_queue_view: Whether the item is in queue view
            queue_index: Index of the item in the queue (for queue management)
        """
        self.active = True
        self.target_item = item
        self.target_queue_index = queue_index
        self.layer = 0
        self._in_queue_view = in_queue_view
        
        # Build options
        options = self._get_options_for_item(item)
        self._update_menu_items(options)

    def close(self):
        """Close the context menu."""
        self.active = False
        self.target_item = None
        self.target_queue_index = None
        self.layer = 0
        self._in_queue_view = False
        self.menu.set_items([])

    def go_back(self):
        """Handle back action in context menu."""
        if self.layer == 1:
            # Return to main context menu
            self.layer = 0
            options = self._get_options_for_item(self.target_item)
            self._update_menu_items(options)
        else:
            self.close()
            
    def _update_menu_items(self, options: List[str]):
        """Update menu controller items from string list."""
        items = [{'name': opt, 'type': 'file', 'action': opt} for opt in options]
        self.menu.set_items(items)

    def _get_options_for_item(self, item: dict) -> List[str]:
        """Get context menu options based on item type."""
        # Queue view has special options for queue management
        if self._in_queue_view and item.get('type') == 'file':
            opts = [
                t('player.context.remove_from_queue'),
                t('player.context.send_to_top'),
                t('player.context.move_up'),
                t('player.context.move_down')
            ]
            if item.get('artist'):
                opts.append(t('player.context.go_to_artist'))
            if item.get('album'):
                opts.append(t('player.context.go_to_album'))
            opts.append(t('player.context.cancel'))
            return opts

        if item.get('type') == 'playlist':
            return [
                t('player.context.add_to_queue'),
                t('player.context.delete_playlist'),
                t('player.context.cancel')
            ]
        elif item.get('type') == 'artist':
            return [
                t('player.context.add_to_queue'),
                t('player.context.favourite_artist'),
                t('player.context.cancel')
            ]
        elif item.get('type') == 'album':
            return [
                t('player.context.add_to_queue'),
                t('player.context.favourite_album'),
                t('player.context.cancel')
            ]
        elif item.get('type') == 'heading':
            # Check if this is an alphabetical heading (single char like A, B, #)
            # vs album/disc heading (longer name like "Album Name" or "Disc 1")
            name = item.get('name', '')
            disc_prefix = t('player.browse.disc', num='').strip()
            if len(name) <= 1 or name.startswith(disc_prefix):
                # Alphabetical or disc heading - no context menu options
                return [t('player.context.cancel')]
            # Album heading in artist view
            return [
                t('player.context.go_to_album'),
                t('player.context.add_to_queue'),
                t('player.context.favourite_album'),
                t('player.context.cancel')
            ]
        elif item.get('type') == 'file':
            opts = [
                t('player.context.add_to_queue'),
                t('player.context.favourite_song'),
                t('player.context.add_to_playlist')
            ]
            if item.get('artist'):
                opts.append(t('player.context.go_to_artist'))
            if item.get('album'):
                opts.append(t('player.context.go_to_album'))
            opts.append(t('player.context.cancel'))
            return opts
        return [t('player.context.cancel')]

    def select_up(self):
        """Move selection up."""
        if self.active:
            self.menu.move_selection(-1)

    def select_down(self):
        """Move selection down."""
        if self.active:
            self.menu.move_selection(1)

    def execute_action(self, current_mode: str, on_refresh: Callable) -> Optional[dict]:
        """
        Execute the selected action.

        Args:
            current_mode: Current browse mode
            on_refresh: Callback to refresh the list

        Returns:
            Navigation info dict if navigation required, None otherwise
        """
        item = self.menu.get_selected_item()
        if not item: return None

        opt = item['action']
        target = self.target_item

        if self.layer == 0:
            if opt == t('player.context.cancel'):
                self.close()
                return None

            # Queue management options (for QUEUE_VIEW)
            elif opt == t('player.context.remove_from_queue'):
                if self.target_queue_index is not None:
                    self.playlist.remove_from_queue(self.target_queue_index)
                self.close()
                on_refresh()
                return None

            elif opt == t('player.context.send_to_top'):
                if self.target_queue_index is not None:
                    self.playlist.move_in_queue(self.target_queue_index, 0)
                self.close()
                on_refresh()
                return None

            elif opt == t('player.context.move_up'):
                if self.target_queue_index is not None and self.target_queue_index > 0:
                    self.playlist.move_in_queue(self.target_queue_index, self.target_queue_index - 1)
                self.close()
                on_refresh()
                return None

            elif opt == t('player.context.move_down'):
                if self.target_queue_index is not None:
                    self.playlist.move_in_queue(self.target_queue_index, self.target_queue_index + 1)
                self.close()
                on_refresh()
                return None

            elif opt == t('player.context.add_to_queue'):
                if target['type'] == 'file':
                    self.playlist.add_to_manual_queue(str(target['path']))

                elif target['type'] == 'album':
                    tracks = self.lib.get_album_tracks(target['name'])
                    for track in tracks:
                        self.playlist.add_to_manual_queue(str(track['path']))

                elif target['type'] == 'heading':
                    # Headings represent albums in artist view
                    tracks = self.lib.get_album_tracks(target['name'])
                    for track in tracks:
                        self.playlist.add_to_manual_queue(str(track['path']))

                elif target['type'] == 'artist':
                    tracks = self.lib.get_artist_tracks(target['name'])
                    for track in tracks:
                        self.playlist.add_to_manual_queue(str(track['path']))

                elif target['type'] == 'playlist':
                    tracks = self.lib.get_playlist_tracks(Path(target['path']))
                    for track in tracks:
                        self.playlist.add_to_manual_queue(str(track['path']))

                self.close()
                return None

            elif opt == t('player.context.favourite_song'):
                self.lib.toggle_fav_track(str(target['path']))
                self.close()
                if current_mode == 'FAV_TRACKS_VIEW':
                    on_refresh()
                return None

            elif opt == t('player.context.favourite_artist'):
                self.lib.toggle_fav_artist(target['name'])
                self.close()
                if current_mode == 'FAV_ARTISTS':
                    on_refresh()
                return None

            elif opt == t('player.context.favourite_album'):
                # Works for both album and heading types
                self.lib.toggle_fav_album(target['name'])
                self.close()
                if current_mode == 'FAV_ALBUMS':
                    on_refresh()
                return None

            elif opt == t('player.context.delete_playlist'):
                self.lib.delete_playlist(target['path'])
                self.close()
                on_refresh()
                return None

            elif opt == t('player.context.add_to_playlist'):
                self.layer = 1
                pl_files = self.lib.get_playlists()
                options = [t('player.context.new_playlist')] + [
                    t('player.context.add_to', name=p.stem) for p in pl_files
                ]
                self._update_menu_items(options)
                return None

            elif opt == t('player.context.go_to_artist'):
                self.close()
                return {
                    'mode': 'ARTIST_VIEW',
                    'path': target['artist']
                }

            elif opt == t('player.context.go_to_album'):
                self.close()
                # For file items, album is in 'album' field; for headings, it's in 'name'
                album_name = target.get('album') or target.get('name')
                return {
                    'mode': 'ALBUM_VIEW',
                    'path': album_name
                }

        elif self.layer == 1:
            # Playlist selection layer
            if opt == t('player.context.new_playlist'):
                p = self.lib.create_playlist()
                self.lib.add_to_playlist(p, target['path'])
            else:
                # Extract playlist name from localized "Add to: {name}" string
                add_to_prefix = t('player.context.add_to', name='').rstrip()
                pl_name = opt.replace(add_to_prefix, '').strip()
                p = cfg.PLAYLIST_DIR / f"{pl_name}.json"
                self.lib.add_to_playlist(p, target['path'])
            self.close()
            return None

        return None