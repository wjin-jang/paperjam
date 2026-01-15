"""
Unified item rendering for all view types.

This module consolidates item rendering logic from menu_view and music_view
into a single, consistent system.
"""
from PIL import Image, ImageDraw, ImageOps
import config as cfg
from core.metadata import sanitize_text


class ItemRenderer:
    """Unified item rendering for panels.

    Handles all item types consistently:
    - text: Simple text item
    - info: Non-selectable info with columns/lines
    - heading: Section heading (black background)
    - controls: Controls bar with icon buttons
    - file, album, artist, dir, playlist, recent: Icon + text items
    """

    def __init__(self, draw: ImageDraw.Draw, canvas: Image.Image, content_offset_y: int = 0):
        """Create an item renderer.

        Args:
            draw: ImageDraw instance for rendering
            canvas: Canvas image to draw on
            content_offset_y: Y offset for content area (e.g., header height)
        """
        self.draw = draw
        self.canvas = canvas
        self.content_offset_y = content_offset_y

    def render_item(self, item, x: int, y: int, w: int, h: int,
                    is_selected: bool = False, context: dict = None) -> int:
        """Render an item and return the height consumed.

        Args:
            item: Item dict with 'type' and type-specific fields, or string
            x: X position
            y: Y position
            w: Width available
            h: Row height
            is_selected: Whether item is currently selected
            context: Optional context dict with state info for music view items

        Returns:
            Height consumed by this item
        """
        if isinstance(item, str):
            self._render_text(item, x, y, w, h, is_selected)
            return h

        item_type = item.get('type', 'text')

        if item_type == 'text':
            text = item.get('name', str(item))
            self._render_text(text, x, y, w, h, is_selected)
            return h

        if item_type == 'info':
            return self._render_info(item, x, y, w, h)

        if item_type == 'heading':
            self._render_heading(item, x, y, w, h, is_selected)
            return h

        if item_type == 'controls':
            # Controls are rendered by specialized method in music view
            # Return height but don't render (caller handles this)
            return h

        # Icon + text items (file, album, artist, dir, playlist, recent)
        if item_type in ('file', 'album', 'artist', 'dir', 'playlist', 'recent'):
            self._render_icon_text(item, x, y, w, h, is_selected, context)
            return h

        # Default: render as text
        text = item.get('name', str(item))
        self._render_text(text, x, y, w, h, is_selected)
        return h

    def get_item_height(self, item) -> int:
        """Get the height an item will consume.

        Args:
            item: Item dict or string

        Returns:
            Height in pixels
        """
        if isinstance(item, str):
            return cfg.ROW_HEIGHT

        if item.get('type') == 'info' and item.get('lines'):
            return len(item['lines']) * cfg.ROW_HEIGHT

        return cfg.ROW_HEIGHT

    def _render_text(self, text: str, x: int, y: int, w: int, h: int,
                     is_selected: bool, center: bool = False, font=None):
        """Render a text item."""
        self._draw_text_box(text, x, y, w, h, invert=is_selected,
                           center=center, font=font)

    def _render_info(self, item: dict, x: int, y: int, w: int, h: int) -> int:
        """Render an info item with columns/lines support.

        Returns height consumed.
        """
        lines = item.get('lines', [])

        if lines:
            for i, line in enumerate(lines):
                line_y = y + (i * cfg.ROW_HEIGHT)
                if isinstance(line, list):
                    self._render_columns(line, x, line_y, w, cfg.ROW_HEIGHT)
                else:
                    self._draw_text_box(sanitize_text(str(line)), x, line_y, w, cfg.ROW_HEIGHT)
            return len(lines) * cfg.ROW_HEIGHT

        columns = item.get('columns', [])
        if columns:
            self._render_columns(columns, x, y, w, h)
            return h

        # Single text info item
        name = sanitize_text(item.get('name', ''))
        self._draw_text_box(name, x, y, w, h)
        return h

    def _render_columns(self, columns: list, x: int, y: int, w: int, h: int):
        """Render a row with multiple columns.

        First column is left-aligned, remaining columns are right-aligned
        with calculated widths.
        """
        if not columns:
            return

        if len(columns) == 1:
            self._draw_text_box(sanitize_text(str(columns[0])), x, y, w, h)
            return

        # Calculate widths for right columns (~6px per char + padding)
        right_widths = []
        for col in columns[1:]:
            text = sanitize_text(str(col))
            col_w = max(20, len(text) * 6 + 8)
            right_widths.append(col_w)

        total_right = sum(right_widths)
        left_w = w - total_right

        # Scale down if columns don't fit
        if total_right + 20 > w:
            scale = (w - 20) / total_right if total_right > 0 else 1
            right_widths = [max(10, int(cw * scale)) for cw in right_widths]
            total_right = sum(right_widths)
            left_w = max(20, w - total_right)

        # Render left column
        self._draw_text_box(sanitize_text(str(columns[0])), x, y, left_w, h)

        # Render right columns (centered)
        col_x = x + left_w
        for i, col in enumerate(columns[1:]):
            col_w = right_widths[i]
            self._draw_text_box(sanitize_text(str(col)), col_x, y, col_w, h, center=True)
            col_x += col_w

    def _render_heading(self, item: dict, x: int, y: int, w: int, h: int, is_selected: bool):
        """Render a section heading (black background, white text)."""
        name = sanitize_text(item.get('name', '')).upper()
        abs_y = y + self.content_offset_y

        self.draw.rectangle((x, abs_y, x + w, abs_y + h - 1), fill=cfg.BLACK)
        self._draw_text_box(name, x, y, w, h, invert=True, font=cfg.FONT_MAIN)

        if is_selected:
            self.draw.rectangle((x + 1, abs_y + 1, x + w - 1, abs_y + h - 1), outline=cfg.WHITE)

    def _render_icon_text(self, item: dict, x: int, y: int, w: int, h: int,
                          is_selected: bool, context: dict = None):
        """Render an item with icon and text."""
        icon_w = 12
        icon_str = self._get_item_icon(item, context)

        self._draw_text_box(icon_str, x, y, icon_w, h, invert=is_selected, center=True)

        name = sanitize_text(item.get('title', item.get('name', '')))
        self._draw_text_box(name, x + icon_w, y, w - icon_w, h, invert=is_selected)

    def _get_item_icon(self, item: dict, context: dict = None) -> str:
        """Get the appropriate icon for an item."""
        itype = item.get('type')
        icons = cfg.MENU_ICONS

        # Check if this is the currently playing item
        if context:
            state = context.get('state')
            if state:
                is_playing = state.is_playing
                current_status_icon = icons.get('playing', 'Ⓟ') if is_playing else icons.get('paused', 'Ⓢ')

                is_active = False
                if itype == 'file' and state.playing_path:
                    if str(item.get('path')) == str(state.playing_path):
                        is_active = True
                elif itype == 'album' and state.playing_album:
                    if item.get('name') == state.playing_album:
                        is_active = True
                elif itype == 'artist' and state.playing_artist:
                    if item.get('name') == state.playing_artist:
                        is_active = True

                if is_active:
                    return current_status_icon

        # Item has explicit icon
        if 'icon' in item:
            icon = item['icon']
            # Handle stale 'P' icon from previous state
            if itype == 'file' and icon == 'P':
                track_num = item.get('track', 0)
                display_idx = context.get('display_idx') if context else None
                icon_val = track_num if track_num else display_idx
                return f"{icon_val}." if icon_val else ""
            if itype == 'file' and icon not in ('S', ''):
                return icon if icon.endswith('.') else f"{icon}."
            return icon

        # Default icons by type
        if itype == 'file':
            track_num = item.get('track', 0)
            display_idx = context.get('display_idx') if context else None
            icon_val = track_num if track_num else display_idx
            return f"{icon_val}." if icon_val else ""
        if itype == 'dir':
            return icons.get('dir', 'Ⓕ')
        if itype == 'artist':
            return icons.get('artist', 'Ⓐ')
        if itype == 'album':
            return icons.get('album', 'Ⓑ')
        if itype == 'recent':
            return icons.get('recent', 'Ⓡ')
        if itype == 'playlist':
            if "Fav" in item.get('name', ''):
                return icons.get('fav', 'Ⓗ')
            return icons.get('playlist', 'Ⓛ')

        return item.get('icon', '')

    def _draw_text_box(self, text: str, x: int, y: int, w: int, h: int,
                       invert: bool = False, padding: tuple = (5, 3),
                       center: bool = False, font=None):
        """Draw a text box with optional inversion."""
        if h < 1 or w < 1:
            return

        if font is None:
            font = cfg.FONT_MAIN

        abs_y = y + self.content_offset_y

        bg = cfg.BLACK if invert else cfg.WHITE
        fg = cfg.WHITE if invert else cfg.BLACK

        text_layer = Image.new('1', (w + 1, h + 1), bg)
        text_draw = ImageDraw.Draw(text_layer)
        text_draw.rectangle((0, 0, w, h), outline=cfg.BLACK)

        if center:
            bbox = text_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            draw_x = (w - text_w) // 2 + 1
            draw_y = padding[1]
        else:
            draw_x = padding[0]
            draw_y = padding[1]

        text_draw.text((draw_x, draw_y), text, font=font, fill=fg)
        self.canvas.paste(text_layer, (x, abs_y))
