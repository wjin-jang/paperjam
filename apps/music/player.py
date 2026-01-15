"""
Main music player application - orchestrates all components.
"""
import random
import time
from pathlib import Path
from PIL import Image

from core.library import LibraryManager
from core.metadata import get_cover
from core.navigation import nav_index_up, nav_index_down, nav_skip_info_up, nav_skip_info_down, find_next_heading
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
        self.context_menu = ContextMenuHandler(self.lib)
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

    def _wake_from_screensaver(self):
        """Wake from screensaver if active. Returns True if was active."""
        was_active = self.state.screensaver_image is not None
        self.last_input_time = time.time()
        self.state.screensaver_image = None
        self.state.screensaver_album = None

        if was_active:
            self.state.needs_refresh = True

        return was_active

    # --- Navigation Keys ---
    def nav_up(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            self.state.context_index = nav_index_up(self.state.context_index, len(self.state.context_options))
        else:
            if not self.state.items:
                return
            self.state.selection_index = nav_skip_info_up(self.state.selection_index, self.state.items)

    def nav_down(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            self.state.context_index = nav_index_down(self.state.context_index, len(self.state.context_options))
        else:
            if not self.state.items:
                return
            self.state.selection_index = nav_skip_info_down(self.state.selection_index, self.state.items)

    def nav_enter(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            self._handle_context_action()
            return
        if self.state.has_header and self.state.selection_index == 0:
            self._handle_header_action()
            return

        item = self.state.items[self.state.selection_index]

        # Clicking a heading jumps to the next heading
        if item.get('type') == 'heading':
            self.state.selection_index = find_next_heading(self.state.selection_index, self.state.items)
            return

        # Info items are non-interactive
        if item.get('type') == 'info':
            return

        if item['type'] in ['playlist', 'dir', 'artist', 'album']:
            self.history.append((self.mode, self.current_path, self.state.selection_index))
            new_mode = item['mode']

            # Show loading for potentially large lists
            if new_mode in ['PLAYLIST_VIEW', 'RECENTS', 'ARTIST_VIEW', 'ALBUM_VIEW', 'FAV_TRACKS_VIEW', 'TRACKS_VIEW']:
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
            if self.state.context_layer == 1:
                self._open_context_menu(self.state.context_target_item)
            else:
                self.state.context_menu_active = False
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

        item = self.state.items[self.state.selection_index]
        if item['type'] == 'file' or (self.mode == 'PLAYLISTS_ROOT' and item['type'] == 'playlist'):
            self._open_context_menu(item)

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

        if from_user and not self.state.screensaver_image and self.state.has_header and self.state.selection_index == 0:
            self.state.top_bar_index = min(3, self.state.top_bar_index + 1)
            return

        if not self.playlist.has_queue:
            return

        # Check if we're about to wrap around to the beginning
        next_idx = (self.playlist.queue_idx + 1) % len(self.playlist.queue)
        at_end = next_idx == 0 and not from_user

        # If endless playback is enabled and we've reached the end, play a random album
        if at_end and self._settings and self._settings.get('endless_playback', False):
            self._play_random_album()
            return

        self.playlist.queue_idx = next_idx
        real_idx = self.playlist.queue[self.playlist.queue_idx]
        if from_user:
            self.state.set_status_message("NEXT")
        self._load_track(real_idx)

    def prev_track(self):
        if not self.state.screensaver_image:
            self.last_input_time = time.time()

        if not self.state.screensaver_image and self.state.has_header and self.state.selection_index == 0:
            self.state.top_bar_index = max(0, self.state.top_bar_index - 1)
            return

        if not self.playlist.has_queue:
            return

        self.playlist.queue_idx = (self.playlist.queue_idx - 1) % len(self.playlist.queue)
        real_idx = self.playlist.queue[self.playlist.queue_idx]
        self.state.set_status_message("PREVIOUS")
        self._load_track(real_idx)

    def _load_track(self, real_idx):
        """Load and play a track by its index in the playlist source."""
        path = self.playlist.playlist_source[real_idx]
        self.state.playing_path = path
        self.audio.play(path)
        self.state.is_playing = True

        covers = get_cover(Path(path))
        self.state.playing_cover_s = covers[0]
        self.state.playing_cover_l = covers[1]

        if self.state.screensaver_image:
            self.state.screensaver_image = self.state.playing_cover_l or self.state.playing_cover_s

        self.lib.add_recent(Path(path))

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

    def refresh_list(self):
        """Refresh the current list based on mode."""
        self.running = True
        self.state.is_scanning = self.lib.is_scanning
        self.state.browse_mode = self.mode
        self.state.reset_browsing_state()

        if self.mode == 'ROOT':
            self.state.album, self.state.items = self.browse.get_root_menu()

        elif self.mode == 'ARTISTS_ROOT':
            self.state.album, self.state.items = self.browse.get_artists_list()

        elif self.mode == 'ALBUMS_ROOT':
            self.state.album, self.state.items = self.browse.get_albums_list()

        elif self.mode == 'FAV_ARTISTS':
            self.state.album, self.state.items = self.browse.get_fav_artists_list()

        elif self.mode == 'FAV_ALBUMS':
            self.state.album, self.state.items = self.browse.get_fav_albums_list()

        elif self.mode == 'PLAYLISTS_ROOT':
            self.state.album, self.state.items = self.browse.get_playlists_list()

        elif self.mode == 'TRACKS_VIEW':
            shuffle = self.state.shuffle_active
            album, tracks, track_count, duration, cover = self.browse.get_all_tracks(shuffle=shuffle)
            self.state.album = album
            if not tracks:
                self.state.items = [{'name': '(No Tracks)', 'type': 'info'}]
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
            self.state.browsing_cover_s = cover

        self.state.total_items = len(self.state.items)

    def _load_tracks(self, tracks):
        """Convert track list to state items with header."""
        self.state.has_header = True
        self.state.items = [{'type': 'header'}]
        for t in tracks:
            item_type = t.get('type')
            # Pass through heading and info items as-is
            if item_type in ('heading', 'info'):
                self.state.items.append(t)
                continue
            # Convert track dicts to item format
            icon = 'P' if self.state.playing_path == str(t.get('path', '')) else 'S'
            self.state.items.append({
                'name': t.get('title', ''),
                'type': 'file',
                'path': t.get('path'),
                'icon': icon,
                'artist': t.get('artist'),
                'album': t.get('album'),
                'track': t.get('track', 0)
            })

    def _open_context_menu(self, item):
        """Open context menu for an item."""
        self.state.context_menu_active = True
        self.state.context_index = 0
        self.state.context_target_item = item
        self.state.context_layer = 0

        opts = []
        if item['type'] == 'playlist':
            opts = ["Delete Playlist", "Cancel"]
        elif item['type'] == 'file':
            opts = ["Favourite Song", "Add to Playlist"]
            if item.get('artist'):
                opts.append("Go to Artist")
            if item.get('album'):
                opts.append("Go to Album")
            opts.append("Cancel")
        self.state.context_options = opts

    def _handle_context_action(self):
        """Handle context menu action selection."""
        idx = self.state.context_index
        opt = self.state.context_options[idx]
        target = self.state.context_target_item

        if self.state.context_layer == 0:
            if opt == "Cancel":
                self.state.context_menu_active = False
            elif opt == "Favourite Song":
                self.lib.toggle_fav_track(str(target['path']))
                self.state.context_menu_active = False
                if self.mode == 'FAV_TRACKS_VIEW':
                    self.refresh_list()
            elif opt == "Delete Playlist":
                self.lib.delete_playlist(target['path'])
                self.state.context_menu_active = False
                self.refresh_list()
            elif opt == "Add to Playlist":
                self.state.context_layer = 1
                self.state.context_index = 0
                pl_files = self.lib.get_playlists()
                self.state.context_options = ["New Playlist"] + [f"Add to: {p.stem}" for p in pl_files]
            elif opt == "Go to Artist":
                self.state.context_menu_active = False
                self.history.append((self.mode, self.current_path, self.state.selection_index))
                self.mode = 'ARTIST_VIEW'
                self.current_path = target['artist']
                self.state.selection_index = 0
                self.refresh_list()
            elif opt == "Go to Album":
                self.state.context_menu_active = False
                self.history.append((self.mode, self.current_path, self.state.selection_index))
                self.mode = 'ALBUM_VIEW'
                self.current_path = target['album']
                self.state.selection_index = 0
                self.refresh_list()

        elif self.state.context_layer == 1:
            if opt == "New Playlist":
                p = self.lib.create_playlist()
                self.lib.add_to_playlist(p, target['path'])
            else:
                pl_name = opt.replace("Add to: ", "")
                p = cfg.PLAYLIST_DIR / f"{pl_name}.json"
                self.lib.add_to_playlist(p, target['path'])
            self.state.context_menu_active = False

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

    def _handle_header_action(self):
        """Handle header bar button actions."""
        idx = self.state.top_bar_index
        if idx == 0:
            self.nav_back()
        elif idx == 1:
            self.state.shuffle_active = not self.state.shuffle_active
            if self.state.shuffle_active:
                self.state.set_status_message("SHUFFLE ON")
                if not self.state.playing_path:
                    files = [item for item in self.state.items if item.get('type') == 'file']
                    if files:
                        target = random.choice(files)
                        self._play_from_list(target['path'])
            else:
                self.state.set_status_message("SHUFFLE OFF")
        elif idx == 2:
            self.state.loop_mode = (self.state.loop_mode + 1) % 3
            loop_messages = ["LOOP OFF", "LOOP ALL", "LOOP ONE"]
            self.state.set_status_message(loop_messages[self.state.loop_mode])
        elif idx == 3:
            if self.mode == 'ARTIST_VIEW':
                self.lib.toggle_fav_artist(self.state.album)
            else:
                self.lib.toggle_fav_album(self.state.album)

    def get_frame(self):
        """Render and return current frame."""
        if self.state.screensaver_image:
            return self.renderer.render_screensaver(self.state)

        # Separate header, pinned items, and scrollable items
        header_items = [item for item in self.state.items if item.get('type') == 'header']
        pinned_items = [item for item in self.state.items if item.get('pinned')]
        scrollable_items = [item for item in self.state.items
                           if item.get('type') != 'header' and not item.get('pinned')]

        pinned_count = len(pinned_items)
        header_count = len(header_items)
        fixed_count = header_count + pinned_count

        current_list_y = cfg.PANEL_Y + cfg.ROW_HEIGHT + (pinned_count * cfg.ROW_HEIGHT)
        avail_h = (cfg.PANEL_Y + cfg.PANEL_H) - current_list_y
        self.state.page_size = max(1, avail_h // cfg.ROW_HEIGHT)

        page = self.state.page_size
        # Selection index relative to scrollable items (after header + pinned)
        sel = max(0, self.state.selection_index - fixed_count)
        start = (sel // page) * page
        self.state.view_start_index = start

        # Order: header, pinned items, then slice of scrollable items
        view_items = header_items + pinned_items + scrollable_items[start: start + page + 1]

        return self.renderer.render_music_view(self.state, view_items)
