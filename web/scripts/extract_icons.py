#!/usr/bin/env python3
"""Extract icon glyphs from BMmini and Nintendo-DS-BIOS fonts as PNGs.

Uses the actual codepoints present in each font (verified via fontTools cmap).
BMmini contains circled uppercase letters used as menu/status icons.
Nintendo-DS-BIOS contains circled letters used for status indicators.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
OUTPUT_DIR = Path(__file__).parent.parent / "static" / "icons" / "ui"


# BMmini circled letters (U+24xx) — used as menu/status icons in non-web version
# Plus star and useful ASCII symbols
BMMINI_GLYPHS = {
    # Circled letters (menu icons from config.py MENU_ICONS)
    "artist":       "\u24b6",  # Ⓐ
    "album":        "\u24b7",  # Ⓑ
    "folder":       "\u24bb",  # Ⓕ
    "heart":        "\u24bd",  # Ⓗ
    "playlist":     "\u24c1",  # Ⓛ
    "playing":      "\u24c5",  # Ⓟ
    "recent":       "\u24c7",  # Ⓡ
    "stopped":      "\u24c8",  # Ⓢ
    "tracks":       "\u24c9",  # Ⓣ
    # Star
    "star":         "\u2605",  # ★
    # ASCII symbols used as UI controls
    "gt":           ">",       # > (play / forward)
    "lt":           "<",       # < (back)
    "plus":         "+",       # + (add / volume up)
    "minus":        "-",       # - (volume down)
    "eq":           "=",       # = (menu / hamburger)
    "x":            "x",       # x (close)
    "bar":          "|",       # | (separator)
    "hash":         "#",       # # (number)
    "qmark":        "?",       # ? (help/search)
    "at":           "@",       # @ (user)
}

# Nintendo-DS-BIOS circled letters — used for status in non-web version
DS_BIOS_GLYPHS = {
    "idle":         "\u24be",  # Ⓘ
    "next":         "\u24c3",  # Ⓝ
    "playing":      "\u24c5",  # Ⓟ
    "recent":       "\u24c7",  # Ⓡ
    "stopped":      "\u24c8",  # Ⓢ
    "endless":      "\u24ca",  # Ⓤ
}

# Sizes to extract — 16px for inline icons, 24 for touch targets, 32 for album view
SIZES = [16, 24, 32]


def render_glyph(font_path: Path, char: str, name: str, prefix: str, sizes: list[int]):
    """Render a single glyph at multiple sizes and save as PNG."""
    rendered = []
    for size in sizes:
        try:
            font = ImageFont.truetype(str(font_path), size)
        except Exception:
            continue

        bbox = font.getbbox(char)
        if not bbox or (bbox[2] - bbox[0]) == 0 or (bbox[3] - bbox[1]) == 0:
            continue

        w = bbox[2] - bbox[0] + 4
        h = bbox[3] - bbox[1] + 4

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((2 - bbox[0], 2 - bbox[1]), char, font=font, fill=(255, 255, 255, 255))

        out_path = OUTPUT_DIR / f"{prefix}_{name}_{size}.png"
        img.save(out_path)
        rendered.append(size)

    return rendered


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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fonts = {
        "bm": (ASSETS_DIR / "BMmini.ttf", BMMINI_GLYPHS),
        "ds": (ASSETS_DIR / "Nintendo-DS-BIOS.ttf", DS_BIOS_GLYPHS),
    }

    total = 0
    for prefix, (font_path, glyphs) in fonts.items():
        if not font_path.exists():
            print(f"Warning: {font_path} not found, skipping")
            continue

        print(f"Extracting from {font_path.name}:")
        for name, char in glyphs.items():
            rendered = render_glyph(font_path, char, name, prefix, SIZES)
            if rendered:
                total += 1
                print(f"  {name} (U+{ord(char):04X}) -> {rendered}")
            else:
                print(f"  {name} (U+{ord(char):04X}) -> SKIPPED (not in font)")

    # Generate PWA app icons
    ds_font = ASSETS_DIR / "Nintendo-DS-BIOS.ttf"
    if ds_font.exists():
        print("Generating PWA app icons:")
        render_app_icons(ds_font)

    print(f"\nExtracted {total} glyphs at sizes {SIZES}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
