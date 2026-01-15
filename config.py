import json
import os
from pathlib import Path
from PIL import ImageFont

# --- Defaults ---
DEFAULT_CONFIG = {
    "music_path": str(Path.home() / "music"),
    "screensaver_timeout": 60,
    "long_press_duration": 0.5,
    "recents_limit": 50,
    "invert_colors": False,
    "font_main": "BMmini.ttf",
    "font_header": "Nintendo-DS-BIOS.ttf",
    "font_icons": "Icons.ttf"
}

# --- Paths ---
CONFIG_DIR = Path.home() / ".config" / "paperjam"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR = Path("data")
PLAYLIST_DIR = DATA_DIR / "playlists"
CACHE_FILE = DATA_DIR / "library_cache.json"
RECENTS_FILE = DATA_DIR / "recents.json"
FAVS_FILE = DATA_DIR / "favorites.json"

# Create directories
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
PLAYLIST_DIR.mkdir(exist_ok=True)

# --- Load Config ---
def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG

_config = load_config()

def save_config(updates):
    global _config
    _config.update(updates)
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(_config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

# --- Exported Constants ---
MUSIC_PATH = Path(_config["music_path"])
if not MUSIC_PATH.exists():
    MUSIC_PATH = Path.cwd()

SCREENSAVER_TIMEOUT = _config["screensaver_timeout"]
LONG_PRESS_DURATION = _config["long_press_duration"]
RECENTS_LIMIT = _config["recents_limit"]

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
SCREENSAVER_OPTIONS = [10, 30, 60, 300, 1800, 0] 
LONG_PRESS_OPTIONS = [0.3, 0.5, 0.8, 1.0, 1.5, 2.0]
RECENTS_LIMIT_OPTIONS = [10, 30, 50, 100]
VALID_EXTS = {'.mp3', '.flac', '.wav', '.m4a'}

# --- Fonts ---
def load_fonts():
    base_path = Path(__file__).parent / "assets"
    
    def get_font(name, size):
        path = base_path / name
        return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()

    main = get_font(_config.get("font_main", "BMmini.ttf"), 9)
    header = get_font(_config.get("font_header", "Nintendo-DS-BIOS.ttf"), 12)
    
    icons_path = base_path / _config.get("font_icons", "Icons.ttf")
    icons = ImageFont.truetype(str(icons_path), 6) if icons_path.exists() else None
    
    return main, header, icons

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