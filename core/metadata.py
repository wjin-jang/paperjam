"""
Audio file metadata extraction using Mutagen.

Supports:
- FLAC: album, artist, title, track/disc numbers, year
- MP3: ID3 tags (TALB, TPE1/2, TIT2, TRCK, TPOS, TDRC/TYER)

Optional text romanization for Korean/Japanese characters
using korean_romanizer and pykakasi libraries.
"""
import os
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

try:
    from korean_romanizer.romanizer import Romanizer
    import pykakasi
    HAS_ROMANIZER = True
    kks = pykakasi.kakasi()
except ImportError:
    HAS_ROMANIZER = False

def sanitize_text(text):
    if not text: return ""
    if HAS_ROMANIZER:
        try:
            text = Romanizer(text).romanize()
            text = ''.join([item['hepburn'] for item in kks.convert(text)])
        except (ValueError, KeyError, AttributeError):
            pass
    return text.encode('ascii', 'ignore').decode().strip()

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
    Returns: (album, artist, title, track_number, disc_number, year, duration)
    """
    if not os.path.exists(file_path):
        return ("Unknown Album", "Unknown Artist", format_track_name(file_path), 0, 0, "", 0)

    album, album_artist, title, year = None, None, None, None
    track_num, disc_num = 0, 0
    duration = 0

    try:
        audio = File(file_path)
        if audio and audio.info:
            duration = int(audio.info.length)

        if isinstance(audio, FLAC):
            album = audio.get("album", [None])[0]
            album_artist = audio.get("albumartist", [None])[0]
            if not album_artist: album_artist = audio.get("artist", [None])[0]
            title = audio.get("title", [None])[0]

            track_num = parse_num(audio.get("tracknumber", [0])[0])
            # Try multiple disc number tag variations (different taggers use different names)
            disc_val = (audio.get("discnumber") or audio.get("disc") or
                       audio.get("disknumber") or audio.get("part") or [1])
            disc_num = parse_num(disc_val[0])

            date_str = audio.get("date", [None])[0]
            if date_str: year = date_str.split('-')[0]

        elif isinstance(audio, MP3):
            tags = audio.tags
            if tags:
                if 'TALB' in tags: album = tags['TALB'].text[0]
                if 'TPE2' in tags: album_artist = tags['TPE2'].text[0]
                if not album_artist and 'TPE1' in tags: album_artist = tags['TPE1'].text[0]
                if 'TIT2' in tags: title = tags['TIT2'].text[0]
                if 'TRCK' in tags: track_num = parse_num(tags['TRCK'].text[0])
                if 'TPOS' in tags: disc_num = parse_num(tags['TPOS'].text[0])

                if 'TDRC' in tags: year = str(tags['TDRC'].text[0]).split('-')[0]
                elif 'TYER' in tags: year = str(tags['TYER'].text[0])

    except (OSError, ValueError, KeyError, AttributeError):
        pass

    album = clean_tag(album)
    album_artist = clean_tag(album_artist)
    if not title: title = format_track_name(file_path)

    return (
        sanitize_text(album or "Unknown Album"),
        sanitize_text(album_artist or "Unknown Artist"),
        sanitize_text(title),
        track_num,
        disc_num,
        str(year) if year else "",
        duration
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
