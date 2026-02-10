"""PaperJam Web — Library scanner (adapted from original)."""

import json
import logging
import threading
import time
from pathlib import Path

from config import MUSIC_PATH, VALID_EXTENSIONS, LIBRARY_CACHE_FILE
from core.metadata import extract_track_info, clean_title, format_duration

logger = logging.getLogger(__name__)


class LibraryScanner:
    """Scans and indexes the music library."""

    def __init__(self):
        self.artists: dict[str, list[dict]] = {}
        self.albums: dict[str, list[dict]] = {}
        self.tracks: list[dict] = []
        self.scanning = False
        self.scan_progress = 0
        self.scan_total = 0
        self._lock = threading.Lock()
        self._load_cache()

    def _load_cache(self):
        if LIBRARY_CACHE_FILE.exists():
            try:
                with open(LIBRARY_CACHE_FILE, "r") as f:
                    data = json.load(f)
                self.artists = data.get("artists", {})
                self.albums = data.get("albums", {})
                self.tracks = data.get("tracks", [])
                logger.info(
                    f"Loaded cache: {len(self.tracks)} tracks, "
                    f"{len(self.artists)} artists, {len(self.albums)} albums"
                )
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")

    def _save_cache(self):
        try:
            data = {
                "artists": self.artists,
                "albums": self.albums,
                "tracks": self.tracks,
                "scanned_at": time.time(),
            }
            with open(LIBRARY_CACHE_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def scan(self, background: bool = True):
        """Start a library scan."""
        if self.scanning:
            return
        if background:
            thread = threading.Thread(target=self._scan_worker, daemon=True)
            thread.start()
        else:
            self._scan_worker()

    def _scan_worker(self):
        self.scanning = True
        self.scan_progress = 0
        logger.info(f"Scanning: {MUSIC_PATH}")

        try:
            # Collect all audio files
            files = [
                p for p in MUSIC_PATH.rglob("*")
                if p.suffix.lower() in VALID_EXTENSIONS and not p.name.startswith(".")
            ]
            self.scan_total = len(files)
            logger.info(f"Found {self.scan_total} audio files")

            artists: dict[str, list[dict]] = {}
            albums: dict[str, list[dict]] = {}
            tracks: list[dict] = []

            # Normalize casing maps
            artist_canonical: dict[str, str] = {}
            album_canonical: dict[str, str] = {}

            for i, path in enumerate(files):
                self.scan_progress = i + 1
                info = extract_track_info(path)
                if not info:
                    continue

                track = {
                    "path": str(path),
                    "title": clean_title(info.title),
                    "artist": info.artist,
                    "album": info.album,
                    "year": info.year,
                    "track_num": info.track_num,
                    "disc_num": info.disc_num,
                    "duration": info.duration,
                    "duration_fmt": format_duration(info.duration),
                }
                tracks.append(track)

                # Normalize artist name (case-insensitive, preserve first seen)
                artist_lower = info.artist.lower()
                if artist_lower not in artist_canonical:
                    artist_canonical[artist_lower] = info.artist
                canonical_artist = artist_canonical[artist_lower]
                artists.setdefault(canonical_artist, []).append(track)

                # Normalize album name
                album_lower = info.album.lower()
                if album_lower not in album_canonical:
                    album_canonical[album_lower] = info.album
                canonical_album = album_canonical[album_lower]
                albums.setdefault(canonical_album, []).append(track)

            # Sort tracks within albums by disc/track number
            for album_tracks in albums.values():
                album_tracks.sort(key=lambda t: (t["disc_num"], t["track_num"]))

            # Sort artists and albums alphabetically
            with self._lock:
                self.artists = dict(sorted(artists.items(), key=lambda x: x[0].lower()))
                self.albums = dict(sorted(albums.items(), key=lambda x: x[0].lower()))
                self.tracks = sorted(tracks, key=lambda t: (t["artist"].lower(), t["album"].lower(), t["disc_num"], t["track_num"]))

            self._save_cache()
            logger.info(
                f"Scan complete: {len(tracks)} tracks, "
                f"{len(artists)} artists, {len(albums)} albums"
            )

        except Exception as e:
            logger.error(f"Scan error: {e}")
        finally:
            self.scanning = False

    def get_artists(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": name,
                    "track_count": len(tracks),
                    "album_count": len(set(t["album"] for t in tracks)),
                }
                for name, tracks in self.artists.items()
            ]

    def get_artist(self, name: str) -> dict | None:
        with self._lock:
            tracks = self.artists.get(name)
            if not tracks:
                # Case-insensitive fallback
                for k, v in self.artists.items():
                    if k.lower() == name.lower():
                        tracks = v
                        name = k
                        break
            if not tracks:
                return None

            albums = {}
            for t in tracks:
                albums.setdefault(t["album"], []).append(t)

            return {
                "name": name,
                "albums": [
                    {
                        "name": album,
                        "tracks": sorted(trks, key=lambda t: (t["disc_num"], t["track_num"])),
                        "year": trks[0].get("year", ""),
                        "track_count": len(trks),
                    }
                    for album, trks in sorted(albums.items())
                ],
                "track_count": len(tracks),
            }

    def get_albums(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": name,
                    "artist": tracks[0]["artist"] if tracks else "Unknown",
                    "year": tracks[0].get("year", ""),
                    "track_count": len(tracks),
                }
                for name, tracks in self.albums.items()
            ]

    def get_album(self, name: str) -> dict | None:
        with self._lock:
            tracks = self.albums.get(name)
            if not tracks:
                for k, v in self.albums.items():
                    if k.lower() == name.lower():
                        tracks = v
                        name = k
                        break
            if not tracks:
                return None

            total_duration = sum(t["duration"] for t in tracks)
            return {
                "name": name,
                "artist": tracks[0]["artist"],
                "year": tracks[0].get("year", ""),
                "tracks": sorted(tracks, key=lambda t: (t["disc_num"], t["track_num"])),
                "track_count": len(tracks),
                "duration": format_duration(total_duration),
            }

    def get_tracks(self) -> list[dict]:
        with self._lock:
            return list(self.tracks)

    def search(self, query: str, limit: int = 50) -> dict:
        """Search across tracks, albums, and artists."""
        q = query.lower()
        with self._lock:
            matching_tracks = [
                t for t in self.tracks
                if q in t["title"].lower() or q in t["artist"].lower() or q in t["album"].lower()
            ][:limit]

            matching_albums = [
                {"name": name, "artist": tracks[0]["artist"], "track_count": len(tracks)}
                for name, tracks in self.albums.items()
                if q in name.lower()
            ][:limit]

            matching_artists = [
                {"name": name, "track_count": len(tracks)}
                for name, tracks in self.artists.items()
                if q in name.lower()
            ][:limit]

        return {
            "tracks": matching_tracks,
            "albums": matching_albums,
            "artists": matching_artists,
        }

    def get_track_by_path(self, path: str) -> dict | None:
        with self._lock:
            for t in self.tracks:
                if t["path"] == path:
                    return dict(t)
        return None

    @property
    def stats(self) -> dict:
        with self._lock:
            total_duration = sum(t["duration"] for t in self.tracks)
            return {
                "tracks": len(self.tracks),
                "artists": len(self.artists),
                "albums": len(self.albums),
                "total_duration": format_duration(total_duration),
            }


# Global instance
_scanner: LibraryScanner | None = None


def get_scanner() -> LibraryScanner:
    global _scanner
    if _scanner is None:
        _scanner = LibraryScanner()
    return _scanner
