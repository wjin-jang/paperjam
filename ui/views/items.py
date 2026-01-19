"""
Menu item classes for the UI rendering system.

This module provides the building blocks for menu-based UIs.
All items are now instances of the unified Item class, configured via parameters.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Union, Optional, Any
from PIL import Image, ImageDraw, ImageOps

import config as cfg
from core.metadata import sanitize_text
from core.i18n import t
from ui.graphics import draw_text_with_cjk, get_text_width_with_cjk


@dataclass
class Column:
    """A single column within a multi-column layout."""
    content: Union[str, Image.Image]  # Text string or PIL Image
    width: Optional[int] = None  # None = auto-calculate
    align: str = 'left'  # 'left', 'center', 'right'
    active: bool = False  # For toggle states (e.g., shuffle on)


class Item:
    """Unified renderable item for menus."""

    def __init__(self,
                 text: str = None,
                 icon: Union[str, Image.Image] = None,
                 columns: List[Union[str, Column]] = None,
                 lines: List = None,
                 image: Image.Image = None,
                 placeholder: str = None,
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
                 font=None,
                 padding: tuple = None,
                 id: Any = None,
                 sanitize: bool = True):
        # Content
        self.text = text
        self.icon = icon
        self.columns = columns
        self.lines = lines
        self.image = image
        self.placeholder = placeholder or t('player.browse.no_image')
        self.value = value

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
        self.sanitize = sanitize

        self._wrapped_lines: List[str] = []
        self._last_width: int = 0
        self._height: Optional[int] = None

    @property
    def kind(self) -> Optional[str]:
        """Get content kind from id dict."""
        return self.id.get('kind') if isinstance(self.id, dict) else None

    def set_height(self, h: int):
        self._height = h

    def get_height(self, width: Optional[int] = None) -> int:
        if self._height is not None:
            return self._height

        # Info-style items (non-selectable with content)
        if not self.selectable or self.lines or (self.columns and not self.column_nav):
            if self.lines:
                return len(self.lines) * cfg.ROW_HEIGHT
            if self.text and not self.columns:
                if self.wrap_text:
                    # Eagerly compute wrapped lines if width is provided
                    if width and width != self._last_width:
                        self._wrapped_lines = self._wrap_text(sanitize_text(self.text), width)
                        self._last_width = width

                    if self._wrapped_lines:
                        return len(self._wrapped_lines) * cfg.ROW_HEIGHT

        return cfg.ROW_HEIGHT

    def get_column_count(self) -> int:
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
                    display_text = sanitize_text(self.text) if self.sanitize else self.text
                    self._draw_text_box(draw, canvas, display_text, x, y, w, cfg.ROW_HEIGHT,
                                       invert=invert, font=self.font, padding=self.padding)
                return

        # Heading rendering
        invert = self.heading or (selected and self.selectable)

        if self.heading:
             draw.rectangle((x, y, x + w, y + h), fill=cfg.BLACK)

        text = sanitize_text(self.text or "") if self.sanitize else (self.text or "")
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
                col_text = sanitize_text(col.content) if self.sanitize else col.content
                self._draw_aligned_text(draw, col_text, col_x, y, col_w, h, col.align, fg)
            else:
                self._draw_icon_content(canvas, col.content, col_x, y, col_w, h, invert)
            if add_border:
                draw.rectangle((col_x + 1, y + 1, col_x + col_w - 1, y + h - 1), outline=fg)
            col_x += col_w

    def _draw_aligned_text(self, draw, text, x, y, w, h, align, fill):
        font = cfg.FONT_MAIN
        cjk_font = cfg.FONT_CJK_MAIN
        text_w = get_text_width_with_cjk(text, font, cjk_font)
        if align == 'center': text_x = x + (w - text_w) // 2
        elif align == 'right': text_x = x + w - text_w - 5
        else: text_x = x + 5
        draw_text_with_cjk(draw, (text_x, y + 1), text, font, cjk_font, fill=fill)

    def _draw_icon_content(self, canvas, icon, x, y, w, h, invert):
        if invert: icon = ImageOps.invert(icon.convert('L')).convert('1')
        ix = x + (w - icon.width) // 2
        iy = y + (h - icon.height) // 2
        canvas.paste(icon, (ix, iy + 1), mask=icon if not invert else None)

    def _render_multi_line(self, draw, canvas, x, y, w, invert=False, column_widths=None):
        total_h = len(self.lines) * cfg.ROW_HEIGHT
        self._draw_container(draw, x, y, w, total_h, invert=invert)
        fg = cfg.WHITE if invert else cfg.BLACK
        for i, line in enumerate(self.lines):
            line_y = y + (i * cfg.ROW_HEIGHT)
            if isinstance(line, list): self._render_plain_columns(draw, line, x, line_y, w, fg=fg, column_widths=column_widths)
            else: draw_text_with_cjk(draw, (x + 5, line_y + 1), sanitize_text(str(line)), cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=fg)

    def _render_plain_columns(self, draw, columns, x, y, w, fg=cfg.BLACK, column_widths=None):
        if not columns: return
        col0_text = sanitize_text(str(columns[0])) if self.sanitize else str(columns[0])
        draw_text_with_cjk(draw, (x + 5, y + 1), col0_text, cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=fg)
        if len(columns) > 1:
            right_widths = column_widths if column_widths else self._calc_column_widths(columns, w)
            col_x = x + max(20, w - sum(right_widths))
            for i, col in enumerate(columns[1:]):
                col_w = right_widths[i] if i < len(right_widths) else 12
                col_text = sanitize_text(str(col)) if self.sanitize else str(col)
                self._draw_aligned_text(draw, col_text, col_x, y, col_w, cfg.ROW_HEIGHT, 'center', fg)
                col_x += col_w

    def _render_info_columns(self, draw, canvas, x, y, w, invert=False, column_widths=None):
        if not self.columns: return
        right_widths = column_widths if column_widths else self._calc_column_widths(self.columns, w)
        left_w = max(20, w - sum(right_widths)) if right_widths else w
        col0_text = sanitize_text(str(self.columns[0])) if self.sanitize else str(self.columns[0])
        self._draw_text_box(draw, canvas, col0_text, x, y, left_w, cfg.ROW_HEIGHT, invert=invert)
        col_x = x + left_w
        if invert:
            draw.line((col_x, y + 1, col_x, y + cfg.ROW_HEIGHT), fill=cfg.WHITE)
        for i, col in enumerate(self.columns[1:]):
            col_w = right_widths[i] if i < len(right_widths) else 12
            col_text = sanitize_text(str(col)) if self.sanitize else str(col)
            self._draw_text_box(draw, canvas, col_text, col_x, y, col_w, cfg.ROW_HEIGHT, center=True, invert=invert)
            col_x += col_w
            if invert and i < len(self.columns) - 2:
                draw.line((col_x, y + 1, col_x, y + cfg.ROW_HEIGHT), fill=cfg.WHITE)

    def _render_wrapped_text(self, draw, canvas, x, y, w, invert=False):
        if w != self._last_width:
            self._wrapped_lines = self._wrap_text(sanitize_text(self.text), w)
            self._last_width = w
        lines = self._wrapped_lines
        if len(lines) == 1:
            self._draw_text_box(draw, canvas, lines[0], x, y, w, cfg.ROW_HEIGHT, invert=invert)
        else:
            total_h = len(lines) * cfg.ROW_HEIGHT
            self._draw_container(draw, x, y, w, total_h, invert=invert)
            padding_x = self.padding[0] if self.padding else 5
            padding_y = self.padding[1] if self.padding else 3
            fg = cfg.WHITE if invert else cfg.BLACK
            font = self.font or cfg.FONT_MAIN
            cjk_font = cfg.FONT_CJK_HEADER if font == cfg.FONT_HEADER else cfg.FONT_CJK_MAIN
            for i, line in enumerate(lines):
                draw_text_with_cjk(draw, (x + padding_x, y + (i * cfg.ROW_HEIGHT) + padding_y), line, font, cjk_font, fill=fg)

    def _draw_container(self, draw, x, y, w, h, invert=False):
        bg = cfg.BLACK if invert else cfg.WHITE
        draw.rectangle((x, y, x + w, y + h), fill=bg, outline=cfg.BLACK)

    def _draw_text_box(self, draw, canvas, text, x, y, w, h, invert=False, center=False, font=None, padding=None):
        if h < 1 or w < 1: return
        font = font or (self.font if self.font else cfg.FONT_MAIN)
        cjk_font = cfg.FONT_CJK_HEADER if font == cfg.FONT_HEADER else cfg.FONT_CJK_MAIN
        padding = padding or (self.padding if self.padding else (5, 3))
        padding_x, padding_y = padding
        bg = cfg.BLACK if invert else cfg.WHITE
        fg = cfg.WHITE if invert else cfg.BLACK
        draw.rectangle((x, y, x + w, y + h), fill=bg, outline=cfg.BLACK)
        if center:
            text_w = get_text_width_with_cjk(text, font, cjk_font)
            draw_x = x + (w - text_w) // 2 + 1
        else: draw_x = x + padding_x
        draw_text_with_cjk(draw, (draw_x, y + padding_y), text, font, cjk_font, fill=fg)

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
        padding_x = self.padding[0] if self.padding else 5
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
                text_width = len(sanitize_text(str(col))) * 6 + 8
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
