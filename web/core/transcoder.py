"""PaperJam Web — FFmpeg audio transcoding for streaming."""

import hashlib
import logging
import subprocess
import shutil
from pathlib import Path

from config import TRANSCODE_CACHE_DIR, QUALITY_PRESETS

logger = logging.getLogger(__name__)

# Check for FFmpeg
FFMPEG_PATH = shutil.which("ffmpeg")
FFPROBE_PATH = shutil.which("ffprobe")


def get_cache_path(source_path: str, quality: str) -> Path:
    """Get the cache path for a transcoded file."""
    key = f"{source_path}:{quality}"
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return TRANSCODE_CACHE_DIR / f"{h}.mp3"


def get_audio_info(path: str) -> dict | None:
    """Get audio file info using ffprobe."""
    if not FFPROBE_PATH:
        return None
    try:
        result = subprocess.run(
            [
                FFPROBE_PATH, "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            import json
            return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"ffprobe error: {e}")
    return None


def needs_transcoding(path: str, quality: str) -> bool:
    """Check if a file needs transcoding for the given quality."""
    if quality == "original":
        return False

    suffix = Path(path).suffix.lower()
    
    # Browsers natively support FLAC, MP3, M4A/AAC, WAV, OGG — no need to transcode
    browser_native = {".flac", ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus"}
    if suffix in browser_native:
        return False
    
    return True


def transcode(source_path: str, quality: str) -> Path | None:
    """Transcode an audio file to MP3 at the given quality.

    Returns the path to the transcoded file, or None if transcoding failed.
    Uses caching to avoid re-transcoding.
    """
    if not FFMPEG_PATH:
        logger.error("FFmpeg not found")
        return None

    bitrate = QUALITY_PRESETS.get(quality, 256)
    if bitrate == 0:
        return Path(source_path)

    cache_path = get_cache_path(source_path, quality)

    # Check cache
    if cache_path.exists():
        source_mtime = Path(source_path).stat().st_mtime
        cache_mtime = cache_path.stat().st_mtime
        if cache_mtime > source_mtime:
            return cache_path

    # Transcode
    try:
        result = subprocess.run(
            [
                FFMPEG_PATH, "-y",
                "-i", str(source_path),
                "-vn",  # no video
                "-codec:a", "libmp3lame",
                "-b:a", f"{bitrate}k",
                "-ar", "44100",
                "-ac", "2",
                "-map_metadata", "0",
                str(cache_path),
            ],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return cache_path
        else:
            logger.error(f"FFmpeg error: {result.stderr[:500]}")
            return None
    except subprocess.TimeoutExpired:
        logger.error(f"Transcode timeout: {source_path}")
        return None
    except Exception as e:
        logger.error(f"Transcode error: {e}")
        return None


def get_mime_type(path: str) -> str:
    """Get MIME type for an audio file."""
    suffix = Path(path).suffix.lower()
    mime_map = {
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".opus": "audio/opus",
        ".wma": "audio/x-ms-wma",
        ".aac": "audio/aac",
    }
    return mime_map.get(suffix, "application/octet-stream")
