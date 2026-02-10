"""PaperJam Web — Database models and initialization."""

import sqlite3
import time
import secrets
import bcrypt
from pathlib import Path
from contextlib import contextmanager

from config import DB_PATH, SESSION_EXPIRY_HOURS


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database schema."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at REAL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at REAL DEFAULT (unixepoch()),
                expires_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                item_type TEXT NOT NULL CHECK(item_type IN ('track', 'album', 'artist')),
                item_key TEXT NOT NULL,
                created_at REAL DEFAULT (unixepoch()),
                UNIQUE(user_id, item_type, item_key)
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at REAL DEFAULT (unixepoch()),
                updated_at REAL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                track_path TEXT NOT NULL,
                position INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY(user_id, key)
            );

            CREATE TABLE IF NOT EXISTS recents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                track_path TEXT NOT NULL,
                played_at REAL DEFAULT (unixepoch())
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);
            CREATE INDEX IF NOT EXISTS idx_playlists_user ON playlists(user_id);
            CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist ON playlist_tracks(playlist_id);
            CREATE INDEX IF NOT EXISTS idx_recents_user ON recents(user_id, played_at DESC);
        """)


def create_default_admin():
    """Create default admin user if no users exist."""
    with get_db() as db:
        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            password_hash = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()
            db.execute(
                "INSERT INTO users (username, display_name, password_hash, is_admin) VALUES (?, ?, ?, 1)",
                ("admin", "Administrator", password_hash),
            )
            print("Created default admin user: admin / admin")
            print("** Change this password immediately! **")


# --- User operations ---

def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_username(username: str) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_user(username: str, display_name: str, password: str, is_admin: bool = False) -> int:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO users (username, display_name, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            (username, display_name, password_hash, int(is_admin)),
        )
        return cursor.lastrowid


def update_user(user_id: int, **kwargs):
    allowed = {"display_name", "is_admin"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if "password" in kwargs:
        updates["password_hash"] = bcrypt.hashpw(kwargs["password"].encode(), bcrypt.gensalt()).decode()
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]
    with get_db() as db:
        db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)


def delete_user(user_id: int):
    with get_db() as db:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))


def list_users() -> list[dict]:
    with get_db() as db:
        rows = db.execute("SELECT id, username, display_name, is_admin, created_at FROM users ORDER BY id").fetchall()
        return [dict(r) for r in rows]


# --- Session operations ---

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = time.time() + (SESSION_EXPIRY_HOURS * 3600)
    with get_db() as db:
        db.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
    return token


def validate_session(token: str) -> dict | None:
    if not token:
        return None
    with get_db() as db:
        row = db.execute(
            """SELECT s.user_id, u.username, u.display_name, u.is_admin
               FROM sessions s JOIN users u ON s.user_id = u.id
               WHERE s.token = ? AND s.expires_at > ?""",
            (token, time.time()),
        ).fetchone()
        return dict(row) if row else None


def delete_session(token: str):
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))


def cleanup_sessions():
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))


# --- Favorites operations ---

def get_favorites(user_id: int, item_type: str = None) -> list[dict]:
    with get_db() as db:
        if item_type:
            rows = db.execute(
                "SELECT * FROM favorites WHERE user_id = ? AND item_type = ? ORDER BY created_at DESC",
                (user_id, item_type),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM favorites WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def toggle_favorite(user_id: int, item_type: str, item_key: str) -> bool:
    """Toggle favorite. Returns True if added, False if removed."""
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM favorites WHERE user_id = ? AND item_type = ? AND item_key = ?",
            (user_id, item_type, item_key),
        ).fetchone()
        if existing:
            db.execute("DELETE FROM favorites WHERE id = ?", (existing[0],))
            return False
        else:
            db.execute(
                "INSERT INTO favorites (user_id, item_type, item_key) VALUES (?, ?, ?)",
                (user_id, item_type, item_key),
            )
            return True


def is_favorite(user_id: int, item_type: str, item_key: str) -> bool:
    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND item_type = ? AND item_key = ?",
            (user_id, item_type, item_key),
        ).fetchone()
        return row is not None


# --- Playlist operations ---

def get_playlists(user_id: int) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            """SELECT p.*, COUNT(pt.id) as track_count
               FROM playlists p LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
               WHERE p.user_id = ? GROUP BY p.id ORDER BY p.updated_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def create_playlist(user_id: int, name: str) -> int:
    with get_db() as db:
        cursor = db.execute(
            "INSERT INTO playlists (user_id, name) VALUES (?, ?)",
            (user_id, name),
        )
        return cursor.lastrowid


def delete_playlist(playlist_id: int, user_id: int):
    with get_db() as db:
        db.execute("DELETE FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, user_id))


def rename_playlist(playlist_id: int, user_id: int, name: str):
    with get_db() as db:
        db.execute(
            "UPDATE playlists SET name = ?, updated_at = unixepoch() WHERE id = ? AND user_id = ?",
            (name, playlist_id, user_id),
        )


def get_playlist_tracks(playlist_id: int, user_id: int) -> list[dict]:
    with get_db() as db:
        # Verify ownership
        owner = db.execute("SELECT user_id FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
        if not owner or owner[0] != user_id:
            return []
        rows = db.execute(
            "SELECT * FROM playlist_tracks WHERE playlist_id = ? ORDER BY position",
            (playlist_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_track_to_playlist(playlist_id: int, user_id: int, track_path: str):
    with get_db() as db:
        owner = db.execute("SELECT user_id FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
        if not owner or owner[0] != user_id:
            return
        max_pos = db.execute(
            "SELECT COALESCE(MAX(position), -1) FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO playlist_tracks (playlist_id, track_path, position) VALUES (?, ?, ?)",
            (playlist_id, track_path, max_pos + 1),
        )
        db.execute("UPDATE playlists SET updated_at = unixepoch() WHERE id = ?", (playlist_id,))


def remove_track_from_playlist(playlist_id: int, user_id: int, track_id: int):
    with get_db() as db:
        owner = db.execute("SELECT user_id FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
        if not owner or owner[0] != user_id:
            return
        db.execute("DELETE FROM playlist_tracks WHERE id = ? AND playlist_id = ?", (track_id, playlist_id))


# --- Recents operations ---

def add_recent(user_id: int, track_path: str, limit: int = 50):
    with get_db() as db:
        db.execute(
            "INSERT INTO recents (user_id, track_path) VALUES (?, ?)",
            (user_id, track_path),
        )
        # Trim to limit
        db.execute(
            """DELETE FROM recents WHERE id NOT IN (
                SELECT id FROM recents WHERE user_id = ? ORDER BY played_at DESC LIMIT ?
            ) AND user_id = ?""",
            (user_id, limit, user_id),
        )


def get_recents(user_id: int, limit: int = 50) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM recents WHERE user_id = ? ORDER BY played_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# --- User settings operations ---

DEFAULT_SETTINGS = {
    "streaming_quality": "high",
    "locale": "en",
    "theme": "dark",
    "recents_limit": "50",
}


def get_user_settings(user_id: int) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    with get_db() as db:
        rows = db.execute("SELECT key, value FROM user_settings WHERE user_id = ?", (user_id,)).fetchall()
        for row in rows:
            settings[row["key"]] = row["value"]
    return settings


def set_user_setting(user_id: int, key: str, value: str):
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO user_settings (user_id, key, value) VALUES (?, ?, ?)",
            (user_id, key, value),
        )
