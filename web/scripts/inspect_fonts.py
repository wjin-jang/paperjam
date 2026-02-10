#!/usr/bin/env python3
"""Inspect which codepoints are available in each font."""
from pathlib import Path
from fontTools.ttLib import TTFont

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"

for font_name in ["BMmini.ttf", "Nintendo-DS-BIOS.ttf", "Icons.ttf"]:
    font_path = ASSETS_DIR / font_name
    if not font_path.exists():
        print(f"--- {font_name}: NOT FOUND ---")
        continue

    tt = TTFont(str(font_path))
    cmap = tt.getBestCmap()
    if not cmap:
        print(f"--- {font_name}: NO CMAP ---")
        continue

    print(f"\n--- {font_name} ({len(cmap)} glyphs) ---")
    for cp in sorted(cmap.keys()):
        ch = chr(cp)
        # Show printable repr
        if 0x20 <= cp <= 0x7E:
            label = ch
        else:
            label = repr(ch)
        glyph_name = cmap[cp]
        print(f"  U+{cp:04X}  {label}  -> {glyph_name}".encode("ascii", "replace").decode())
