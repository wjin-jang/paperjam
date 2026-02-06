"""
Audio file metadata extraction using Mutagen.

Supports:
- FLAC: album, artist, title, track/disc numbers, year
- MP3: ID3 tags (TALB, TPE1/2, TIT2, TRCK, TPOS, TDRC/TYER)
"""
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3


def format_track_name(file_path):
    name = file_path.stem
    parts = name.split(' ', 1)
    if len(parts) > 1 and parts[0].replace('.', '').isdigit():
        return parts[1]
    return name

def clean_tag(text):
    if text and isinstance(text, str):
        return text.split(';')[0].strip()
    return text


# Patterns for detecting featured artists
_FEAT_PATTERNS = [
    r'\s*[\(\[]\s*(?:feat\.?|ft\.?|featuring)\s+(.+?)[\)\]]',  # (feat. X) or [feat. X]
    r'\s+(?:feat\.?|ft\.?|featuring)\s+(.+?)(?:\s*[\(\[]|$)',  # feat. X at end or before (
]
_FEAT_REGEX = re.compile('|'.join(_FEAT_PATTERNS), re.IGNORECASE)

# Patterns for splitting multiple artists
_ARTIST_SPLIT_PATTERN = re.compile(r'\s*[,&;]\s*|\s+(?:and|with|x)\s+', re.IGNORECASE)


def parse_artists(artist_str: str, title_str: str = None) -> tuple:
    """
    Parse primary artist and featured artists from artist and title strings.

    Args:
        artist_str: The artist tag value
        title_str: The title tag value (optional, checked for feat. patterns)

    Returns:
        Tuple of (primary_artist, list of featured_artists)
    """
    if not artist_str:
        return ("Unknown Artist", [])

    featured = []
    primary = artist_str.strip()

    # Extract featured artists from title
    if title_str:
        for match in _FEAT_REGEX.finditer(title_str):
            feat_str = match.group(1) or match.group(2)
            if feat_str:
                # Split multiple featured artists
                for artist in _ARTIST_SPLIT_PATTERN.split(feat_str):
                    artist = artist.strip()
                    if artist and artist.lower() not in [f.lower() for f in featured]:
                        featured.append(artist)

    # Check if primary artist string contains multiple artists
    # Only split if there's a clear separator and it's not part of band name
    artists = _ARTIST_SPLIT_PATTERN.split(primary)
    if len(artists) > 1:
        primary = artists[0].strip()
        for artist in artists[1:]:
            artist = artist.strip()
            if artist and artist.lower() not in [f.lower() for f in featured]:
                featured.append(artist)

    return (primary if primary else "Unknown Artist", featured)


def clean_title(title_str: str) -> str:
    """
    Remove featured artist annotations from title for cleaner display.

    Args:
        title_str: The title tag value

    Returns:
        Title with feat./ft. portions removed
    """
    if not title_str:
        return title_str
    return _FEAT_REGEX.sub('', title_str).strip()

def parse_num(val):
    if not val: return 0
    try:
        if isinstance(val, str): return int(val.split('/')[0])
        return int(val)
    except (ValueError, TypeError, IndexError):
        return 0

def get_metadata(file_path):
    """
    Fast extraction of text-only metadata.
    Returns: (album, artist, title, track_number, disc_number, year, duration, featured_artists, artist_sort)
    """
    if not os.path.exists(file_path):
        return ("Unknown Album", "Unknown Artist", format_track_name(file_path), 0, 0, "", 0, [], "")

    album, album_artist, title, year = None, None, None, None
    track_num, disc_num = 0, 0
    duration = 0
    raw_artist = None  # Track artist (for featured detection)
    artist_sort = None  # Album artist sort order

    try:
        audio = File(file_path)
        if audio and audio.info:
            duration = int(audio.info.length)

        if isinstance(audio, FLAC):
            album = audio.get("album", [None])[0]
            album_artist = audio.get("albumartist", [None])[0]
            raw_artist = audio.get("artist", [None])[0]
            if not album_artist:
                album_artist = raw_artist
            title = audio.get("title", [None])[0]
            artist_sort = audio.get("albumartistsort", [None])[0]

            track_num = parse_num(audio.get("tracknumber", [0])[0])
            # Try multiple disc number tag variations (different taggers use different names)
            disc_val = (audio.get("discnumber") or audio.get("disc") or
                       audio.get("disknumber") or audio.get("part") or [1]
                       or audio.get("disc #"))
            disc_num = parse_num(disc_val[0])

            date_str = audio.get("date", [None])[0]
            if date_str: year = date_str.split('-')[0]

        elif isinstance(audio, MP3):
            tags = audio.tags
            if tags:
                if 'TALB' in tags: album = tags['TALB'].text[0]
                if 'TPE2' in tags: album_artist = tags['TPE2'].text[0]
                if 'TPE1' in tags: raw_artist = tags['TPE1'].text[0]
                if not album_artist:
                    album_artist = raw_artist
                if 'TIT2' in tags: title = tags['TIT2'].text[0]
                if 'TSO2' in tags: artist_sort = tags['TSO2'].text[0]
                if 'TRCK' in tags: track_num = parse_num(tags['TRCK'].text[0])
                if 'TPOS' in tags: disc_num = parse_num(tags['TPOS'].text[0])

                if 'TDRC' in tags: year = str(tags['TDRC'].text[0]).split('-')[0]
                elif 'TYER' in tags: year = str(tags['TYER'].text[0])

    except (OSError, ValueError, KeyError, AttributeError):
        pass

    album = clean_tag(album)
    album_artist = clean_tag(album_artist)
    artist_sort = clean_tag(artist_sort)
    if not title: title = format_track_name(file_path)

    # Parse featured artists from title and track artist
    _, featured = parse_artists(raw_artist or "", title)

    return (
        album or "Unknown Album",
        album_artist or "Unknown Artist",
        title,
        track_num,
        disc_num,
        str(year) if year else "",
        duration,
        featured,
        artist_sort or ""
    )


