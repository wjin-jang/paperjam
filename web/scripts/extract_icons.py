#!/usr/bin/env python3
"""Extract icon glyphs from BMmini, Nintendo-DS-BIOS, and Icons fonts as PNGs."""

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
OUTPUT_DIR = Path(__file__).parent.parent / "static" / "icons" / "extracted"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Icon glyphs to extract from Icons.ttf (status and menu icons from config.py)
ICON_GLYPHS = {
    "playing": "\u24df",      # Ⓟ
    "paused": "\u24e2",       # Ⓢ
    "idle": "\u24d8",         # Ⓘ
    "endless": "\u24d4",      # Ⓔ
    "artist": "\u24d0",       # Ⓐ
    "album": "\u24d1",        # Ⓑ
    "tracks": "\u24e3",       # Ⓣ
    "playlist": "\u24db",     # Ⓛ
    "favorite": "\u24bd",     # Ⓗ (lowercase h circled)
    "queue": "\u24e0",        # Ⓠ
    "settings": "\u24e2",     # Ⓢ
    "search": "\u24e2",       # Ⓢ
}

# Useful characters to extract from BMmini (navigation/UI icons)
BMMINI_GLYPHS = {
    "play": "\u25b6",         # ▶
    "pause": "\u23f8",        # ⏸
    "stop": "\u23f9",         # ⏹
    "next": "\u23ed",         # ⏭
    "prev": "\u23ee",         # ⏮
    "shuffle": "\u2928",      # ⤨
    "repeat": "\u21bb",       # ↻
    "heart": "\u2665",        # ♥
    "heart_empty": "\u2661",  # ♡
    "music_note": "\u266a",   # ♪
    "music_notes": "\u266b",  # ♫
    "folder": "\u25a1",       # □
    "file": "\u25a0",         # ■
    "arrow_right": "\u25b8",  # ▸
    "arrow_left": "\u25c2",   # ◂
    "arrow_up": "\u25b4",     # ▴
    "arrow_down": "\u25be",   # ▾
    "check": "\u2713",        # ✓
    "cross": "\u2717",        # ✗
    "star": "\u2605",         # ★
    "star_empty": "\u2606",   # ☆
    "gear": "\u2699",         # ⚙
    "volume_up": "\u25b2",    # ▲
    "volume_down": "\u25bc",  # ▼
    "user": "\u263a",         # ☺
    "lock": "\u2302",         # ⌂
}

# Title/header characters from Nintendo-DS-BIOS
DS_BIOS_GLYPHS = {
    "logo_p": "P",
    "logo_a": "A",
    "logo_e": "E",
    "logo_r": "R",
    "logo_j": "J",
    "logo_m": "M",
}

SIZES = [16, 24, 32, 48, 64]


def render_glyph(font_path: Path, char: str, name: str, prefix: str, sizes: list[int]):
    """Render a single glyph at multiple sizes and save as PNG."""
    for size in sizes:
        try:
            font = ImageFont.truetype(str(font_path), size)
        except Exception:
            continue

        # Measure the glyph
        bbox = font.getbbox(char)
        if not bbox or (bbox[2] - bbox[0]) == 0 or (bbox[3] - bbox[1]) == 0:
            continue

        w = bbox[2] - bbox[0] + 4
        h = bbox[3] - bbox[1] + 4

        # Render on transparent background
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((2 - bbox[0], 2 - bbox[1]), char, font=font, fill=(255, 255, 255, 255))

        out_path = OUTPUT_DIR / f"{prefix}_{name}_{size}.png"
        img.save(out_path)


def render_app_icons(font_path: Path):
    """Render PWA app icons using Nintendo-DS-BIOS font."""
    for icon_size in [192, 512]:
        font_size = int(icon_size * 0.4)
        try:
            font = ImageFont.truetype(str(font_path), font_size)
        except Exception:
            continue

        img = Image.new("RGBA", (icon_size, icon_size), (18, 18, 18, 255))
        draw = ImageDraw.Draw(img)

        text = "PJ"
        bbox = font.getbbox(text)
        if bbox:
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            x = (icon_size - tw) // 2 - bbox[0]
            y = (icon_size - th) // 2 - bbox[1]
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

        out_path = OUTPUT_DIR.parent / f"icon-{icon_size}.png"
        img.save(out_path)
        print(f"  PWA icon: {out_path.name}")


def main():
    fonts = {
        "icons": (ASSETS_DIR / "Icons.ttf", ICON_GLYPHS),
        "bmmini": (ASSETS_DIR / "BMmini.ttf", BMMINI_GLYPHS),
        "dsbios": (ASSETS_DIR / "Nintendo-DS-BIOS.ttf", DS_BIOS_GLYPHS),
    }

    total = 0
    for prefix, (font_path, glyphs) in fonts.items():
        if not font_path.exists():
            print(f"Warning: {font_path} not found, skipping")
            continue

        print(f"Extracting from {font_path.name}:")
        for name, char in glyphs.items():
            render_glyph(font_path, char, name, prefix, SIZES)
            total += 1
            print(f"  {name} ({char})")

    # Generate PWA app icons
    ds_font = ASSETS_DIR / "Nintendo-DS-BIOS.ttf"
    if ds_font.exists():
        print("Generating PWA app icons:")
        render_app_icons(ds_font)

    print(f"\nExtracted {total} glyphs at {len(SIZES)} sizes each")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
