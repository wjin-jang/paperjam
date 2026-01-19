"""
Generate weather icons for the e-ink display.
Run this script to create the PNG icon files.
"""
from PIL import Image, ImageDraw

ICON_SIZE = 16
WHITE = 255
BLACK = 0


def create_icon():
    """Create a blank icon canvas."""
    img = Image.new('1', (ICON_SIZE, ICON_SIZE), WHITE)
    return img, ImageDraw.Draw(img)


def save_icon(img, name):
    """Save icon to file."""
    img.save(f"{name}.png")
    print(f"Created {name}.png")


# Clear/Sunny - Simple sun
img, draw = create_icon()
draw.ellipse((4, 4, 12, 12), fill=BLACK)
# Sun rays
for i in range(0, 16, 4):
    draw.point((i, 8), fill=BLACK)
    draw.point((8, i), fill=BLACK)
save_icon(img, "clear")

# Partly Cloudy - Sun with cloud
img, draw = create_icon()
draw.ellipse((2, 2, 8, 8), fill=BLACK)  # Small sun
draw.ellipse((5, 7, 15, 14), fill=WHITE, outline=BLACK)  # Cloud outline
save_icon(img, "partly_cloudy")

# Cloudy/Overcast - Cloud
img, draw = create_icon()
draw.ellipse((1, 6, 9, 13), fill=WHITE, outline=BLACK)
draw.ellipse((5, 4, 15, 12), fill=WHITE, outline=BLACK)
save_icon(img, "cloudy")

# Rain - Cloud with drops
img, draw = create_icon()
draw.ellipse((2, 2, 10, 8), fill=WHITE, outline=BLACK)
draw.ellipse((6, 1, 14, 7), fill=WHITE, outline=BLACK)
# Rain drops
draw.line((4, 10, 4, 14), fill=BLACK)
draw.line((8, 10, 8, 14), fill=BLACK)
draw.line((12, 10, 12, 14), fill=BLACK)
save_icon(img, "rain")

# Heavy Rain - Cloud with more drops
img, draw = create_icon()
draw.ellipse((2, 1, 10, 6), fill=WHITE, outline=BLACK)
draw.ellipse((6, 0, 14, 5), fill=WHITE, outline=BLACK)
# Rain drops (more)
draw.line((3, 8, 3, 12), fill=BLACK)
draw.line((6, 8, 6, 15), fill=BLACK)
draw.line((9, 8, 9, 13), fill=BLACK)
draw.line((12, 8, 12, 15), fill=BLACK)
save_icon(img, "heavy_rain")

# Snow - Cloud with snowflakes
img, draw = create_icon()
draw.ellipse((2, 2, 10, 8), fill=WHITE, outline=BLACK)
draw.ellipse((6, 1, 14, 7), fill=WHITE, outline=BLACK)
# Snowflakes (asterisks)
draw.point((4, 11), fill=BLACK)
draw.point((8, 13), fill=BLACK)
draw.point((12, 11), fill=BLACK)
draw.point((6, 14), fill=BLACK)
draw.point((10, 14), fill=BLACK)
save_icon(img, "snow")

# Thunderstorm - Cloud with lightning
img, draw = create_icon()
draw.ellipse((1, 1, 9, 6), fill=WHITE, outline=BLACK)
draw.ellipse((5, 0, 13, 5), fill=WHITE, outline=BLACK)
# Lightning bolt
draw.polygon([(8, 7), (6, 11), (8, 11), (6, 15), (10, 10), (8, 10)], fill=BLACK)
save_icon(img, "thunderstorm")

# Fog - Horizontal lines
img, draw = create_icon()
draw.line((2, 4, 14, 4), fill=BLACK)
draw.line((1, 7, 15, 7), fill=BLACK)
draw.line((2, 10, 14, 10), fill=BLACK)
draw.line((3, 13, 13, 13), fill=BLACK)
save_icon(img, "fog")

# Drizzle - Cloud with dots
img, draw = create_icon()
draw.ellipse((2, 2, 10, 8), fill=WHITE, outline=BLACK)
draw.ellipse((6, 1, 14, 7), fill=WHITE, outline=BLACK)
# Light drops (dots)
draw.point((4, 11), fill=BLACK)
draw.point((8, 12), fill=BLACK)
draw.point((12, 11), fill=BLACK)
draw.point((6, 14), fill=BLACK)
draw.point((10, 13), fill=BLACK)
save_icon(img, "drizzle")

# Unknown - Question mark
img, draw = create_icon()
draw.arc((4, 2, 12, 10), 180, 0, fill=BLACK)
draw.line((10, 6, 8, 9), fill=BLACK)
draw.point((8, 12), fill=BLACK)
save_icon(img, "unknown")

print("All weather icons generated!")
