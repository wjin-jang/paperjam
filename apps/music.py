import random
import time
from pathlib import Path
from dataclasses import dataclass, field
from core.library import LibraryManager
# Updated import
from core.metadata import get_metadata, get_cover
from ui.renderer import UIRenderer
import config as cfg

@dataclass
class PlayerState:
    items: list 
    selection_index: int = 0
    view_start_index: int = 0
    top_bar_index: int = 0
    album: str = "Library"
    artist: str = ""
    year: str = ""
    has_header: bool = False
    is_playing: bool = False
    shuffle_active: bool = False
    loop_mode: int = 0
    playing_path: str = None
    
    # Images
    playing_cover_s: object = None
    playing_cover_l: object = None
    browsing_cover_s: object = None
    screensaver_image: object = None
    
    # Flags
    needs_refresh: bool = False
    fav_albums: set = None
    is_scanning: bool = False
    total_items: int = 0
    page_size: int = 7
    context_menu_active: bool = False
    context_options: list = field(default_factory=list)
    context_index: int = 0
    context_target_item: dict = None
    context_layer: int = 0

class MusicPlayerApp:
    def __init__(self, audio, input_handler):
        self.audio = audio
        self.input = input_handler
        self.lib = LibraryManager()
        self.renderer = UIRenderer()
        
        self.state = PlayerState(items=[], fav_albums=self.lib.fav_albums)
        self.history = []
        self.mode = 'ROOT'
        self.current_path = cfg.MUSIC_PATH
        self.queue = []
        self.queue_idx = 0
        self.playlist_source = []
        self.last_input_time = time.time()
        
        self.running = True 
        self.refresh_list()

    def get_callbacks(self):
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
        was_active = self.state.screensaver_image is not None
        self.last_input_time = time.time()
        self.state.screensaver_image = None
        
        if was_active:
            self.state.needs_refresh = True
            
        return was_active

    # --- Navigation Keys ---
    def nav_up(self):
        if self._wake_from_screensaver(): return

        if self.state.context_menu_active:
            self.state.context_index = (self.state.context_index - 1) % len(self.state.context_options)
        else:
            if not self.state.items: return
            self.state.selection_index = (self.state.selection_index - 1) % len(self.state.items)

    def nav_down(self):
        if self._wake_from_screensaver(): return

        if self.state.context_menu_active:
            self.state.context_index = (self.state.context_index + 1) % len(self.state.context_options)
        else:
            if not self.state.items: return
            self.state.selection_index = (self.state.selection_index + 1) % len(self.state.items)

    def nav_enter(self):
        if self._wake_from_screensaver(): return

        if self.state.context_menu_active:
            self._handle_context_action()
            return
        if self.state.has_header and self.state.selection_index == 0:
            self._handle_header_action()
            return
        item = self.state.items[self.state.selection_index]
        if item['type'] == 'playlist':
            self.history.append((self.mode, self.current_path, self.state.selection_index))
            self.mode = item['mode']
            self.current_path = item.get('path', item.get('name'))
            self.state.selection_index = 0
            self.refresh_list()
        elif item['type'] == 'dir' or item['type'] in ['artist', 'album']:
            self.history.append((self.mode, self.current_path, self.state.selection_index))
            self.mode = item['mode']
            self.current_path = item.get('path', item.get('name'))
            self.state.selection_index = 0
            self.refresh_list()
        elif item['type'] == 'file':
            self._play_from_list(item['path'])

    def nav_back(self):
        if self._wake_from_screensaver(): return

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
        if self._wake_from_screensaver(): return
        if self.state.context_menu_active: return
        item = self.state.items[self.state.selection_index]
        if item['type'] == 'file' or (self.mode == 'PLAYLISTS_ROOT' and item['type'] == 'playlist'):
            self._open_context_menu(item)

    def toggle_play(self):
        if not self.state.screensaver_image:
            self.last_input_time = time.time()
            
        self.state.is_playing = self.audio.toggle_pause()

    def next_track(self, from_user=True):
        if from_user and not self.state.screensaver_image:
            self.last_input_time = time.time()

        if from_user and not self.state.screensaver_image and self.state.has_header and self.state.selection_index == 0:
            self.state.top_bar_index = min(3, self.state.top_bar_index + 1)
            return

        if not self.queue: return
        self.queue_idx = (self.queue_idx + 1) % len(self.queue)
        self._load_track(self.queue[self.queue_idx])

    def prev_track(self):
        if not self.state.screensaver_image:
            self.last_input_time = time.time()

        if not self.state.screensaver_image and self.state.has_header and self.state.selection_index == 0:
            self.state.top_bar_index = max(0, self.state.top_bar_index - 1)
            return
        if not self.queue: return
        self.queue_idx = (self.queue_idx - 1) % len(self.queue)
        self._load_track(self.queue[self.queue_idx])

    def _load_track(self, real_idx):
        path = self.playlist_source[real_idx]
        self.state.playing_path = path
        self.audio.play(path)
        self.state.is_playing = True
        
        # Heavy operation: Load cover ONLY
        covers = get_cover(Path(path))
        self.state.playing_cover_s = covers[0]
        self.state.playing_cover_l = covers[1]
        
        if self.state.screensaver_image:
            self.state.screensaver_image = self.state.playing_cover_l or self.state.playing_cover_s
            
        self.lib.add_recent(Path(path))

    def update(self):
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
                            from PIL import Image
                            self.state.screensaver_image = Image.new('1', (1,1))
        return self.running
    
    def refresh_list(self):
        self.running = True 
        self.state.is_scanning = self.lib.is_scanning
        self.state.items = []
        self.state.artist = ""
        self.state.year = ""
        self.state.has_header = False
        self.state.browsing_cover_s = None
        
        if self.mode == 'ROOT':
            self.state.album = "MAIN MENU"
            self.state.items = [
                {'name': 'Artists', 'type': 'dir', 'mode': 'ARTISTS_ROOT', 'icon': 'Ⓐ'},
                {'name': 'Albums', 'type': 'dir', 'mode': 'ALBUMS_ROOT', 'icon': 'Ⓑ'},
                {'name': 'Fav Albums', 'type': 'dir', 'mode': 'FAV_ALBUMS', 'icon': 'Ⓗ'},
                {'name': 'Playlists', 'type': 'dir', 'mode': 'PLAYLISTS_ROOT', 'icon': 'Ⓛ'},
                {'name': 'Recents', 'type': 'dir', 'mode': 'RECENTS', 'icon': 'Ⓡ'},
                {'name': 'Files', 'type': 'dir', 'mode': 'FILES', 'path': cfg.MUSIC_PATH, 'icon': 'Ⓕ'}
            ]
        elif self.mode == 'ARTISTS_ROOT':
            self.state.album = "ARTISTS"
            self.state.items = [{'name': k, 'type': 'artist', 'mode': 'ARTIST_VIEW'} for k in self.lib.artists.keys()]
        elif self.mode == 'ALBUMS_ROOT':
            self.state.album = "ALBUMS"
            self.state.items = [{'name': k, 'type': 'album', 'mode': 'ALBUM_VIEW'} for k in self.lib.albums.keys()]
        elif self.mode == 'FAV_ALBUMS':
            self.state.album = "FAV ALBUMS"
            if not self.lib.fav_albums:
                self.state.items = [{'name': '(No Fav Albums)', 'type': 'info'}]
            else:
                self.state.items = [{'name': k, 'type': 'album', 'mode': 'ALBUM_VIEW', 'icon': 'Ⓗ'} for k in sorted(self.lib.fav_albums, key=lambda s: s.lower())]
        elif self.mode == 'PLAYLISTS_ROOT':
            self.state.album = "PLAYLISTS"
            items = []
            items.append({'name': 'Favourites', 'type': 'playlist', 'mode': 'FAV_TRACKS_VIEW', 'icon': 'Ⓗ'})
            playlists = self.lib.get_playlists()
            for p in playlists:
                items.append({'name': p.stem, 'type': 'playlist', 'path': p, 'mode': 'PLAYLIST_VIEW'})
            self.state.items = items
        elif self.mode == 'FAV_TRACKS_VIEW':
            self.state.album = "FAVOURITES"
            tracks = self.lib.get_fav_tracks_list()
            if not tracks:
                self.state.items = [{'name': '(No Fav Songs)', 'type': 'info'}]
            else:
                self._load_tracks(tracks)
            self.state.artist = ""
            self.state.year = ""
        elif self.mode == 'PLAYLIST_VIEW':
            self.state.album = self.current_path.stem
            self._load_tracks(self.lib.get_playlist_tracks(self.current_path))
            self.state.artist = ""
            self.state.year = ""
        elif self.mode == 'RECENTS':
            self.state.album = "RECENTS"
            tracks = []
            for p in self.lib.recents:
                 if p.exists():
                     try:
                         meta = get_metadata(p)
                         title = meta[2] if meta and meta[2] else p.stem
                         artist = meta[1] if meta else None
                         album = meta[0] if meta else None
                         year = meta[5] if meta else None
                     except:
                         title = p.stem; artist = None; album = None; year = None
                     
                     tracks.append({'path': p, 'title': title, 'artist': artist, 'year': year, 'album': album})
            
            self._load_tracks(tracks)
            self.state.artist = ""
            self.state.year = ""
        elif self.mode == 'ARTIST_VIEW':
            self.state.album = str(self.current_path)
            self._load_tracks(self.lib.get_artist_tracks(self.current_path))
        elif self.mode == 'ALBUM_VIEW':
            self.state.album = str(self.current_path)
            self._load_tracks(self.lib.get_album_tracks(self.current_path))
        elif self.mode == 'FILES':
            if not isinstance(self.current_path, Path): self.current_path = Path(self.current_path)
            self.state.album = self.current_path.name
            if self.current_path != cfg.MUSIC_PATH:
                 self.state.items.append({'name': '..', 'type': 'dir', 'mode': 'FILES', 'path': self.current_path.parent, 'icon': 'Ⓕ'})
            try:
                all_items = sorted(self.current_path.iterdir(), key=lambda p: p.name.lower())
                found_art = False 
                for p in all_items:
                    if p.name.startswith('.'): continue
                    if p.is_dir():
                        self.state.items.append({'name': p.name, 'type': 'dir', 'mode': 'FILES', 'path': p, 'icon': 'Ⓕ'})
                    elif p.is_file() and p.suffix.lower() in cfg.VALID_EXTS:
                        try:
                            # Use fast text extraction
                            meta_text = get_metadata(p)
                            title = meta_text[2] if (meta_text and meta_text[2]) else p.stem
                            artist = meta_text[1] if meta_text else None
                            album = meta_text[0] if meta_text else None
                        except:
                            title = p.stem; artist = None; album = None
                        icon = 'P' if self.state.playing_path == str(p) else 'S'
                        self.state.items.append({
                            'name': title, 'type': 'file', 'path': p, 'icon': icon,
                            'artist': artist, 'album': album
                        })
                        if not found_art:
                            # Only load cover for the first valid file
                            covers = get_cover(p)
                            if covers[0]:
                                self.state.browsing_cover_s = covers[0]
                                found_art = True
            except OSError: pass
        self.state.total_items = len(self.state.items)

    def _load_tracks(self, tracks):
        self.state.has_header = True
        self.state.items = [{'type': 'header'}]
        for t in tracks:
            icon = 'P' if self.state.playing_path == str(t['path']) else 'S'
            self.state.items.append({
                'name': t['title'], 'type': 'file', 'path': t['path'], 'icon': icon, 
                'artist': t.get('artist'), 'album': t.get('album')
            })
        if tracks:
            # Only read the cover image here. Text data comes from the list items.
            covers = get_cover(Path(tracks[0]['path']))
            if covers[0]: 
                self.state.browsing_cover_s = covers[0]
            
            self.state.artist = tracks[0]['artist']
            self.state.year = str(tracks[0].get('year', ''))

    def _open_context_menu(self, item):
        self.state.context_menu_active = True
        self.state.context_index = 0
        self.state.context_target_item = item
        self.state.context_layer = 0
        opts = []
        if item['type'] == 'playlist':
            opts = ["Delete Playlist", "Cancel"]
        elif item['type'] == 'file':
            opts = ["Favourite Song", "Add to Playlist"]
            if item.get('artist'): opts.append("Go to Artist")
            if item.get('album'): opts.append("Go to Album")
            opts.append("Cancel")
        self.state.context_options = opts

    def _handle_context_action(self):
        idx = self.state.context_index
        opt = self.state.context_options[idx]
        target = self.state.context_target_item
        if self.state.context_layer == 0:
            if opt == "Cancel":
                self.state.context_menu_active = False
            elif opt == "Favourite Song":
                self.lib.toggle_fav_track(str(target['path']))
                self.state.context_menu_active = False
                if self.mode == 'FAV_TRACKS_VIEW': self.refresh_list()
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
        self.playlist_source = [str(i['path']) for i in self.state.items if i['type'] == 'file']
        path_str = str(path)
        if not self.playlist_source: return
        self.queue = list(range(len(self.playlist_source)))
        if self.state.shuffle_active: random.shuffle(self.queue)
        try: real_idx = self.playlist_source.index(path_str)
        except: real_idx = 0
        if self.state.shuffle_active:
            if real_idx in self.queue: self.queue.remove(real_idx)
            self.queue.insert(0, real_idx)
            self.queue_idx = 0
        else: self.queue_idx = real_idx
        self._load_track(real_idx)

    def _handle_header_action(self):
        idx = self.state.top_bar_index
        if idx == 0: self.nav_back()
        elif idx == 1: 
            self.state.shuffle_active = not self.state.shuffle_active
            if self.state.shuffle_active and not self.state.playing_path:
                files = [item for item in self.state.items if item.get('type') == 'file']
                if files:
                    target = random.choice(files)
                    self._play_from_list(target['path'])
        elif idx == 2: self.state.loop_mode = (self.state.loop_mode + 1) % 3
        elif idx == 3: self.lib.toggle_fav_album(self.state.album)

    def get_frame(self):
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
        
        view_items = self.state.items[start : start + page + 1]
        
        return self.renderer.render_music_view(self.state, view_items)
