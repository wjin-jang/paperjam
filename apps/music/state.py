"""
Player state management for the music player application.
"""
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set, Any

from ui.views.core import Cursor


@dataclass
class PlayerState:
    """State container for the music player."""
    items: List[dict] = field(default_factory=list)
    pinned_items: List[dict] = field(default_factory=list)
    scrollable_items: List[dict] = field(default_factory=list)
    cursor: Cursor = field(default_factory=Cursor)
    album: str = "Library"
    artist: str = ""
    year: str = ""
    is_playing: bool = False
    shuffle_active: bool = False
    loop_mode: int = 0
    playing_path: Optional[str] = None
    playing_artist: Optional[str] = None
    playing_album: Optional[str] = None

    # Images
    playing_cover_s: Any = None
    playing_cover_l: Any = None
    browsing_cover_s: Any = None
    screensaver_image: Any = None
    screensaver_album: Optional[str] = None

    # Flags
    needs_refresh: bool = False
    fav_albums: Optional[Set[str]] = None
    fav_artists: Optional[Set[str]] = None
    browse_mode: str = 'ROOT'
    is_scanning: bool = False
    total_items: int = 0

    # Temporary status message
    status_message: Optional[str] = None
    status_message_time: float = 0
    status_message_duration: float = 1.5

    # Context menu
    context_menu_active: bool = False
    context_options: List[str] = field(default_factory=list)
    context_index: int = 0
    context_target_item: Optional[dict] = None
    context_layer: int = 0

    # Loading overlay
    loading_message: Optional[str] = None

    def reset_context_menu(self):
        """Reset context menu state."""
        self.context_menu_active = False
        self.context_options = []
        self.context_index = 0
        self.context_target_item = None
        self.context_layer = 0

    def reset_browsing_state(self, reset_controls=True):
        """Reset browsing-related state."""
        self.items = []
        self.pinned_items = []
        self.scrollable_items = []
        self.artist = ""
        self.year = ""
        if reset_controls:
            self.cursor.col = 0
        self.browsing_cover_s = None

    @property
    def selection_index(self) -> int:
        """Current selection index (cursor row position)."""
        return self.cursor.row

    @selection_index.setter
    def selection_index(self, value: int):
        self.cursor.row = value

    @property
    def controls_index(self) -> int:
        """Current controls index (cursor column position)."""
        return self.cursor.col

    @controls_index.setter
    def controls_index(self, value: int):
        self.cursor.col = value

    def set_status_message(self, message: str, duration: float = 1.5):
        """Set a temporary status message."""
        self.status_message = message
        self.status_message_time = time.time()
        self.status_message_duration = duration

    def get_status_text(self) -> str:
        """Get the current status text, considering temporary messages."""
        # Check if temporary message is still active
        if self.status_message and (time.time() - self.status_message_time) < self.status_message_duration:
            return self.status_message

        # Clear expired message
        self.status_message = None

        # Return default status
        if self.is_playing:
            return "PLAYING"
        elif self.playing_path:
            return "PAUSED"
        else:
            return "IDLE"
