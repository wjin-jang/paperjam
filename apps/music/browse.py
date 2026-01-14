"""
Browse mode handling for the music player.
Handles different browse modes: artists, albums, playlists, recents, files.
"""
from pathlib import Path
from typing import List, Optional, Tuple

import config as cfg
from core.metadata import get_cover
from core.track_info import extract_track_info


class BrowseHandler:
    """Handles different browse modes for the music player."""

    def __init__(self, library_manager):
        """
        Initialize browse handler.

        Args:
            library_manager: Library manager instance
        """
        self.lib = library_manager

    def get_root_menu(self) -> Tuple[str, List[dict]]:
        """Get the root menu items."""
        return "MAIN MENU", [
            {'name': 'Artists', 'type': 'dir', 'mode': 'ARTISTS_ROOT', 'icon': 'Ⓐ'},
            {'name': 'Albums', 'type': 'dir', 'mode': 'ALBUMS_ROOT', 'icon': 'Ⓑ'},
            {'name': 'Fav Albums', 'type': 'dir', 'mode': 'FAV_ALBUMS', 'icon': 'Ⓗ'},
            {'name': 'Playlists', 'type': 'dir', 'mode': 'PLAYLISTS_ROOT', 'icon': 'Ⓛ'},
            {'name': 'Recents', 'type': 'dir', 'mode': 'RECENTS', 'icon': 'Ⓡ'},
            {'name': 'Files', 'type': 'dir', 'mode': 'FILES', 'path': cfg.MUSIC_PATH, 'icon': 'Ⓕ'}
        ]

    def get_artists_list(self) -> Tuple[str, List[dict]]:
        """Get list of all artists."""
        items = [{'name': k, 'type': 'artist', 'mode': 'ARTIST_VIEW'} for k in self.lib.artists.keys()]
        return "ARTISTS", items

    def get_albums_list(self) -> Tuple[str, List[dict]]:
        """Get list of all albums."""
        items = [{'name': k, 'type': 'album', 'mode': 'ALBUM_VIEW'} for k in self.lib.albums.keys()]
        return "ALBUMS", items

    def get_fav_albums_list(self) -> Tuple[str, List[dict]]:
        """Get list of favorite albums."""
        if not self.lib.fav_albums:
            return "FAV ALBUMS", [{'name': '(No Fav Albums)', 'type': 'info'}]
        items = [
            {'name': k, 'type': 'album', 'mode': 'ALBUM_VIEW', 'icon': 'Ⓗ'}
            for k in sorted(self.lib.fav_albums, key=lambda s: s.lower())
        ]
        return "FAV ALBUMS", items

    def get_playlists_list(self) -> Tuple[str, List[dict]]:
        """Get list of playlists."""
        items = [{'name': 'Favourites', 'type': 'playlist', 'mode': 'FAV_TRACKS_VIEW', 'icon': 'Ⓗ'}]
        for p in self.lib.get_playlists():
            items.append({'name': p.stem, 'type': 'playlist', 'path': p, 'mode': 'PLAYLIST_VIEW'})
        return "PLAYLISTS", items

    def get_recents_tracks(self) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """
        Get recent tracks with metadata.

        Returns:
            Tuple of (album_name, tracks, artist, year, cover)
        """
        tracks = []
        for p in self.lib.recents:
            if p.exists():
                try:
                    track = extract_track_info(p)
                    tracks.append({
                        'path': p, 'title': track.title, 'artist': track.artist,
                        'year': track.year, 'album': track.album
                    })
                except:
                    tracks.append({
                        'path': p, 'title': p.stem, 'artist': None,
                        'year': None, 'album': None
                    })

        cover = None
        artist = ""
        year = ""
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None
            artist = tracks[0].get('artist', '')
            year = str(tracks[0].get('year', ''))

        return "RECENTS", tracks, artist, year, cover

    def get_fav_tracks(self) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get favorite tracks."""
        tracks = self.lib.get_fav_tracks_list()
        cover = None
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None

        return "FAVOURITES", tracks, "", "", cover

    def get_playlist_tracks(self, playlist_path: Path) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get tracks from a playlist."""
        tracks = self.lib.get_playlist_tracks(playlist_path)
        cover = None
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None

        return playlist_path.stem, tracks, "", "", cover

    def get_artist_tracks(self, artist: str) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get tracks by an artist."""
        tracks = self.lib.get_artist_tracks(artist)
        cover = None
        artist_name = ""
        year = ""
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None
            artist_name = tracks[0].get('artist', '')
            year = str(tracks[0].get('year', ''))

        return str(artist), tracks, artist_name, year, cover

    def get_album_tracks(self, album: str) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get tracks from an album."""
        tracks = self.lib.get_album_tracks(album)
        cover = None
        artist = ""
        year = ""
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None
            artist = tracks[0].get('artist', '')
            year = str(tracks[0].get('year', ''))

        return str(album), tracks, artist, year, cover

    def get_files_list(self, current_path: Path, playing_path: Optional[str] = None) -> Tuple[str, List[dict], Optional[object]]:
        """
        Get files and directories at a path.

        Returns:
            Tuple of (folder_name, items, cover_image)
        """
        if not isinstance(current_path, Path):
            current_path = Path(current_path)

        items = []

        # Add parent directory link if not at root
        if current_path != cfg.MUSIC_PATH:
            items.append({
                'name': '..', 'type': 'dir', 'mode': 'FILES',
                'path': current_path.parent, 'icon': 'Ⓕ'
            })

        cover = None
        try:
            all_items = sorted(current_path.iterdir(), key=lambda p: p.name.lower())
            found_art = False

            for p in all_items:
                if p.name.startswith('.'):
                    continue
                if p.is_dir():
                    items.append({
                        'name': p.name, 'type': 'dir', 'mode': 'FILES',
                        'path': p, 'icon': 'Ⓕ'
                    })
                elif p.is_file() and p.suffix.lower() in cfg.VALID_EXTS:
                    try:
                        track = extract_track_info(p)
                        title = track.title
                        artist = track.artist
                        album = track.album
                    except:
                        title = p.stem
                        artist = None
                        album = None

                    icon = 'P' if playing_path == str(p) else 'S'
                    items.append({
                        'name': title, 'type': 'file', 'path': p, 'icon': icon,
                        'artist': artist, 'album': album
                    })

                    if not found_art:
                        covers = get_cover(p)
                        if covers[0]:
                            cover = covers[0]
                            found_art = True
        except OSError:
            pass

        return current_path.name, items, cover
