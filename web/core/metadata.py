"""PaperJam Web — Audio metadata extraction (adapted from original)."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus


@dataclass
class TrackInfo:
    path: str
    title: str
    artist: str
    album: str
    year: str = ""
    track_num: int = 0
    disc_num: int = 1
    duration: int = 0
    featured: list[str] = field(default_factory=list)
    artist_sort: str = ""


FEAT_PATTERN = re.compile(
    r"\s*[\(\[]\s*(?:feat\.?|featuring|ft\.?)\s+(.+?)[\)\]]",
    re.IGNORECASE,
)

SPLIT_PATTERN = re.compile(r"\s*(?:,\s*|\s+&\s+|\s+and\s+|\s+with\s+|\s*;\s*|\s+x\s+)\s*", re.IGNORECASE)


def clean_title(title: str) -> str:
    return FEAT_PATTERN.sub("", title).strip()


def parse_featured(title: str) -> list[str]:
    match = FEAT_PATTERN.search(title)
    if not match:
        return []
    raw = match.group(1)
    return [a.strip() for a in SPLIT_PATTERN.split(raw) if a.strip()]


def parse_num(val) -> int:
    if isinstance(val, int):
        return val
    s = str(val).strip()
    if "/" in s:
        s = s.split("/")[0]
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def clean_tag(val) -> str:
    if not val:
        return ""
    s = str(val).strip()
    if ";" in s:
        s = s.split(";")[0].strip()
    return s


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0:00"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def extract_track_info(path: Path) -> TrackInfo | None:
    """Extract metadata from an audio file."""
    try:
        audio = MutagenFile(str(path))
    except Exception:
        return None

    if audio is None:
        # Fallback: use filename
        return TrackInfo(
            path=str(path),
            title=path.stem,
            artist="Unknown Artist",
            album=path.parent.name or "Unknown Album",
        )

    title = ""
    artist = ""
    album = ""
    year = ""
    track_num = 0
    disc_num = 1
    duration = int(audio.info.length) if audio.info else 0
    artist_sort = ""

    if isinstance(audio, FLAC):
        title = clean_tag((audio.get("title") or [""])[0])
        album_artist = clean_tag((audio.get("albumartist") or [""])[0])
        raw_artist = clean_tag((audio.get("artist") or [""])[0])
        artist = album_artist or raw_artist
        album = clean_tag((audio.get("album") or [""])[0])
        year = clean_tag((audio.get("date") or [""])[0])[:4]
        track_num = parse_num((audio.get("tracknumber") or ["0"])[0])
        disc_num = parse_num((audio.get("discnumber") or audio.get("disc") or ["1"])[0])
        artist_sort = clean_tag((audio.get("albumartistsort") or [""])[0])

    elif isinstance(audio, MP3):
        tags = audio.tags
        if tags:
            title = clean_tag(tags.get("TIT2"))
            album_artist = clean_tag(tags.get("TPE2"))
            raw_artist = clean_tag(tags.get("TPE1"))
            artist = album_artist or raw_artist
            album = clean_tag(tags.get("TALB"))
            track_num = parse_num(tags.get("TRCK"))
            disc_num = parse_num(tags.get("TPOS") or "1")
            artist_sort = clean_tag(tags.get("TSO2"))
            year_tag = tags.get("TDRC") or tags.get("TYER")
            if year_tag:
                year = str(year_tag)[:4]

    elif isinstance(audio, MP4):
        title = clean_tag((audio.get("\xa9nam") or [""])[0])
        album_artist = clean_tag((audio.get("aART") or [""])[0])
        raw_artist = clean_tag((audio.get("\xa9ART") or [""])[0])
        artist = album_artist or raw_artist
        album = clean_tag((audio.get("\xa9alb") or [""])[0])
        year = clean_tag((audio.get("\xa9day") or [""])[0])[:4]
        trkn = audio.get("trkn")
        if trkn:
            track_num = trkn[0][0] if trkn[0] else 0
        disk = audio.get("disk")
        if disk:
            disc_num = disk[0][0] if disk[0] else 1

    elif isinstance(audio, (OggVorbis, OggOpus)):
        title = clean_tag((audio.get("title") or [""])[0])
        album_artist = clean_tag((audio.get("albumartist") or [""])[0])
        raw_artist = clean_tag((audio.get("artist") or [""])[0])
        artist = album_artist or raw_artist
        album = clean_tag((audio.get("album") or [""])[0])
        year = clean_tag((audio.get("date") or [""])[0])[:4]
        track_num = parse_num((audio.get("tracknumber") or ["0"])[0])
        disc_num = parse_num((audio.get("discnumber") or ["1"])[0])

    else:
        # Generic fallback
        tags = audio.tags
        if tags:
            title = clean_tag(tags.get("title", [""]) if isinstance(tags.get("title"), list) else tags.get("title", ""))
            artist = clean_tag(tags.get("artist", [""]) if isinstance(tags.get("artist"), list) else tags.get("artist", ""))
            album = clean_tag(tags.get("album", [""]) if isinstance(tags.get("album"), list) else tags.get("album", ""))

    # Fallbacks
    if not title:
        title = path.stem
    if not artist:
        artist = "Unknown Artist"
    if not album:
        album = path.parent.name or "Unknown Album"
    if disc_num < 1:
        disc_num = 1

    featured = parse_featured(title)

    return TrackInfo(
        path=str(path),
        title=title,
        artist=artist,
        album=album,
        year=year,
        track_num=track_num,
        disc_num=disc_num,
        duration=duration,
        featured=featured,
        artist_sort=artist_sort,
    )
