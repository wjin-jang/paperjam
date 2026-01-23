#!/usr/bin/env python3
"""
PaperJam Bare-Metal OS - Bitmap Font Compiler

Converts TTF/OTF fonts to C header files for embedded use.
Generates 1-bit bitmap fonts suitable for e-paper display.

Usage:
    python mkfont.py <input.ttf> <size> <output.h> [--chars RANGE]

Example:
    python mkfont.py DejaVuSans.ttf 8 font_8x8.h --chars 32-126
"""

import argparse
import sys

try:
    from PIL import Image, ImageFont, ImageDraw
except ImportError:
    print("Error: Pillow library required. Install with: pip install Pillow")
    sys.exit(1)


def render_char(font, char, size):
    """Render a single character to a 1-bit bitmap."""
    # Create image slightly larger than needed
    img = Image.new('1', (size * 2, size * 2), color=1)
    draw = ImageDraw.Draw(img)

    # Draw character
    draw.text((0, 0), char, font=font, fill=0)

    # Get bounding box
    bbox = img.getbbox()
    if bbox is None:
        # Empty character (space)
        return bytes(size), size, size

    # Crop to character
    char_img = img.crop((0, 0, size, size))

    # Convert to bytes (MSB first within each byte)
    width = size
    height = size
    data = []

    for y in range(height):
        byte = 0
        for x in range(width):
            if x % 8 == 0 and x > 0:
                data.append(byte)
                byte = 0
            pixel = char_img.getpixel((x, y))
            if pixel == 0:  # Black pixel
                byte |= (0x80 >> (x % 8))
        data.append(byte)

    return bytes(data), width, height


def generate_font(ttf_path, size, first_char=32, last_char=126):
    """Generate font data from TTF file."""
    try:
        font = ImageFont.truetype(ttf_path, size)
    except IOError:
        print(f"Error: Cannot load font file: {ttf_path}")
        sys.exit(1)

    chars = []
    for code in range(first_char, last_char + 1):
        char = chr(code)
        data, width, height = render_char(font, char, size)
        chars.append({
            'code': code,
            'char': char if code >= 32 else '?',
            'data': data,
            'width': width,
            'height': height
        })

    return chars


def write_header(chars, output_path, name="custom_font"):
    """Write font data as C header file."""
    if not chars:
        print("Error: No characters to output")
        return

    first_code = chars[0]['code']
    last_code = chars[-1]['code']
    width = chars[0]['width']
    height = chars[0]['height']
    bytes_per_char = len(chars[0]['data'])

    with open(output_path, 'w') as f:
        f.write(f"/* Auto-generated bitmap font */\n")
        f.write(f"/* Characters {first_code}-{last_code}, {width}x{height} pixels */\n\n")
        f.write(f"#ifndef {name.upper()}_H\n")
        f.write(f"#define {name.upper()}_H\n\n")
        f.write(f"#include <stdint.h>\n\n")

        # Font data array
        f.write(f"static const uint8_t {name}_data[] = {{\n")

        for char_info in chars:
            char = char_info['char']
            if char == '\\':
                char = '\\\\'
            elif char == "'":
                char = "\\'"
            f.write(f"    /* '{char}' ({char_info['code']}) */\n    ")

            for i, byte in enumerate(char_info['data']):
                f.write(f"0x{byte:02X}, ")
                if (i + 1) % 8 == 0:
                    f.write("\n    ")
            f.write("\n")

        f.write("};\n\n")

        # Font structure
        f.write(f"static const font_t {name} = {{\n")
        f.write(f"    .data = {name}_data,\n")
        f.write(f"    .char_width = {width},\n")
        f.write(f"    .char_height = {height},\n")
        f.write(f"    .first_char = {first_code},\n")
        f.write(f"    .last_char = {last_code},\n")
        f.write(f"    .bytes_per_char = {bytes_per_char}\n")
        f.write(f"}};\n\n")

        f.write(f"#endif /* {name.upper()}_H */\n")

    print(f"Generated {output_path}")
    print(f"  Characters: {first_code}-{last_code} ({last_code - first_code + 1} chars)")
    print(f"  Size: {width}x{height} pixels")
    print(f"  Data size: {len(chars) * bytes_per_char} bytes")


def main():
    parser = argparse.ArgumentParser(description='Compile TTF font to C header')
    parser.add_argument('input', help='Input TTF/OTF font file')
    parser.add_argument('size', type=int, help='Font size in pixels')
    parser.add_argument('output', help='Output C header file')
    parser.add_argument('--chars', default='32-126',
                       help='Character range (default: 32-126 for ASCII)')
    parser.add_argument('--name', default='custom_font',
                       help='Font variable name in C code')

    args = parser.parse_args()

    # Parse character range
    if '-' in args.chars:
        first, last = args.chars.split('-')
        first_char = int(first)
        last_char = int(last)
    else:
        first_char = last_char = int(args.chars)

    # Generate font
    chars = generate_font(args.input, args.size, first_char, last_char)

    # Write header
    write_header(chars, args.output, args.name)


if __name__ == '__main__':
    main()
