"""
Main music player application - orchestrates all components.
"""
import random
import time
from pathlib import Path
from PIL import Image

from core.library import LibraryManager
from core.metadata import get_cover
from core.navigation import nav_index_up, nav_index_down
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

        # Initialize components
        self.state = PlayerState(items=[], fav_albums=self.lib.fav_albums)
        self.playlist = PlaylistManager()
        self.context_menu = ContextMenuHandler(self.lib)
        self.browse = BrowseHandler(self.lib)

        # Navigation state
        self.history = []
        self.mode = 'ROOT'
        self.current_path = cfg.MUSIC_PATH

        # Timing
        self.last_input_time = time.time()
        self.running = True

        self.refresh_list()

    def get_callbacks(self):
        """Return input callbacks for the music player."""
        return {
            'up': self.nav_up,
            'down': self.nav_down,
            'enter': self.nav_enter,
            'enter_long': self.nav_enter_long,
            'back': self.nav_back,
            'play_pause': self.toggle_play,
            'next': self.next_track,
            'prev': self.prev_track
        }

    def _wake_from_screensaver(self):
        """Wake from screensaver if active. Returns True if was active."""
        was_active = self.state.screensaver_image is not None
        self.last_input_time = time.time()
        self.state.screensaver_image = None

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
            self.state.selection_index = nav_index_up(self.state.selection_index, len(self.state.items))

    def nav_down(self):
        if self._wake_from_screensaver():
            return

        if self.state.context_menu_active:
            self.state.context_index = nav_index_down(self.state.context_index, len(self.state.context_options))
        else:
            if not self.state.items:
                return
            self.state.selection_index = nav_index_down(self.state.selection_index, len(self.state.items))

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
        if item['type'] in ['playlist', 'dir', 'artist', 'album']:
            self.history.append((self.mode, self.current_path, self.state.selection_index))
            self.mode = item['mode']
            self.current_path = item.get('path', item.get('name'))
            self.state.selection_index = 0
            self.refresh_list()
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

        self.playlist.queue_idx = (self.playlist.queue_idx + 1) % len(self.playlist.queue)
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

                if self.state.is_playing:
                    self.state.screensaver_image = self.state.playing_cover_l or self.state.playing_cover_s
                else:
                    if self.state.screensaver_image is None:
                        self.state.screensaver_image = self.lib.get_random_cover()
                        if not self.state.screensaver_image:
                            self.state.screensaver_image = Image.new('1', (1, 1))

        return self.running

    def refresh_list(self):
        """Refresh the current list based on mode."""
        self.running = True
        self.state.is_scanning = self.lib.is_scanning
        self.state.reset_browsing_state()

        if self.mode == 'ROOT':
            self.state.album, self.state.items = self.browse.get_root_menu()

        elif self.mode == 'ARTISTS_ROOT':
            self.state.album, self.state.items = self.browse.get_artists_list()

        elif self.mode == 'ALBUMS_ROOT':
            self.state.album, self.state.items = self.browse.get_albums_list()

        elif self.mode == 'FAV_ALBUMS':
            self.state.album, self.state.items = self.browse.get_fav_albums_list()

        elif self.mode == 'PLAYLISTS_ROOT':
            self.state.album, self.state.items = self.browse.get_playlists_list()

        elif self.mode == 'FAV_TRACKS_VIEW':
            album, tracks, artist, year, cover = self.browse.get_fav_tracks()
            self.state.album = album
            if not tracks:
                self.state.items = [{'name': '(No Fav Songs)', 'type': 'info'}]
            else:
                self._load_tracks(tracks)
                self.state.browsing_cover_s = cover
            self.state.artist = artist
            self.state.year = year

        elif self.mode == 'PLAYLIST_VIEW':
            album, tracks, artist, year, cover = self.browse.get_playlist_tracks(self.current_path)
            self.state.album = album
            self._load_tracks(tracks)
            self.state.browsing_cover_s = cover
            self.state.artist = artist
            self.state.year = year

        elif self.mode == 'RECENTS':
            album, tracks, artist, year, cover = self.browse.get_recents_tracks()
            self.state.album = album
            self._load_tracks(tracks)
            self.state.browsing_cover_s = cover
            self.state.artist = ""
            self.state.year = ""

        elif self.mode == 'ARTIST_VIEW':
            album, tracks, artist, year, cover = self.browse.get_artist_tracks(self.current_path)
            self.state.album = album
            self._load_tracks(tracks)
            self.state.browsing_cover_s = cover
            self.state.artist = artist
            self.state.year = year

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
            icon = 'P' if self.state.playing_path == str(t['path']) else 'S'
            self.state.items.append({
                'name': t.get('title', ''),
                'type': 'file',
                'path': t['path'],
                'icon': icon,
                'artist': t.get('artist'),
                'album': t.get('album')
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
            self.lib.toggle_fav_album(self.state.album)

    def get_frame(self):
        """Render and return current frame."""
        if self.state.screensaver_image:
            return self.renderer.render_screensaver(self.state)

        current_list_y = cfg.PANEL_Y + cfg.ROW_HEIGHT
        if self.state.artist:
            current_list_y += cfg.ROW_HEIGHT
        avail_h = (cfg.PANEL_Y + cfg.PANEL_H) - current_list_y
        self.state.page_size = max(1, avail_h // cfg.ROW_HEIGHT)

        page = self.state.page_size
        sel = self.state.selection_index
        start = (sel // page) * page
        self.state.view_start_index = start

        view_items = self.state.items[start: start + page + 1]

        return self.renderer.render_music_view(self.state, view_items)
