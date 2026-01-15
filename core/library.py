import json
import threading
import random
import os
from pathlib import Path
from dataclasses import dataclass
import config as cfg
from ui.image_utils import get_cover
from core.track_info import extract_track_info
from core.logger import setup_logger

logger = setup_logger()

@dataclass
class TrackItem:
    path: Path
    title: str
    album: str
    artist: str
    year: str
    track_num: int
    disc_num: int

class LibraryManager:
    def __init__(self):
        self.artists = {}
        self.albums = {}
        self.recents = []
        self.fav_tracks = set()
        self.fav_albums = set()
        self.fav_artists = set()

        self.is_scanning = False
        self._lock = threading.Lock()
        self._scan_lock = threading.Lock()  # Separate lock for scan progress
        self._all_tracks_cache = None
        self._on_scan_complete = None  # Callback for scan completion

        # Scan progress tracking (protected by _scan_lock)
        self._scan_current_file = ""
        self._scan_track_count = 0
        self._scan_album_count = 0
        self._scan_artist_count = 0

        cfg.DATA_DIR.mkdir(exist_ok=True)
        cfg.PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)

        self.load_recents()
        self.load_favs()
        self.load_cache()

    def is_first_run(self) -> bool:
        """Check if this is the first run (no cache file exists)."""
        return not cfg.CACHE_FILE.exists()

    def set_on_scan_complete(self, callback):
        """Set callback to be called when library scan completes."""
        self._on_scan_complete = callback

    def load_cache(self):
        if cfg.CACHE_FILE.exists():
            try:
                with open(cfg.CACHE_FILE, 'r') as f:
                    data = json.load(f)

                # Validate cache structure
                if not isinstance(data, dict):
                    raise ValueError("Cache must be a dict")
                if 'artists' in data and not isinstance(data['artists'], dict):
                    raise ValueError("artists must be a dict")
                if 'albums' in data and not isinstance(data['albums'], dict):
                    raise ValueError("albums must be a dict")

                self._deserialize_library(data)
                logger.info(f"Library cache loaded: {len(self.artists)} artists, {len(self.albums)} albums")
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.error(f"Cache load error: {e}")
                # Reset to empty on corrupted cache
                self.artists = {}
                self.albums = {}
        # Don't auto-scan here - let main.py handle welcome screen

    @property
    def scan_current_file(self):
        with self._scan_lock:
            return self._scan_current_file

    @property
    def scan_track_count(self):
        with self._scan_lock:
            return self._scan_track_count

    @property
    def scan_album_count(self):
        with self._scan_lock:
            return self._scan_album_count

    @property
    def scan_artist_count(self):
        with self._scan_lock:
            return self._scan_artist_count

    def scan_async(self, force=False):
        if self.is_scanning: return
        self.is_scanning = True
        # Reset progress tracking
        with self._scan_lock:
            self._scan_current_file = ""
            self._scan_track_count = 0
            self._scan_album_count = 0
            self._scan_artist_count = 0
        t = threading.Thread(target=self._scan_worker)
        t.daemon = True
        t.start()

    def _normalize_name(self, raw_name: str, case_map: dict) -> str:
        """Normalize name while preserving first-seen case."""
        key = raw_name.strip().lower()
        if key not in case_map:
            case_map[key] = raw_name
        return case_map[key]

    def _scan_worker(self):
        temp_artists = {}
        temp_albums = {}

        artist_case_map = {}
        album_case_map = {}

        for ext in cfg.VALID_EXTS:
            for p in cfg.MUSIC_PATH.rglob(f"*{ext}"):
                try:
                    # Update progress with lock
                    with self._scan_lock:
                        self._scan_current_file = p.name[:30]

                    track = extract_track_info(p)

                    # Normalize names
                    canonical_artist = self._normalize_name(track.artist, artist_case_map)
                    canonical_album = self._normalize_name(track.album, album_case_map)

                    data = {
                        'path': str(p),
                        'album': canonical_album,
                        'artist': canonical_artist,
                        'title': track.title,
                        'track': track.track_num,
                        'disc': track.disc_num,
                        'year': track.year,
                        'duration': track.duration
                    }

                    temp_artists.setdefault(canonical_artist, []).append(data)
                    temp_albums.setdefault(canonical_album, []).append(data)

                    # Update counts with lock
                    with self._scan_lock:
                        self._scan_track_count += 1
                        self._scan_album_count = len(temp_albums)
                        self._scan_artist_count = len(temp_artists)
                except Exception as e:
                    logger.warning(f"Scan error processing {p}: {e}")
                    continue

        with self._lock:
            self.artists = dict(sorted(temp_artists.items(), key=lambda x: x[0].lower()))
            self.albums = dict(sorted(temp_albums.items(), key=lambda x: x[0].lower()))
            self._all_tracks_cache = None
            self._save_cache()

        with self._scan_lock:
            self._scan_current_file = ""
        self.is_scanning = False

        # Notify listeners that scan completed
        if self._on_scan_complete:
            try:
                self._on_scan_complete()
            except Exception as e:
                logger.error(f"Scan complete callback error: {e}")

    def _save_cache(self):
        try:
            with open(cfg.CACHE_FILE, 'w') as f:
                json.dump({'artists': self.artists, 'albums': self.albums}, f)
        except Exception as e:
            logger.error(f"Cache save error: {e}")

    def _deserialize_library(self, data):
        self.artists = data.get('artists', {})
        self.albums = data.get('albums', {})

    def get_playlists(self):
        return sorted(list(cfg.PLAYLIST_DIR.glob("*.json")))

    def create_playlist(self):
        i = 1
        while True:
            name = f"Playlist {i}"
            p = cfg.PLAYLIST_DIR / f"{name}.json"
            if not p.exists():
                with open(p, 'w') as f: json.dump([], f)
                return p
            i += 1

    def delete_playlist(self, path):
        try:
            if path.exists():
                os.remove(path)
        except OSError as e:
            logger.error(f"Error deleting playlist {path}: {e}")

    def add_to_playlist(self, playlist_path, track_path):
        try:
            content = []
            if playlist_path.exists():
                with open(playlist_path, 'r') as f:
                    content = json.load(f)
            str_path = str(track_path)
            if str_path not in content:
                content.append(str_path)
                with open(playlist_path, 'w') as f:
                    json.dump(content, f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Error updating playlist {playlist_path}: {e}")

    def get_playlist_tracks(self, playlist_path):
        tracks = []
        if playlist_path.exists():
            try:
                with open(playlist_path, 'r') as f:
                    paths = json.load(f)
                    for p_str in paths:
                        p = Path(p_str)
                        if p.exists():
                            track = extract_track_info(p)
                            tracks.append({
                                'path': p, 'album': track.album, 'artist': track.artist,
                                'title': track.title, 'year': track.year,
                                'duration': track.duration
                            })
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Error reading playlist {playlist_path}: {e}")
        return tracks

    def get_artist_tracks(self, artist):
        tracks = self.artists.get(artist, [])
        tracks.sort(key=lambda x: (x.get('album','').lower(), x.get('disc',0), x.get('track',0)))
        return tracks

    def get_album_tracks(self, album):
        tracks = self.albums.get(album, [])
        tracks.sort(key=lambda x: (x.get('disc',0), x.get('track',0)))
        return tracks

    def get_random_cover(self, with_album=False):
        """Used for screensaver/shutdown. Calls the heavy get_cover explicitly.

        Args:
            with_album: If True, returns (cover, album_name) tuple
        """
        try:
            if not self.albums:
                return (None, None) if with_album else None
            alb = random.choice(list(self.albums.keys()))
            tracks = self.albums[alb]
            if tracks:
                # Only gets the large cover
                covers = get_cover(Path(tracks[0]['path']))
                if with_album:
                    return covers[1], alb
                return covers[1]  # Return Large
        except (OSError, KeyError, IndexError):
            return (None, None) if with_album else None

    def get_random_covers(self, count=10, small=True):
        """Get multiple random album covers for tiled displays.

        Args:
            count: Number of covers to retrieve
            small: If True, return small covers; if False, return large covers

        Returns:
            List of cover images (may contain None entries)
        """
        covers = []
        if not self.albums:
            return covers

        album_keys = list(self.albums.keys())
        random.shuffle(album_keys)

        for alb in album_keys[:count]:
            try:
                tracks = self.albums[alb]
                if tracks:
                    cover_pair = get_cover(Path(tracks[0]['path']))
                    cover = cover_pair[0] if small else cover_pair[1]
                    if cover:
                        covers.append(cover)
            except (OSError, KeyError, IndexError):
                continue

        return covers

    def load_recents(self):
        if cfg.RECENTS_FILE.exists():
            try:
                with open(cfg.RECENTS_FILE, 'r') as f:
                    self.recents = [Path(p) for p in json.load(f) if Path(p).exists()]
            except (OSError, json.JSONDecodeError):
                self.recents = []

    def add_recent(self, path):
        if path in self.recents:
            self.recents.remove(path)
        self.recents.insert(0, path)
        if len(self.recents) > cfg.RECENTS_LIMIT:
            self.recents.pop()
        try:
            with open(cfg.RECENTS_FILE, 'w') as f:
                json.dump([str(p) for p in self.recents], f)
        except OSError as e:
            logger.error(f"Error saving recents: {e}")

    def load_favs(self):
        if cfg.FAVS_FILE.exists():
            try:
                with open(cfg.FAVS_FILE, 'r') as f:
                    d = json.load(f)
                    if isinstance(d, list):
                        self.fav_tracks = set(d)
                        self.fav_albums = set()
                        self.fav_artists = set()
                    else:
                        self.fav_tracks = set(d.get('tracks', []))
                        self.fav_albums = set(d.get('albums', []))
                        self.fav_artists = set(d.get('artists', []))
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Error loading favorites: {e}")

    def toggle_fav_track(self, path_str):
        if path_str in self.fav_tracks: self.fav_tracks.remove(path_str)
        else: self.fav_tracks.add(path_str)
        self._save_favs()

    def toggle_fav_album(self, album_name):
        if album_name in self.fav_albums: self.fav_albums.remove(album_name)
        else: self.fav_albums.add(album_name)
        self._save_favs()

    def toggle_fav_artist(self, artist_name):
        if artist_name in self.fav_artists: self.fav_artists.remove(artist_name)
        else: self.fav_artists.add(artist_name)
        self._save_favs()

    def _save_favs(self):
        with open(cfg.FAVS_FILE, 'w') as f:
            json.dump({
                "tracks": list(self.fav_tracks),
                "albums": list(self.fav_albums),
                "artists": list(self.fav_artists)
            }, f)

    def get_fav_tracks_list(self):
        tracks = []
        for p_str in self.fav_tracks:
            p = Path(p_str)
            if p.exists():
                track = extract_track_info(p)
                tracks.append({
                    'path': p, 'album': track.album, 'artist': track.artist,
                    'title': track.title, 'year': track.year,
                    'duration': track.duration,
                    'disc': track.disc_num, 'track': track.track_num
                })
        # Sort by artist > album > disc > track
        tracks.sort(key=lambda x: (
            x.get('artist', '').lower(),
            x.get('album', '').lower(),
            x.get('disc', 0),
            x.get('track', 0)
        ))
        return tracks

    def get_total_tracks(self):
        count = 0
        for tracks in self.artists.values():
            count += len(tracks)
        return count

    @staticmethod
    def get_total_duration(tracks) -> int:
        """Calculate total duration in seconds from a list of tracks."""
        return sum(t.get('duration', 0) for t in tracks)

    def get_all_tracks(self, shuffle=False):
        """
        Get all tracks from the library cache.
        Uses cached metadata - no file I/O required.

        Args:
            shuffle: If True, return tracks in random order

        Returns:
            List of track dicts with path, title, artist, album, year
        """
        # Return cached list if available and no shuffle
        if not shuffle and self._all_tracks_cache is not None:
            return self._all_tracks_cache

        # If we need to rebuild the list (first run or cache cleared)
        if self._all_tracks_cache is None:
            all_tracks = []
            for album_tracks in self.albums.values():
                all_tracks.extend(album_tracks)

            # Sort by artist, then album, then disc/track
            all_tracks.sort(key=lambda x: (
                x.get('artist', '').lower(),
                x.get('album', '').lower(),
                x.get('disc', 0),
                x.get('track', 0)
            ))
            self._all_tracks_cache = all_tracks

        # If shuffle is requested, return a shuffled copy of the cache
        if shuffle:
            shuffled = list(self._all_tracks_cache)
            random.shuffle(shuffled)
            return shuffled
        
        return self._all_tracks_cache
