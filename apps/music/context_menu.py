"""
Context menu handling for the music player.
"""
from typing import Any, Callable, List, Optional
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

    def open(self, item: Any, in_queue_view: bool = False, queue_index: int = None):
        """
        Open context menu for an item.

        Args:
            item: Item dict or Item object to show context menu for
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
        from ui.views.items import Item
        items = [Item(text=opt, id=opt) for opt in options]
        self.menu.set_items(items)

    def _get_options_for_item(self, item: Any) -> List[str]:
        """Get context menu options based on item kind."""
        from ui.views.items import Item, extract_item_props

        # Use utility function for unified property extraction
        props = extract_item_props(item)
        ikind = props['kind']
        is_heading = props['heading']
        iname = props['text']

        # Get artist/album from item id dict (not in standard props)
        if isinstance(item, Item) and isinstance(item.id, dict):
            iartist = item.id.get('artist')
            ialbum = item.id.get('album')
        else:
            iartist = item.get('artist') if isinstance(item, dict) else None
            ialbum = item.get('album') if isinstance(item, dict) else None

        # Queue view has special options for queue management
        if self._in_queue_view and ikind == 'file':
            opts = [
                t('player.context.remove_from_queue'),
                t('player.context.send_to_top'),
                t('player.context.move_up'),
                t('player.context.move_down')
            ]
            if iartist:
                opts.append(t('player.context.go_to_artist'))
            if ialbum:
                opts.append(t('player.context.go_to_album'))
            opts.append(t('player.context.cancel'))
            return opts

        if ikind == 'playlist':
            return [
                t('player.context.add_to_queue'),
                t('player.context.delete_playlist'),
                t('player.context.cancel')
            ]
        elif ikind == 'artist':
            return [
                t('player.context.add_to_queue'),
                t('player.context.favourite_artist'),
                t('player.context.cancel')
            ]
        elif ikind == 'album':
            return [
                t('player.context.add_to_queue'),
                t('player.context.favourite_album'),
                t('player.context.cancel')
            ]
        elif is_heading:
            # Check if this is an alphabetical heading (single char like A, B, #)
            # vs album/disc heading (longer name like "Album Name" or "Disc 1")
            name = iname or ''
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
        elif ikind == 'file':
            opts = [
                t('player.context.add_to_queue'),
                t('player.context.favourite_song'),
                t('player.context.add_to_playlist')
            ]
            if iartist:
                opts.append(t('player.context.go_to_artist'))
            if ialbum:
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
        from ui.views.items import Item, extract_item_props
        item = self.menu.get_selected_item()
        if not item: return None

        opt = item.id if isinstance(item, Item) else item['action']
        target = self.target_item

        # Use utility function for unified property extraction
        props = extract_item_props(target)
        tkind = props['kind']
        is_heading = props['heading']
        tpath = props['path']
        tname = props['text']

        # Get artist/album from target item id dict
        if isinstance(target, Item) and isinstance(target.id, dict):
            tartist = target.id.get('artist')
            talbum = target.id.get('album')
        else:
            tartist = target.get('artist') if isinstance(target, dict) else None
            talbum = target.get('album') if isinstance(target, dict) else None

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
                if tkind == 'file':
                    self.playlist.add_to_manual_queue(str(tpath))

                elif tkind == 'album':
                    tracks = self.lib.get_album_tracks(tname)
                    for track in tracks:
                        self.playlist.add_to_manual_queue(str(track['path']))

                elif is_heading:
                    # Headings represent albums in artist view
                    tracks = self.lib.get_album_tracks(tname)
                    for track in tracks:
                        self.playlist.add_to_manual_queue(str(track['path']))

                elif tkind == 'artist':
                    tracks = self.lib.get_artist_tracks(tname)
                    for track in tracks:
                        self.playlist.add_to_manual_queue(str(track['path']))

                elif tkind == 'playlist':
                    tracks = self.lib.get_playlist_tracks(Path(tpath))
                    for track in tracks:
                        self.playlist.add_to_manual_queue(str(track['path']))

                self.close()
                return None

            elif opt == t('player.context.favourite_song'):
                self.lib.toggle_fav_track(str(tpath))
                self.close()
                if current_mode == 'FAV_TRACKS_VIEW':
                    on_refresh()
                return None

            elif opt == t('player.context.favourite_artist'):
                self.lib.toggle_fav_artist(tname)
                self.close()
                if current_mode == 'FAV_ARTISTS':
                    on_refresh()
                return None

            elif opt == t('player.context.favourite_album'):
                # Works for both album and heading types
                self.lib.toggle_fav_album(tname)
                self.close()
                if current_mode == 'FAV_ALBUMS':
                    on_refresh()
                return None

            elif opt == t('player.context.delete_playlist'):
                self.lib.delete_playlist(tpath)
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
                    'path': tartist
                }

            elif opt == t('player.context.go_to_album'):
                self.close()
                return {
                    'mode': 'ALBUM_VIEW',
                    'path': talbum or tname
                }

        elif self.layer == 1:
            # Playlist selection layer
            if opt == t('player.context.new_playlist'):
                p = self.lib.create_playlist()
                self.lib.add_to_playlist(p, tpath)
            else:
                # Extract playlist name from localized "Add to: {name}" string
                add_to_prefix = t('player.context.add_to', name='').rstrip()
                pl_name = opt.replace(add_to_prefix, '').strip()
                p = cfg.PLAYLIST_DIR / f"{pl_name}.json"
                self.lib.add_to_playlist(p, tpath)
            self.close()
            return None

        return None
