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
                 type: str = 'text',
                 icon: Union[str, Image.Image] = None,
                 columns: List[Union[str, Column]] = None,
                 lines: List = None,
                 image: Image.Image = None,
                 placeholder: str = "NO IMAGE",
                 value: int = 0,
                 selectable: bool = True,
                 pinned: bool = False,
                 font=None,
                 padding: tuple = None):
        self.text = text
        self.type = type
        self.icon = icon
        self.columns = columns
        self.lines = lines
        self.image = image
        self.placeholder = placeholder
        self.value = value
        self.selectable = selectable
        self.pinned = pinned
        self.font = font
        self.padding = padding
        
        # Internal state for text wrapping (info type)
        self._wrapped_lines: List[str] = []
        self._last_width: int = 0
        self._height: Optional[int] = None

    def set_height(self, h: int):
        self._height = h

    def get_height(self) -> int:
        if self._height is not None:
            return self._height
            
        if self.type == 'info':
            if self.lines:
                return len(self.lines) * cfg.ROW_HEIGHT
            if self.text and not self.columns:
                if self._wrapped_lines:
                    return len(self._wrapped_lines) * cfg.ROW_HEIGHT
        
        return cfg.ROW_HEIGHT

    def get_column_count(self) -> int:
        if self.type == 'column' and self.columns:
            return len(self.columns)
        return 1

    def render(self, draw: ImageDraw.Draw, canvas: Image.Image,
               x: int, y: int, w: int, h: int,
               selected: bool = False, selected_col: int = -1):
        """Unified render method."""
        
        # Handle 'volume' type separately as it's distinct
        if self.type == 'volume':
            self._render_volume(draw, x, y, w, h)
            return

        # Handle 'image' type
        if self.type == 'image':
            if self.image:
                canvas.paste(self.image, (x + 1, y + 1))
            else:
                placeholder_y = y + (h // 2) - (cfg.ROW_HEIGHT // 2)
                self._draw_text_box(draw, canvas, self.placeholder,
                                   x, placeholder_y, w, cfg.ROW_HEIGHT,
                                   invert=True, center=True)
            return

        # Handle 'column' type (complex iteration)
        if self.type == 'column' and self.columns:
            self._render_column_layout(draw, canvas, x, y, w, h, selected, selected_col)
            return

        # Handle 'info' type (lines, columns, or wrapped text)
        if self.type == 'info':
            if self.lines:
                self._render_multi_line(draw, canvas, x, y, w)
                return
            if self.columns:
                self._render_info_columns(draw, canvas, x, y, w)
                return
            # If text, fall through to text rendering (wrapped)
            if self.text:
                self._render_wrapped_text(draw, canvas, x, y, w)
                return

        # Handle 'text' and 'heading' types (and 'info' text fallback)
        # Setup specific attributes
        is_heading = (self.type == 'heading')
        invert = is_heading or (selected and self.selectable)
        bg_color = cfg.BLACK if is_heading else None # Only Heading forces black bg outside selection
        
        # Draw background if needed (Heading always black, Text only if selected handled by _draw_text_box internally mostly, but let's be explicit if needed)
        if is_heading:
             draw.rectangle((x, y, x + w, y + h), fill=cfg.BLACK)
        
        text = sanitize_text(self.text or "")
        if is_heading:
            text = text.upper()

        if self.icon:
            self._render_text_with_icon(draw, canvas, text, x, y, w, h, invert)
        else:
            self._draw_text_box(draw, canvas, text, x, y, w, h, invert=invert)

        # Draw selection outline for Heading if selected
        if is_heading and selected:
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
                draw.rectangle((x, y, x + icon_w, y + h), fill=cfg.BLACK)
            canvas.paste(icon, (ix, iy))
        
        self._draw_text_box(draw, canvas, text, x + icon_w, y, w - icon_w, h,
                           invert=invert)

    def _render_volume(self, draw, x, y, w, h):
        btn_w = cfg.ROW_HEIGHT
        bar_w = w - (btn_w * 2)
        bar_x = x + btn_w

        # Draw buttons
        for bx, sym in [(x, "-"), (x + w - btn_w, "+")]:
            draw.rectangle((bx, y, bx + btn_w, y + h), outline=cfg.BLACK)
            draw.text((bx + (3 if sym == "-" else 2), y - 2), sym, font=cfg.FONT_HEADER, fill=cfg.BLACK)

        # Draw bar
        draw.rectangle((bar_x, y, bar_x + bar_w, y + h), outline=cfg.BLACK)
        fill_w = int(bar_w * (self.value / 100.0))
        if fill_w > 0:
            draw.rectangle((bar_x, y, bar_x + fill_w, y + h), fill=cfg.BLACK)

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

            draw.rectangle((col_x, y, col_x + col_w, y + h), fill=bg, outline=cfg.BLACK)

            if isinstance(col.content, str):
                self._draw_aligned_text(draw, col.content, col_x, y, col_w, h, col.align, fg)
            else:
                self._draw_icon_content(canvas, col.content, col_x, y, col_w, h, invert)

            if add_border:
                draw.rectangle((col_x + 1, y + 1, col_x + col_w - 1, y + h - 1), outline=fg)
            
            col_x += col_w

    def _draw_aligned_text(self, draw, text, x, y, w, h, align, fill):
        text = sanitize_text(text)
        font = cfg.FONT_MAIN
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]

        if align == 'center':
            text_x = x + (w - text_w) // 2
        elif align == 'right':
            text_x = x + w - text_w - 5
        else:
            text_x = x + 5
        
        draw.text((text_x, y + 3), text, font=font, fill=fill)

    def _draw_icon_content(self, canvas, icon, x, y, w, h, invert):
        if invert:
            icon = ImageOps.invert(icon.convert('L')).convert('1')
        ix = x + (w - icon.width) // 2
        iy = y + (h - icon.height) // 2
        canvas.paste(icon, (ix, iy + 1), mask=icon if not invert else None)

    def _render_multi_line(self, draw, canvas, x, y, w):
        total_h = len(self.lines) * cfg.ROW_HEIGHT
        self._draw_container(draw, x, y, w, total_h)
        
        for i, line in enumerate(self.lines):
            line_y = y + (i * cfg.ROW_HEIGHT)
            if isinstance(line, list):
                # Render sub-columns without boxes
                self._render_plain_columns(draw, line, x, line_y, w)
            else:
                draw.text((x + 5, line_y + 3), sanitize_text(str(line)), font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _render_plain_columns(self, draw, columns, x, y, w):
        if not columns: return
        # Simple rendering for InfoItem lines list
        # First col left, rest calculated
        draw.text((x + 5, y + 3), sanitize_text(str(columns[0])), font=cfg.FONT_MAIN, fill=cfg.BLACK)
        
        if len(columns) > 1:
            # Calculate widths logic similar to others but simplified for just text
            right_widths = [max(20, len(sanitize_text(str(c))) * 6 + 8) for c in columns[1:]]
            total_right = sum(right_widths)
            
            # Check overflow
            if total_right + 20 > w:
                scale = (w - 20) / total_right if total_right > 0 else 1
                right_widths = [max(10, int(cw * scale)) for cw in right_widths]
            
            col_x = x + max(20, w - sum(right_widths))
            for i, col in enumerate(columns[1:]):
                col_w = right_widths[i]
                self._draw_aligned_text(draw, str(col), col_x, y, col_w, cfg.ROW_HEIGHT, 'center', cfg.BLACK)
                col_x += col_w

    def _render_info_columns(self, draw, canvas, x, y, w):
        # Render columns WITH boxes
        if not self.columns: return
        
        # First column takes remaining space
        right_widths = [max(20, len(sanitize_text(str(c))) * 6 + 8) for c in self.columns[1:]]
        total_right = sum(right_widths)
        left_w = w - total_right
        
        # Scale if needed
        if total_right + 20 > w:
            scale = (w - 20) / total_right if total_right > 0 else 1
            right_widths = [max(10, int(cw * scale)) for cw in right_widths]
            left_w = max(20, w - sum(right_widths))

        # Draw left
        self._draw_text_box(draw, canvas, sanitize_text(str(self.columns[0])), x, y, left_w, cfg.ROW_HEIGHT)
        
        # Draw right
        col_x = x + left_w
        for i, col in enumerate(self.columns[1:]):
            col_w = right_widths[i]
            self._draw_text_box(draw, canvas, sanitize_text(str(col)), col_x, y, col_w, cfg.ROW_HEIGHT, center=True)
            col_x += col_w

    def _render_wrapped_text(self, draw, canvas, x, y, w):
        if w != self._last_width:
            self._wrapped_lines = self._wrap_text(sanitize_text(self.text), w)
            self._last_width = w
            
        lines = self._wrapped_lines
        if len(lines) == 1:
            self._draw_text_box(draw, canvas, lines[0], x, y, w, cfg.ROW_HEIGHT)
        else:
            total_h = len(lines) * cfg.ROW_HEIGHT
            self._draw_container(draw, x, y, w, total_h)
            padding_x = self.padding[0] if self.padding else 5
            padding_y = self.padding[1] if self.padding else 3
            
            for i, line in enumerate(lines):
                draw.text((x + padding_x, y + (i * cfg.ROW_HEIGHT) + padding_y), line, font=self.font or cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_container(self, draw, x, y, w, h):
        """Draw a white container with black border."""
        draw.rectangle((x, y, x + w, y + h), fill=cfg.WHITE, outline=cfg.BLACK)

    def _draw_text_box(self, draw: ImageDraw.Draw, canvas: Image.Image,
                       text: str, x: int, y: int, w: int, h: int,
                       invert: bool = False, center: bool = False,
                       font=None, padding: tuple = None):
        """Draw a text box with optional inversion."""
        if h < 1 or w < 1: return

        font = font or (self.font if self.font else cfg.FONT_MAIN)
        padding = padding or (self.padding if self.padding else (5, 3))
        padding_x, padding_y = padding

        bg = cfg.BLACK if invert else cfg.WHITE
        fg = cfg.WHITE if invert else cfg.BLACK

        draw.rectangle((x, y, x + w, y + h), fill=bg, outline=cfg.BLACK)

        if center:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            draw_x = x + (w - text_w) // 2 + 1
        else:
            draw_x = x + padding_x

        draw.text((draw_x, y + padding_y), text, font=font, fill=fg)

    def _calculate_widths(self, total_w: int, count: int) -> List[int]:
        if not self.columns: return []
        widths = []
        fixed_total = 0
        auto_count = 0
        for col in self.columns:
            if isinstance(col, Column) and col.width is not None:
                widths.append(col.width)
                fixed_total += col.width
            else:
                widths.append(None)
                auto_count += 1
        
        if auto_count > 0:
            remaining = total_w - fixed_total
            auto_width = remaining // auto_count
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
        
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            if temp_draw.textbbox((0, 0), test_line, font=font)[2] <= max_text_width:
                current_line.append(word)
            else:
                if current_line: lines.append(' '.join(current_line))
                current_line = [word]
        if current_line: lines.append(' '.join(current_line))
        return lines

# For backward compatibility during transition (optional)
TextItem = lambda text, **kwargs: Item(text, type='text', **kwargs)
HeadingItem = lambda text, **kwargs: Item(text, type='heading', **kwargs)
InfoItem = lambda text=None, columns=None, lines=None, **kwargs: Item(text=text, type='info', columns=columns, lines=lines, **kwargs)
ColumnItem = lambda columns, **kwargs: Item(type='column', columns=columns, **kwargs)
ImageItem = lambda image=None, **kwargs: Item(type='image', image=image, **kwargs)
VolumeBarItem = lambda level, **kwargs: Item(type='volume', value=level, **kwargs)
