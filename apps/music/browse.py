"""
Browse mode handling for the music player.
Handles different browse modes: artists, albums, playlists, recents, files.
"""
from pathlib import Path
from typing import List, Optional, Tuple

import config as cfg
from core.i18n import t
from core.metadata import format_duration, get_sort_key
from ui.graphics import get_cover
from core.metadata import extract_track_info
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
        return t('menu.main_menu'), [
            {'name': t('player.browse.artists'), 'id': {'kind': 'dir', 'mode': 'ARTISTS_ROOT'}, 'icon': icons['artist']},
            {'name': t('player.browse.albums'), 'id': {'kind': 'dir', 'mode': 'ALBUMS_ROOT'}, 'icon': icons['album']},
            {'name': t('player.browse.tracks'), 'id': {'kind': 'dir', 'mode': 'TRACKS_VIEW'}, 'icon': icons['tracks']},
            {'name': t('player.browse.fav_artists'), 'id': {'kind': 'dir', 'mode': 'FAV_ARTISTS'}, 'icon': icons['fav']},
            {'name': t('player.browse.fav_albums'), 'id': {'kind': 'dir', 'mode': 'FAV_ALBUMS'}, 'icon': icons['fav']},
            {'name': t('player.browse.playlists'), 'id': {'kind': 'dir', 'mode': 'PLAYLISTS_ROOT'}, 'icon': icons['playlist']},
            {'name': t('player.browse.recent'), 'id': {'kind': 'dir', 'mode': 'RECENTS'}, 'icon': icons['recent']},
            {'name': t('player.browse.files'), 'id': {'kind': 'dir', 'mode': 'FILES', 'path': cfg.MUSIC_PATH}, 'icon': icons['dir']}
        ]

    def _create_alphabetical_list(self, data_dict: dict, item_kind: str, item_mode: str) -> List[dict]:
        """Create a list with alphabetical headings if needed."""
        items = []
        current_letter = None
        use_headings = len(data_dict) > cfg.ALPHABETICAL_HEADING_THRESHOLD

        for k in data_dict.keys():
            if use_headings:
                group_key = get_sort_key(k)
                if group_key != current_letter:
                    current_letter = group_key
                    items.append({'name': group_key, 'heading': True})
            items.append({'name': k, 'id': {'kind': item_kind, 'mode': item_mode}})
        return items

    def _process_track_list(self, title: str, tracks: List[dict]) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Helper to process a raw list of tracks into the view format."""
        cover = None
        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None

        track_count = t('player.browse.track_count', count=len(tracks))
        duration = format_duration(LibraryManager.get_total_duration(tracks))
        return title, tracks, track_count, duration, cover

    def get_artists_list(self) -> Tuple[str, List[dict]]:
        """Get list of all artists, organized alphabetically with headings."""
        if self._artist_list_cache is None:
            self._artist_list_cache = self._create_alphabetical_list(self.lib.artists, 'artist', 'ARTIST_VIEW')
        return t('player.browse.artists'), self._artist_list_cache

    def get_albums_list(self) -> Tuple[str, List[dict]]:
        """Get list of all albums."""
        if self._album_list_cache is None:
            self._album_list_cache = self._create_alphabetical_list(self.lib.albums, 'album', 'ALBUM_VIEW')
        return t('player.browse.albums'), self._album_list_cache

    def get_fav_artists_list(self) -> Tuple[str, List[dict]]:
        """Get list of favorite artists."""
        if not self.lib.fav_artists:
            return t('player.browse.fav_artists'), [{'name': t('player.browse.no_fav_artists'), 'selectable': False}]
        items = [
            {'name': k, 'id': {'kind': 'artist', 'mode': 'ARTIST_VIEW'}, 'icon': 'Ⓗ'}
            for k in sorted(self.lib.fav_artists, key=lambda s: s.lower())
        ]
        return t('player.browse.fav_artists'), items

    def get_fav_albums_list(self) -> Tuple[str, List[dict]]:
        """Get list of favorite albums."""
        if not self.lib.fav_albums:
            return t('player.browse.fav_albums'), [{'name': t('player.browse.no_fav_albums'), 'selectable': False}]
        items = [
            {'name': k, 'id': {'kind': 'album', 'mode': 'ALBUM_VIEW'}, 'icon': 'Ⓗ'}
            for k in sorted(self.lib.fav_albums, key=lambda s: s.lower())
        ]
        return t('player.browse.fav_albums'), items

    def get_playlists_list(self) -> Tuple[str, List[dict]]:
        """Get list of playlists."""
        items = [{'name': t('player.browse.favourites'), 'id': {'kind': 'playlist', 'mode': 'FAV_TRACKS_VIEW'}, 'icon': 'Ⓗ'}]
        for p in self.lib.get_playlists():
            items.append({'name': p.stem, 'id': {'kind': 'playlist', 'path': p, 'mode': 'PLAYLIST_VIEW'}})
        return t('player.browse.playlists'), items

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
        title = t('player.browse.shuffle_all') if shuffle else t('player.browse.all_tracks')
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
        return self._process_track_list(t('player.browse.recent'), tracks)

    def get_fav_tracks(self) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get favorite tracks."""
        tracks = self.lib.get_fav_tracks_list()
        return self._process_track_list(t('player.browse.favourites'), tracks)

    def get_playlist_tracks(self, playlist_path: Path) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get tracks from a playlist."""
        tracks = self.lib.get_playlist_tracks(playlist_path)
        return self._process_track_list(playlist_path.stem, tracks)

    def get_artist_tracks(self, artist: str) -> Tuple[str, List[dict], str, str, Optional[object]]:
        """Get tracks by an artist, organized by album with headings, plus featured tracks."""
        tracks = self.lib.get_artist_tracks(artist)
        featured_tracks = self.lib.get_featured_tracks(artist)
        cover = None
        tracks_with_headings = []

        if tracks:
            covers = get_cover(Path(tracks[0]['path']))
            cover = covers[0] if covers else None

            # Group tracks by album and insert headings
            current_album = None
            for track in tracks:
                album = track.get('album', t('player.browse.unknown'))
                if album != current_album:
                    current_album = album
                    tracks_with_headings.append({
                        'heading': True,
                        'name': album
                    })
                tracks_with_headings.append(track)

        # Add "Featured on" section if there are featured tracks
        if featured_tracks:
            tracks_with_headings.append({
                'heading': True,
                'name': t('player.browse.featured_on', default='Featured on')
            })
            for track in featured_tracks:
                tracks_with_headings.append(track)

        tracks = tracks_with_headings

        # Count only actual tracks (not headings)
        actual_tracks = [tr for tr in tracks if not tr.get('heading')]
        own_tracks = [tr for tr in self.lib.get_artist_tracks(artist)]
        track_count = t('player.browse.track_count', count=len(own_tracks))
        duration = format_duration(LibraryManager.get_total_duration(own_tracks))

        # Add pinned info item at the beginning
        info_item = {
            'selectable': False,
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
            discs = set(track.get('disc', 0) or 1 for track in tracks)
            if len(discs) > 1:
                # Insert disc headings
                tracks_with_headings = []
                current_disc = None
                for track in tracks:
                    disc = track.get('disc', 0) or 1
                    if disc != current_disc:
                        current_disc = disc
                        tracks_with_headings.append({
                            'heading': True,
                            'name': t('player.browse.disc', num=disc),
                            'id': {'kind': 'disc', 'disc': disc}
                        })
                    tracks_with_headings.append(track)
                tracks = tracks_with_headings

        # Add pinned info item at the beginning
        info_item = {
            'selectable': False,
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
                        'name': '..', 'id': {'kind': 'dir', 'mode': 'FILES', 'path': parent},
                        'icon': 'Ⓕ'
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

            music_root = cfg.MUSIC_PATH.resolve()
            for p in all_items:
                if p.name.startswith('.'):
                    continue

                # Security: resolve symlinks and verify path is within music directory
                try:
                    resolved = p.resolve()
                    if not resolved.is_relative_to(music_root):
                        continue  # Skip paths outside music directory
                except (ValueError, OSError):
                    continue

                if p.is_dir():
                    dirs.append({
                        'name': p.name, 'id': {'kind': 'dir', 'mode': 'FILES', 'path': p},
                        'icon': 'Ⓕ'
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
                        'name': title, 'id': {'kind': 'file', 'path': p},
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
            manual_items.append({'name': t('player.browse.manual_queue'), 'heading': True})
            for p_str in playlist.manual_queue:
                p = Path(p_str)
                try:
                    name = extract_track_info(p).title
                except (OSError, ValueError, AttributeError):
                    name = p.stem
                manual_items.append({
                    'name': name, 'id': {'kind': 'file', 'path': p}, 'icon': 'Q'
                })

        # Auto Queue
        auto_items = []
        if playlist.has_queue:
            auto_items.append({'name': t('player.browse.auto_queue'), 'heading': True})
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
                    'name': name, 'id': {'kind': 'file', 'path': p}, 'icon': icon
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
                item_kind = item.get('id', {}).get('kind') if isinstance(item.get('id'), dict) else None
                item_path = item.get('id', {}).get('path') if isinstance(item.get('id'), dict) else None
                if item_kind == 'file' and str(item_path) == str(playing_path):
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
                playing_item = {'name': name, 'id': {'kind': 'file', 'path': p}, 'icon': 'P'}

            playing_item['pinned'] = True
            pinned_items.append(playing_item)

        scrollable_items = []
        if not all_items and not pinned_items:
            scrollable_items = [{'name': t('player.browse.queue_empty'), 'selectable': False}]
        else:
            scrollable_items = all_items

        cover = None
        if playing_path:
            covers = get_cover(Path(playing_path))
            cover = covers[0] if covers else None

        return t('player.browse.queue'), pinned_items, scrollable_items, cover
