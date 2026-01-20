"""
Configuration management for PaperJam.

This module serves as the central configuration hub for the entire application.
It loads user settings from ~/.config/paperjam/config.json and provides:

- Display dimensions and colors
- Font loading and padding configuration
- File paths (music library, data storage, cache)
- UI layout parameters (panel dimensions, row heights)
- Status and menu icons for the e-paper display
- Logging setup with file and console output

Configuration values are loaded at module import time and can be updated
at runtime via save_config(). Some values (like MUSIC_PATH) are computed
once at startup and require a restart to reflect changes.

Example:
    >>> from config import MUSIC_PATH, SCREEN_WIDTH
    >>> print(f"Music library: {MUSIC_PATH}")
    >>> print(f"Display width: {SCREEN_WIDTH}px")
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from PIL import ImageFont

logger = logging.getLogger(__name__)


# --- Logging ---
def setup_logger() -> logging.Logger:
    """Configure application-wide logging with file and console output.

    Creates a log file at ~/.cache/paperjam/paperjam.log and also outputs
    to stdout. Sets PIL and VLC loggers to WARNING level to reduce noise.

    Returns:
        The configured 'paperjam' logger instance.
    """
    log_dir = Path.home() / ".cache" / "paperjam"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "paperjam.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Quiet down noisy libraries to reduce log spam
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("vlc").setLevel(logging.WARNING)

    return logging.getLogger("paperjam")

# --- Defaults ---
# Default configuration values used when no user config exists or values are missing
DEFAULT_CONFIG: dict[str, Any] = {
    "music_path": str(Path.home() / "Music"),   # Root directory for music library
    "screensaver_timeout": 60,                   # Seconds of inactivity before screensaver (0 = disabled)
    "long_press_duration": 0.5,                  # Seconds to trigger long-press action
    "recents_limit": 50,                         # Maximum recently played tracks to remember
    "invert_colors": False,                      # Invert display colors (for e-paper visibility)
    "locale": "en",                              # UI language code
    "font_main": "BMmini.ttf",                   # Primary pixel font for menu items
    "font_header": "Nintendo-DS-BIOS.ttf",       # Header/title font
    "font_icons": "Icons.ttf"                    # Icon font for status indicators
}

# --- Paths ---
# User configuration directory (persistent across updates)
CONFIG_DIR: Path = Path.home() / ".config" / "paperjam"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"

# Application data directory (relative to working directory)
DATA_DIR: Path = Path("data")
PLAYLIST_DIR: Path = DATA_DIR / "playlists"
CACHE_FILE: Path = DATA_DIR / "library_cache.json"
RECENTS_FILE: Path = DATA_DIR / "recents.json"
FAVS_FILE: Path = DATA_DIR / "favorites.json"

# Ensure required directories exist at startup
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
PLAYLIST_DIR.mkdir(exist_ok=True)


# --- Load Config ---
def load_config() -> dict[str, Any]:
    """Load configuration from disk, merging with defaults.

    Reads user configuration from CONFIG_FILE and merges it with DEFAULT_CONFIG.
    Default values are used for any missing keys.

    Returns:
        Configuration dictionary with all settings.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()


# Module-level configuration state (loaded once at import)
_config: dict[str, Any] = load_config()


def save_config(updates: dict[str, Any]) -> None:
    """Save configuration updates to disk.

    Merges the provided updates into the current configuration and persists
    the entire config to CONFIG_FILE.

    Args:
        updates: Dictionary of configuration keys and values to update.
    """
    global _config
    _config.update(updates)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(_config, f, indent=4)
    except OSError as e:
        logger.error(f"Error saving config: {e}")

# --- Exported Constants ---
# Music library root path (created by welcome app if missing)
MUSIC_PATH: Path = Path(_config["music_path"])

# --- Volume Persistence ---
VOLUME_FILE: Path = DATA_DIR / "volume.json"
DEFAULT_VOLUME: int = 30  # Default volume level (0-100)

# User-configurable behavior settings
SCREENSAVER_TIMEOUT: int = _config["screensaver_timeout"]
LONG_PRESS_DURATION: float = _config["long_press_duration"]
RECENTS_LIMIT: int = _config["recents_limit"]

# --- Display ---
# Waveshare 2.13" e-paper display dimensions (landscape orientation)
SCREEN_WIDTH: int = 250
SCREEN_HEIGHT: int = 122

