"""
Item classes for the Menu rendering system.

All items share a common interface for rendering and navigation.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Union, Optional
from PIL import Image, ImageDraw, ImageOps
from abc import ABC, abstractmethod

import config as cfg
from core.metadata import sanitize_text


class Item(ABC):
    """Base class for all menu items.

    Items are rendered within a Menu and support cursor selection.
    """

    def __init__(self, selectable: bool = True, pinned: bool = False):
        """Create an item.

        Args:
            selectable: Whether this item can be selected
            pinned: Whether item stays at top (doesn't scroll)
        """
        self.selectable = selectable
        self.pinned = pinned

    def get_height(self) -> int:
        """Get item height in pixels."""
        return cfg.ROW_HEIGHT

    def get_column_count(self) -> int:
        """Get number of columns (for horizontal navigation)."""
        return 1

    @abstractmethod
    def render(self, draw: ImageDraw.Draw, canvas: Image.Image,
               x: int, y: int, w: int, h: int,
               selected: bool = False, selected_col: int = -1):
        """Render the item.

        Args:
            draw: ImageDraw instance
            canvas: Target canvas for pasting images
            x, y: Position to render at
            w, h: Available dimensions
            selected: Whether item is selected
            selected_col: Selected column index (-1 if whole item selected)
        """
        pass

    def _draw_text_box(self, draw: ImageDraw.Draw, canvas: Image.Image,
                       text: str, x: int, y: int, w: int, h: int,
                       invert: bool = False, center: bool = False,
                       font=None):
        """Draw a text box with optional inversion.

        Args:
            draw: ImageDraw instance
            canvas: Canvas for compositing
            text: Text to draw
            x, y, w, h: Box dimensions
            invert: Whether to invert colors
            center: Whether to center text
            font: Optional font override
        """
        if h < 1 or w < 1:
            return

        if font is None:
            font = cfg.FONT_MAIN

        bg = cfg.BLACK if invert else cfg.WHITE
        fg = cfg.WHITE if invert else cfg.BLACK

        text_layer = Image.new('1', (w + 1, h + 1), bg)
        text_draw = ImageDraw.Draw(text_layer)
        text_draw.rectangle((0, 0, w, h), outline=cfg.BLACK)

        padding_x, padding_y = 5, 3
        if center:
            bbox = text_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            draw_x = (w - text_w) // 2 + 1
        else:
            draw_x = padding_x

        text_draw.text((draw_x, padding_y), text, font=font, fill=fg)
        canvas.paste(text_layer, (x, y))


class TextItem(Item):
    """Simple text item with optional icon prefix."""

    def __init__(self, text: str, icon: Union[str, Image.Image] = None,
                 selectable: bool = True, pinned: bool = False):
        """Create a text item.

        Args:
            text: Display text
            icon: Optional icon (text string or PIL Image)
            selectable: Whether item can be selected
            pinned: Whether item stays at top
        """
        super().__init__(selectable, pinned)
        self.text = text
        self.icon = icon

    def render(self, draw: ImageDraw.Draw, canvas: Image.Image,
               x: int, y: int, w: int, h: int,
               selected: bool = False, selected_col: int = -1):
        """Render text item."""
        invert = selected and self.selectable
        text = sanitize_text(self.text)

        if self.icon:
            icon_w = 12
            if isinstance(self.icon, str):
                # Text icon
                self._draw_text_box(draw, canvas, self.icon, x, y, icon_w, h,
                                   invert=invert, center=True)
            else:
                # Image icon
                icon = self.icon
                if invert:
                    icon = ImageOps.invert(icon.convert('L')).convert('1')
                ix = x + (icon_w - icon.width) // 2
                iy = y + (h - icon.height) // 2
                if invert:
                    draw.rectangle((x, y, x + icon_w, y + h), fill=cfg.BLACK)
                canvas.paste(icon, (ix, iy))
            self._draw_text_box(draw, canvas, text, x + icon_w, y, w - icon_w, h,
                               invert=invert)
        else:
            self._draw_text_box(draw, canvas, text, x, y, w, h, invert=invert)


@dataclass
class Column:
    """A single column within a ColumnItem."""
    content: Union[str, Image.Image]  # Text string or PIL Image
    width: Optional[int] = None  # None = auto-calculate
    align: str = 'left'  # 'left', 'center', 'right'
    active: bool = False  # For toggle states (e.g., shuffle on)


class ColumnItem(Item):
    """Item with multiple columns supporting horizontal navigation."""

    def __init__(self, columns: List[Column],
                 selectable: bool = True, pinned: bool = False):
        """Create a column item.

        Args:
            columns: List of Column objects
            selectable: Whether item can be selected
            pinned: Whether item stays at top
        """
        super().__init__(selectable, pinned)
        self.columns = columns

    def get_column_count(self) -> int:
        """Get number of columns."""
        return len(self.columns)

    def render(self, draw: ImageDraw.Draw, canvas: Image.Image,
               x: int, y: int, w: int, h: int,
               selected: bool = False, selected_col: int = -1):
        """Render column item.

        Selection logic:
        - If column.active: always inverted
        - If column is selected (selected_col == col_idx): inverted
        - If column.active AND selected: add white inner border
        """
        # Calculate column widths
        widths = self._calculate_widths(w)

        col_x = x
        for i, (col, col_w) in enumerate(zip(self.columns, widths)):
            is_col_selected = selected and (selected_col == i)
            invert = col.active or is_col_selected
            add_inner_border = col.active and is_col_selected

            self._render_column(draw, canvas, col, col_x, y, col_w, h,
                               invert, add_inner_border)
            col_x += col_w

    def _calculate_widths(self, total_w: int) -> List[int]:
        """Calculate column widths."""
        widths = []
        fixed_total = 0
        auto_count = 0

        for col in self.columns:
            if col.width is not None:
                widths.append(col.width)
                fixed_total += col.width
            else:
                widths.append(None)
                auto_count += 1

        # Distribute remaining width to auto columns
        if auto_count > 0:
            remaining = total_w - fixed_total
            auto_width = remaining // auto_count
            widths = [w if w is not None else auto_width for w in widths]

        return widths

    def _render_column(self, draw: ImageDraw.Draw, canvas: Image.Image,
                       col: Column, x: int, y: int, w: int, h: int,
                       invert: bool, add_inner_border: bool):
        """Render a single column."""
        bg = cfg.BLACK if invert else cfg.WHITE
        fg = cfg.WHITE if invert else cfg.BLACK

        # Draw background
        draw.rectangle((x, y, x + w, y + h), fill=bg, outline=cfg.BLACK)

        if isinstance(col.content, str):
            # Text content
            text = sanitize_text(col.content)
            font = cfg.FONT_MAIN

            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]

            if col.align == 'center':
                text_x = x + (w - text_w) // 2
            elif col.align == 'right':
                text_x = x + w - text_w - 5
            else:
                text_x = x + 5

            draw.text((text_x, y + 3), text, font=font, fill=fg)
        else:
            # Image content
            icon = col.content
            if invert:
                icon = ImageOps.invert(icon.convert('L')).convert('1')

            ix = x + (w - icon.width) // 2
            iy = y + (h - icon.height) // 2
            canvas.paste(icon, (ix, iy), mask=icon if not invert else None)

        # Add inner border for active+selected
        if add_inner_border:
            draw.rectangle((x + 1, y + 1, x + w - 1, y + h - 1), outline=fg)


class ImageItem(Item):
    """Item displaying an image (for album art)."""

    def __init__(self, image: Image.Image = None, placeholder: str = "NO IMAGE",
                 selectable: bool = False, pinned: bool = False):
        """Create an image item.

        Args:
            image: PIL Image to display
            placeholder: Text to show when no image
            selectable: Whether item can be selected
            pinned: Whether item stays at top
        """
        super().__init__(selectable, pinned)
        self.image = image
        self.placeholder = placeholder
        self._height = None  # Set by parent

    def set_height(self, h: int):
        """Set item height (for album art sizing)."""
        self._height = h

    def get_height(self) -> int:
        """Get item height."""
        return self._height if self._height else cfg.ROW_HEIGHT

    def render(self, draw: ImageDraw.Draw, canvas: Image.Image,
               x: int, y: int, w: int, h: int,
               selected: bool = False, selected_col: int = -1):
        """Render image item."""
        if self.image:
            # Paste image (assumes it's already sized correctly)
            canvas.paste(self.image, (x, y))
        else:
            # Show placeholder text
            placeholder_y = y + (h // 2) - (cfg.ROW_HEIGHT // 2)
            self._draw_text_box(draw, canvas, self.placeholder,
                               x, placeholder_y, w, cfg.ROW_HEIGHT,
                               invert=True, center=True)


class HeadingItem(Item):
    """Section heading (always inverted background)."""

    def __init__(self, text: str, selectable: bool = True, pinned: bool = False):
        """Create a heading item.

        Args:
            text: Heading text (will be uppercased)
            selectable: Whether heading can be selected (for jumping)
            pinned: Whether item stays at top
        """
        super().__init__(selectable, pinned)
        self.text = text

    def render(self, draw: ImageDraw.Draw, canvas: Image.Image,
               x: int, y: int, w: int, h: int,
               selected: bool = False, selected_col: int = -1):
        """Render heading item."""
        text = sanitize_text(self.text).upper()

        # Always black background
        draw.rectangle((x, y, x + w, y + h - 1), fill=cfg.BLACK)
        self._draw_text_box(draw, canvas, text, x, y, w, h,
                           invert=True, font=cfg.FONT_MAIN)

        # Add white outline when selected
        if selected:
            draw.rectangle((x + 1, y + 1, x + w - 1, y + h - 1), outline=cfg.WHITE)


class InfoItem(Item):
    """Non-selectable info item with optional columns."""

    def __init__(self, columns: List[str] = None, lines: List = None,
                 text: str = None, pinned: bool = False):
        """Create an info item.

        Args:
            columns: Single row of column strings
            lines: Multiple rows, each a string or list of column strings
            text: Simple text (if no columns/lines)
            pinned: Whether item stays at top
        """
        super().__init__(selectable=False, pinned=pinned)
        self.columns = columns
        self.lines = lines
        self.text = text

    def get_height(self) -> int:
        """Get item height based on line count."""
        if self.lines:
            return len(self.lines) * cfg.ROW_HEIGHT
        return cfg.ROW_HEIGHT

    def render(self, draw: ImageDraw.Draw, canvas: Image.Image,
               x: int, y: int, w: int, h: int,
               selected: bool = False, selected_col: int = -1):
        """Render info item."""
        if self.lines:
            for i, line in enumerate(self.lines):
                line_y = y + (i * cfg.ROW_HEIGHT)
                if isinstance(line, list):
                    self._render_columns(draw, canvas, line, x, line_y, w)
                else:
                    self._draw_text_box(draw, canvas, sanitize_text(str(line)),
                                       x, line_y, w, cfg.ROW_HEIGHT)
        elif self.columns:
            self._render_columns(draw, canvas, self.columns, x, y, w)
        elif self.text:
            self._draw_text_box(draw, canvas, sanitize_text(self.text),
                               x, y, w, cfg.ROW_HEIGHT)

    def _render_columns(self, draw: ImageDraw.Draw, canvas: Image.Image,
                        columns: List[str], x: int, y: int, w: int):
        """Render a row of text columns."""
        if not columns:
            return

        if len(columns) == 1:
            self._draw_text_box(draw, canvas, sanitize_text(str(columns[0])),
                               x, y, w, cfg.ROW_HEIGHT)
            return

        # Calculate widths for right columns
        right_widths = []
        for col in columns[1:]:
            text = sanitize_text(str(col))
            col_w = max(20, len(text) * 6 + 8)
            right_widths.append(col_w)

        total_right = sum(right_widths)
        left_w = w - total_right

        # Scale if needed
        if total_right + 20 > w:
            scale = (w - 20) / total_right if total_right > 0 else 1
            right_widths = [max(10, int(cw * scale)) for cw in right_widths]
            total_right = sum(right_widths)
            left_w = max(20, w - total_right)

        # Render left column
        self._draw_text_box(draw, canvas, sanitize_text(str(columns[0])),
                           x, y, left_w, cfg.ROW_HEIGHT)

        # Render right columns (centered)
        col_x = x + left_w
        for i, col in enumerate(columns[1:]):
            col_w = right_widths[i]
            self._draw_text_box(draw, canvas, sanitize_text(str(col)),
                               col_x, y, col_w, cfg.ROW_HEIGHT, center=True)
            col_x += col_w
