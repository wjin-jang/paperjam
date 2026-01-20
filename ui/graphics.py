"""
Graphics utilities for e-paper display rendering.

This module provides image processing and rendering utilities optimized for
the Waveshare 2.13" e-paper display, including:

- **Bayer dithering**: Converts grayscale images to 1-bit using ordered dithering,
  which produces better results on e-paper than Floyd-Steinberg.

- **Cover art extraction**: Extracts embedded album art from audio files (MP3/FLAC)
  and processes it for display. Includes disk caching to avoid re-processing.

- **CJK text rendering**: Renders mixed CJK/Latin text using appropriate fonts
  for each character range.

- **UI icon management**: Pre-rendered icons for common UI elements.

The cover art cache is stored at ~/.cache/paperjam/covers/ and uses LRU-style
eviction when it exceeds COVER_CACHE_MAX_SIZE_MB.

Example:
    >>> from ui.graphics import get_cover, dither_image
    >>> small, large = get_cover(Path("/path/to/song.mp3"))
    >>> if large:
    ...     display.paste(large, (0, 0))
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import time
from pathlib import Path

import numpy as np
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from config import (
    BLACK,
    COVER_CACHE_MAX_AGE_DAYS,
    COVER_CACHE_MAX_SIZE_MB,
    COVER_SIZE_LARGE,
    COVER_SIZE_SMALL,
    FONT_CJK_HEADER,
    FONT_CJK_MAIN,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

logger = logging.getLogger(__name__)

# --- Cover Art Cache Configuration ---
# Cache directory for processed cover art images
_COVER_CACHE_DIR: Path = Path.home() / ".cache" / "paperjam" / "covers"
_COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting for cache eviction checks (avoid expensive disk scans)
_last_cache_eviction: float = 0
_CACHE_EVICTION_INTERVAL: int = 3600  # Seconds between eviction checks (1 hour)


def _evict_cache_if_needed() -> None:
    """Evict old cache entries if cache size exceeds the configured limit.

    Uses LRU-style eviction based on file access time (st_atime). Only runs
    at most once per _CACHE_EVICTION_INTERVAL to avoid expensive disk scans.

    Eviction strategy:
    1. Skip if last check was less than 1 hour ago
    2. Calculate total cache size
    3. If under limit, do nothing
    4. Sort files by access time (oldest first)
    5. Delete files until cache is at 80% capacity (leaves headroom)
    6. Also delete files older than COVER_CACHE_MAX_AGE_DAYS regardless of size
    """
    global _last_cache_eviction

    now = time.time()

    # Rate limit: only check once per hour to avoid disk I/O overhead
    if now - _last_cache_eviction < _CACHE_EVICTION_INTERVAL:
        return

    _last_cache_eviction = now

    try:
        cache_files = list(_COVER_CACHE_DIR.glob("*.png"))
        if not cache_files:
            return

        # Calculate total cache size in bytes
        total_size = sum(f.stat().st_size for f in cache_files)
        max_size_bytes = COVER_CACHE_MAX_SIZE_MB * 1024 * 1024

        # No eviction needed if under limit
        if total_size <= max_size_bytes:
            return

        # Sort by access time (LRU: least recently accessed first)
        cache_files.sort(key=lambda f: f.stat().st_atime)

        # Calculate age cutoff for mandatory eviction
        max_age_seconds = COVER_CACHE_MAX_AGE_DAYS * 24 * 3600
        cutoff_time = now - max_age_seconds

        # Target 80% capacity to avoid frequent re-eviction
        target_size = int(max_size_bytes * 0.8)

        # Delete files until we're under the target
        for cache_file in cache_files:
            if total_size <= target_size:
                break
            try:
                file_stat = cache_file.stat()
                # Delete if over size limit OR file is too old
                if total_size > max_size_bytes or file_stat.st_atime < cutoff_time:
                    file_size = file_stat.st_size
                    cache_file.unlink()
                    total_size -= file_size
                    logger.debug(f"Evicted cache file: {cache_file.name}")
            except OSError:
                continue

    except OSError as e:
        logger.debug(f"Cache eviction error: {e}")


def get_bayer_matrix() -> np.ndarray:
    """Get a normalized 4x4 Bayer dithering matrix.

    The Bayer matrix provides ordered dithering thresholds that produce
    a pleasing pattern on e-paper displays (better than error diffusion
    methods like Floyd-Steinberg which can cause banding).

    Returns:
        4x4 numpy array with values scaled to 0-255 range.
    """
    # Standard 4x4 Bayer matrix (index values 0-15)
    bayer_matrix = np.array([
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5]
    ], dtype=float)
    # Normalize to 0-255 range for comparison with 8-bit grayscale
    return (bayer_matrix / 16.0) * 255.0


def dither_image(input_img: Image.Image, target_size: tuple[int, int] = (83, 83)) -> Image.Image:
    """Convert an image to 1-bit dithered monochrome for e-paper display.

    Uses ordered (Bayer) dithering with enhanced sharpness and contrast
    to produce clear, readable images on the e-paper display.

    Processing steps:
    1. Resize/crop to target size using high-quality LANCZOS resampling
    2. Flatten transparency (composite onto white background)
    3. Convert to grayscale
    4. Enhance sharpness (2x) and contrast (1.4x)
    5. Apply 4x4 Bayer ordered dithering
    6. Convert to 1-bit

    Args:
        input_img: Source PIL Image in any mode.
        target_size: Output dimensions as (width, height) tuple.

    Returns:
        1-bit PIL Image suitable for e-paper display.
    """
    # Step 1: Resize and crop to fit target dimensions
    input_img = ImageOps.fit(input_img, target_size, method=Image.Resampling.LANCZOS)

    # Step 2: Handle transparency by compositing onto white background
    if input_img.mode in ('RGBA', 'LA') or (input_img.mode == 'P' and 'transparency' in input_img.info):
        alpha = input_img.convert('RGBA')
        bg = Image.new("RGBA", alpha.size, (255, 255, 255, 255))
        bg.alpha_composite(alpha)
        input_img = bg

    # Step 3: Convert to 8-bit grayscale
    grey_img = input_img.convert('L')

    # Step 4: Enhance for better e-paper rendering
    enhancer = ImageEnhance.Sharpness(grey_img)
    grey_img = enhancer.enhance(2.0)  # Sharper edges

    enhancer = ImageEnhance.Contrast(grey_img)
    grey_img = enhancer.enhance(1.4)  # More contrast

    # Step 5: Apply Bayer ordered dithering
    img_array = np.array(grey_img, dtype=float)
    bayer = get_bayer_matrix()

    # Tile the 4x4 Bayer matrix to cover the entire image
    repeat_y = (target_size[1] // 4) + 1
    repeat_x = (target_size[0] // 4) + 1
    threshold_map = np.tile(bayer, (repeat_y, repeat_x))
    threshold_map = threshold_map[:target_size[1], :target_size[0]]

    # Compare each pixel to its threshold value
    dithered_array = np.where(img_array > threshold_map, 255, 0)

    # Step 6: Convert to 1-bit image
    return Image.fromarray(dithered_array.astype(np.uint8)).convert('1')


def create_dithered_strip(width: int, height: int) -> Image.Image:
    """Create a checkerboard-patterned strip for UI elements (e.g., scrollbar).

    Args:
        width: Strip width in pixels.
        height: Strip height in pixels.

    Returns:
        1-bit PIL Image with checkerboard pattern and black border.
    """
    # Create checkerboard using coordinate parity
    y, x = np.indices((height, width))
    pattern = (x + y) % 2 == 0
    dithered_array = np.where(pattern, 255, 0).astype(np.uint8)

    dither = Image.fromarray(dithered_array).convert('1')

    # Add border
    draw = ImageDraw.Draw(dither)
    draw.rectangle((0, 0, width - 1, height - 1), outline=BLACK)

    return dither


def _get_cache_key(file_path: Path) -> str:
    """Generate a cache key based on file path and modification time.

    Including mtime ensures the cache is invalidated when the file changes
    (e.g., if cover art is re-embedded).

    Args:
        file_path: Path to the audio file.

    Returns:
        MD5 hash string suitable for use as a filename.
    """
    try:
        mtime = os.path.getmtime(file_path)
        key_str = f"{file_path}:{mtime}"
        return hashlib.md5(key_str.encode()).hexdigest()
    except OSError:
        return hashlib.md5(str(file_path).encode()).hexdigest()


def _load_cached_cover(cache_key: str, size: str) -> Image.Image | None:
    """Load a cached cover image from disk.

    Args:
        cache_key: MD5 hash identifying the audio file.
        size: Either "small" or "large".

    Returns:
        1-bit PIL Image if cached, None otherwise.
    """
    cache_file = _COVER_CACHE_DIR / f"{cache_key}_{size}.png"
    if cache_file.exists():
        try:
            img = Image.open(cache_file)
            img.load()  # Force load image data (PIL uses lazy loading)
            return img.convert('1')
        except (OSError, IOError):
            pass
    return None


def _save_cached_cover(cache_key: str, size: str, img: Image.Image) -> None:
    """Save a cover image to the disk cache.

    Args:
        cache_key: MD5 hash identifying the audio file.
        size: Either "small" or "large".
        img: Processed cover image to cache.
    """
    cache_file = _COVER_CACHE_DIR / f"{cache_key}_{size}.png"
    try:
        img.save(cache_file, 'PNG')
    except OSError as e:
        logger.debug(f"Failed to cache cover: {e}")


def get_cover(file_path: Path) -> tuple[Image.Image | None, Image.Image | None]:
    """Extract and process cover art from an audio file.

    Extracts embedded album art from MP3 (APIC frames) or FLAC (picture blocks)
    files, processes it through Bayer dithering, and caches the results to disk.

    The disk cache avoids expensive re-processing on subsequent loads. Cache
    keys include the file's modification time, so updated files get fresh covers.

    Args:
        file_path: Path to the audio file.

    Returns:
        Tuple of (small_cover, large_cover) where each is a dithered 1-bit
        PIL Image sized according to COVER_SIZE_SMALL/LARGE. Returns (None, None)
        if no embedded cover art is found or the file doesn't exist.
    """
    if not os.path.exists(file_path):
        return (None, None)

    # Periodically evict old cache entries to prevent unbounded growth
    _evict_cache_if_needed()

    # Check disk cache first for both sizes
    cache_key = _get_cache_key(file_path)
    cached_small = _load_cached_cover(cache_key, "small")
    cached_large = _load_cached_cover(cache_key, "large")

    # Fast path: both sizes already cached (most common case)
    if cached_small is not None and cached_large is not None:
        return (cached_small, cached_large)

    # Determine which sizes need processing
    need_small = cached_small is None
    need_large = cached_large is None

    # Extract cover bytes from audio file metadata
    cover_bytes: bytes | None = None
    try:
        audio = File(file_path)
        if isinstance(audio, FLAC):
            # FLAC stores pictures in a dedicated pictures list
            if audio.pictures:
                cover_bytes = audio.pictures[0].data
        elif isinstance(audio, MP3):
            # MP3 uses ID3 APIC frames for attached pictures
            if audio.tags:
                for key in audio.tags.keys():
                    if key.startswith('APIC'):
                        cover_bytes = audio.tags[key].data
                        break
    except Exception:
        pass

    final_small = cached_small
    final_large = cached_large

    if cover_bytes:
        try:
            img_obj = Image.open(io.BytesIO(cover_bytes))

            # Only process the sizes we need
            if need_small:
                final_small = dither_image(img_obj.copy(), target_size=COVER_SIZE_SMALL)
                if final_small:
                    _save_cached_cover(cache_key, "small", final_small)

            if need_large:
                final_large = dither_image(img_obj.copy(), target_size=COVER_SIZE_LARGE)
                if final_large:
                    _save_cached_cover(cache_key, "large", final_large)
        except (OSError, IOError):
            pass

    return (final_small, final_large)


# --- CJK Text Rendering ---
# These functions handle mixed-script text (Latin + CJK) by switching fonts
# as needed. The Galmuri pixel font is used for CJK characters.


def is_cjk(char: str) -> bool:
    """Check if a character is CJK (Chinese, Japanese, Korean).

    Covers the main Unicode ranges for East Asian scripts:
    - CJK Unified Ideographs (Chinese characters)
    - Hangul (Korean)
    - Hiragana and Katakana (Japanese)

    Args:
        char: Single character to check.

    Returns:
        True if the character is in a CJK Unicode range.
    """
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF or      # CJK Unified Ideographs
        0x3400 <= code <= 0x4DBF or      # CJK Unified Ideographs Extension A
        0xAC00 <= code <= 0xD7AF or      # Hangul Syllables (Korean)
        0x3040 <= code <= 0x309F or      # Hiragana (Japanese)
        0x30A0 <= code <= 0x30FF or      # Katakana (Japanese)
        0x1100 <= code <= 0x11FF or      # Hangul Jamo
        0x3130 <= code <= 0x318F         # Hangul Compatibility Jamo
    )


def draw_text_with_cjk(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    cjk_font: ImageFont.FreeTypeFont,
    fill: int = 0,
    cjk_y_offset: int = 0
) -> None:
    """Draw text using appropriate fonts for CJK and non-CJK characters.

    Splits the text into runs of CJK and non-CJK characters, rendering
    each run with the appropriate font. This allows mixed-script text
    like "Track 1 - 月光" to render correctly.

    Args:
        draw: PIL ImageDraw object to render onto.
        xy: (x, y) starting position.
        text: Text string to render.
        font: Font for non-CJK (Latin, etc.) characters.
        cjk_font: Font for CJK characters (e.g., Galmuri).
        fill: Color value (0=black, 255=white).
        cjk_y_offset: Vertical offset for CJK font baseline alignment.
    """
    if not text:
        return

    x, y = xy
    current_text = ""
    current_is_cjk: bool | None = None

    for char in text:
        char_is_cjk = is_cjk(char)

        if current_is_cjk is None:
            # First character
            current_is_cjk = char_is_cjk
            current_text = char
        elif char_is_cjk == current_is_cjk:
            # Same script run, accumulate
            current_text += char
        else:
            # Script changed, render accumulated text
            used_font = cjk_font if current_is_cjk else font
            text_y = y + cjk_y_offset if current_is_cjk else y
            draw.text((x, text_y), current_text, font=used_font, fill=fill)
            bbox = used_font.getbbox(current_text)
            x += bbox[2] - bbox[0]

            # Start new segment
            current_text = char
            current_is_cjk = char_is_cjk

    # Render remaining text
    if current_text:
        used_font = cjk_font if current_is_cjk else font
        text_y = y + cjk_y_offset if current_is_cjk else y
        draw.text((x, text_y), current_text, font=used_font, fill=fill)


def get_text_width_with_cjk(
    text: str,
    font: ImageFont.FreeTypeFont,
    cjk_font: ImageFont.FreeTypeFont
) -> int:
    """Calculate text width accounting for mixed CJK/non-CJK fonts.

    Uses the same run-splitting logic as draw_text_with_cjk to ensure
    accurate width calculations for layout purposes.

    Args:
        text: Text string to measure.
        font: Font for non-CJK characters.
        cjk_font: Font for CJK characters.

    Returns:
        Total width in pixels.
    """
    if not text:
        return 0

    total_width = 0
    current_text = ""
    current_is_cjk: bool | None = None

    for char in text:
        char_is_cjk = is_cjk(char)

        if current_is_cjk is None:
            current_is_cjk = char_is_cjk
            current_text = char
        elif char_is_cjk == current_is_cjk:
            current_text += char
        else:
            used_font = cjk_font if current_is_cjk else font
            bbox = used_font.getbbox(current_text)
            total_width += bbox[2] - bbox[0]

            current_text = char
            current_is_cjk = char_is_cjk

    if current_text:
        used_font = cjk_font if current_is_cjk else font
        bbox = used_font.getbbox(current_text)
        total_width += bbox[2] - bbox[0]

    return total_width


# --- UI Icons ---
# Backward-compatible import of pre-rendered icon assets
from ui.assets import get_ui_icons

UI_ICONS: dict[str, Image.Image] = get_ui_icons()
