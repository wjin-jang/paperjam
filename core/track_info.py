"""
Unified track information extraction utility.
Consolidates metadata extraction logic that was previously duplicated
across library.py and music.py.
"""
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any
from core.metadata import get_metadata


@dataclass
class TrackInfo:
    """Unified track information container."""
    path: Path
    title: str
    artist: str
    album: str
    year: str
    track_num: int
    disc_num: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing code."""
        return {
            'path': self.path,
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'year': self.year,
            'track': self.track_num,
            'disc': self.disc_num
        }


def extract_track_info(file_path: Path) -> TrackInfo:
    """
    Extract track metadata from a file path.

    This is the single source of truth for metadata extraction,
    replacing duplicated logic across the codebase.

    Args:
        file_path: Path to the audio file

    Returns:
        TrackInfo object with extracted metadata
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    meta = get_metadata(file_path)
    # meta structure: (album, artist, title, track_num, disc_num, year)

    return TrackInfo(
        path=file_path,
        album=meta[0] if meta[0] else "Unknown Album",
        artist=meta[1] if meta[1] else "Unknown Artist",
        title=meta[2] if meta[2] else file_path.stem,
        track_num=meta[3] if meta[3] else 0,
        disc_num=meta[4] if meta[4] else 0,
        year=meta[5] if meta[5] else ""
    )


def extract_track_dict(file_path: Path) -> Dict[str, Any]:
    """
    Extract track metadata as a dictionary.

    Convenience wrapper for code that expects dict format.

    Args:
        file_path: Path to the audio file

    Returns:
        Dictionary with track metadata
    """
    return extract_track_info(file_path).to_dict()
