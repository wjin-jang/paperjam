"""
Logging configuration for PaperJam.

Logs to both file (~/.cache/paperjam/paperjam.log) and stdout.
File logs are limited to 1MB with 3 backup rotations.
"""
import logging
import sys
from pathlib import Path
import config as cfg

def setup_logger():
    """Configure logging for the application."""
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
    
    # Quiet down some noisy libraries
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("vlc").setLevel(logging.WARNING)
    
    return logging.getLogger("paperjam")