# Main content panel position and size (right side of screen)
PANEL_X: int = 100   # Panel left edge (leaves room for cover art on left)
PANEL_Y: int = 8     # Panel top margin
PANEL_W: int = 140   # Panel width
PANEL_H: int = 104   # Panel height
ROW_HEIGHT: int = 12 # Height of each menu row in pixels

# --- Colors ---
# E-paper uses 8-bit grayscale (0=black, 255=white)
WHITE: int = 255
BLACK: int = 0

# --- UI Layout Constants ---
# Standard spacing and margins (in pixels)
UI_MARGIN: int = 8                # Standard margin/padding around elements
UI_MARGIN_SMALL: int = 4          # Small margin for tight layouts
BORDER_WIDTH: int = 1             # Panel border thickness

# Scrollbar dimensions
SCROLLBAR_WIDTH: int = 8          # Width of scrollbar track
SCROLLBAR_MIN_HANDLE: int = 6     # Minimum scrollbar handle height
SCROLLBAR_MIN_PANEL_WIDTH: int = 20  # Minimum panel width to show scrollbar

# Album art panel (left side of music view)
# Size = COVER_SIZE_SMALL[0] + BORDER_WIDTH = 83 + 1 = 84
ART_PANEL_SIZE: int = 84
ART_PANEL_X: int = UI_MARGIN      # 8px from left edge
ART_PANEL_Y: int = UI_MARGIN      # 8px from top

# Status bar (below album art)
# Y position = ART_PANEL_Y + ART_PANEL_SIZE + UI_MARGIN = 8 + 84 + 8 = 100
STATUS_BAR_Y: int = ART_PANEL_Y + ART_PANEL_SIZE + UI_MARGIN
STATUS_BAR_WIDTH: int = ART_PANEL_SIZE
STATUS_BAR_HEIGHT: int = ROW_HEIGHT

# Screensaver track info panel
# X offset reserves space for track info panel (width 96 + margins)
TRACK_INFO_PANEL_WIDTH: int = 96
SCREENSAVER_PANEL_OFFSET: int = TRACK_INFO_PANEL_WIDTH + ROW_HEIGHT  # ~108

# Popup/overlay panel widths
MENU_PANEL_WIDTH: int = 160       # Standard menu panel width
CONTEXT_MENU_WIDTH: int = 120     # Context menu overlay width
CONTEXT_MENU_MAX_HEIGHT: int = 96 # Max height for context menu
MESSAGE_POPUP_WIDTH: int = 200    # Message popup width
LOADING_OVERLAY_WIDTH: int = 100  # Loading message width
IDLE_PANEL_WIDTH: int = 100       # Screensaver idle text panel
WELCOME_PANEL_WIDTH: int = 130    # Welcome dialog panel
POWER_OFF_TEXT_WIDTH: int = 48    # Shutdown text panel

# Confirm dialog dimensions
CONFIRM_POPUP_WIDTH: int = 160
CONFIRM_POPUP_HEIGHT: int = 80

# Loading popup dimensions
LOADING_POPUP_WIDTH: int = 140
LOADING_POPUP_HEIGHT: int = 50

# Popup timeouts (in seconds)
POPUP_DEFAULT_TIMEOUT: float = 2.0
VOLUME_POPUP_TIMEOUT: float = 1.5

# Battery indicator
BATTERY_ICON_STEPS: int = 8       # Number of battery level icons

# --- UI Behavior Constants ---
CONTROLS_BUTTON_COUNT: int = 4    # Buttons in controls bar (back, shuffle, loop, action)
ALPHABETICAL_HEADING_THRESHOLD: int = 24  # Min items before showing A-Z section headings
QUEUE_VIEW_MAX_ITEMS: int = 20    # Max items visible in queue view

# --- Cover Art ---
# Cover art dimensions for small (list) and large (now playing) views
COVER_SIZE_SMALL: tuple[int, int] = (83, 83)
COVER_SIZE_LARGE: tuple[int, int] = (113, 113)

# Cover art cache eviction settings (LRU-based cleanup)
COVER_CACHE_MAX_SIZE_MB: int = 100  # Trigger eviction when cache exceeds this size
COVER_CACHE_MAX_AGE_DAYS: int = 30  # Only evict entries older than this

