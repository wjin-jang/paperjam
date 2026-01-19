"""
Playlist and queue management for the music player.
"""
import random
import threading
import json
from collections import deque
from pathlib import Path
from typing import List, Optional, Callable

import config as cfg
from ui.graphics import get_cover
from config import setup_logger

logger = setup_logger()

class PlaylistManager:
    """Manages playback queue and playlist operations."""

    def __init__(self, on_track_change: Optional[Callable] = None):
        """
        Initialize playlist manager.

        Args:
            on_track_change: Callback when track changes, receives (path, covers)
        """
        self._lock = threading.Lock()  # Lock for thread-safe queue operations
        self.playlist_source: List[str] = []
        self.queue: List[int] = []
        self.queue_idx: int = 0
        self.manual_queue: deque = deque()  # Queue for manually added tracks
        self.shuffle_active: bool = False
        self.loop_mode: int = 0  # 0=off, 1=all, 2=one
        self._on_track_change = on_track_change
        
        # Load persisted queue on startup
        self.load_queue()

    def build_queue_from_items(self, items: List[dict], start_path: Path, shuffle: bool = False):
        """
        Build playback queue from a list of items.

        Args:
            items: List of item dicts with id={'kind': 'file', 'path': ...}
            start_path: Path to start playing from
            shuffle: Whether to shuffle the queue
        """
        # Filter to file items using kind from id dict
        def get_file_path(item):
            item_id = item.get('id', {})
            if isinstance(item_id, dict) and item_id.get('kind') == 'file':
                return item_id.get('path')
            return None

        self.playlist_source = [str(get_file_path(i)) for i in items if get_file_path(i)]
        if not self.playlist_source:
            return

        self.shuffle_active = shuffle
        self.queue = list(range(len(self.playlist_source)))

        if shuffle:
            random.shuffle(self.queue)

        path_str = str(start_path)
        try:
            real_idx = self.playlist_source.index(path_str)
        except ValueError:
            real_idx = 0

        if shuffle:
            if real_idx in self.queue:
                self.queue.remove(real_idx)
            self.queue.insert(0, real_idx)
            self.queue_idx = 0
        else:
            self.queue_idx = real_idx
            
        self.save_queue()

    def get_current_path(self) -> Optional[str]:
        """Get the current track path."""
        if not self.queue or not self.playlist_source:
            return None
        real_idx = self.queue[self.queue_idx]
        return self.playlist_source[real_idx]

    def add_to_manual_queue(self, path: str):
        """Add a track to the manual queue (thread-safe)."""
        with self._lock:
            self.manual_queue.append(path)
        self.save_queue()

    def clear_manual_queue(self):
        """Clear the manual queue (thread-safe)."""
        with self._lock:
            self.manual_queue.clear()
        self.save_queue()

    def remove_from_queue(self, index: int):
        """Remove a track from the manual queue by index (thread-safe)."""
        with self._lock:
            if 0 <= index < len(self.manual_queue):
                del self.manual_queue[index]
        self.save_queue()

    def move_in_queue(self, from_index: int, to_index: int):
        """Move a track in the manual queue from one position to another (thread-safe)."""
        with self._lock:
            if 0 <= from_index < len(self.manual_queue):
                # Clamp to_index to valid range
                to_index = max(0, min(to_index, len(self.manual_queue) - 1))
                if from_index != to_index:
                    item = self.manual_queue[from_index]
                    del self.manual_queue[from_index]
                    self.manual_queue.insert(to_index, item)
        self.save_queue()

    def next_track(self, auto_advance=False) -> Optional[str]:
        """
        Move to next track and return its path.
        
        Args:
            auto_advance: True if advancing automatically (track finished), 
                         False if user requested next.
        """
        # Priority 1: Manual Queue
        if self.manual_queue:
            path = self.manual_queue.popleft()
            self.save_queue()
            return path

        # Priority 2: Auto Queue
        if not self.queue:
            return None

        next_idx = (self.queue_idx + 1) % len(self.queue)
        at_end = next_idx == 0
        
        # Stop at end if Loop Off (Manual or Auto)
        if at_end and self.loop_mode == 0:
            self.queue_idx = 0 # Reset or stay? Reset is fine.
            return None
            
        # Loop All (1) or One (2) -> Wrap to start (next_idx is 0)
            
        self.queue_idx = next_idx
        # Don't save on every auto-advance to avoid excessive writes, 
        # but maybe we should to resume playback? 
        # For now, let's only save if it's a significant change or periodically?
        # Actually, saving current index is useful for resume.
        self.save_queue()
        return self.get_current_path()


    def prev_track(self) -> Optional[str]:
        """Move to previous track and return its path."""
        if not self.queue:
            return None

        # User navigation overrides Loop One, so we always move back
        self.queue_idx = (self.queue_idx - 1) % len(self.queue)
        self.save_queue()
        return self.get_current_path()

    def load_track_covers(self, path: str):
        """
        Load cover images for a track.

        Args:
            path: Path to the audio file

        Returns:
            Tuple of (small_cover, large_cover)
        """
        return get_cover(Path(path))

    def toggle_shuffle(self):
        """Toggle shuffle mode."""
        self.shuffle_active = not self.shuffle_active
        # Reshuffle queue if needed
        if self.shuffle_active and self.playlist_source:
            current_path = self.get_current_path()
            self.queue = list(range(len(self.playlist_source)))
            random.shuffle(self.queue)
            # Move current track to front
            if current_path:
                try:
                    real_idx = self.playlist_source.index(current_path)
                    if real_idx in self.queue:
                        self.queue.remove(real_idx)
                    self.queue.insert(0, real_idx)
                    self.queue_idx = 0
                except ValueError:
                    pass
        self.save_queue()
        return self.shuffle_active

    def cycle_loop_mode(self) -> int:
        """Cycle through loop modes (off -> all -> one -> off)."""
        self.loop_mode = (self.loop_mode + 1) % 3
        self.save_queue()
        return self.loop_mode

    @property
    def has_queue(self) -> bool:
        """Check if there's an active queue."""
        return bool(self.queue and self.playlist_source)
        
    def save_queue(self):
        """Save current queue state to disk."""
        try:
            state = {
                'playlist_source': self.playlist_source,
                'queue': self.queue,
                'queue_idx': self.queue_idx,
                'manual_queue': list(self.manual_queue),
                'shuffle': self.shuffle_active,
                'loop_mode': self.loop_mode
            }
            queue_file = cfg.CONFIG_DIR / 'queue.json'
            with open(queue_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")

    def load_queue(self):
        """Load queue state from disk."""
        queue_file = cfg.CONFIG_DIR / 'queue.json'
        if not queue_file.exists():
            return
            
        try:
            with open(queue_file, 'r') as f:
                state = json.load(f)
                
            self.playlist_source = state.get('playlist_source', [])
            self.queue = state.get('queue', [])
            self.queue_idx = state.get('queue_idx', 0)
            self.manual_queue = deque(state.get('manual_queue', []))
            self.shuffle_active = state.get('shuffle', False)
            self.loop_mode = state.get('loop_mode', 0)
            
            # Validate indices
            if self.queue and self.queue_idx >= len(self.queue):
                self.queue_idx = 0
                
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")