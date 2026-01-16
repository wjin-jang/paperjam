"""
Version information for PaperJam.

Provides VERSION constant and helper to get version date from git history.
Used by settings app to display current version info.
"""
import subprocess
import os

VERSION = "1.0"

def _get_version_date():
    try:
        # Get the directory of this file
        dir_path = os.path.dirname(os.path.abspath(__file__))
        # Get last commit date and time from git
        return subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M"],
            cwd=dir_path,
            encoding='utf-8',
            stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        # Fallback if git is not available or not a repo
        return "2026-01-15"

VERSION_DATE = _get_version_date()