def format_duration(seconds: int) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    if seconds <= 0:
        return ""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


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
    duration: int = 0
    featured: List[str] = field(default_factory=list)
    artist_sort: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with existing code."""
        return {
            'path': self.path,
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'year': self.year,
            'track': self.track_num,
            'disc': self.disc_num,
            'duration': self.duration,
            'featured': self.featured
        }


def extract_track_info(file_path: Path) -> TrackInfo:
    """
    Extract track metadata from a file path.

    Args:
        file_path: Path to the audio file

    Returns:
        TrackInfo object with extracted metadata
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    meta = get_metadata(file_path)

    return TrackInfo(
        path=file_path,
        album=meta[0] if meta[0] else "Unknown Album",
        artist=meta[1] if meta[1] else "Unknown Artist",
        title=meta[2] if meta[2] else file_path.stem,
        track_num=meta[3] if meta[3] else 0,
        disc_num=meta[4] if meta[4] else 0,
        year=meta[5] if meta[5] else "",
        duration=meta[6] if len(meta) > 6 else 0,
        featured=meta[7] if len(meta) > 7 else [],
        artist_sort=meta[8] if len(meta) > 8 else ""
    )


# --- CJK Sorting ---

# Korean Hangul initial consonants (Choseong)
_HANGUL_INITIALS = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'

# Language group order
LANG_SYMBOL = 0
LANG_LATIN = 1
LANG_KOREAN = 2
LANG_JAPANESE = 3
LANG_CHINESE = 4
LANG_OTHER = 5

# Display labels for non-Latin language groups
_LANG_LABELS = {
    LANG_KOREAN: '가-힣',
    LANG_JAPANESE: 'あ-ん',
    LANG_CHINESE: '漢字',
    LANG_OTHER: '기타',
}


def get_language_and_key(text: str) -> tuple:
    """
    Get (language_group, sort_key, display_key) for text.

    For Latin: individual letter grouping (A, B, C...)
    For non-Latin: grouped by language with internal sorting

    Returns:
        Tuple of (language_order, sort_key_for_ordering, display_key_for_heading)
    """
    if not text:
        return (LANG_SYMBOL, '', '#')

    char = text[0]
    code = ord(char)

    # ASCII letters (A-Z) - individual letter grouping
    if char.isascii() and char.isalpha():
        upper = char.upper()
        return (LANG_LATIN, upper, upper)

    # Korean Hangul syllables (AC00-D7AF)
    if 0xAC00 <= code <= 0xD7AF:
        initial_idx = (code - 0xAC00) // 588
        # Sort by initial consonant within Korean group
        base_order = 'ㄱㄱㄴㄷㄷㄹㅁㅂㅂㅅㅅㅇㅈㅈㅊㅋㅌㅍㅎ'
        sort_key = base_order[initial_idx] + chr(initial_idx + 0x100)
        return (LANG_KOREAN, sort_key, _LANG_LABELS[LANG_KOREAN])

    # Korean Hangul Jamo
    if 0x1100 <= code <= 0x1112 or 0x3131 <= code <= 0x314E:
        return (LANG_KOREAN, char, _LANG_LABELS[LANG_KOREAN])

    # Japanese Hiragana (3040-309F)
    if 0x3041 <= code <= 0x3096:
        row_idx = (code - 0x3041) // 5
        return (LANG_JAPANESE, chr(row_idx + 0x100), _LANG_LABELS[LANG_JAPANESE])

    # Japanese Katakana (30A0-30FF)
    if 0x30A1 <= code <= 0x30F6:
        row_idx = (code - 0x30A1) // 5
        return (LANG_JAPANESE, chr(row_idx + 0x100), _LANG_LABELS[LANG_JAPANESE])

    # CJK Unified Ideographs - sort by Unicode code point
    if 0x4E00 <= code <= 0x9FFF:
        return (LANG_CHINESE, char, _LANG_LABELS[LANG_CHINESE])

    # Other alphabetic (Cyrillic, Greek, etc.)
    if char.isalpha():
        return (LANG_OTHER, char.lower(), _LANG_LABELS[LANG_OTHER])

    # Symbols, numbers, etc.
    return (LANG_SYMBOL, text[0], '#')


def get_sort_key(text: str) -> str:
    """Get display key for alphabetical heading."""
    return get_language_and_key(text)[2]


def get_full_sort_key(text: str) -> tuple:
    """Get full sort key tuple for ordering: (language_group, sort_key, text)."""
    lang, key, _ = get_language_and_key(text)
    return (lang, key, text.lower())
