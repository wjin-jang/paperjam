"""
Main music player application - orchestrates all components.
"""
import random
import time
from pathlib import Path
from PIL import Image

from core.library import LibraryManager
from core.metadata import get_cover
from core.track_info import extract_track_info
from core.navigation import nav_skip_info_up, nav_skip_info_down, find_next_heading
from ui.renderer import UIRenderer
import config as cfg

from apps.music.state import PlayerState
from apps.music.playlist import PlaylistManager
from apps.music.context_menu import ContextMenuHandler
from apps.music.browse import BrowseHandler


class MusicPlayerApp:
    """Main music player application."""

    def __init__(self, audio, input_handler):
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

    def _show_loading(self, message: str = "Loading..."):
        """Show loading overlay and force display update."""
        self.state.loading_message = message
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
        
        self.history.append((self.mode, self.current_path, self.state.selection_index))
        self.mode = 'QUEUE_VIEW'
        self.state.selection_index = 0
        self.refresh_list()

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
        self.state.context_options = self.context_menu.options
        self.state.context_index = self.context_menu.index
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
            if not self.state.items:
                return
            self.state.selection_index = nav_skip_info_up(self.state.selection_index, self.state.items)

    def nav_down(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            self.context_menu.select_down()
            self._sync_context_state()
        else:
            if not self.state.items:
                return
            self.state.selection_index = nav_skip_info_down(self.state.selection_index, self.state.items)

    def nav_enter(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            nav_req = self.context_menu.execute_action(self.mode, self.refresh_list)
            self._sync_context_state()

            if nav_req:
                self.history.append((self.mode, self.current_path, self.state.selection_index))
                self.mode = nav_req['mode']
                self.current_path = nav_req['path']
                self.state.selection_index = 0
                self.refresh_list()
            return

        # Bounds check before accessing items
        if not self.state.items or not (0 <= self.state.selection_index < len(self.state.items)):
            return
        item = self.state.items[self.state.selection_index]
        item_type = item.get('type')

        # Controls bar - handle button press
        if item_type == 'controls':
            self._handle_controls_action()
            return

        # Clicking a heading jumps to the next heading
        if item_type == 'heading':
            self.state.selection_index = find_next_heading(self.state.selection_index, self.state.items)
            return

        # Info items are non-interactive
        if item_type == 'info':
            return

        if item['type'] in ['playlist', 'dir', 'artist', 'album']:
            self.history.append((self.mode, self.current_path, self.state.selection_index))
            new_mode = item['mode']

            # Show loading for potentially large lists
            if new_mode in ['PLAYLIST_VIEW', 'RECENTS', 'ARTIST_VIEW', 'ALBUM_VIEW', 'FAV_TRACKS_VIEW', 'TRACKS_VIEW', 'ARTISTS_ROOT', 'ALBUMS_ROOT']:
                self._show_loading("Loading...")

            self.mode = new_mode
            self.current_path = item.get('path', item.get('name'))
            self.state.selection_index = 0
            self.refresh_list()
            self._hide_loading()
        elif item['type'] == 'file':
            self._play_from_list(item['path'])

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
        self.refresh_list()
        self.state.selection_index = idx

    def nav_enter_long(self):
        if self._wake_from_screensaver():
            return
        if self.state.context_menu_active:
            return

        # Bounds check before accessing items
        if not self.state.items or not (0 <= self.state.selection_index < len(self.state.items)):
            return
        item = self.state.items[self.state.selection_index]
        # Allow context menu for artists and albums too now
        if item['type'] in ['file', 'playlist', 'artist', 'album']:
            self.context_menu.open(item)
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
            self.refresh_list()

    def toggle_play(self):
        if not self.state.screensaver_image:
            self.last_input_time = time.time()

        # If on screensaver with no song playing, play the screensaver album
        if self.state.screensaver_image and not self.state.playing_path and self.state.screensaver_album:
            self._play_screensaver_album()
            return

        self.state.is_playing = self.audio.toggle_pause()
        if self.state.is_playing:
            self.state.set_status_message("PLAYING")
        else:
            self.state.set_status_message("PAUSED")

    def next_track(self, from_user=True):
        if from_user and not self.state.screensaver_image:
            self.last_input_time = time.time()

        # Navigate controls bar buttons with next/prev when on controls item
        if from_user and not self.state.screensaver_image:
            item = self.state.items[self.state.selection_index] if self.state.items else None
            if item and item.get('type') == 'controls':
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
                self.state.set_status_message("NEXT")
            self._play_media(next_path)
            return

        # Queue finished (Loop Off + Auto)
        if self._settings and self._settings.get('endless_playback', False):
            self._play_random_album()
        else:
            self.audio.stop()
            self.state.is_playing = False
            self.state.set_status_message("IDLE")
            # Don't auto-reset to the first track; stay on the current (last) track

    def prev_track(self):
        if not self.state.screensaver_image:
            self.last_input_time = time.time()

        # Navigate controls bar buttons with next/prev when on controls item
        if not self.state.screensaver_image:
            item = self.state.items[self.state.selection_index] if self.state.items else None
            if item and item.get('type') == 'controls':
                self.state.controls_index = max(0, self.state.controls_index - 1)
                return

        path = self.playlist.prev_track()
        if path:
            self.state.set_status_message("PREVIOUS")
            self._play_media(path)

    def _load_track(self, real_idx, play=True):
        """Load a track by its index. If play is True, start playback."""
        path = self.playlist.playlist_source[real_idx]
        self.state.playing_path = path
        
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
            self.refresh_list()

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

    def _set_initial_selection(self):
        """Set selection to the first selectable item (skipping headers/controls)."""
        self.state.selection_index = 0
        for i, item in enumerate(self.state.items):
            itype = item.get('type')
            if itype not in ('heading', 'info', 'controls'):
                self.state.selection_index = i
                break

    def refresh_list(self, reset_selection=True):
        """Refresh the current list based on mode."""
        self.running = True
        self.state.is_scanning = self.lib.is_scanning
        self.state.browse_mode = self.mode
        self.state.reset_browsing_state(reset_controls=reset_selection)

        if self.mode == 'ROOT':
            self.state.album, self.state.items = self.browse.get_root_menu()
            self.state.scrollable_items = self.state.items

        elif self.mode == 'ARTISTS_ROOT':
            self.state.album, self.state.items = self.browse.get_artists_list()
            self.state.scrollable_items = self.state.items

        elif self.mode == 'ALBUMS_ROOT':
            self.state.album, self.state.items = self.browse.get_albums_list()
            self.state.scrollable_items = self.state.items

        elif self.mode == 'FAV_ARTISTS':
            self.state.album, self.state.items = self.browse.get_fav_artists_list()
            self.state.scrollable_items = self.state.items

        elif self.mode == 'FAV_ALBUMS':
            self.state.album, self.state.items = self.browse.get_fav_albums_list()
            self.state.scrollable_items = self.state.items

        elif self.mode == 'PLAYLISTS_ROOT':
            self.state.album, self.state.items = self.browse.get_playlists_list()
            self.state.scrollable_items = self.state.items

        elif self.mode == 'TRACKS_VIEW':
            shuffle = self.state.shuffle_active
            album, tracks, track_count, duration, cover = self.browse.get_all_tracks(shuffle=shuffle)
            self.state.album = album
            if not tracks:
                self.state.items = [{'name': '(No Tracks)', 'type': 'info'}]
                self.state.scrollable_items = self.state.items
            else:
                self._load_tracks(tracks)
                self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration

        elif self.mode == 'FAV_TRACKS_VIEW':
            album, tracks, track_count, duration, cover = self.browse.get_fav_tracks()
            self.state.album = album
            if not tracks:
                self.state.items = [{'name': '(No Fav Songs)', 'type': 'info'}]
                self.state.scrollable_items = self.state.items
            else:
                self._load_tracks(tracks)
                self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration

        elif self.mode == 'PLAYLIST_VIEW':
            album, tracks, track_count, duration, cover = self.browse.get_playlist_tracks(self.current_path)
            self.state.album = album
            self._load_tracks(tracks)
            self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration

        elif self.mode == 'RECENTS':
            album, tracks, track_count, duration, cover = self.browse.get_recents_tracks()
            self.state.album = album
            self._load_tracks(tracks)
            self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration

        elif self.mode == 'ARTIST_VIEW':
            album, tracks, track_count, duration, cover = self.browse.get_artist_tracks(self.current_path)
            self.state.album = album
            self._load_tracks(tracks)
            self.state.browsing_cover_s = cover
            self.state.artist = track_count
            self.state.year = duration

        elif self.mode == 'ALBUM_VIEW':
            album, tracks, artist, year, cover = self.browse.get_album_tracks(self.current_path)
            self.state.album = album
            self._load_tracks(tracks)
            self.state.browsing_cover_s = cover
            self.state.artist = artist
            self.state.year = year

        elif self.mode == 'FILES':
            album, items, cover = self.browse.get_files_list(self.current_path, self.state.playing_path)
            self.state.album = album
            self.state.items = items
            self.state.scrollable_items = items
            self.state.browsing_cover_s = cover

        elif self.mode == 'QUEUE_VIEW':
            title, pinned, scrollable, cover = self.browse.get_queue_view(self.playlist, self.state.playing_path)
            self.state.album = title
            self.state.pinned_items = pinned
            self.state.scrollable_items = scrollable
            self.state.items = pinned + scrollable
            self.state.browsing_cover_s = cover

        self.state.total_items = len(self.state.items)
        
        if reset_selection:
            self._set_initial_selection()
        else:
            # Clamp selection to bounds if list shrank
            if self.state.items:
                self.state.selection_index = max(0, min(self.state.selection_index, self.state.total_items - 1))
            else:
                self.state.selection_index = 0

    def _load_tracks(self, tracks):
        """Convert track list to state items with controls bar."""
        # Separate pinned items from the rest
        pinned_items = [t for t in tracks if t.get('pinned')]
        other_items = [t for t in tracks if not t.get('pinned')]

        # Build items: pinned first, then controls bar
        self.state.items = list(pinned_items)
        self.state.pinned_items = list(pinned_items)
        
        controls_idx = len(self.state.items)
        self.state.items.append({'type': 'controls'})
        self.state.pinned_items.append({'type': 'controls'})

        # Set initial selection to controls bar
        self.state.selection_index = controls_idx

        # Optimized list construction
        playing_path = self.state.playing_path
        
        # Pre-process items that don't need conversion (heading, info)
        # and convert track items in one pass using list comprehension
        processed_items = [
            t if t.get('type') in ('heading', 'info') else {
                'name': t.get('title', ''),
                'type': 'file',
                'path': t.get('path'),
                'icon': 'P' if playing_path == str(t.get('path', '')) else 'S',
                'artist': t.get('artist'),
                'album': t.get('album'),
                'track': t.get('track', 0)
            }
            for t in other_items
        ]
        
        self.state.items.extend(processed_items)
        self.state.scrollable_items = processed_items

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
        self.state.set_status_message("PLAYING")

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

        # Load and play first track
        self._load_track(self.playlist.queue[0])
        self.state.set_status_message("ENDLESS")

    def _play_from_list(self, path):
        """Start playing from the current list."""
        self.playlist.playlist_source = [str(i['path']) for i in self.state.items if i['type'] == 'file']
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
                self.state.set_status_message("SHUFFLE ON")
                if not self.state.playing_path:
                    files = [item for item in self.state.items if item.get('type') == 'file']
                    if files:
                        target = random.choice(files)
                        self._play_from_list(target['path'])
            else:
                self.state.set_status_message("SHUFFLE OFF")
            
            if self.mode == 'QUEUE_VIEW':
                self.refresh_list(reset_selection=False)

        elif idx == 2:
            self.state.loop_mode = (self.state.loop_mode + 1) % 3
            self.playlist.loop_mode = self.state.loop_mode # Sync with playlist manager
            loop_messages = ["LOOP OFF", "LOOP ALL", "LOOP ONE"]
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
        return self.renderer.render_music_view(self.state, view_items)
