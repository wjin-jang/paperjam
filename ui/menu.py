"""
Menu navigation controller for list-based UI views.

This module provides the MenuController class which manages navigation state
for scrollable menu lists. It handles:

- Selection state (which item is highlighted)
- Scroll position (pixel offset for smooth scrolling)
- Non-selectable items (automatically skipped during navigation)
- Wrapping behavior (selection wraps from end to beginning)

The controller works with both legacy dict-based items and the newer Item
dataclass format.

Example:
    >>> items = [Item(label="Option 1"), Item(label="Option 2")]
    >>> menu = MenuController(items)
    >>> menu.move_selection(1)  # Select next item
    >>> selected = menu.get_selected_item()
"""
from __future__ import annotations

from typing import Any

from ui.views.items import Item

# Type alias for menu items (supports both dict and Item formats)
MenuItem = dict[str, Any] | Item


class MenuController:
    """Controller for managing menu/list navigation state.

    Handles selection movement, scroll position, and automatic skipping
    of non-selectable items (headings, separators, etc.).

    Attributes:
        items: List of menu items (dicts or Item objects).
        selected_index: Index of currently selected item (-1 if none selectable).
        scroll_offset: Pixel offset for smooth scrolling.
    """

    def __init__(self, items: list[MenuItem], start_index: int = 0) -> None:
        """Initialize the controller with a list of items.

        Args:
            items: List of item dictionaries or Item objects.
            start_index: Initial selected index (adjusted to nearest selectable if needed).
        """
        self.items: list[MenuItem] = items
        self.selected_index: int = start_index
        self.scroll_offset: int = 0  # Persistent pixel offset for smooth scrolling

        # Ensure initial selection points to a selectable item
        if items:
            self._validate_selection()

    def set_items(self, items: list[MenuItem], reset_index: bool = True) -> None:
        """Replace the current items list.

        Args:
            items: New list of menu items.
            reset_index: If True, reset selection to 0; if False, try to preserve position.
        """
        self.items = items
        if reset_index:
            self.selected_index = 0
            self.scroll_offset = 0
        else:
            # Clamp selection to valid range for new items
            if self.selected_index >= len(items):
                self.selected_index = max(0, len(items) - 1)
        self._validate_selection()

    def _is_selectable(self, index: int) -> bool:
        """Check if an item at the given index is selectable.

        Args:
            index: Index to check.

        Returns:
            True if the item exists and is selectable.
        """
        if not (0 <= index < len(self.items)):
            return False

        item = self.items[index]
        if isinstance(item, Item):
            return item.selectable

        # Legacy dict items - use selectable key if present, else default True
        return item.get('selectable', True)

    def _validate_selection(self) -> None:
        """Ensure selected_index points to a selectable item.

        If the current selection is non-selectable, searches forward then
        backward to find the nearest selectable item. Sets selected_index
        to -1 if no selectable items exist.
        """
        if not self.items:
            self.selected_index = -1
            return

        if self._is_selectable(self.selected_index):
            return

        original = max(0, self.selected_index)

        # Search forward first
        for i in range(original, len(self.items)):
            if self._is_selectable(i):
                self.selected_index = i
                return

        # Then search backward
        for i in range(original - 1, -1, -1):
            if self._is_selectable(i):
                self.selected_index = i
                return

        # No selectable items found
        self.selected_index = -1

    def move_selection(self, delta: int) -> None:
        """Move selection by delta, skipping non-selectable items.

        Selection wraps around the list (moving past the end goes to the
        beginning, and vice versa).

        Args:
            delta: Direction and amount to move (-1 for up, +1 for down).
        """
        if not self.items:
            return

        # No selectable items - do nothing
        if self.selected_index < 0:
            return

        count = len(self.items)
        current = self.selected_index

        # Safety limit to prevent infinite loops if nothing is selectable
        for _ in range(count):
            current = (current + delta) % count
            if self._is_selectable(current):
                self.selected_index = current
                return

    def get_selected_item(self) -> MenuItem | None:
        """Get the currently selected item.

        Returns:
            The selected item (dict or Item), or None if no valid selection.
        """
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def get_render_args(self) -> dict[str, Any]:
        """Get arguments for UIRenderer.render_menu().

        Automatically derives info_indices (non-selectable items) from
        the items list.

        Returns:
            Dict with 'items', 'sel_idx', 'scroll_idx', and 'info_indices' keys.
        """
        info_indices: list[int] = []
        for i, item in enumerate(self.items):
            if isinstance(item, Item):
                if not item.selectable:
                    info_indices.append(i)
            elif not item.get('selectable', True):
                info_indices.append(i)

        return {
            'items': self.items,
            'sel_idx': self.selected_index,
            'scroll_idx': self.scroll_offset,
            'info_indices': info_indices
        }


def _is_item_heading(item: MenuItem) -> bool:
    """Check if an item is a heading (section header).

    Args:
        item: Item object or dict to check.

    Returns:
        True if the item is marked as a heading.
    """
    if isinstance(item, Item):
        return item.heading
    return item.get('heading', False)


def find_next_heading(current: int, items: list[MenuItem]) -> int:
    """Find the next heading item after the current index.

    Used for fast navigation between sections (e.g., jumping between
    alphabetical groups in a long list).

    Args:
        current: Starting index.
        items: List of menu items.

    Returns:
        Index of the next heading, or current index if no headings found.
    """
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
            # Wrapped around without finding a heading
            return current

    return current
