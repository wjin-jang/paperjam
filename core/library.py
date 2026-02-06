"""
Music library management and caching.

This module provides the core library management functionality for PaperJam:

- **Background scanning**: Asynchronous library scanning with real-time progress
  tracking. Scans run in a daemon thread to avoid blocking the UI.

- **Organization**: Tracks are organized by artist and album with case-insensitive
  normalization (preserving the first-seen casing for display).

- **Favorites**: Supports favorite tracks, albums, and artists with lazy persistence
  (dirty flag avoids constant disk writes).

- **Playlists**: User-created playlists stored as JSON files in the playlists directory.

- **Recent plays**: Tracks recently played history with configurable limit.

- **Caching**: Library metadata is cached to JSON for fast startup. The cache is
  automatically invalidated and rebuilt when scanning.

Thread Safety:
    The LibraryManager uses two locks:
    - `_lock`: Protects library data (artists, albums, caches)
    - `_scan_lock`: Protects scan progress counters

Example:
    >>> library = LibraryManager()
    >>> library.scan_async()  # Start background scan
    >>> while library.is_scanning:
    ...     print(f"Scanned {library.scan_track_count} tracks...")
    >>> print(f"Found {len(library.artists)} artists")
"""
from __future__ import annotations

import json
import os
import random
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import config as cfg
from config import setup_logger
from core.i18n import t
from core.metadata import extract_track_info, get_full_sort_key
from ui.graphics import get_cover

logger = setup_logger()

# Type aliases for clarity
TrackDict = dict[str, Any]  # Track metadata dictionary from cache
ScanCallback = Callable[[], None]  # Callback invoked when scan completes

@dataclass
class TrackItem:
    """Structured track metadata extracted from audio files.

    This dataclass represents the essential metadata for a single track,
    used during library scanning before conversion to dictionary format.
    """

    path: Path
    title: str
    album: str
    artist: str
    year: str
    track_num: int
    disc_num: int


