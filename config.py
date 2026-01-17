"""
Configuration management for PaperJam.

Loads settings from ~/.config/paperjam/config.json with sensible defaults.
Provides global constants for:
- Display dimensions and colors
- Font loading
- File paths (music, data, cache)
- UI layout parameters
- Status and menu icons
"""
import json
import logging
import os
from pathlib import Path
from PIL import ImageFont

logger = logging.getLogger(__name__)

# --- Defaults ---
DEFAULT_CONFIG = {
    "music_path": str(Path.home() / "Music"),
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
            logger.error(f"Error loading config: {e}")
    return DEFAULT_CONFIG

_config = load_config()

def save_config(updates):
    global _config
    _config.update(updates)
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(_config, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving config: {e}")

# --- Exported Constants ---
MUSIC_PATH = Path(_config["music_path"])
# Note: Music directory is created in welcome app if it doesn't exist

# --- Volume Persistence ---
VOLUME_FILE = DATA_DIR / "volume.json"
DEFAULT_VOLUME = 30

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

# --- UI Constants ---
CONTROLS_BUTTON_COUNT = 4  # Number of buttons in controls bar (back, shuffle, loop, action)
ALPHABETICAL_HEADING_THRESHOLD = 24  # Min items before showing alphabetical headings
QUEUE_VIEW_MAX_ITEMS = 20  # Max items to show in queue view

# --- Behavior ---
SCREENSAVER_OPTIONS = [10, 30, 60, 300, 1800, 0] 
LONG_PRESS_OPTIONS = [0.3, 0.5, 0.8, 1.0, 1.5, 2.0]
RECENTS_LIMIT_OPTIONS = [10, 30, 50, 100]
VALID_EXTS = {'.mp3', '.flac', '.wav', '.m4a'}

# --- Sys Constants ---
BATTERY_SHUTDOWN_THRESHOLD = 12

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