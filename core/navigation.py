"""
Navigation controller for consistent list navigation across the application.
Extracts repeated modulo arithmetic and navigation logic.
"""
from typing import Callable, Optional


class NavigationController:
    """
    Manages index-based navigation through a list of items.

    Handles wraparound, callbacks, and consistent navigation behavior
    that was previously duplicated across music.py and settings.py.
    """

    def __init__(self, item_count: int = 0, on_change: Optional[Callable[[int], None]] = None):
        """
        Initialize navigation controller.

        Args:
            item_count: Number of items to navigate through
            on_change: Optional callback when index changes
        """
        self._index = 0
        self._item_count = item_count
        self._on_change = on_change

    @property
    def index(self) -> int:
        """Current navigation index."""
        return self._index

    @index.setter
    def index(self, value: int):
        """Set index with bounds checking."""
        if self._item_count > 0:
            self._index = value % self._item_count
        else:
            self._index = 0

    @property
    def item_count(self) -> int:
        """Number of items being navigated."""
        return self._item_count

    @item_count.setter
    def item_count(self, value: int):
        """Update item count and adjust index if needed."""
        self._item_count = max(0, value)
        if self._item_count > 0 and self._index >= self._item_count:
            self._index = self._item_count - 1
        elif self._item_count == 0:
            self._index = 0

    def move_up(self) -> int:
        """Move selection up (previous item with wraparound)."""
        if self._item_count == 0:
            return self._index
        self._index = (self._index - 1) % self._item_count
        if self._on_change:
            self._on_change(self._index)
        return self._index

    def move_down(self) -> int:
        """Move selection down (next item with wraparound)."""
        if self._item_count == 0:
            return self._index
        self._index = (self._index + 1) % self._item_count
        if self._on_change:
            self._on_change(self._index)
        return self._index

    def reset(self, item_count: Optional[int] = None):
        """Reset index to 0, optionally updating item count."""
        self._index = 0
        if item_count is not None:
            self._item_count = max(0, item_count)

    def set_index_safe(self, index: int):
        """Set index with bounds checking (no wraparound)."""
        if self._item_count > 0:
            self._index = max(0, min(index, self._item_count - 1))
        else:
            self._index = 0


def nav_index_up(current: int, total: int) -> int:
    """Standalone function for moving index up with wraparound."""
    if total == 0:
        return 0
    return (current - 1) % total


def nav_index_down(current: int, total: int) -> int:
    """Standalone function for moving index down with wraparound."""
    if total == 0:
        return 0
    return (current + 1) % total


def _is_item_selectable(item) -> bool:
    """Check if an item is selectable (works with Item objects or dicts)."""
    from ui.views.items import Item
    if isinstance(item, Item):
        return item.selectable
    return item.get('selectable', True)


def _is_item_heading(item) -> bool:
    """Check if an item is a heading (works with Item objects or dicts)."""
    from ui.views.items import Item
    if isinstance(item, Item):
        return item.heading
    return item.get('heading', False)


def nav_skip_info_up(current: int, items: list) -> int:
    """Move index up, skipping non-selectable items. Returns new index."""
    if not items:
        return 0
    total = len(items)
    new_idx = (current - 1) % total
    # Skip non-selectable items
    attempts = 0
    while not _is_item_selectable(items[new_idx]) and attempts < total:
        new_idx = (new_idx - 1) % total
        attempts += 1
    return new_idx


def nav_skip_info_down(current: int, items: list) -> int:
    """Move index down, skipping non-selectable items. Returns new index."""
    if not items:
        return 0
    total = len(items)
    new_idx = (current + 1) % total
    # Skip non-selectable items
    attempts = 0
    while not _is_item_selectable(items[new_idx]) and attempts < total:
        new_idx = (new_idx + 1) % total
        attempts += 1
    return new_idx


def find_next_heading(current: int, items: list) -> int:
    """Find the next heading item after current index. Wraps around."""
    if not items:
        return 0
    total = len(items)
    idx = (current + 1) % total
    start_idx = idx
    while True:
        if _is_item_heading(items[idx]):
            return idx
        idx = (idx + 1) % total
        if idx == start_idx:
            # No other headings found, stay at current
            return current
    return current
