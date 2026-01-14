"""
Player state management for the music player application.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set, Any


@dataclass
class PlayerState:
    """State container for the music player."""
    items: List[dict] = field(default_factory=list)
    selection_index: int = 0
    view_start_index: int = 0
    top_bar_index: int = 0
    album: str = "Library"
    artist: str = ""
    year: str = ""
    has_header: bool = False
    is_playing: bool = False
    shuffle_active: bool = False
    loop_mode: int = 0
    playing_path: Optional[str] = None

    # Images
    playing_cover_s: Any = None
    playing_cover_l: Any = None
    browsing_cover_s: Any = None
    screensaver_image: Any = None

    # Flags
    needs_refresh: bool = False
    fav_albums: Optional[Set[str]] = None
    is_scanning: bool = False
    total_items: int = 0
    page_size: int = 7

    # Context menu
    context_menu_active: bool = False
    context_options: List[str] = field(default_factory=list)
    context_index: int = 0
    context_target_item: Optional[dict] = None
    context_layer: int = 0

    def reset_context_menu(self):
        """Reset context menu state."""
        self.context_menu_active = False
        self.context_options = []
        self.context_index = 0
        self.context_target_item = None
        self.context_layer = 0

    def reset_browsing_state(self):
        """Reset browsing-related state."""
        self.items = []
        self.artist = ""
        self.year = ""
        self.has_header = False
        self.browsing_cover_s = None
