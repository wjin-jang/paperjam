"""
Browse mode handling for the music player.
Handles different browse modes: artists, albums, playlists, recents, files.
"""
from pathlib import Path
from typing import List, Optional, Tuple

import config as cfg
from core.metadata import get_cover, format_duration
from core.track_info import extract_track_info
from core.library import LibraryManager


class BrowseHandler:
    """Handles different browse modes for the music player."""

    def __init__(self, library_manager):
        """
        Initialize browse handler.

        Args:
            library_manager: Library manager instance
        """
        self.lib = library_manager
        self._artist_list_cache = None
        self._album_list_cache = None

    def clear_cache(self):
        """Clear the browse cache."""
        self._artist_list_cache = None
        self._album_list_cache = None

    def get_root_menu(self) -> Tuple[str, List[dict]]:
        """Get the root menu items."""
        track_count = self.lib.get_total_tracks()
        icons = cfg.MENU_ICONS
        return "MAIN MENU", [
            {'name': 'Artists', 'type': 'dir', 'mode': 'ARTISTS_ROOT', 'icon': icons['artist']},
            {'name': 'Albums', 'type': 'dir', 'mode': 'ALBUMS_ROOT', 'icon': icons['album']},
            {'name': 'Tracks', 'type': 'dir', 'mode': 'TRACKS_VIEW', 'icon': icons['tracks']},
            {'name': 'Fav Artists', 'type': 'dir', 'mode': 'FAV_ARTISTS', 'icon': icons['fav']},
            {'name': 'Fav Albums', 'type': 'dir', 'mode': 'FAV_ALBUMS', 'icon': icons['fav']},
            {'name': 'Playlists', 'type': 'dir', 'mode': 'PLAYLISTS_ROOT', 'icon': icons['playlist']},
            {'name': 'Recents', 'type': 'dir', 'mode': 'RECENTS', 'icon': icons['recent']},
            {'name': 'Files', 'type': 'dir', 'mode': 'FILES', 'path': cfg.MUSIC_PATH, 'icon': icons['dir']}
        ]

    def _create_alphabetical_list(self, data_dict: dict, item_type: str, item_mode: str) -> List[dict]:
        """Create a list with alphabetical headings if needed."""
        items = []
        current_letter = None
        use_headings = len(data_dict) > cfg.ALPHABETICAL_HEADING_THRESHOLD

        for k in data_dict.keys():
            if use_headings:
                first_char = k[0].upper() if k else '#'
                if not first_char.isalpha():
                    first_char = '#'
                if first_char != current_letter:
                    current_letter = first_char
                    items.append({'name': first_char, 'type': 'heading'})
            items.append({'name': k, 'type': item_type, 'mode': item_mode})
        return items

    def _process_track_list(self, title: str, tracks: List[dict]) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Helper to process a raw list of tracks into the view format."""
        cover = None
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None

        track_count = f"{len(tracks)} tracks"
        duration = format_duration(LibraryManager.get_total_duration(tracks))
        return title, tracks, track_count, duration, cover

    def get_artists_list(self) -> Tuple[str, List[dict]]:
        """Get list of all artists, organized alphabetically with headings."""
        if self._artist_list_cache is None:
            self._artist_list_cache = self._create_alphabetical_list(self.lib.artists, 'artist', 'ARTIST_VIEW')
        return "ARTISTS", self._artist_list_cache

    def get_albums_list(self) -> Tuple[str, List[dict]]:
        """Get list of all albums."""
        if self._album_list_cache is None:
            self._album_list_cache = self._create_alphabetical_list(self.lib.albums, 'album', 'ALBUM_VIEW')
        return "ALBUMS", self._album_list_cache

    def get_fav_artists_list(self) -> Tuple[str, List[dict]]:
        """Get list of favorite artists."""
        if not self.lib.fav_artists:
            return "FAV ARTISTS", [{'name': '(No Fav Artists)', 'type': 'info'}]
        items = [
            {'name': k, 'type': 'artist', 'mode': 'ARTIST_VIEW', 'icon': 'Ⓗ'}
            for k in sorted(self.lib.fav_artists, key=lambda s: s.lower())
        ]
        return "FAV ARTISTS", items

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

    def get_all_tracks(self, shuffle: bool = False) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """
        Get all tracks from the library.
        Uses cached metadata for performance with large libraries.

        Args:
            shuffle: If True, return tracks in random order

        Returns:
            Tuple of (title, tracks, track_count, duration, cover)
        """
        tracks = self.lib.get_all_tracks(shuffle=shuffle)
        title = "SHUFFLE ALL" if shuffle else "ALL TRACKS"
        return self._process_track_list(title, tracks)

    def get_recents_tracks(self) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """
        Get recent tracks with metadata.

        Returns:
            Tuple of (album_name, tracks, track_count, duration, cover)
        """
        tracks = []
        for p in self.lib.recents:
            if p.exists():
                try:
                    track = extract_track_info(p)
                    tracks.append({
                        'path': p, 'title': track.title, 'artist': track.artist,
                        'year': track.year, 'album': track.album,
                        'duration': track.duration
                    })
                except (OSError, ValueError, AttributeError):
                    tracks.append({
                        'path': p, 'title': p.stem, 'artist': None,
                        'year': None, 'album': None, 'duration': 0
                    })
        return self._process_track_list("RECENTS", tracks)

    def get_fav_tracks(self) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get favorite tracks."""
        tracks = self.lib.get_fav_tracks_list()
        return self._process_track_list("FAVOURITES", tracks)

    def get_playlist_tracks(self, playlist_path: Path) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get tracks from a playlist."""
        tracks = self.lib.get_playlist_tracks(playlist_path)
        return self._process_track_list(playlist_path.stem, tracks)

    def get_artist_tracks(self, artist: str) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get tracks by an artist, organized by album with headings."""
        tracks = self.lib.get_artist_tracks(artist)
        cover = None
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None

            # Group tracks by album and insert headings
            tracks_with_headings = []
            current_album = None
            for t in tracks:
                album = t.get('album', 'Unknown')
                if album != current_album:
                    current_album = album
                    tracks_with_headings.append({
                        'type': 'heading',
                        'name': album
                    })
                tracks_with_headings.append(t)
            tracks = tracks_with_headings

        # Count only actual tracks (not headings)
        actual_tracks = [t for t in tracks if t.get('type') != 'heading']
        track_count = f"{len(actual_tracks)} tracks"
        duration = format_duration(LibraryManager.get_total_duration(actual_tracks))

        # Add pinned info item at the beginning
        info_item = {
            'type': 'info',
            'pinned': True,
            'columns': [track_count, duration]
        }
        tracks = [info_item] + tracks

        return str(artist), tracks, track_count, duration, cover

    def get_album_tracks(self, album: str) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get tracks from an album. Returns artist and year instead of track count."""
        tracks = self.lib.get_album_tracks(album)
        cover = None
        artist = ""
        year = ""
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None
            artist = tracks[0].get('artist', '')
            year = str(tracks[0].get('year', '') or '')

            # Check if album has multiple discs
            discs = set(t.get('disc', 1) for t in tracks)
            if len(discs) > 1:
                # Insert disc headings
                tracks_with_headings = []
                current_disc = None
                for t in tracks:
                    disc = t.get('disc', 1)
                    if disc != current_disc:
                        current_disc = disc
                        tracks_with_headings.append({
                            'type': 'heading',
                            'name': f'Disc {disc}'
                        })
                    tracks_with_headings.append(t)
                tracks = tracks_with_headings

        # Add pinned info item at the beginning
        info_item = {
            'type': 'info',
            'pinned': True,
            'columns': [artist, year] if year else [artist]
        }
        tracks = [info_item] + tracks

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
        # Path traversal protection: ensure parent is within MUSIC_PATH
        if current_path != cfg.MUSIC_PATH:
            parent = current_path.parent
            try:
                # Resolve paths to handle symlinks and ensure parent is within music path
                if parent.resolve().is_relative_to(cfg.MUSIC_PATH.resolve()):
                    items.append({
                        'name': '..', 'type': 'dir', 'mode': 'FILES',
                        'path': parent, 'icon': 'Ⓕ'
                    })
            except (ValueError, OSError):
                # is_relative_to may raise ValueError on older Python, OSError on bad paths
                pass

        cover = None
        try:
            all_items = list(current_path.iterdir())
            found_art = False

            # Separate directories and files
            dirs = []
            files = []

            for p in all_items:
                if p.name.startswith('.'):
                    continue
                if p.is_dir():
                    dirs.append({
                        'name': p.name, 'type': 'dir', 'mode': 'FILES',
                        'path': p, 'icon': 'Ⓕ'
                    })
                elif p.is_file() and p.suffix.lower() in cfg.VALID_EXTS:
                    try:
                        track = extract_track_info(p)
                        title = track.title
                        artist = track.artist
                        album = track.album
                        disc = track.disc_num
                        track_num = track.track_num
                    except (OSError, ValueError, AttributeError):
                        title = p.stem
                        artist = None
                        album = None
                        disc = 0
                        track_num = 0

                    # Don't set icon - let music_view._get_item_icon() handle it
                    # based on playing state and track number
                    files.append({
                        'name': title, 'type': 'file', 'path': p,
                        'artist': artist, 'album': album,
                        'disc': disc, 'track': track_num
                    })

                    if not found_art:
                        covers = get_cover(p)
                        if covers[0]:
                            cover = covers[0]
                            found_art = True

            # Sort directories by name, files by disc then track
            dirs.sort(key=lambda x: x['name'].lower())
            files.sort(key=lambda x: (x.get('disc', 0), x.get('track', 0)))

            items.extend(dirs)
            items.extend(files)
        except OSError:
            pass

        return current_path.name, items, cover

    def get_queue_view(self, playlist, playing_path: Optional[str]) -> Tuple[str, List[dict], List[dict], Optional[object]]:
        """
        Get items for Queue View.

        Returns:
            Tuple of (title, pinned_items, scrollable_items, cover)
        """
        pinned_items = []
        
        # Manual Queue
        manual_items = []
        if playlist.manual_queue:
            manual_items.append({'name': 'MANUAL QUEUE', 'type': 'heading'})
            for p_str in playlist.manual_queue:
                p = Path(p_str)
                try:
                    name = extract_track_info(p).title
                except (OSError, ValueError, AttributeError):
                    name = p.stem
                manual_items.append({
                    'name': name, 'type': 'file', 'path': p, 'icon': 'Q'
                })

        # Auto Queue
        auto_items = []
        if playlist.has_queue:
            auto_items.append({'name': 'AUTO QUEUE', 'type': 'heading'})
            start_idx = playlist.queue_idx
            count = 0
            idx = start_idx
            # Bounds check to prevent IndexError
            if not playlist.queue or idx >= len(playlist.queue):
                idx = 0
            while count < cfg.QUEUE_VIEW_MAX_ITEMS and playlist.queue:
                if idx >= len(playlist.queue):
                    break
                real_idx = playlist.queue[idx]
                if real_idx >= len(playlist.playlist_source):
                    break
                path_str = playlist.playlist_source[real_idx]
                p = Path(path_str)
                try:
                    name = extract_track_info(p).title
                except (OSError, ValueError, AttributeError):
                    name = p.stem
                
                # Distinguish icon based on queue position relative to playing
                icon = str(count) if count > 0 else "P"
                
                auto_items.append({
                    'name': name, 'type': 'file', 'path': p, 'icon': icon
                })
                
                idx = (idx + 1) % len(playlist.queue)
                
                # Stop at end of playlist if Loop is Off
                if idx == 0 and playlist.loop_mode == 0:
                    break
                
                if idx == start_idx: break
                count += 1
        
        all_items = manual_items + auto_items
        
        # Find and pin playing item
        playing_item = None
        if playing_path:
            for i, item in enumerate(all_items):
                if item.get('type') == 'file' and str(item.get('path')) == str(playing_path):
                    playing_item = item
                    del all_items[i]
                    break
            
            # If not found in list (e.g. playing from outside queue or list truncated), create it
            if not playing_item:
                p = Path(playing_path)
                try:
                    name = extract_track_info(p).title
                except (OSError, ValueError, AttributeError):
                    name = p.stem
                playing_item = {'name': name, 'type': 'file', 'path': p, 'icon': 'P'}

            playing_item['pinned'] = True
            pinned_items.append(playing_item)

        controls_item = {'type': 'controls', 'pinned': True}
        pinned_items.append(controls_item)
        
        scrollable_items = []
        if not all_items and not pinned_items:
            scrollable_items = [{'name': '(Queue Empty)', 'type': 'info'}]
        else:
            scrollable_items = all_items

        cover = None
        if playing_path:
            covers = get_cover(Path(playing_path))
            cover = covers[0] if covers else None

        return "QUEUE", pinned_items, scrollable_items, cover
