"""
Menu item classes for the UI rendering system.

This module provides the building blocks for menu-based UIs on the e-paper display.
The main class is `Item`, a unified renderable item that supports:

- Simple text labels with optional icons
- Multi-column layouts (for controls bars, settings)
- Multi-line content (for info panels)
- Text wrapping for long content
- Volume sliders
- Text input fields with character cycling
- Section headings

Item Configuration:
    Items are configured via constructor parameters rather than subclassing.
    This allows flexible composition of rendering behaviors.

Rendering Modes:
    - **Heading**: Inverted background, uppercase text
    - **Column navigation**: Horizontal button bar with selection highlight
    - **Info columns**: Key-value display with right-aligned values
    - **Text input**: Character-by-character entry with underline cursor
    - **Volume slider**: Horizontal bar with +/- buttons
    - **Image display**: Dithered image with placeholder text

Example:
    >>> # Simple menu item
    >>> item = Item(text="Play All", icon="▶")
    >>>
    >>> # Settings item with value column
    >>> item = Item(columns=["Volume", "50%"], selectable=True)
    >>>
    >>> # Section heading
    >>> item = Item(text="Library", heading=True, selectable=False)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

import config as cfg
from core.i18n import t
from ui.graphics import draw_text_with_cjk, get_text_width_with_cjk


def get_font_padding(font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """Get the default padding for a font.

    Padding values compensate for font metrics that don't render well at
    small sizes on the e-paper display.

    Args:
        font: The PIL font object.

    Returns:
        (x, y) padding tuple in pixels.
    """
    return cfg.FONT_PADDING.get(font, (5, 0))


def get_cjk_y_offset(font: ImageFont.FreeTypeFont) -> int:
    """Get the Y offset for CJK characters relative to the main font.

    CJK fonts often have different baselines than Latin fonts. This offset
    aligns them properly when rendering mixed-script text.

    Args:
        font: The main (Latin) font being used.

    Returns:
        Y offset in pixels to apply to CJK characters.
    """
    # Determine which CJK font pairs with this font
    cjk_font = cfg.FONT_CJK_HEADER if font == cfg.FONT_HEADER else cfg.FONT_CJK_MAIN

    main_pad = get_font_padding(font)
    cjk_pad = get_font_padding(cjk_font)

    # CJK y offset is the difference in Y padding
    return cjk_pad[1] - main_pad[1]


# --- Character Sets for Text Input ---
# Password entry: full alphanumeric plus common symbols
CHARSET_PASSWORD: list[str] = (
    list('abcdefghijklmnopqrstuvwxyz') +
    list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') +
    list('0123456789') +
    list('!@#$%^&*()-_=+[]{}|;:,.<>?/~` ')
)

# Location entry: letters, numbers, and common punctuation for place names
CHARSET_LOCATION: list[str] = list(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz -'.,0123456789"
)


class TextInput:
    """Reusable text input component with character-by-character entry.

    Designed for devices without a keyboard (like the e-paper music player).
    Users cycle through characters using up/down buttons and confirm each
    character to build the text. An underline cursor indicates the current
    character position.

    Attributes:
        charset: Available characters to cycle through.
        chars: List of confirmed characters (the entered text).
        char_idx: Index into charset for the current character selection.
    """

    def __init__(self, charset: list[str] | None = None, initial_text: str = "") -> None:
        """Initialize text input.

        Args:
            charset: List of characters to cycle through. Defaults to CHARSET_PASSWORD.
            initial_text: Starting text value.
        """
        self.charset: list[str] = charset or CHARSET_PASSWORD
        self.chars: list[str] = list(initial_text)
        self.char_idx: int = 0

    def reset(self, initial_text: str = "") -> None:
        """Reset input state to initial text."""
        self.chars = list(initial_text)
        self.char_idx = 0

    @property
    def text(self) -> str:
        """Get the current entered text (confirmed characters only)."""
        return ''.join(self.chars)

    @property
    def current_char(self) -> str:
        """Get the currently selected character (not yet confirmed)."""
        return self.charset[self.char_idx]

    def next_char(self) -> None:
        """Move to next character in the charset (wraps around)."""
        self.char_idx = (self.char_idx + 1) % len(self.charset)

    def prev_char(self) -> None:
        """Move to previous character in the charset (wraps around)."""
        self.char_idx = (self.char_idx - 1) % len(self.charset)

    def confirm_char(self) -> None:
        """Add current character to text and reset selection to first char."""
        self.chars.append(self.charset[self.char_idx])
        self.char_idx = 0

    def delete_char(self) -> bool:
        """Delete last confirmed character.

        Returns:
            True if a character was deleted, False if text was empty.
        """
        if self.chars:
            self.chars.pop()
            return True
        return False

    def get_display_text(self, show_cursor: bool = True) -> str:
        """Get text for simple display (without underline rendering).

        Args:
            show_cursor: If True, append current char. If False, append underscore.

        Returns:
            Display string including cursor indicator.
        """
        if show_cursor:
            return self.text + self.current_char
        return self.text + "_"

    def render(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        w: int,
        h: int,
        selected: bool = True,
        font: ImageFont.FreeTypeFont | None = None,
        padding: tuple[int, int] | None = None,
        prefix: str | None = None
    ) -> None:
        """Render the text input with underline cursor.

        Args:
            draw: PIL ImageDraw object to render onto.
            x, y, w, h: Bounding box for the input field.
            selected: Whether this input is currently selected (shows cursor).
            font: Font to use (defaults to cfg.FONT_MAIN).
            padding: (x, y) custom padding tuple (added to font padding).
            prefix: Optional prefix text to display before input (e.g., "Name: ").
        """
        font = font or cfg.FONT_MAIN
        cjk_font = cfg.FONT_CJK_HEADER if font == cfg.FONT_HEADER else cfg.FONT_CJK_MAIN

        # Combine font padding with custom padding
        font_pad = get_font_padding(font)
        custom_pad = padding or (0, 0)
        padding_x = font_pad[0] + custom_pad[0]
        padding_y = font_pad[1] + custom_pad[1]

        # Draw background box (inverted when selected)
        bg = cfg.BLACK if selected else cfg.WHITE
        fg = cfg.WHITE if selected else cfg.BLACK
        draw.rectangle((x, y, x + w, y + h), fill=bg, outline=cfg.BLACK)

        text_x = x + padding_x
        text_y = y + padding_y

        # Draw prefix text if provided
        if prefix:
            draw_text_with_cjk(draw, (text_x, text_y), prefix, font, cjk_font, fill=fg)
            text_x += get_text_width_with_cjk(prefix, font, cjk_font)

        # Draw entered text
        entered_text = self.text
        if entered_text:
            draw_text_with_cjk(draw, (text_x, text_y), entered_text, font, cjk_font, fill=fg)
            text_x += get_text_width_with_cjk(entered_text, font, cjk_font)

        if selected:
            # Draw current character with underline cursor
            current = self.current_char
            char_width = get_text_width_with_cjk(current, font, cjk_font)

            draw_text_with_cjk(draw, (text_x, text_y), current, font, cjk_font, fill=fg)

            # Underline beneath the character indicates cursor position
            underline_y = y + h - 1
            draw.line((text_x, underline_y, text_x + char_width, underline_y), fill=fg)


@dataclass
class Column:
    """A single column within a multi-column layout.

    Used for controls bars and settings items where content is arranged
    horizontally with individual column selection.

    Attributes:
        content: Text string or PIL Image to display.
        width: Column width in pixels, or None for auto-calculation.
        align: Text alignment ('left', 'center', 'right').
        active: Whether this column is in an active state (e.g., shuffle on).
    """

    content: str | Image.Image
    width: int | None = None
    align: str = 'left'
    active: bool = False


# Type alias for Item properties dict
ItemProps = dict[str, Any]


def extract_item_props(item: "Item | dict[str, Any] | None") -> ItemProps:
    """Extract properties from an Item or legacy dict in a unified way.

    This helper eliminates repeated isinstance checks throughout the codebase
    when working with mixed Item/dict item lists.

    Args:
        item: An Item instance, a legacy dict, or None.

    Returns:
        Dict with keys: kind, path, mode, heading, column_nav, selectable, text.
        All values are None/False/True defaults if the item doesn't provide them.
    """
    if item is None:
        return {
            'kind': None, 'path': None, 'mode': None,
            'heading': False, 'column_nav': False, 'selectable': True, 'text': None
        }

    if isinstance(item, Item):
        item_id = item.id if isinstance(item.id, dict) else {}
        return {
            'kind': item_id.get('kind'),
            'path': item_id.get('path'),
            'mode': item_id.get('mode'),
            'heading': item.heading,
            'column_nav': item.column_nav,
            'selectable': item.selectable,
            'text': item.text
        }

    # Legacy dict format
    item_id = item.get('id', {})
    if isinstance(item_id, dict):
        return {
            'kind': item_id.get('kind'),
            'path': item_id.get('path'),
            'mode': item_id.get('mode'),
            'heading': item.get('heading', False),
            'column_nav': item.get('column_nav', False),
            'selectable': item.get('selectable', True),
            'text': item.get('name') or item.get('text')
        }

    return {
        'kind': None, 'path': None, 'mode': None,
        'heading': item.get('heading', False),
        'column_nav': item.get('column_nav', False),
        'selectable': item.get('selectable', True),
        'text': item.get('name') or item.get('text')
    }


class Item:
    """Unified renderable item for menus and UI panels.

    This is the core building block for all menu-based UIs. Items can display
    various types of content (text, icons, columns, images) and have different
    behaviors (selectable, heading, text input).

    Content Types:
        - text: Simple label text
        - icon: Leading icon (string for text icon, Image for bitmap)
        - columns: Multi-column layout (list of strings or Column objects)
        - lines: Multi-line content (list of strings or nested lists)
        - image: Dithered image to display
        - text_input: TextInput instance for character entry

    Rendering Modes (mutually exclusive, checked in this order):
        1. show_volume: Volume slider bar
        2. text_input: Text input field with cursor
        3. show_image: Image display with border
        4. column_nav: Horizontal column navigation (controls bar)
        5. Info style: Non-selectable text/columns/lines
        6. Default: Simple text with optional icon, inverted when selected
    """

    def __init__(
        self,
        text: str | None = None,
        icon: str | Image.Image | None = None,
        columns: list[str | Column] | None = None,
        lines: list[str | list[str]] | None = None,
        image: Image.Image | None = None,
        placeholder: str | None = None,
        value: int = 0,
        # Rendering flags
        heading: bool = False,
        show_volume: bool = False,
        show_image: bool = False,
        column_nav: bool = False,
        # Behavior
        selectable: bool = True,
        pinned: bool = False,
        wrap_text: bool = False,
        font: ImageFont.FreeTypeFont | None = None,
        padding: tuple[int, int] | None = None,
        id: Any = None,
        # Text input support
        text_input: TextInput | None = None
    ) -> None:
        """Initialize a menu item.

        Args:
            text: Primary label text.
            icon: Leading icon (string char or PIL Image).
            columns: Column content for multi-column layouts.
            lines: Multi-line content.
            image: Image to display (for show_image mode).
            placeholder: Text shown when image is None.
            value: Numeric value (used for volume slider 0-100).
            heading: Render as section heading (inverted, uppercase).
            show_volume: Render as volume slider.
            show_image: Render as image display.
            column_nav: Enable horizontal column navigation.
            selectable: Whether this item can be selected.
            pinned: Keep item visible when scrolling.
            wrap_text: Enable text wrapping for long content.
            font: Custom font (defaults to FONT_MAIN).
            padding: Additional (x, y) padding beyond font default.
            id: Arbitrary identifier dict (typically has 'kind', 'path', 'mode').
            text_input: TextInput instance for character entry mode.
        """
        # Content
        self.text = text
        self.icon = icon
        self.columns = columns
        self.lines = lines
        self.image = image
        self.placeholder = placeholder or t('player.browse.no_image')
        self.value = value
        self.text_input = text_input

        # Rendering flags
        self.heading = heading
        self.show_volume = show_volume
        self.show_image = show_image
        self.column_nav = column_nav

        # Behavior
        self.selectable = selectable
        self.pinned = pinned
        self.wrap_text = wrap_text
        self.font = font
        self.padding = padding
        self.id = id

        # Internal caching for wrapped text
        self._wrapped_lines: list[str] = []
        self._last_width: int = 0
        self._height: int | None = None

    @property
    def kind(self) -> str | None:
        """Get content kind from id dict (convenience accessor)."""
        return self.id.get('kind') if isinstance(self.id, dict) else None

    def set_height(self, h: int) -> None:
        """Override the calculated height for this item."""
        self._height = h

    def get_height(self, width: int | None = None) -> int:
        """Calculate the height of this item in pixels.

        Args:
            width: Available width (needed for text wrapping calculation).

        Returns:
            Height in pixels (multiple of ROW_HEIGHT for most items).
        """
        if self._height is not None:
            return self._height

        # Info-style items (non-selectable with content)
        if not self.selectable or self.lines or (self.columns and not self.column_nav):
            if self.lines:
                return len(self.lines) * cfg.ROW_HEIGHT
            if self.text and not self.columns:
                if self.wrap_text:
                    # Compute wrapped lines if width changed
                    if width and width != self._last_width:
                        self._wrapped_lines = self._wrap_text(self.text, width)
                        self._last_width = width

                    if self._wrapped_lines:
                        return len(self._wrapped_lines) * cfg.ROW_HEIGHT

        return cfg.ROW_HEIGHT

    def get_column_count(self) -> int:
        """Get the number of navigable columns in this item."""
        if self.column_nav and self.columns:
            return len(self.columns)
        return 1

    def render(self, draw: ImageDraw.Draw, canvas: Image.Image,
               x: int, y: int, w: int, h: int,
               selected: bool = False, selected_col: int = -1,
               column_widths: list = None):
        """Unified render method.

        Args:
            column_widths: Optional pre-calculated column widths from menu
        """

        # Volume slider
        if self.show_volume:
            self._render_volume(draw, x, y, w, h)
            return

        # Text input with underline cursor (always render as selected/inverted for visibility)
        if self.text_input is not None:
            self.text_input.render(draw, x, y, w, h, selected=True,
                                   font=self.font, padding=self.padding,
                                   prefix=self.text)
            return

        # Image display
        if self.show_image:
            if self.image:
                # Paste image inside border
                canvas.paste(self.image, (x + 1, y + 1))
            else:
                placeholder_y = y + (h // 2) - (cfg.ROW_HEIGHT // 2)
                self._draw_text_box(draw, canvas, self.placeholder,
                                   x, placeholder_y, w, cfg.ROW_HEIGHT,
                                   invert=True, center=True)
            return

        # Column layout with navigation (controls bar)
        if self.column_nav and self.columns:
            self._render_column_layout(draw, canvas, x, y, w, h, selected, selected_col)
            return

        # Info-style rendering (non-selectable or has lines/columns without nav)
        if not self.selectable or self.lines or (self.columns and not self.column_nav):
            invert = (selected and self.selectable)
            if self.lines:
                self._render_multi_line(draw, canvas, x, y, w, invert=invert, column_widths=column_widths)
                return
            if self.columns:
                self._render_info_columns(draw, canvas, x, y, w, invert=invert, column_widths=column_widths)
                return
            if self.text:
                if self.wrap_text:
                    self._render_wrapped_text(draw, canvas, x, y, w, invert=invert)
                else:
                    self._draw_text_box(draw, canvas, self.text, x, y, w, cfg.ROW_HEIGHT,
                                       invert=invert, font=self.font, padding=self.padding)
                return

        # Heading rendering
        invert = self.heading or (selected and self.selectable)

        if self.heading:
             draw.rectangle((x, y, x + w, y + h), fill=cfg.BLACK)

        text = self.text or ""
        if self.heading:
            text = text.upper()

        if self.icon:
            self._render_text_with_icon(draw, canvas, text, x, y, w, h, invert)
        else:
            self._draw_text_box(draw, canvas, text, x, y, w, h, invert=invert)

        if self.heading and selected:
            draw.rectangle((x + 1, y + 1, x + w - 1, y + h - 1), outline=cfg.WHITE)

    def _render_text_with_icon(self, draw, canvas, text, x, y, w, h, invert):
        icon_w = 12
        if isinstance(self.icon, str):
            self._draw_text_box(draw, canvas, self.icon, x, y, icon_w, h,
                               invert=invert, center=True)
        else:
            icon = self.icon
            if invert:
                icon = ImageOps.invert(icon.convert('L')).convert('1')
            ix = x + (icon_w - icon.width) // 2
            iy = y + (h - icon.height) // 2
            if invert:
                draw.rectangle((x, y, x + icon_w - 1, y + h), fill=cfg.BLACK)
            canvas.paste(icon, (ix, iy))

        if invert:
            draw.line((x + icon_w, y + 1, x + icon_w, y + h), fill=cfg.WHITE)
        self._draw_text_box(draw, canvas, text, x + icon_w, y, w - icon_w, h,
                           invert=invert)

    def _render_volume(self, draw, x, y, w, h):
        btn_w = cfg.ROW_HEIGHT
        bar_w = w - (btn_w * 2)
        bar_x = x + btn_w

        for bx, sym in [(x, "-"), (x + w - btn_w, "+")]:
            draw.rectangle((bx, y, bx + btn_w , y + h ), outline=cfg.BLACK)
            draw.text((bx + (3 if sym == "-" else 2), y - 2), sym, font=cfg.FONT_HEADER, fill=cfg.BLACK)

        draw.rectangle((bar_x, y, bar_x + bar_w , y + h ), outline=cfg.BLACK)
        fill_w = int(bar_w * (self.value / 100.0))
        if fill_w > 0:
            draw.rectangle((bar_x, y, bar_x + fill_w , y + h ), fill=cfg.BLACK)

    def _render_column_layout(self, draw, canvas, x, y, w, h, selected, selected_col):
        widths = self._calculate_widths(w, len(self.columns))
        col_x = x
        for i, (col, col_w) in enumerate(zip(self.columns, widths)):
            if not isinstance(col, Column): continue
            is_col_selected = selected and (selected_col == i)
            invert = col.active or is_col_selected
            add_border = col.active and is_col_selected
            bg = cfg.BLACK if invert else cfg.WHITE
            fg = cfg.WHITE if invert else cfg.BLACK
            draw.rectangle((col_x, y, col_x + col_w , y + h ), fill=bg, outline=cfg.BLACK)
            if isinstance(col.content, str):
                self._draw_aligned_text(draw, col.content, col_x, y, col_w, h, col.align, fg)
            else:
                self._draw_icon_content(canvas, col.content, col_x, y, col_w, h, invert)
            if add_border:
                draw.rectangle((col_x + 1, y + 1, col_x + col_w - 1, y + h - 1), outline=fg)
            col_x += col_w

    def _draw_aligned_text(self, draw, text, x, y, w, h, align, fill):
        font = cfg.FONT_MAIN
        cjk_font = cfg.FONT_CJK_MAIN
        font_pad = get_font_padding(font)
        text_w = get_text_width_with_cjk(text, font, cjk_font)
        if align == 'center': text_x = x + (w - text_w) // 2
        elif align == 'right': text_x = x + w - text_w - font_pad[0]
        else: text_x = x + font_pad[0]
        draw_text_with_cjk(draw, (text_x, y + font_pad[1]), text, font, cjk_font, fill=fill)

    def _draw_icon_content(self, canvas, icon, x, y, w, h, invert):
        if invert: icon = ImageOps.invert(icon.convert('L')).convert('1')
        ix = x + (w - icon.width) // 2
        iy = y + (h - icon.height) // 2
        canvas.paste(icon, (ix, iy + 1), mask=icon if not invert else None)

    def _render_multi_line(self, draw, canvas, x, y, w, invert=False, column_widths=None):
        total_h = len(self.lines) * cfg.ROW_HEIGHT
        self._draw_container(draw, x, y, w, total_h, invert=invert)
        fg = cfg.WHITE if invert else cfg.BLACK
        font_pad = get_font_padding(cfg.FONT_MAIN)
        for i, line in enumerate(self.lines):
            line_y = y + (i * cfg.ROW_HEIGHT)
            if isinstance(line, list): self._render_plain_columns(draw, line, x, line_y, w, fg=fg, column_widths=column_widths)
            else: draw_text_with_cjk(draw, (x + font_pad[0], line_y + font_pad[1]), str(line), cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=fg)

    def _render_plain_columns(self, draw, columns, x, y, w, fg=cfg.BLACK, column_widths=None):
        if not columns: return
        font_pad = get_font_padding(cfg.FONT_MAIN)
        draw_text_with_cjk(draw, (x + font_pad[0], y + font_pad[1]), str(columns[0]), cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=fg)
        if len(columns) > 1:
            right_widths = column_widths if column_widths else self._calc_column_widths(columns, w)
            col_x = x + max(20, w - sum(right_widths))
            for i, col in enumerate(columns[1:]):
                col_w = right_widths[i] if i < len(right_widths) else 12
                self._draw_aligned_text(draw, str(col), col_x, y, col_w, cfg.ROW_HEIGHT, 'center', fg)
                col_x += col_w

    def _render_info_columns(self, draw, canvas, x, y, w, invert=False, column_widths=None):
        if not self.columns: return
        right_widths = column_widths if column_widths else self._calc_column_widths(self.columns, w)
        left_w = max(20, w - sum(right_widths)) if right_widths else w
        self._draw_text_box(draw, canvas, str(self.columns[0]), x, y, left_w, cfg.ROW_HEIGHT, invert=invert)
        col_x = x + left_w
        if invert:
            draw.line((col_x, y + 1, col_x, y + cfg.ROW_HEIGHT), fill=cfg.WHITE)
        for i, col in enumerate(self.columns[1:]):
            col_w = right_widths[i] if i < len(right_widths) else 12
            self._draw_text_box(draw, canvas, str(col), col_x, y, col_w, cfg.ROW_HEIGHT, center=True, invert=invert)
            col_x += col_w
            if invert and i < len(self.columns) - 2:
                draw.line((col_x, y + 1, col_x, y + cfg.ROW_HEIGHT), fill=cfg.WHITE)

    def _render_wrapped_text(self, draw, canvas, x, y, w, invert=False):
        if w != self._last_width:
            self._wrapped_lines = self._wrap_text(self.text, w)
            self._last_width = w
        lines = self._wrapped_lines
        if len(lines) == 1:
            self._draw_text_box(draw, canvas, lines[0], x, y, w, cfg.ROW_HEIGHT, invert=invert)
        else:
            total_h = len(lines) * cfg.ROW_HEIGHT
            self._draw_container(draw, x, y, w, total_h, invert=invert)
            fg = cfg.WHITE if invert else cfg.BLACK
            font = self.font or cfg.FONT_MAIN
            cjk_font = cfg.FONT_CJK_HEADER if font == cfg.FONT_HEADER else cfg.FONT_CJK_MAIN
            # Get font padding, then add custom padding on top
            font_pad = get_font_padding(font)
            custom_pad = self.padding or (0, 0)
            padding_x = font_pad[0] + custom_pad[0]
            padding_y = font_pad[1] + custom_pad[1]
            cjk_y_off = get_cjk_y_offset(font)
            for i, line in enumerate(lines):
                draw_text_with_cjk(draw, (x + padding_x, y + (i * cfg.ROW_HEIGHT) + padding_y), line, font, cjk_font, fill=fg, cjk_y_offset=cjk_y_off)

    def _draw_container(self, draw, x, y, w, h, invert=False):
        bg = cfg.BLACK if invert else cfg.WHITE
        draw.rectangle((x, y, x + w, y + h), fill=bg, outline=cfg.BLACK)

    def _draw_text_box(self, draw, canvas, text, x, y, w, h, invert=False, center=False, font=None, padding=None):
        if h < 1 or w < 1: return
        font = font or (self.font if self.font else cfg.FONT_MAIN)
        cjk_font = cfg.FONT_CJK_HEADER if font == cfg.FONT_HEADER else cfg.FONT_CJK_MAIN
        # Get font padding, then add custom padding on top
        font_pad = get_font_padding(font)
        custom_pad = padding or (self.padding if self.padding else (0, 0))
        padding_x = font_pad[0] + custom_pad[0]
        padding_y = font_pad[1] + custom_pad[1]
        cjk_y_off = get_cjk_y_offset(font)
        bg = cfg.BLACK if invert else cfg.WHITE
        fg = cfg.WHITE if invert else cfg.BLACK
        draw.rectangle((x, y, x + w, y + h), fill=bg, outline=cfg.BLACK)
        if center:
            text_w = get_text_width_with_cjk(text, font, cjk_font)
            draw_x = x + (w - text_w) // 2 + 1
        else: draw_x = x + padding_x
        draw_text_with_cjk(draw, (draw_x, y + padding_y), text, font, cjk_font, fill=fg, cjk_y_offset=cjk_y_off)

    def _calculate_widths(self, total_w: int, count: int) -> List[int]:
        if not self.columns: return []
        widths, fixed_total, auto_count = [], 0, 0
        for col in self.columns:
            if isinstance(col, Column) and col.width is not None:
                widths.append(col.width); fixed_total += col.width
            else: widths.append(None); auto_count += 1
        if auto_count > 0:
            auto_width = (total_w - fixed_total) // auto_count
            widths = [w if w is not None else auto_width for w in widths]
        return widths

    def _wrap_text(self, text: str, width: int) -> List[str]:
        font = self.font if self.font else cfg.FONT_MAIN
        # Get font padding, then add custom padding on top
        font_pad = get_font_padding(font)
        custom_pad = self.padding or (0, 0)
        padding_x = font_pad[0] + custom_pad[0]
        max_text_width = width - (padding_x * 2)
        temp = Image.new('1', (1, 1))
        temp_draw = ImageDraw.Draw(temp)
        words = text.split()
        if not words: return [text]
        lines, current_line = [], []
        for word in words:
            test_line = ' '.join(current_line + [word])
            if temp_draw.textbbox((0, 0), test_line, font=font)[2] <= max_text_width: current_line.append(word)
            else:
                if current_line: lines.append(' '.join(current_line))
                current_line = [word]
        if current_line: lines.append(' '.join(current_line))
        return lines

    def _calc_column_widths(self, columns, total_width):
        """Calculate column widths for a single item (fallback)."""
        return calc_menu_column_widths([self], total_width)

    def get_columns_for_width_calc(self):
        """Get columns from this item for width calculation."""
        if self.columns and not self.column_nav:
            return self.columns
        if self.lines:
            for line in self.lines:
                if isinstance(line, list):
                    return line
        return None


def calc_menu_column_widths(items, total_width):
    """Calculate column widths for items, grouping similar widths together.

    Args:
        items: List of Item objects
        total_width: Available width for content

    Returns:
        Dict mapping item index to list of column widths
    """
    if not items:
        return {}

    default_col_width = 12
    group_threshold = 32  # Group widths within this difference

    # Collect all column widths per item
    item_widths = {}
    max_cols = 0
    for idx, item in enumerate(items):
        cols = item.get_columns_for_width_calc() if hasattr(item, 'get_columns_for_width_calc') else None
        if cols and len(cols) > 1:
            max_cols = max(max_cols, len(cols) - 1)
            widths = []
            for col in cols[1:]:
                text_width = len(str(col)) * 6 + 8
                widths.append(max(default_col_width, text_width))
            item_widths[idx] = widths

    if not item_widths:
        return {}

    # For each column position, group similar widths
    col_groups = {}  # col_position -> list of (group_max, [item_indices])
    for col_pos in range(max_cols):
        # Collect widths for this column position
        widths_at_pos = []
        for idx, widths in item_widths.items():
            if col_pos < len(widths):
                widths_at_pos.append((widths[col_pos], idx))

        if not widths_at_pos:
            continue

        # Sort by width and group
        widths_at_pos.sort(key=lambda x: x[0])
        groups = []
        current_group = [widths_at_pos[0]]

        for w, idx in widths_at_pos[1:]:
            if w - current_group[0][0] <= group_threshold:
                current_group.append((w, idx))
            else:
                groups.append(current_group)
                current_group = [(w, idx)]
        groups.append(current_group)

        col_groups[col_pos] = groups

    # Build result: map item index to its column widths
    result = {}
    for idx, widths in item_widths.items():
        final_widths = []
        for col_pos, w in enumerate(widths):
            # Find which group this item belongs to for this column
            group_width = w
            if col_pos in col_groups:
                for group in col_groups[col_pos]:
                    if any(i == idx for _, i in group):
                        group_width = max(gw for gw, _ in group)
                        break
            final_widths.append(group_width)

        # Scale down if total exceeds available space
        total_right = sum(final_widths)
        if total_right + 20 > total_width:
            scale = (total_width - 20) / total_right if total_right > 0 else 1
            final_widths = [max(10, int(cw * scale)) for cw in final_widths]

        result[idx] = final_widths

    return result
