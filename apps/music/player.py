"""
Main music player application - orchestrates all components.
"""
import random
import time
from pathlib import Path
from PIL import Image

from core.library import LibraryManager
from core.i18n import t
from ui.image_utils import get_cover
from core.track_info import extract_track_info
from core.navigation import find_next_heading
from ui.renderer import UIRenderer
from ui.menu import MenuController
from ui.views.items import Item
import config as cfg

from apps.music.state import PlayerState
from apps.music.playlist import PlaylistManager
from apps.music.context_menu import ContextMenuHandler
from apps.music.browse import BrowseHandler
from apps.base import AppBase


class MusicPlayerApp(AppBase):
    """Main music player application."""

    def __init__(self, audio, input_handler):
        super().__init__(name=t('menu.music'))
        self.audio = audio
        self.input = input_handler
        self.lib = LibraryManager()
        self.renderer = UIRenderer()
        self._settings = None

        # Initialize components
        self.state = PlayerState(items=[], fav_albums=self.lib.fav_albums, fav_artists=self.lib.fav_artists)
        self.playlist = PlaylistManager()
        self.context_menu = ContextMenuHandler(self.lib, self.playlist)
        self.browse = BrowseHandler(self.lib)
        
        # Menu Controller for navigation
        self.menu = MenuController([])

        # Clear browse cache when library scan completes
        self.lib.set_on_scan_complete(self.browse.clear_cache)

        # Navigation state
        self.history = []
        self.mode = 'ROOT'
        self.current_path = cfg.MUSIC_PATH

        # Timing
        self.running = True

        # Display callback for immediate updates (set by main.py)
        self._display_callback = None

        # Volume callbacks (set by main.py)
        self._vol_up_callback = None
        self._vol_down_callback = None
        
        # Resume playback if queue loaded
        if self.playlist.has_queue:
            path = self.playlist.get_current_path()
            if path:
                self._play_media(path, play=False)
                self.state.playing_path = path

        self.refresh_list()

        # Reset input time after init to prevent immediate screensaver
        self.last_input_time = time.time()

    def set_display_callback(self, callback):
        """Set callback for immediate display updates."""
        self._display_callback = callback

    def set_volume_callbacks(self, vol_up, vol_down):
        """Set callbacks for volume control."""
        self._vol_up_callback = vol_up
        self._vol_down_callback = vol_down

    def set_settings(self, settings_manager):
        """Set settings manager reference for features like endless playback."""
        self._settings = settings_manager

    def _show_loading(self, message: str = None):
        """Show loading overlay and force display update."""
        self.state.loading_message = message or t('general.loading')
        if self._display_callback:
            self._display_callback(self.get_frame())

    def _hide_loading(self):
        """Hide loading overlay."""
        self.state.loading_message = None

    def get_callbacks(self):
        """Return input callbacks for the music player."""
        callbacks = {
            'up': self.nav_up,
            'down': self.nav_down,
            'enter': self.nav_enter,
            'enter_long': self.nav_enter_long,
            'back': self.nav_back,
            'back_long': self.nav_home,
            'play_pause': self.toggle_play,
            'play_pause_long': self.show_queue_view,
            'next': self.next_track,
            'prev': self.prev_track
        }
        if self._vol_up_callback:
            callbacks['vol_up'] = self._vol_up_callback
        if self._vol_down_callback:
            callbacks['vol_down'] = self._vol_down_callback
        return callbacks

    def nav_home(self):
        """Long press back - return to home menu."""
        self._wake_from_screensaver()
        self.running = False

    def show_queue_view(self):
        """Show the current play queue."""
        if self._wake_from_screensaver():
            return
        
        self.history.append((self.mode, self.current_path, self.menu.selected_index))
        self.mode = 'QUEUE_VIEW'
        self.refresh_list(reset_selection=True)

    def _wake_from_screensaver(self):
        """Wake from screensaver if active. Returns True if was active."""
        was_active = self.state.screensaver_image is not None
        self.last_input_time = time.time()
        self.state.screensaver_image = None
        self.state.screensaver_album = None

        if was_active:
            self.state.needs_refresh = True

        return was_active

    def _sync_context_state(self):
        """Sync context menu state to player state."""
        self.state.context_menu_active = self.context_menu.active
        self.state.context_options = self.context_menu.menu.items # Use menu items
        self.state.context_index = self.context_menu.menu.selected_index
        self.state.context_target_item = self.context_menu.target_item
        self.state.context_layer = self.context_menu.layer

    # --- Navigation Keys ---
    def nav_up(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            self.context_menu.select_up()
            self._sync_context_state()
        else:
            self.menu.move_selection(-1)
            self._sync_state_selection()

    def nav_down(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            self.context_menu.select_down()
            self._sync_context_state()
        else:
            self.menu.move_selection(1)
            self._sync_state_selection()
            
    def _sync_state_selection(self):
        """Update state selection index from menu controller."""
        self.state.selection_index = self.menu.selected_index

    def nav_enter(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            nav_req = self.context_menu.execute_action(self.mode, self.refresh_list)
            self._sync_context_state()

            if nav_req:
                self.history.append((self.mode, self.current_path, self.menu.selected_index))
                self.mode = nav_req['mode']
                self.current_path = nav_req['path']
                self.refresh_list(reset_selection=True)
            return

        item = self.menu.get_selected_item()
        if not item: return

        # Get item kind from id dict
        item_kind = item.kind if isinstance(item, Item) else (item.get('id', {}).get('kind') if isinstance(item.get('id'), dict) else None)
        is_heading = item.heading if isinstance(item, Item) else item.get('heading', False)
        is_column_nav = item.column_nav if isinstance(item, Item) else item.get('column_nav', False)
        is_selectable = item.selectable if isinstance(item, Item) else item.get('selectable', True)

        # Controls bar - handle button press
        if is_column_nav:
            self._handle_controls_action()
            return

        # Clicking a heading jumps to the next heading
        if is_heading:
            # Find next heading index
            current_idx = self.menu.selected_index
            total = len(self.menu.items)
            for i in range(1, total):
                idx = (current_idx + i) % total
                target = self.menu.items[idx]
                target_heading = target.heading if isinstance(target, Item) else target.get('heading', False)
                if target_heading:
                    self.menu.selected_index = idx
                    self._sync_state_selection()
                    return
            return

        # Info items are non-interactive (skipped by MenuController)
        if not is_selectable:
            return

        if item_kind in ['playlist', 'dir', 'artist', 'album']:
            self.history.append((self.mode, self.current_path, self.menu.selected_index))
            new_mode = item.id.get('mode') if isinstance(item, Item) and isinstance(item.id, dict) else item.get('id', {}).get('mode')

            # Show loading for potentially large lists
            if new_mode in ['PLAYLIST_VIEW', 'RECENTS', 'ARTIST_VIEW', 'ALBUM_VIEW', 'FAV_TRACKS_VIEW', 'TRACKS_VIEW', 'ARTISTS_ROOT', 'ALBUMS_ROOT']:
                self._show_loading(t('general.loading'))

            self.mode = new_mode
            self.current_path = (item.id.get('path') or item.text) if isinstance(item, Item) and isinstance(item.id, dict) else (item.get('id', {}).get('path') or item.get('name'))
            self.refresh_list(reset_selection=True)
            self._hide_loading()
        elif item_kind == 'file':
            tpath = item.id.get('path') if isinstance(item, Item) and isinstance(item.id, dict) else item.get('id', {}).get('path')
            self._play_from_list(tpath)

    def nav_back(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            self.context_menu.go_back()
            self._sync_context_state()
            return

        if not self.history:
            self.running = False
            return

        self.mode, self.current_path, idx = self.history.pop()
        self.refresh_list(reset_selection=False)
        self.menu.selected_index = idx
        self._sync_state_selection()

    def nav_enter_long(self):
        if self._wake_from_screensaver():
            return
        if self.state.context_menu_active:
            return

        item = self.menu.get_selected_item()
        if not item: return

        item_kind = item.kind if isinstance(item, Item) else (item.get('id', {}).get('kind') if isinstance(item.get('id'), dict) else None)
        is_heading = item.heading if isinstance(item, Item) else item.get('heading', False)

        # Allow context menu for artists, albums, files, playlists, and headings (album headings in artist view)
        if item_kind in ['file', 'playlist', 'artist', 'album'] or is_heading:
            # Pass queue context for queue view items
            in_queue = self.state.browse_mode == 'QUEUE_VIEW'

            # Count pinned items
            pinned_count = len(self.state.pinned_items)
            queue_idx = self.menu.selected_index - pinned_count if in_queue else None

            self.context_menu.open(item, in_queue_view=in_queue, queue_index=queue_idx)
            self._sync_context_state()

    def _play_media(self, path, play=True):
        """Play a media file and update state."""
        self.state.playing_path = str(path)
        
        # Update playing metadata
        try:
            info = extract_track_info(Path(path))
            self.state.playing_artist = info.artist
            self.state.playing_album = info.album
        except (OSError, ValueError, AttributeError):
            self.state.playing_artist = None
            self.state.playing_album = None

        if play:
            self.audio.play(path)
            self.state.is_playing = True
        else:
            self.audio.stop()
            self.state.is_playing = False

        covers = get_cover(Path(path))
        self.state.playing_cover_s = covers[0]
        self.state.playing_cover_l = covers[1]

        if self.state.screensaver_image:
            self.state.screensaver_image = self.state.playing_cover_l or self.state.playing_cover_s

        if play:
            self.lib.add_recent(Path(path))

        if self.mode == 'QUEUE_VIEW':
            self.refresh_list(reset_selection=False)

    def toggle_play(self):
        if not self.state.screensaver_image:
            self.last_input_time = time.time()

        # If on screensaver with no song playing, play the screensaver album
        if self.state.screensaver_image and not self.state.playing_path and self.state.screensaver_album:
            self._play_screensaver_album()
            return

        self.state.is_playing = self.audio.toggle_pause()
        if self.state.is_playing:
            self.state.set_status_message(t('player.status.playing'))
        else:
            self.state.set_status_message(t('player.status.paused'))

    def next_track(self, from_user=True):
        if from_user and not self.state.screensaver_image:
            self.last_input_time = time.time()

        # Navigate controls bar buttons with next/prev when on controls item
        if from_user and not self.state.screensaver_image:
            item = self.menu.get_selected_item()
            is_column_nav = item.column_nav if isinstance(item, Item) else item.get('column_nav', False) if item else False
            if item and is_column_nav:
                self.state.controls_index = min(cfg.CONTROLS_BUTTON_COUNT - 1, self.state.controls_index + 1)
                return

        # Handle Loop One (Auto-advance only)
        if not from_user and self.state.loop_mode == 2 and self.state.playing_path:
            self._play_media(self.state.playing_path)
            return

        # Get next track from playlist manager
        next_path = self.playlist.next_track(auto_advance=not from_user)

        if next_path:
            if from_user:
                self.state.set_status_message(t('player.status.next'))
            self._play_media(next_path)
            return

        # Queue finished (Loop Off + Auto)
        if self._settings and self._settings.get('endless_playback', False):
            self._play_random_album()
        else:
            self.audio.stop()
            self.state.is_playing = False
            self.state.set_status_message(t('player.status.idle'))
            # Don't auto-reset to the first track; stay on the current (last) track

    def prev_track(self):
        if not self.state.screensaver_image:
            self.last_input_time = time.time()

        # Navigate controls bar buttons with next/prev when on controls item
        if not self.state.screensaver_image:
            item = self.menu.get_selected_item()
            is_column_nav = item.column_nav if isinstance(item, Item) else item.get('column_nav', False) if item else False
            if item and is_column_nav:
                self.state.controls_index = max(0, self.state.controls_index - 1)
                return

        path = self.playlist.prev_track()
        if path:
            self.state.set_status_message(t('player.status.previous'))
            self._play_media(path)

    def _load_track(self, real_idx, play=True):
        """Load a track by its index. If play is True, start playback."""
        path = self.playlist.playlist_source[real_idx]
        self._play_media(path, play=play)

    def update(self):
        """Update loop - check for track end, screensaver, etc."""
        if self.state.is_playing and self.audio.has_ended():
            self.next_track(from_user=False)

        if cfg.SCREENSAVER_TIMEOUT > 0:
            idle_time = time.time() - self.last_input_time
            if idle_time > cfg.SCREENSAVER_TIMEOUT:
                if self.state.screensaver_image is None:
                    self.state.needs_refresh = True

                # Show playing track's cover if a track is loaded (playing or paused)
                if self.state.playing_path:
                    self.state.screensaver_image = self.state.playing_cover_l or self.state.playing_cover_s
                    self.state.screensaver_album = None
                else:
                    # Only show random cover if no track is loaded (IDLE state)
                    if self.state.screensaver_image is None:
                        cover, album = self.lib.get_random_cover(with_album=True)
                        self.state.screensaver_image = cover if cover else Image.new('1', (1, 1))
                        self.state.screensaver_album = album

        return self.running

    def refresh_list(self, reset_selection=True):
        """Refresh the current list based on mode."""
        self.running = True
        self.state.is_scanning = self.lib.is_scanning
        self.state.browse_mode = self.mode
        self.state.reset_browsing_state(reset_controls=reset_selection)

        # Get items from BrowseHandler
        if self.mode == 'ROOT':
            self.state.album, items = self.browse.get_root_menu()
            
        elif self.mode == 'ARTISTS_ROOT':
            self.state.album, items = self.browse.get_artists_list()

        elif self.mode == 'ALBUMS_ROOT':
            self.state.album, items = self.browse.get_albums_list()

        elif self.mode == 'FAV_ARTISTS':
            self.state.album, items = self.browse.get_fav_artists_list()

        elif self.mode == 'FAV_ALBUMS':
            self.state.album, items = self.browse.get_fav_albums_list()

        elif self.mode == 'PLAYLISTS_ROOT':
            self.state.album, items = self.browse.get_playlists_list()

        elif self.mode == 'TRACKS_VIEW':
            shuffle = self.state.shuffle_active
            album, tracks, track_count, duration, cover = self.browse.get_all_tracks(shuffle=shuffle)
            self.state.album = album
            items = tracks if tracks else [Item(text='(No Tracks)', selectable=False)]
            if tracks:
                self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration
            if tracks: items = self._process_tracks(items)

        elif self.mode == 'FAV_TRACKS_VIEW':
            album, tracks, track_count, duration, cover = self.browse.get_fav_tracks()
            self.state.album = album
            items = tracks if tracks else [Item(text='(No Favourites)', selectable=False)]
            if tracks:
                self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration
            if tracks: items = self._process_tracks(items)

        elif self.mode == 'PLAYLIST_VIEW':
            album, tracks, track_count, duration, cover = self.browse.get_playlist_tracks(self.current_path)
            self.state.album = album
            self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration
            items = self._process_tracks(tracks)

        elif self.mode == 'RECENTS':
            album, tracks, track_count, duration, cover = self.browse.get_recents_tracks()
            self.state.album = album
            self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration
            items = self._process_tracks(tracks)

        elif self.mode == 'ARTIST_VIEW':
            album, tracks, track_count, duration, cover = self.browse.get_artist_tracks(self.current_path)
            self.state.album = album
            self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration
            items = self._process_tracks(tracks)

        elif self.mode == 'ALBUM_VIEW':
            album, tracks, artist, year, cover = self.browse.get_album_tracks(self.current_path)
            self.state.album = album
            self.state.browsing_cover_s = cover
            self.state.artist = artist
            self.state.year = year
            items = self._process_tracks(tracks)

        elif self.mode == 'FILES':
            album, items, cover = self.browse.get_files_list(self.current_path, self.state.playing_path)
            self.state.album = album
            self.state.browsing_cover_s = cover

        elif self.mode == 'QUEUE_VIEW':
            title, pinned, scrollable, cover = self.browse.get_queue_view(self.playlist, self.state.playing_path)
            self.state.album = title
            self.state.browsing_cover_s = cover

            # Combine logic similar to _load_tracks but handling pre-pinned
            items = list(pinned)
            items.append({'column_nav': True}) # Add controls
            items.extend(scrollable)

            # Manually set state for renderer
            self.state.pinned_items = list(pinned)
            self.state.pinned_items.append({'column_nav': True})
            self.state.scrollable_items = scrollable
        
        # Update MenuController
        self.menu.set_items(items, reset_index=reset_selection)
        
        # Determine scrollable items if not set by track logic
        if self.mode not in ['TRACKS_VIEW', 'FAV_TRACKS_VIEW', 'PLAYLIST_VIEW', 'RECENTS', 'ARTIST_VIEW', 'ALBUM_VIEW', 'QUEUE_VIEW']:
             self.state.scrollable_items = items
             self.state.items = items # For consistency
             self.state.pinned_items = []
        else:
             self.state.items = items

        self.state.total_items = len(self.state.items)
        self._sync_state_selection()

    def _process_tracks(self, tracks):
        """Convert track list to state items with controls bar."""
        # Separate pinned items from the rest
        pinned_items = [t for t in tracks if t.get('pinned')]
        other_items = [t for t in tracks if not t.get('pinned')]

        # Build final list
        final_items = list(pinned_items)
        final_items.append({'column_nav': True}) # Add controls

        processed_items = [
            t if t.get('heading') or not t.get('selectable', True) else {
                'name': t.get('title', ''),
                'id': {'kind': 'file', 'path': t.get('path')},
                'artist': t.get('artist'),
                'album': t.get('album'),
                'track': t.get('track', 0)
            }
            for t in other_items
        ]
        final_items.extend(processed_items)

        # Update state for renderer
        self.state.pinned_items = list(pinned_items)
        self.state.pinned_items.append({'column_nav': True})
        self.state.scrollable_items = processed_items

        return final_items

    def _play_screensaver_album(self):
        """Play the album shown on the screensaver."""
        album = self.state.screensaver_album
        if not album:
            return

        tracks = self.lib.get_album_tracks(album)
        if not tracks:
            return

        # Build playlist from album tracks
        self.playlist.playlist_source = [str(t['path']) for t in tracks]
        self.playlist.queue = list(range(len(self.playlist.playlist_source)))
        if self.state.shuffle_active:
            random.shuffle(self.playlist.queue)
        self.playlist.queue_idx = 0

        # Load and play first track
        self._load_track(self.playlist.queue[0])
        self.state.set_status_message(t('player.status.playing'))

    def _play_random_album(self):
        """Play a random album (used for endless playback)."""
        if not self.lib.albums:
            return

        # Pick a random album
        album = random.choice(list(self.lib.albums.keys()))
        tracks = self.lib.get_album_tracks(album)
        if not tracks:
            return

        # Build playlist from album tracks
        self.playlist.playlist_source = [str(t['path']) for t in tracks]
        self.playlist.queue = list(range(len(self.playlist.playlist_source)))
        if self.state.shuffle_active:
            random.shuffle(self.playlist.queue)
        self.playlist.queue_idx = 0

        # Wake screensaver to show new album
        if self.state.screensaver_image is not None:
            self.state.screensaver_image = None
            self.state.screensaver_album = None
            self.state.needs_refresh = True
            self.last_input_time = time.time()  # Reset timer to keep display on

        # Load and play first track
        self._load_track(self.playlist.queue[0])
        self.state.set_status_message(t('player.status.endless'))

    def _play_from_list(self, path):
        """Start playing from the current list."""
        # Filter to only file items using kind
        def get_file_path(item):
            if isinstance(item, Item):
                return item.id.get('path') if isinstance(item.id, dict) and item.kind == 'file' else None
            elif isinstance(item, dict):
                item_id = item.get('id', {})
                if isinstance(item_id, dict) and item_id.get('kind') == 'file':
                    return item_id.get('path')
            return None

        self.playlist.playlist_source = [str(get_file_path(i)) for i in self.state.items if get_file_path(i)]
        path_str = str(path)
        if not self.playlist.playlist_source:
            return

        self.playlist.queue = list(range(len(self.playlist.playlist_source)))
        if self.state.shuffle_active:
            random.shuffle(self.playlist.queue)

        try:
            real_idx = self.playlist.playlist_source.index(path_str)
        except ValueError:
            real_idx = 0

        if self.state.shuffle_active:
            if real_idx in self.playlist.queue:
                self.playlist.queue.remove(real_idx)
            self.playlist.queue.insert(0, real_idx)
            self.playlist.queue_idx = 0
        else:
            self.playlist.queue_idx = real_idx
        
        self.playlist.save_queue() # Save after building new queue
        self._load_track(real_idx)

    def _handle_controls_action(self):
        """Handle controls bar button actions."""
        idx = self.state.controls_index
        if idx == 0:
            self.nav_back()
        elif idx == 1:
            self.state.shuffle_active = not self.state.shuffle_active
            self.playlist.toggle_shuffle() # Sync with playlist manager

            if self.state.shuffle_active:
                self.state.set_status_message(t('player.status.shuffle_on'))
                if not self.state.playing_path:
                    # Filter to file items using kind
                    def is_file_item(item):
                        if isinstance(item, Item):
                            return item.kind == 'file'
                        elif isinstance(item, dict):
                            item_id = item.get('id', {})
                            return isinstance(item_id, dict) and item_id.get('kind') == 'file'
                        return False

                    files = [item for item in self.state.items if is_file_item(item)]
                    if files:
                        target = random.choice(files)
                        target_path = target.id.get('path') if isinstance(target, Item) else target.get('id', {}).get('path')
                        self._play_from_list(target_path)
            else:
                self.state.set_status_message(t('player.status.shuffle_off'))

            if self.mode == 'QUEUE_VIEW':
                self.refresh_list(reset_selection=False)

        elif idx == 2:
            self.state.loop_mode = (self.state.loop_mode + 1) % 3
            self.playlist.loop_mode = self.state.loop_mode # Sync with playlist manager
            loop_messages = [
                t('player.status.loop_off'),
                t('player.status.loop_all'),
                t('player.status.loop_one')
            ]
            self.state.set_status_message(loop_messages[self.state.loop_mode])
            
            if self.mode == 'QUEUE_VIEW':
                self.refresh_list(reset_selection=False)

        elif idx == 3:
            if self.mode == 'QUEUE_VIEW':
                self.playlist.clear_manual_queue()
                self.refresh_list(reset_selection=False)
            elif self.mode == 'ARTIST_VIEW':
                self.lib.toggle_fav_artist(self.state.album)
            else:
                self.lib.toggle_fav_album(self.state.album)

    def get_frame(self):
        """Render and return current frame."""
        if self.state.screensaver_image:
            return self.renderer.render_screensaver(self.state)

        # Pass all items - the Menu system handles scrolling based on cursor
        view_items = self.state.pinned_items + self.state.scrollable_items
        frame, scroll = self.renderer.render_music_view(self.state, view_items)
        self.state.scroll_offset = scroll
        return frame