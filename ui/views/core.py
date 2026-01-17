"""
Core UI classes: Panel, Menu, Cursor.

This module provides the foundational classes for the Panel → Menu → Item
rendering hierarchy.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING
from PIL import Image, ImageDraw

import config as cfg
from ui.graphics import create_dithered_strip

if TYPE_CHECKING:
    from ui.views.items import Item


@dataclass
class Cursor:
    """Cursor position within a menu.

    Tracks both vertical (row) and horizontal (col) position.
    Horizontal movement only applies to items with multiple columns.
    """
    row: int = 0
    col: int = 0

    def reset(self):
        """Reset cursor to origin."""
        self.row = 0
        self.col = 0


class Menu:
    """A scrollable list of items with cursor navigation.

    The Menu handles:
    - Item storage and rendering
    - Cursor navigation (with column support)
    - Scroll offset management
    - Frame buffer rendering
    """

    def __init__(self, width: int, height: int):
        """Create a menu.

        Args:
            width: Content area width in pixels
            height: Content area height in pixels
        """
        self.width = width
        self.height = height
        self.items: List[Item] = []
        self.cursor = Cursor()
        self.scroll_offset: int = 0  # Pixel offset for scrolling

    def set_items(self, items: List[Item]):
        """Set menu items and reset cursor."""
        self.items = items
        self.cursor.reset()
        self.scroll_offset = 0
        self._ensure_valid_cursor()

    def get_selected_item(self) -> Optional[Item]:
        """Get currently selected item."""
        if 0 <= self.cursor.row < len(self.items):
            return self.items[self.cursor.row]
        return None

    def get_selected_column(self) -> int:
        """Get currently selected column index."""
        return self.cursor.col

    def get_total_height(self) -> int:
        """Get total height of all items."""
        return sum(item.get_height() for item in self.items)

    def needs_scrollbar(self) -> bool:
        """Check if menu needs a scrollbar."""
        return self.get_total_height() > self.height

    def set_scroll_to_row(self, row_idx: int):
        """Set scroll offset to show a specific row at the top.

        Args:
            row_idx: Row index to scroll to
        """
        if row_idx <= 0 or not self.items:
            self.scroll_offset = 0
            return

        # Calculate pixel offset for the row
        y = 0
        for i, item in enumerate(self.items):
            if i >= row_idx:
                break
            y += item.get_height()

        # Clamp to max scrollable area
        max_scroll = max(0, self.get_total_height() - self.height)
        self.scroll_offset = min(y, max_scroll)

    # Navigation

    def nav_up(self) -> bool:
        """Move cursor up. Returns True if moved."""
        if not self.items:
            return False

        original_row = self.cursor.row
        new_row = self.cursor.row

        # Find next selectable item above
        for _ in range(len(self.items)):
            new_row = (new_row - 1) % len(self.items)
            if self.items[new_row].selectable:
                break
        else:
            return False

        if new_row != original_row:
            self.cursor.row = new_row
            self.cursor.col = 0  # Reset column when changing rows
            self._ensure_visible()
            return True
        return False

    def nav_down(self) -> bool:
        """Move cursor down. Returns True if moved."""
        if not self.items:
            return False

        original_row = self.cursor.row
        new_row = self.cursor.row

        # Find next selectable item below
        for _ in range(len(self.items)):
            new_row = (new_row + 1) % len(self.items)
            if self.items[new_row].selectable:
                break
        else:
            return False

        if new_row != original_row:
            self.cursor.row = new_row
            self.cursor.col = 0  # Reset column when changing rows
            self._ensure_visible()
            return True
        return False

    def nav_left(self) -> bool:
        """Move cursor left within current item. Returns True if moved."""
        item = self.get_selected_item()
        if not item:
            return False

        col_count = item.get_column_count()
        if col_count <= 1:
            return False

        if self.cursor.col > 0:
            self.cursor.col -= 1
            return True
        return False

    def nav_right(self) -> bool:
        """Move cursor right within current item. Returns True if moved."""
        item = self.get_selected_item()
        if not item:
            return False

        col_count = item.get_column_count()
        if col_count <= 1:
            return False

        if self.cursor.col < col_count - 1:
            self.cursor.col += 1
            return True
        return False

    def _ensure_valid_cursor(self):
        """Ensure cursor is on a selectable item."""
        if not self.items:
            self.cursor.reset()
            return

        # If current item is selectable, we're fine
        if 0 <= self.cursor.row < len(self.items):
            if self.items[self.cursor.row].selectable:
                return

        # Find first selectable item
        for i, item in enumerate(self.items):
            if item.selectable:
                self.cursor.row = i
                self.cursor.col = 0
                return

        # No selectable items
        self.cursor.row = -1
        self.cursor.col = 0

    def _ensure_visible(self):
        """Ensure cursor row is visible in the viewport using smart scrolling."""
        if not self.items or self.cursor.row < 0:
            return

        # Ensure cursor is in bounds
        if self.cursor.row >= len(self.items):
            self.cursor.row = len(self.items) - 1

        # Calculate cursor item position in pixels
        row_top = 0
        for i, item in enumerate(self.items):
            h = item.get_height()
            if i == self.cursor.row:
                break
            row_top += h
        
        row_height = self.items[self.cursor.row].get_height()
        row_bottom = row_top + row_height
        
        # Current viewport
        view_top = self.scroll_offset
        view_bottom = self.scroll_offset + self.height
        
        # If item is taller than viewport, align top
        if row_height > self.height:
            self.scroll_offset = row_top
        # If above viewport, align top
        elif row_top < view_top:
            self.scroll_offset = row_top
        # If below viewport, align bottom
        elif row_bottom > view_bottom:
            self.scroll_offset = row_bottom - self.height

        # Clamp to valid range
        max_scroll = max(0, self.get_total_height() - self.height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

    def render(self) -> Image.Image:
        """Render menu items to a frame buffer.

        Returns:
            PIL Image with rendered menu content
        """
        frame = Image.new('1', (self.width, self.height), cfg.WHITE)
        draw = ImageDraw.Draw(frame)

        # scroll_offset is in pixels
        render_y = -self.scroll_offset

        for i, item in enumerate(self.items):
            h = item.get_height()

            # Check if item is visible
            if render_y + h > 0 and render_y < self.height:
                # Determine selection state
                is_selected = (i == self.cursor.row)
                selected_col = self.cursor.col if is_selected else -1

                item.render(
                    draw, frame,
                    x=0, y=render_y, w=self.width, h=h,
                    selected=is_selected, selected_col=selected_col
                )

            render_y += h

            # Stop if we're past visible area
            if render_y >= self.height:
                break

        return frame


class Panel:
    """A bordered panel with optional header that contains a Menu.

    The Panel handles:
    - Border and shadow rendering
    - Optional header bar
    - Menu frame compositing
    - Scrollbar rendering
    """

    def __init__(self, x: int, y: int, width: int, height: int,
                 header: str = None):
        """Create a panel.

        Args:
            x: X position on screen
            y: Y position on screen
            width: Panel width including border
            height: Panel height including border
            header: Optional header text
        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.header = header
        self.menu: Optional[Menu] = None

    @property
    def content_y(self) -> int:
        """Y offset of content area (after header)."""
        return cfg.ROW_HEIGHT if self.header else 0

    @property
    def content_height(self) -> int:
        """Height of content area."""
        return self.height - self.content_y

    @property
    def content_width(self) -> int:
        """Width of content area (accounting for scrollbar if needed)."""
        # Only reserve scrollbar space if it's actually needed and panel is large enough
        if self.menu and self.menu.needs_scrollbar() and self.width > 20:
            return self.width - 8  # Scrollbar width
        return self.width

    def set_menu(self, menu: Menu):
        """Set the menu for this panel."""
        self.menu = menu

    def create_menu(self) -> Menu:
        """Create and set a menu sized for this panel's content area."""
        # Initial guess - assumes no scrollbar first to maximize width
        # Width will be updated in render if scrollbar is needed
        menu = Menu(self.width, self.content_height)
        self.menu = menu
        return menu

    def render(self, canvas: Image.Image):
        """Render panel onto canvas.

        Args:
            canvas: Target canvas to render onto
        """
        draw = ImageDraw.Draw(canvas)

        # Draw shadow (offset by 1 pixel)
        draw.rectangle(
            (self.x + 1, self.y + 1,
             self.x + self.width + 1, self.y + self.height + 1),
            outline=cfg.BLACK
        )

        # Draw panel border and fill
        draw.rectangle(
            (self.x, self.y, self.x + self.width, self.y + self.height),
            fill=cfg.WHITE, outline=cfg.BLACK
        )

        # Draw header if present
        if self.header:
            draw.rectangle(
                (self.x, self.y, self.x + self.width, self.y + cfg.ROW_HEIGHT),
                fill=cfg.BLACK
            )
            draw.text(
                (self.x + 5, self.y),
                self.header,
                font=cfg.FONT_HEADER, fill=cfg.WHITE
            )

        # Render menu content
        if self.menu:
            # Update menu dimensions based on scrollbar need
            # We must set dimensions before rendering so wrapped text calculates correctly
            self.menu.height = self.content_height
            
            # First pass: check if scrollbar needed with full width
            self.menu.width = self.width 
            
            if self.menu.needs_scrollbar() and self.width > 20:
                # Needs scrollbar -> reduce width
                self.menu.width = self.content_width
                
            frame = self.menu.render()
            content_x = self.x
            content_y = self.y + self.content_y
            canvas.paste(frame, (content_x, content_y))

            # Render scrollbar if needed
            if self.menu.needs_scrollbar() and self.width > 20:
                self._render_scrollbar(canvas, draw)

    def _render_scrollbar(self, canvas: Image.Image, draw: ImageDraw.Draw):
        """Render scrollbar for menu."""
        if not self.menu:
            return

        sb_x = self.x + self.width - 8
        sb_y = self.y + self.content_y
        sb_h = self.content_height
        sb_w = 8

        # Border around scrollbar track
        draw.rectangle((sb_x, sb_y, sb_x + sb_w, sb_y + sb_h), outline=cfg.BLACK, fill=cfg.WHITE)

        # Dithered background
        strip = create_dithered_strip(sb_w - 1, sb_h - 1)
        canvas.paste(strip, (sb_x + 1, sb_y + 1))

        # Calculate handle size and position
        total_h = self.menu.get_total_height()
        if total_h <= 0:
            return

        # Handle size proportional to visible area
        visible_ratio = self.content_height / total_h
        handle_h = max(6, int(sb_h * visible_ratio))

        # Handle position based on scroll offset (already in pixels)
        max_scroll = max(1, total_h - self.content_height)
        scroll_ratio = min(1.0, self.menu.scroll_offset / max_scroll)

        handle_y = sb_y + int((sb_h - handle_h) * scroll_ratio)

        draw.rectangle(
            (sb_x + 1, handle_y, sb_x + sb_w - 1, handle_y + handle_h - 1),
            fill=cfg.WHITE, outline=cfg.BLACK
        )