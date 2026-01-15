import os
from pathlib import Path
from PIL import ImageFont

# --- Display ---
SCREEN_WIDTH = 250
SCREEN_HEIGHT = 122
PANEL_X = 100
PANEL_Y = 8
PANEL_W = 140
PANEL_H = 104
ROW_HEIGHT = 12

# --- Colors ---
WHITE = 255
BLACK = 0

# --- Behavior ---
SCREENSAVER_TIMEOUT = 60 
SCREENSAVER_OPTIONS = [10, 30, 60, 300, 1800, 0] 

LONG_PRESS_DURATION = 0.5
LONG_PRESS_OPTIONS = [0.3, 0.5, 0.8, 1.0, 1.5, 2.0]

RECENTS_LIMIT = 50
RECENTS_LIMIT_OPTIONS = [10, 30, 50, 100]

# --- Paths ---
MUSIC_PATH = Path("/home/yourusername/music")
if not MUSIC_PATH.exists():
    MUSIC_PATH = Path.cwd()

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CACHE_FILE = DATA_DIR / "library_cache.json"
RECENTS_FILE = DATA_DIR / "recents.json"
FAVS_FILE = DATA_DIR / "favorites.json"
PLAYLIST_DIR = DATA_DIR / "playlists"
PLAYLIST_DIR.mkdir(exist_ok=True)

VALID_EXTS = {'.mp3', '.flac', '.wav', '.m4a'}

# --- Fonts ---
def load_fonts():
    base_path = Path(__file__).parent / "assets"
    try:
        main = ImageFont.truetype(str(base_path / "BMmini.ttf"), 9) if (base_path / "BMmini.ttf").exists() else ImageFont.load_default()
        header = ImageFont.truetype(str(base_path / "Nintendo-DS-BIOS.ttf"), 12) if (base_path / "Nintendo-DS-BIOS.ttf").exists() else ImageFont.load_default()
        # Icons font includes battery (0-8, C), headphones (H), bluetooth (B), wifi (W)
        icons_path = base_path / "Icons.ttf"
        icons = ImageFont.truetype(str(icons_path), 6) if icons_path.exists() else None
        return main, header, icons
    except:
        return ImageFont.load_default(), ImageFont.load_default(), None

FONT_MAIN, FONT_HEADER, FONT_ICONS = load_fonts()
NEEDS_RESCAN = False

# --- Status Icons ---
STATUS_ICONS = {
    'PLAYING': 'Ⓟ',
    'PAUSED': 'Ⓢ',
    'IDLE': 'Ⓘ',
    'NEXT': 'Ⓝ',
    'PREVIOUS': 'Ⓡ',
    'SHUFFLE ON': 'Ⓘ',
    'SHUFFLE OFF': 'Ⓘ',
    'LOOP ALL': 'Ⓘ',
    'LOOP ONE': 'Ⓘ',
    'LOOP OFF': 'Ⓘ',
    'ENDLESS': 'Ⓔ',
}

# --- Menu Icons ---
MENU_ICONS = {
    'artist': 'Ⓐ',
    'album': 'Ⓑ',
    'tracks': 'Ⓣ',
    'playlist': 'Ⓛ',
    'fav': 'Ⓗ',
    'recent': 'Ⓡ',
    'dir': 'Ⓕ',
    'playing': 'Ⓟ',
    'paused': 'Ⓢ'
}
