"""
Playlist and queue management for the music player.
"""
import random
from collections import deque
from pathlib import Path
from typing import List, Optional, Callable

from core.metadata import get_cover


class PlaylistManager:
    """Manages playback queue and playlist operations."""

    def __init__(self, on_track_change: Optional[Callable] = None):
        """
        Initialize playlist manager.

        Args:
            on_track_change: Callback when track changes, receives (path, covers)
        """
        self.playlist_source: List[str] = []
        self.queue: List[int] = []
        self.queue_idx: int = 0
        self.manual_queue: deque = deque()  # Queue for manually added tracks
        self.shuffle_active: bool = False
        self.loop_mode: int = 0  # 0=off, 1=all, 2=one
        self._on_track_change = on_track_change

    def build_queue_from_items(self, items: List[dict], start_path: Path, shuffle: bool = False):
        """
        Build playback queue from a list of items.

        Args:
            items: List of item dicts with 'path' and 'type' keys
            start_path: Path to start playing from
            shuffle: Whether to shuffle the queue
        """
        self.playlist_source = [str(i['path']) for i in items if i.get('type') == 'file']
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

    def get_current_path(self) -> Optional[str]:
        """Get the current track path."""
        if not self.queue or not self.playlist_source:
            return None
        real_idx = self.queue[self.queue_idx]
        return self.playlist_source[real_idx]

    def add_to_manual_queue(self, path: str):
        """Add a track to the manual queue."""
        self.manual_queue.append(path)

    def clear_manual_queue(self):
        """Clear the manual queue."""
        self.manual_queue.clear()

    def next_track(self, auto_advance=False) -> Optional[str]:
        """
        Move to next track and return its path.
        
        Args:
            auto_advance: True if advancing automatically (track finished), 
                         False if user requested next.
        """
        # Priority 1: Manual Queue
        if self.manual_queue:
            return self.manual_queue.popleft()

        # Priority 2: Auto Queue
        if not self.queue:
            return None

        # Loop One handled by caller (usually replaying current path)
        # But if caller calls this, it means we WANT the next track.
        # Except if Loop One logic was missed? No, let's assume caller handles Loop One repeat.
        
        next_idx = (self.queue_idx + 1) % len(self.queue)
        at_end = next_idx == 0
        
        # Stop at end if Loop Off (Manual or Auto)
        if at_end and self.loop_mode == 0:
            self.queue_idx = 0 # Reset or stay? Reset is fine.
            return None
            
        # Loop All (1) or One (2) -> Wrap to start (next_idx is 0)
            
        self.queue_idx = next_idx
        return self.get_current_path()


    def prev_track(self) -> Optional[str]:
        """Move to previous track and return its path."""
        if not self.queue:
            return None

        # User navigation overrides Loop One, so we always move back
        self.queue_idx = (self.queue_idx - 1) % len(self.queue)
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
        return self.shuffle_active

    def cycle_loop_mode(self) -> int:
        """Cycle through loop modes (off -> all -> one -> off)."""
        self.loop_mode = (self.loop_mode + 1) % 3
        return self.loop_mode

    @property
    def has_queue(self) -> bool:
        """Check if there's an active queue."""
        return bool(self.queue and self.playlist_source)
