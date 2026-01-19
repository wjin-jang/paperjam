"""
Generate small weather icons (10x10) for weekly forecast.
Run this script to create the PNG icon files.
"""
from PIL import Image, ImageDraw
import os

ICON_SIZE = 10
WHITE = 255
BLACK = 0

# Create small directory
os.makedirs("small", exist_ok=True)


def create_icon():
    """Create a blank icon canvas."""
    img = Image.new('1', (ICON_SIZE, ICON_SIZE), WHITE)
    return img, ImageDraw.Draw(img)


def save_icon(img, name):
    """Save icon to small directory."""
    img.save(f"small/{name}.png")
    print(f"Created small/{name}.png")


# Clear/Sunny - Simple sun
img, draw = create_icon()
draw.ellipse((2, 2, 7, 7), fill=BLACK)
draw.point((0, 4), fill=BLACK)
draw.point((9, 4), fill=BLACK)
draw.point((4, 0), fill=BLACK)
draw.point((4, 9), fill=BLACK)
save_icon(img, "clear")

# Partly Cloudy - Sun with cloud
img, draw = create_icon()
draw.ellipse((1, 1, 5, 5), fill=BLACK)
draw.ellipse((3, 5, 9, 9), fill=WHITE, outline=BLACK)
save_icon(img, "partly_cloudy")

# Cloudy/Overcast - Cloud
img, draw = create_icon()
draw.ellipse((0, 4, 5, 9), fill=WHITE, outline=BLACK)
draw.ellipse((3, 2, 9, 8), fill=WHITE, outline=BLACK)
save_icon(img, "cloudy")

# Rain - Cloud with drops
img, draw = create_icon()
draw.ellipse((1, 1, 6, 5), fill=WHITE, outline=BLACK)
draw.ellipse((4, 0, 9, 4), fill=WHITE, outline=BLACK)
draw.line((2, 6, 2, 9), fill=BLACK)
draw.line((5, 6, 5, 9), fill=BLACK)
draw.line((8, 6, 8, 9), fill=BLACK)
save_icon(img, "rain")

# Heavy Rain - Cloud with more drops
img, draw = create_icon()
draw.ellipse((1, 0, 6, 4), fill=WHITE, outline=BLACK)
draw.ellipse((4, 0, 9, 3), fill=WHITE, outline=BLACK)
draw.line((2, 5, 2, 9), fill=BLACK)
draw.line((4, 5, 4, 9), fill=BLACK)
draw.line((6, 5, 6, 9), fill=BLACK)
draw.line((8, 5, 8, 9), fill=BLACK)
save_icon(img, "heavy_rain")

# Snow - Cloud with dots
img, draw = create_icon()
draw.ellipse((1, 1, 6, 5), fill=WHITE, outline=BLACK)
draw.ellipse((4, 0, 9, 4), fill=WHITE, outline=BLACK)
draw.point((2, 7), fill=BLACK)
draw.point((5, 8), fill=BLACK)
draw.point((8, 7), fill=BLACK)
draw.point((3, 9), fill=BLACK)
draw.point((7, 9), fill=BLACK)
save_icon(img, "snow")

# Thunderstorm - Cloud with lightning
img, draw = create_icon()
draw.ellipse((0, 0, 5, 4), fill=WHITE, outline=BLACK)
draw.ellipse((3, 0, 8, 3), fill=WHITE, outline=BLACK)
draw.polygon([(5, 4), (4, 6), (5, 6), (3, 9), (6, 6), (5, 6)], fill=BLACK)
save_icon(img, "thunderstorm")

# Fog - Horizontal lines
img, draw = create_icon()
draw.line((1, 2, 8, 2), fill=BLACK)
draw.line((0, 4, 9, 4), fill=BLACK)
draw.line((1, 6, 8, 6), fill=BLACK)
draw.line((2, 8, 7, 8), fill=BLACK)
save_icon(img, "fog")

# Drizzle - Cloud with dots
img, draw = create_icon()
draw.ellipse((1, 1, 6, 5), fill=WHITE, outline=BLACK)
draw.ellipse((4, 0, 9, 4), fill=WHITE, outline=BLACK)
draw.point((2, 7), fill=BLACK)
draw.point((5, 8), fill=BLACK)
draw.point((8, 7), fill=BLACK)
save_icon(img, "drizzle")

# Unknown - Question mark
img, draw = create_icon()
draw.arc((2, 1, 7, 6), 180, 0, fill=BLACK)
draw.line((6, 4, 5, 6), fill=BLACK)
draw.point((5, 8), fill=BLACK)
save_icon(img, "unknown")

print("All small weather icons generated!")
