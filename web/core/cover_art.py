"""PaperJam Web — Cover art extraction and caching."""

import hashlib
import logging
from io import BytesIO
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.id3 import APIC
from PIL import Image

from config import COVER_CACHE_DIR, COVER_SIZES

logger = logging.getLogger(__name__)


def _cache_key(path: str, size: str) -> str:
    h = hashlib.sha256(path.encode()).hexdigest()[:16]
    return f"{h}_{size}.jpg"


def get_cover_path(track_path: str, size: str = "medium") -> Path | None:
    """Get cover art for a track, extracting and caching as needed.

    Checks: embedded art -> folder art -> returns None
    """
    cache_file = COVER_CACHE_DIR / _cache_key(track_path, size)
    if cache_file.exists():
        return cache_file

    # Try to extract cover art
    image_data = _extract_embedded(track_path)
    if not image_data:
        image_data = _find_folder_art(track_path)
    if not image_data:
        return None

    # Resize and cache
    try:
        img = Image.open(BytesIO(image_data))
        img = img.convert("RGB")
        target_size = COVER_SIZES.get(size, 300)
        img.thumbnail((target_size, target_size), Image.LANCZOS)
        img.save(cache_file, "JPEG", quality=85)
        return cache_file
    except Exception as e:
        logger.error(f"Cover processing error: {e}")
        return None


def _extract_embedded(path: str) -> bytes | None:
    """Extract embedded cover art from audio file."""
    try:
        audio = MutagenFile(str(path))
        if audio is None:
            return None

        if isinstance(audio, MP3) and audio.tags:
            for tag in audio.tags.values():
                if isinstance(tag, APIC):
                    return tag.data

        elif isinstance(audio, FLAC) and audio.pictures:
            return audio.pictures[0].data

        elif isinstance(audio, MP4):
            covr = audio.get("covr")
            if covr:
                return bytes(covr[0])

        # Generic: check for pictures attribute
        if hasattr(audio, "pictures") and audio.pictures:
            return audio.pictures[0].data

    except Exception as e:
        logger.debug(f"Embedded art extraction failed: {e}")
    return None


def _find_folder_art(track_path: str) -> bytes | None:
    """Look for cover art images in the track's directory."""
    folder = Path(track_path).parent
    cover_names = [
        "cover", "folder", "front", "album", "art", "artwork", "thumb",
    ]
    image_exts = [".jpg", ".jpeg", ".png", ".webp", ".bmp"]

    for name in cover_names:
        for ext in image_exts:
            candidate = folder / f"{name}{ext}"
            if candidate.exists():
                try:
                    return candidate.read_bytes()
                except Exception:
                    continue
            # Case-insensitive
            candidate_upper = folder / f"{name.title()}{ext}"
            if candidate_upper.exists():
                try:
                    return candidate_upper.read_bytes()
                except Exception:
                    continue

    # Fallback: any image file in the folder
    for ext in image_exts:
        for img_file in folder.glob(f"*{ext}"):
            try:
                return img_file.read_bytes()
            except Exception:
                continue

    return None
