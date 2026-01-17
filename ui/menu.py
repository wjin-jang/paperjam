from typing import List, Dict, Optional, Any, Union
from ui.views.items import Item

class MenuController:
    """
    Simplified controller for managing Menu/List state.
    Handles navigation logic, skipping non-selectable items, and pinning.
    """
    def __init__(self, items: List[Union[Dict[str, Any], Item]], start_index: int = 0):
        """
        Initialize the controller with a list of items.
        
        Args:
            items: List of item dictionaries or Item objects.
            start_index: Initial selected index (will adjust to nearest selectable if needed).
        """
        self.items = items
        self.selected_index = start_index
        
        # Ensure initial selection is valid
        if items:
            self._validate_selection()

    def set_items(self, items: List[Union[Dict[str, Any], Item]], reset_index: bool = True):
        """Replace the current items list."""
        self.items = items
        if reset_index:
            self.selected_index = 0
        self._validate_selection()

    def _is_selectable(self, index: int) -> bool:
        """Check if an item at the given index is selectable."""
        if not (0 <= index < len(self.items)):
            return False
        
        item = self.items[index]
        if isinstance(item, Item):
            return item.selectable
            
        item_type = item.get('type', 'file')
        # Pinned items can be selectable (like controls), unless specified otherwise
        # But commonly 'heading' and 'info' are not.
        return item_type not in ['heading', 'info']

    def _validate_selection(self):
        """Ensure selected_index points to a selectable item if possible."""
        if not self.items:
            self.selected_index = 0
            return

        if self._is_selectable(self.selected_index):
            return

        # Try searching forward
        original = self.selected_index
        found = False
        
        # Search forward
        for i in range(original, len(self.items)):
            if self._is_selectable(i):
                self.selected_index = i
                found = True
                break
        
        if not found:
            # Search backward
            for i in range(original - 1, -1, -1):
                if self._is_selectable(i):
                    self.selected_index = i
                    found = True
                    break
        
        # If still not found (no selectable items), keep original index but it won't render cursor
        
    def move_selection(self, delta: int):
        """
        Move selection by delta (e.g. -1 for up, +1 for down),
        automatically skipping non-selectable items.
        Wraps around the list.
        """
        if not self.items:
            return

        count = len(self.items)
        current = self.selected_index
        
        # Simple safety break to prevent infinite loops if NOTHING is selectable
        attempts = 0
        while attempts < count:
            current = (current + delta) % count
            attempts += 1
            if self._is_selectable(current):
                self.selected_index = current
                return

    def get_selected_item(self) -> Optional[Union[Dict[str, Any], Item]]:
        """Return the currently selected item."""
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def get_render_args(self):
        """
        Get arguments suitable for UIRenderer.render_menu.
        Automatically derives info_indices based on item type.
        """
        info_indices = []
        for i, item in enumerate(self.items):
            if isinstance(item, Item):
                if not item.selectable:
                    info_indices.append(i)
            elif item.get('type') in ['heading', 'info']:
                info_indices.append(i)
        
        return {
            'items': self.items,
            'sel_idx': self.selected_index,
            'scroll_idx': 0, # Renderer handles auto-scroll now
            'info_indices': info_indices
        }