class LibraryManager:
    """Central manager for the music library, playlists, favorites, and recents.

    Handles all library-related operations including background scanning,
    metadata caching, favorites management, and playlist CRUD operations.

    Attributes:
        artists: Dict mapping artist name to list of track dicts.
        albums: Dict mapping album name to list of track dicts.
        recents: List of recently played track paths (most recent first).
        fav_tracks: Set of favorite track paths (as strings).
        fav_albums: Set of favorite album names.
        fav_artists: Set of favorite artist names.
        is_scanning: True while a background scan is in progress.
    """

    def __init__(self) -> None:
        """Initialize the library manager and load cached data."""
        # Primary library data (protected by _lock)
        self.artists: dict[str, list[TrackDict]] = {}
        self.albums: dict[str, list[TrackDict]] = {}
        self.featured_on: dict[str, list[TrackDict]] = {}  # Tracks each artist is featured on
        self.artist_sort_map: dict[str, str] = {}  # Artist name -> album artist sort order

        # User collections
        self.recents: list[Path] = []
        self.fav_tracks: set[str] = set()
        self.fav_albums: set[str] = set()
        self.fav_artists: set[str] = set()

        # Dirty flags for lazy persistence
        self._favs_dirty: bool = False
        self._recents_dirty: bool = False

        # Scanning state
        self.is_scanning: bool = False
        self._lock = threading.Lock()
        self._scan_lock = threading.Lock()  # Separate lock for scan progress

        # Caches (invalidated on rescan)
        self._all_tracks_cache: list[TrackDict] | None = None
        self._track_count_cache: int | None = None

        # Scan completion callback
        self._on_scan_complete: ScanCallback | None = None

        # Scan progress tracking (protected by _scan_lock)
        self._scan_current_file: str = ""
        self._scan_track_count: int = 0
        self._scan_album_count: int = 0
        self._scan_artist_count: int = 0

        # Ensure data directories exist
        cfg.DATA_DIR.mkdir(exist_ok=True)
        cfg.PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)

        # Load persisted state
        self.load_recents()
        self.load_favs()
        self.load_cache()

    def is_first_run(self) -> bool:
        """Check if this is the first run (no cache file exists).

        Returns:
            True if no library cache exists (indicating first run or reset).
        """
        return not cfg.CACHE_FILE.exists()

    def set_on_scan_complete(self, callback: ScanCallback | None) -> None:
        """Set callback to be invoked when library scan completes.

        Args:
            callback: Function to call after scan finishes, or None to clear.
        """
        self._on_scan_complete = callback

    def load_cache(self) -> None:
        """Load library data from the JSON cache file.

        Validates the cache structure before loading. If the cache is
        corrupted or invalid, resets to an empty library (scan will be
        triggered by the main app on first run).
        """
        if cfg.CACHE_FILE.exists():
            try:
                with open(cfg.CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Validate cache structure before loading
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
        # Note: Auto-scan is handled by main.py via welcome screen flow

    @property
    def scan_current_file(self) -> str:
        """Name of the file currently being scanned (thread-safe)."""
        with self._scan_lock:
            return self._scan_current_file

    @property
    def scan_track_count(self) -> int:
        """Number of tracks found so far during scan (thread-safe)."""
        with self._scan_lock:
            return self._scan_track_count

    @property
    def scan_album_count(self) -> int:
        """Number of albums found so far during scan (thread-safe)."""
        with self._scan_lock:
            return self._scan_album_count

    @property
    def scan_artist_count(self) -> int:
        """Number of artists found so far during scan (thread-safe)."""
        with self._scan_lock:
            return self._scan_artist_count

    def scan_async(self, force: bool = False) -> None:
        """Start a background library scan.

        Scans the music directory for audio files and builds the artist/album
        index. Progress can be monitored via the scan_* properties.

        Args:
            force: Unused parameter (kept for API compatibility).

        Note:
            Only one scan can run at a time. Calls while scanning are ignored.
        """
        if self.is_scanning:
            return
        self.is_scanning = True

        # Reset progress tracking
        with self._scan_lock:
            self._scan_current_file = ""
            self._scan_track_count = 0
            self._scan_album_count = 0
            self._scan_artist_count = 0

        scan_thread = threading.Thread(target=self._scan_worker, daemon=True)
        scan_thread.start()

    def _normalize_name(self, raw_name: str, case_map: dict[str, str]) -> str:
        """Normalize a name while preserving the first-seen casing.

        This ensures that "The Beatles" and "THE BEATLES" are treated as
        the same artist, but the display name uses whichever casing was
        encountered first during scanning.

        Args:
            raw_name: The name to normalize.
            case_map: Dict mapping lowercase names to their canonical casing.

        Returns:
            The canonical (first-seen) casing for this name.
        """
        key = raw_name.strip().lower()
        if key not in case_map:
            case_map[key] = raw_name
        return case_map[key]

    def _scan_worker(self) -> None:
        """Background worker that scans the music directory.

        Iterates through all supported audio files, extracts metadata,
        and builds the artist/album index. Progress is tracked via
        the scan_* properties (thread-safe).

        On completion:
        - Sorts artists/albums alphabetically
        - Sorts tracks within each artist/album by disc/track number
        - Saves the cache to disk
        - Invokes the scan complete callback (if set)
        """
        temp_artists: dict[str, list[TrackDict]] = {}
        temp_albums: dict[str, list[TrackDict]] = {}
        temp_featured: dict[str, list[TrackDict]] = {}  # Track featured artist appearances

        # Case normalization maps (lowercase -> first-seen casing)
        artist_case_map: dict[str, str] = {}
        album_case_map: dict[str, str] = {}

        # Album artist sort order map (canonical artist name -> sort value)
        temp_artist_sort_map: dict[str, str] = {}

        # Scan all supported audio files
        for ext in cfg.VALID_EXTS:
            for p in cfg.MUSIC_PATH.rglob(f"*{ext}"):
                try:
                    # Update progress (UI reads this to show current file)
                    with self._scan_lock:
                        self._scan_current_file = p.name

                    track = extract_track_info(p)

                    # Normalize artist/album names (case-insensitive grouping)
                    canonical_artist = self._normalize_name(track.artist, artist_case_map)
                    canonical_album = self._normalize_name(track.album, album_case_map)

                    data: TrackDict = {
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

                    # Store album artist sort order (first non-empty value wins)
                    if track.artist_sort and canonical_artist not in temp_artist_sort_map:
                        temp_artist_sort_map[canonical_artist] = track.artist_sort

                    # Track featured artist appearances
                    for feat_artist in track.featured:
                        canonical_feat = self._normalize_name(feat_artist, artist_case_map)
                        # Don't add to featured if it's the same as primary artist
                        if canonical_feat.lower() != canonical_artist.lower():
                            temp_featured.setdefault(canonical_feat, []).append(data)

                    # Update counters for progress display
                    with self._scan_lock:
                        self._scan_track_count += 1
                        self._scan_album_count = len(temp_albums)
                        self._scan_artist_count = len(temp_artists)
                except (OSError, ValueError) as e:
                    logger.warning(f"Scan error processing {p}: {e}")
                    continue

        # Sort tracks within each artist by album, then disc/track number
        for tracks in temp_artists.values():
            tracks.sort(key=lambda x: (
                x.get('album', '').lower(),
                x.get('disc', 0),
                x.get('track', 0)
            ))

        # Sort tracks within each album by disc/track number
        for tracks in temp_albums.values():
            tracks.sort(key=lambda x: (x.get('disc', 0), x.get('track', 0)))

        # Sort featured tracks by artist then album
        for tracks in temp_featured.values():
            tracks.sort(key=lambda x: (
                x.get('artist', '').lower(),
                x.get('album', '').lower(),
                x.get('disc', 0),
                x.get('track', 0)
            ))

        # Commit results to main library (protected by lock)
        with self._lock:
            self.artist_sort_map = temp_artist_sort_map
            self.artists = dict(sorted(temp_artists.items(),
                key=lambda x: get_full_sort_key(temp_artist_sort_map.get(x[0], x[0]))))
            self.albums = dict(sorted(temp_albums.items(), key=lambda x: get_full_sort_key(x[0])))
            self.featured_on = dict(sorted(temp_featured.items(),
                key=lambda x: get_full_sort_key(temp_artist_sort_map.get(x[0], x[0]))))
            self._all_tracks_cache = None
            self._track_count_cache = None
            self._save_cache()

        # Clear scanning state
        with self._scan_lock:
            self._scan_current_file = ""
        self.is_scanning = False

        # Notify listeners that scan completed
        if self._on_scan_complete:
            try:
                self._on_scan_complete()
            except Exception as e:
                logger.error(f"Scan complete callback error: {e}")

    def _save_cache(self) -> None:
        """Persist the library cache to disk."""
        try:
            with open(cfg.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'artists': self.artists,
                    'albums': self.albums,
                    'featured_on': self.featured_on,
                    'artist_sort_map': self.artist_sort_map
                }, f)
        except OSError as e:
            logger.error(f"Cache save error: {e}")

    def _deserialize_library(self, data: dict[str, Any]) -> None:
        """Load library data from a deserialized cache dict."""
        self.artists = data.get('artists', {})
        self.albums = data.get('albums', {})
        self.featured_on = data.get('featured_on', {})
        self.artist_sort_map = data.get('artist_sort_map', {})

    def get_playlists(self) -> list[Path]:
        """Get all user playlists sorted by name.

        Returns:
            List of Path objects pointing to playlist JSON files.
        """
        return sorted(list(cfg.PLAYLIST_DIR.glob("*.json")))

    def create_playlist(self) -> Path:
        """Create a new empty playlist with an auto-generated name.

        Returns:
            Path to the newly created playlist file.
        """
        i = 1
        while True:
            name = f"{t('player.browse.playlist')} {i}"
            p = cfg.PLAYLIST_DIR / f"{name}.json"
            if not p.exists():
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                return p
            i += 1

    def delete_playlist(self, path: Path) -> None:
        """Delete a playlist file.

        Args:
            path: Path to the playlist file to delete.
        """
        try:
            if path.exists():
                os.remove(path)
        except OSError as e:
            logger.error(f"Error deleting playlist {path}: {e}")

    def add_to_playlist(self, playlist_path: Path, track_path: str | Path) -> None:
        """Add a track to a playlist (if not already present).

        Args:
            playlist_path: Path to the playlist JSON file.
            track_path: Path to the track to add.
        """
        try:
            content: list[str] = []
            if playlist_path.exists():
                with open(playlist_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
            str_path = str(track_path)
            if str_path not in content:
                content.append(str_path)
                with open(playlist_path, 'w', encoding='utf-8') as f:
                    json.dump(content, f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Error updating playlist {playlist_path}: {e}")

    def get_playlist_tracks(self, playlist_path: Path) -> list[TrackDict]:
        """Load tracks from a playlist file with fresh metadata.

        Args:
            playlist_path: Path to the playlist JSON file.

        Returns:
            List of track dicts with metadata (excludes missing files).
        """
        tracks: list[TrackDict] = []
        if playlist_path.exists():
            try:
                with open(playlist_path, 'r', encoding='utf-8') as f:
                    paths = json.load(f)
                    for p_str in paths:
                        p = Path(p_str)
                        if p.exists():
                            track = extract_track_info(p)
                            tracks.append({
                                'path': p,
                                'album': track.album,
                                'artist': track.artist,
                                'title': track.title,
                                'year': track.year,
                                'duration': track.duration
                            })
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Error reading playlist {playlist_path}: {e}")
        return tracks

    def get_artist_tracks(self, artist: str) -> list[TrackDict]:
        """Get all tracks for an artist (pre-sorted by album, disc, track).

        Args:
            artist: Artist name to look up.

        Returns:
            List of track dicts, or empty list if artist not found.
        """
        return self.artists.get(artist, [])

    def get_featured_tracks(self, artist: str) -> list[TrackDict]:
        """Get all tracks where an artist is featured.

        Args:
            artist: Artist name to look up.

        Returns:
            List of track dicts where the artist is featured, or empty list if none.
        """
        return self.featured_on.get(artist, [])

    def get_album_tracks(self, album: str) -> list[TrackDict]:
        """Get all tracks for an album (pre-sorted by disc, track).

        Args:
            album: Album name to look up.

        Returns:
            List of track dicts, or empty list if album not found.
        """
        return self.albums.get(album, [])

    def get_random_cover(self, with_album: bool = False) -> Any:
        """Get a random album cover image for screensaver/shutdown display.

        Args:
            with_album: If True, returns (cover, album_name) tuple.

        Returns:
            Large cover image (PIL Image), or None if no albums exist.
            If with_album=True, returns (cover, album_name) tuple.
        """
        try:
            if not self.albums:
                return (None, None) if with_album else None
            alb = random.choice(list(self.albums.keys()))
            tracks = self.albums[alb]
            if tracks:
                covers = get_cover(Path(tracks[0]['path']))
                if with_album:
                    return covers[1], alb
                return covers[1]  # Large cover
        except (OSError, KeyError, IndexError):
            return (None, None) if with_album else None

    def get_random_covers(self, count: int = 10, small: bool = True) -> list[Any]:
        """Get multiple random album covers for tiled displays.

        Used for screensaver or decorative displays showing multiple
        album covers simultaneously.

        Args:
            count: Maximum number of covers to retrieve.
            small: If True, return small covers; if False, return large covers.

        Returns:
            List of cover images (PIL Image objects). May be shorter than
            count if not enough albums with covers exist.
        """
        covers: list[Any] = []
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

    def load_recents(self) -> None:
        """Load recently played tracks from disk, filtering out missing files."""
        if cfg.RECENTS_FILE.exists():
            try:
                with open(cfg.RECENTS_FILE, 'r', encoding='utf-8') as f:
                    all_paths = json.load(f)
                valid_paths = [Path(p) for p in all_paths if Path(p).exists()]
                self.recents = valid_paths

                # Save back if invalid paths were filtered out
                if len(valid_paths) != len(all_paths):
                    logger.info(f"Removed {len(all_paths) - len(valid_paths)} invalid recent paths")
                    with open(cfg.RECENTS_FILE, 'w', encoding='utf-8') as f:
                        json.dump([str(p) for p in self.recents], f)
            except (OSError, json.JSONDecodeError):
                self.recents = []

    def add_recent(self, path: Path) -> None:
        """Add a track to the recently played list.

        Moves the track to the front if already present. Respects
        RECENTS_LIMIT by dropping the oldest entry when full.

        Args:
            path: Path to the track file.
        """
        if path in self.recents:
            self.recents.remove(path)
        self.recents.insert(0, path)
        if len(self.recents) > cfg.RECENTS_LIMIT:
            self.recents.pop()
        self._recents_dirty = True

    def flush_recents(self) -> None:
        """Persist recents to disk if changed. Call periodically or on shutdown."""
        if self._recents_dirty:
            self._save_recents()
            self._recents_dirty = False

    def _save_recents(self) -> None:
        """Write recents list to disk."""
        try:
            with open(cfg.RECENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump([str(p) for p in self.recents], f)
        except OSError as e:
            logger.error(f"Error saving recents: {e}")

    def flush_all(self) -> None:
        """Persist all dirty state to disk. Call on shutdown."""
        self.flush_recents()
        self.flush_favs()

    def load_favs(self) -> None:
        """Load favorites from disk.

        Supports both legacy format (list of track paths) and current format
        (dict with tracks, albums, artists keys).
        """
        if cfg.FAVS_FILE.exists():
            try:
                with open(cfg.FAVS_FILE, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    # Handle legacy format (plain list of track paths)
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

    def toggle_fav_track(self, path_str: str) -> None:
        """Toggle favorite status for a track.

        Args:
            path_str: Track path as string.
        """
        if path_str in self.fav_tracks:
            self.fav_tracks.remove(path_str)
        else:
            self.fav_tracks.add(path_str)
        self._favs_dirty = True

    def toggle_fav_album(self, album_name: str) -> None:
        """Toggle favorite status for an album.

        Args:
            album_name: Album name to toggle.
        """
        if album_name in self.fav_albums:
            self.fav_albums.remove(album_name)
        else:
            self.fav_albums.add(album_name)
        self._favs_dirty = True

    def toggle_fav_artist(self, artist_name: str) -> None:
        """Toggle favorite status for an artist.

        Args:
            artist_name: Artist name to toggle.
        """
        if artist_name in self.fav_artists:
            self.fav_artists.remove(artist_name)
        else:
            self.fav_artists.add(artist_name)
        self._favs_dirty = True

    def flush_favs(self) -> None:
        """Persist favorites to disk if changed. Call periodically or on shutdown."""
        if self._favs_dirty:
            self._save_favs()
            self._favs_dirty = False

    def _save_favs(self) -> None:
        """Write favorites to disk."""
        try:
            with open(cfg.FAVS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "tracks": list(self.fav_tracks),
                    "albums": list(self.fav_albums),
                    "artists": list(self.fav_artists)
                }, f)
        except OSError as e:
            logger.error(f"Error saving favorites: {e}")

    def get_fav_tracks_list(self) -> list[TrackDict]:
        """Get all favorite tracks with fresh metadata.

        Returns:
            List of track dicts sorted by artist, album, disc, track.
            Missing files are silently excluded.
        """
        tracks: list[TrackDict] = []
        for p_str in self.fav_tracks:
            p = Path(p_str)
            if p.exists():
                track = extract_track_info(p)
                tracks.append({
                    'path': p,
                    'album': track.album,
                    'artist': track.artist,
                    'title': track.title,
                    'year': track.year,
                    'duration': track.duration,
                    'disc': track.disc_num,
                    'track': track.track_num
                })

        # Sort by artist → album → disc → track
        tracks.sort(key=lambda x: (
            x.get('artist', '').lower(),
            x.get('album', '').lower(),
            x.get('disc', 0),
            x.get('track', 0)
        ))
        return tracks

    def get_total_tracks(self) -> int:
        """Get the total number of tracks in the library.

        Returns:
            Total track count (cached for performance).
        """
        if self._track_count_cache is None:
            count = 0
            for tracks in self.artists.values():
                count += len(tracks)
            self._track_count_cache = count
        return self._track_count_cache

    @staticmethod
    def get_total_duration(tracks: list[TrackDict]) -> int:
        """Calculate total duration in seconds from a list of tracks.

        Args:
            tracks: List of track dicts with optional 'duration' key.

        Returns:
            Total duration in seconds.
        """
        return sum(t.get('duration', 0) for t in tracks)

    def get_all_tracks(self, shuffle: bool = False) -> list[TrackDict]:
        """Get all tracks from the library.

        Uses cached metadata from the library scan - no additional file I/O.
        Results are cached internally for subsequent non-shuffled requests.

        Args:
            shuffle: If True, return tracks in random order.

        Returns:
            List of track dicts with path, title, artist, album, year, etc.
        """
        # Return cached list if available and no shuffle requested
        if not shuffle and self._all_tracks_cache is not None:
            return self._all_tracks_cache

        # Build the track list if cache is empty
        if self._all_tracks_cache is None:
            all_tracks: list[TrackDict] = []
            for album_tracks in self.albums.values():
                all_tracks.extend(album_tracks)

            # Sort by artist → album → disc → track
            all_tracks.sort(key=lambda x: (
                x.get('artist', '').lower(),
                x.get('album', '').lower(),
                x.get('disc', 0),
                x.get('track', 0)
            ))
            self._all_tracks_cache = all_tracks

        # If shuffle requested, return a shuffled copy (don't modify cache)
        if shuffle:
            shuffled = list(self._all_tracks_cache)
            random.shuffle(shuffled)
            return shuffled

        return self._all_tracks_cache
