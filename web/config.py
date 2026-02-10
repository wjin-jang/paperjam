"""PaperJam Web — Configuration."""

import os
import secrets
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Music library path (configurable via env)
MUSIC_PATH = Path(os.environ.get("PAPERJAM_MUSIC_PATH", str(Path.home() / "Music")))

# Database
DATABASE_URL = os.environ.get("PAPERJAM_DB_URL", f"sqlite:///{DATA_DIR / 'paperjam.db'}")
DB_PATH = DATA_DIR / "paperjam.db"

# Server
HOST = os.environ.get("PAPERJAM_HOST", "0.0.0.0")
PORT = int(os.environ.get("PAPERJAM_PORT", "8800"))

# Auth
SECRET_KEY = os.environ.get("PAPERJAM_SECRET_KEY", secrets.token_hex(32))
SESSION_EXPIRY_HOURS = 720  # 30 days
COOKIE_NAME = "paperjam_session"

# Transcoding
TRANSCODE_CACHE_DIR = DATA_DIR / "transcode_cache"
TRANSCODE_CACHE_DIR.mkdir(exist_ok=True)
COVER_CACHE_DIR = DATA_DIR / "cover_cache"
COVER_CACHE_DIR.mkdir(exist_ok=True)

# Streaming quality presets (kbps)
QUALITY_PRESETS = {
    "low": 128,
    "medium": 192,
    "high": 256,
    "extreme": 320,
    "original": 0,  # no transcoding
}
DEFAULT_QUALITY = "high"

# Library
VALID_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".opus", ".wma", ".aac"}
LIBRARY_CACHE_FILE = DATA_DIR / "library_cache.json"

# Cover art
COVER_SIZES = {"small": 128, "medium": 300, "large": 600}

# Version
VERSION = "2.0-web"