# --- Behavior Options ---
# Available values for user-configurable settings (used in settings UI)
SCREENSAVER_OPTIONS: list[int] = [10, 30, 60, 300, 1800, 0]  # 0 = disabled
LONG_PRESS_OPTIONS: list[float] = [0.3, 0.5, 0.8, 1.0, 1.5, 2.0]
RECENTS_LIMIT_OPTIONS: list[int] = [10, 30, 50, 100]

# Supported audio file extensions (case-insensitive matching)
VALID_EXTS: set[str] = {'.mp3', '.flac', '.wav', '.m4a'}

# --- System Constants ---
# Battery level (%) below which device initiates safe shutdown
BATTERY_SHUTDOWN_THRESHOLD: int = 12

# --- Fonts ---
def load_fonts() -> tuple[ImageFont.FreeTypeFont, ...]:
    """Load all application fonts from the assets directory.

    Loads pixel fonts with BASIC layout engine (no HarfBuzz) for consistent
    rendering on e-paper displays. Falls back to PIL default font if assets
    are missing.

    Returns:
        Tuple of (main, header, icons, cjk_main, cjk_header) font objects.
    """
    base_path = Path(__file__).parent / "assets"

    def get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
        """Load a font file or fall back to default."""
        path = base_path / name
        if not path.exists():
            return ImageFont.load_default()
        # Use BASIC layout engine (no HarfBuzz) for pixel-perfect rendering
        return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.BASIC)

    main = get_font(_config.get("font_main", "BMmini.ttf"), 10)
    header = get_font(_config.get("font_header", "Nintendo-DS-BIOS.ttf"), 13)

    # CJK fonts (Galmuri family) for Chinese/Japanese/Korean text
    cjk_main = get_font("Galmuri7.ttf", 8)
    cjk_header = get_font("Galmuri9.ttf", 10)

    # Icon font for status indicators and menu icons
    icons_path = base_path / _config.get("font_icons", "Icons.ttf")
    icons = (
        ImageFont.truetype(str(icons_path), 6, layout_engine=ImageFont.Layout.BASIC)
        if icons_path.exists() else None
    )

    return main, header, icons, cjk_main, cjk_header


# Load fonts at module import time
FONT_MAIN, FONT_HEADER, FONT_ICONS, FONT_CJK_MAIN, FONT_CJK_HEADER = load_fonts()


# --- Font Padding ---
# Pixel offset (x, y) applied to text rendering for each font to correct baseline alignment.
# These values compensate for font metrics that don't render well at small sizes.
FONT_PADDING: dict[ImageFont.FreeTypeFont, tuple[int, int]] = {}


def _init_font_padding() -> None:
    """Initialize font padding map after fonts are loaded."""
    global FONT_PADDING
    FONT_PADDING = {
        FONT_MAIN: (5, 1),       # BMmini needs slight right/down offset
        FONT_HEADER: (2, -1),    # Nintendo DS BIOS needs slight up offset
        FONT_CJK_MAIN: (5, 3),   # Galmuri7 needs more vertical offset
        FONT_CJK_HEADER: (2, 1), # Galmuri9 needs slight adjustments
    }


_init_font_padding()

# --- Status Icons ---
STATUS_ICONS = {
    'player.status.playing': 'Ⓟ',
    'player.status.paused': 'Ⓢ',
    'player.status.idle': 'Ⓘ',
    'player.status.next': 'Ⓝ',
    'player.status.previous': 'Ⓡ',
    'player.status.shuffle_on': 'Ⓘ',
    'player.status.shuffle_off': 'Ⓘ',
    'player.status.loop_all': 'Ⓘ',
    'player.status.loop_one': 'Ⓘ',
    'player.status.loop_off': 'Ⓘ',
    'player.status.endless': 'Ⓔ',
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

# --- Version ---
import os
import subprocess

VERSION: str = "1.0"
NEEDS_RESCAN: bool = False  # Set True when update requires library rescan


def _get_version_date() -> str:
    """Get the date of the most recent git commit.

    Used to display version info in the settings/about screen.
    Falls back to a hardcoded date if git is unavailable.

    Returns:
        Date string in 'YYYY-MM-DD HH:MM' format.
    """
    try:
        dir_path = os.path.dirname(os.path.abspath(__file__))
        return subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M"],
            cwd=dir_path,
            encoding='utf-8',
            stderr=subprocess.DEVNULL,
            timeout=5
        ).strip()
    except (subprocess.SubprocessError, OSError):
        return "2026-01-15"


VERSION_DATE: str = _get_version_date()