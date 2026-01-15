"""
Image processing utilities for the UI layer.
Contains cover art extraction that was previously in core/metadata.py,
fixing the circular dependency between core and ui layers.
"""
import io
import os
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from ui.graphics import dither_image


def extract_cover_art(file_path: Path) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Extract and process cover art from an audio file.

    This function was moved from core/metadata.py to fix the circular
    dependency where core modules were importing from ui modules.

    Args:
        file_path: Path to the audio file

    Returns:
        Tuple of (small_cover, large_cover) where each is a dithered
        1-bit PIL Image, or (None, None) if no cover found
    """
    if not os.path.exists(file_path):
        return (None, None)

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
        except Exception:
            pass

    return (final_small, final_large)


# Alias for backward compatibility
get_cover = extract_cover_art
