"""
Graphics utilities and icon assets for the UI.

Provides:
- Bayer matrix dithering for e-paper display
- Pre-rendered UI icons (back, shuffle, loop, fav, clear)
- Image processing helpers
- Cover art extraction with disk caching
"""
import io
import os
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy
from PIL import Image, ImageDraw, ImageOps, ImageEnhance
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from config import SCREEN_WIDTH, SCREEN_HEIGHT, BLACK

logger = logging.getLogger(__name__)

# Cover art cache directory
_COVER_CACHE_DIR = Path.home() / ".cache" / "paperjam" / "covers"
_COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_bayer_matrix():
    """Returns a normalized 4x4 Bayer matrix scaled 0-255."""
    bayer_matrix = numpy.array([
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5]
    ], dtype=float)
    return (bayer_matrix / 16.0) * 255.0


def dither_image(input_img: Image.Image, target_size=(83, 83)) -> Image.Image:
    """Converts an image to 1-bit dithered monochrome with tuned contrast."""

    # 1. Resize / Crop
    input_img = ImageOps.fit(input_img, target_size, method=Image.Resampling.LANCZOS)

    # 2. Handle Transparency
    if input_img.mode in ('RGBA', 'LA') or (input_img.mode == 'P' and 'transparency' in input_img.info):
        alpha = input_img.convert('RGBA')
        bg = Image.new("RGBA", alpha.size, (255, 255, 255, 255))
        bg.alpha_composite(alpha)
        input_img = bg

    # 3. Convert to greyscale
    grey_img = input_img.convert('L')

    enhancer = ImageEnhance.Sharpness(grey_img)
    grey_img = enhancer.enhance(2.0)

    enhancer = ImageEnhance.Contrast(grey_img)
    grey_img = enhancer.enhance(1.4)

    # 5. Apply Bayer Dither
    img_array = numpy.array(grey_img, dtype=float)
    bayer = get_bayer_matrix()

    repeat_y = (target_size[1] // 4) + 1
    repeat_x = (target_size[0] // 4) + 1

    threshold_map = numpy.tile(bayer, (repeat_y, repeat_x))
    threshold_map = threshold_map[:target_size[1], :target_size[0]]

    dithered_array = numpy.where(img_array > threshold_map, 255, 0)
    return Image.fromarray(dithered_array.astype(numpy.uint8)).convert('1')


def create_dithered_strip(width, height):
    """Creates a UI element (scrollbar strip) with a perfect checkerboard pattern."""
    y, x = numpy.indices((height, width))

    pattern = (x + y) % 2 == 0

    dithered_array = numpy.where(pattern, 255, 0).astype(numpy.uint8)

    dither = Image.fromarray(dithered_array).convert('1')

    draw = ImageDraw.Draw(dither)
    draw.rectangle((0, 0, width - 1, height - 1), outline=BLACK)

    return dither


def _get_cache_key(file_path: Path) -> str:
    """Generate a cache key based on file path and modification time."""
    try:
        mtime = os.path.getmtime(file_path)
        key_str = f"{file_path}:{mtime}"
        return hashlib.md5(key_str.encode()).hexdigest()
    except OSError:
        return hashlib.md5(str(file_path).encode()).hexdigest()


def _load_cached_cover(cache_key: str, size: str) -> Optional[Image.Image]:
    """Load a cached cover image from disk."""
    cache_file = _COVER_CACHE_DIR / f"{cache_key}_{size}.png"
    if cache_file.exists():
        try:
            img = Image.open(cache_file)
            img.load()  # Force load image data (PIL uses lazy loading)
            return img.convert('1')
        except Exception:
            pass
    return None


def _save_cached_cover(cache_key: str, size: str, img: Image.Image):
    """Save a cover image to the disk cache."""
    cache_file = _COVER_CACHE_DIR / f"{cache_key}_{size}.png"
    try:
        img.save(cache_file, 'PNG')
    except Exception as e:
        logger.debug(f"Failed to cache cover: {e}")


def get_cover(file_path: Path) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Extract and process cover art from an audio file.
    Uses disk cache to avoid re-processing on subsequent loads.

    Args:
        file_path: Path to the audio file

    Returns:
        Tuple of (small_cover, large_cover) where each is a dithered
        1-bit PIL Image, or (None, None) if no cover found
    """
    if not os.path.exists(file_path):
        return (None, None)

    # Check disk cache first
    cache_key = _get_cache_key(file_path)
    cached_small = _load_cached_cover(cache_key, "small")
    cached_large = _load_cached_cover(cache_key, "large")

    if cached_small is not None and cached_large is not None:
        return (cached_small, cached_large)

    # Extract cover from audio file
    cover_bytes = None

    try:
        audio = File(file_path)
        if isinstance(audio, FLAC):
            if audio.pictures:
                cover_bytes = audio.pictures[0].data
        elif isinstance(audio, MP3):
            if audio.tags:
                for key in audio.tags.keys():
                    if key.startswith('APIC'):
                        cover_bytes = audio.tags[key].data
                        break
    except Exception:
        pass

    final_small = None
    final_large = None

    if cover_bytes:
        try:
            img_obj = Image.open(io.BytesIO(cover_bytes))
            final_small = dither_image(img_obj.copy(), target_size=(83, 83))
            final_large = dither_image(img_obj.copy(), target_size=(112, 112))

            # Cache the processed images
            if final_small:
                _save_cached_cover(cache_key, "small", final_small)
            if final_large:
                _save_cached_cover(cache_key, "large", final_large)
        except Exception:
            pass

    return (final_small, final_large)


# Use asset manager for icons (backward compatible)
from ui.assets import get_ui_icons
UI_ICONS = get_ui_icons()
