"""
Menu view rendering for settings and navigation menus.
"""
import math
import config as cfg
from ui.views.common import RenderBase, Panel
from ui.views.items import ItemRenderer
from ui.graphics import create_dithered_strip


class MenuViewRenderer(RenderBase):
    """Renderer for menu views."""

    def _get_item_row_count(self, item) -> int:
        """Get the number of rows an item should span."""
        if isinstance(item, dict) and item.get('type') == 'info' and item.get('lines'):
            return len(item['lines'])
        return 1

    def _get_total_rows(self, items) -> int:
        """Get total row count including multi-line items."""
        return sum(self._get_item_row_count(item) for item in items)

    def _to_unified_item(self, item, is_info: bool) -> dict:
        """Convert menu item to unified format for ItemRenderer.

        Args:
            item: Menu item (string or dict)
            is_info: Whether this item is in info_indices

        Returns:
            Unified item dict
        """
        # Already a dict with type
        if isinstance(item, dict) and 'type' in item:
            return item

        # String item
        if isinstance(item, str):
            # Info item with colon notation -> convert to columns
            if is_info and ':' in item:
                parts = item.split(':', 1)
                label = parts[0].strip()
                right_text = parts[1].strip() if len(parts) > 1 else ''
                if ',' in right_text:
                    right_cols = [c.strip() for c in right_text.split(',')]
                else:
                    right_cols = [right_text] if right_text else []
                return {'type': 'info', 'columns': [label] + right_cols}
            # Regular text or info without columns
            return {'type': 'info' if is_info else 'text', 'name': item}

        # Dict without type -> treat as text
        if isinstance(item, dict):
            return {'type': 'info' if is_info else 'text', 'name': item.get('name', str(item))}

        return {'type': 'text', 'name': str(item)}

    def render_menu(self, title, items, sel_idx, scroll_idx, info_indices=None):
        """Render a menu with title and items.

        Args:
            title: Menu title
            items: List of menu items (strings or dicts with 'lines' for multi-line)
            sel_idx: Selected index (-1 for no selection)
            scroll_idx: Scroll offset
            info_indices: List of indices that are info-only (non-selectable, rendered as columns)
        """
        self.clear()
        if info_indices is None:
            info_indices = []

        box_w = 160
        total_rows = self._get_total_rows(items)
        full_content_h = (total_rows * cfg.ROW_HEIGHT) + cfg.ROW_HEIGHT
        box_h = min(cfg.PANEL_H, full_content_h)
        box_x = (cfg.SCREEN_WIDTH - box_w) // 2
        box_y = (cfg.SCREEN_HEIGHT - box_h) // 2

        # Create panel for clipped rendering
        panel = self.create_panel(box_x, box_y, box_w, box_h, header=title)

        avail_list_h = box_h - cfg.ROW_HEIGHT
        needs_scrollbar = total_rows * cfg.ROW_HEIGHT > avail_list_h
        item_draw_w = box_w

        # Create item renderer for this panel
        item_renderer = ItemRenderer(panel.draw, panel.canvas, content_offset_y=panel.content_y)

        # Render items to panel (y positions are relative to panel content area)
        current_row = 0
        for abs_idx, item_obj in enumerate(items):
            row_count = self._get_item_row_count(item_obj)

            # Calculate y position relative to panel content area
            y_offset = current_row - scroll_idx
            y_pos = y_offset * cfg.ROW_HEIGHT

            is_selected = (sel_idx == abs_idx)
            is_info = abs_idx in info_indices

            # Convert to unified format
            unified_item = self._to_unified_item(item_obj, is_info)

            # Render using ItemRenderer
            item_renderer.render_item(
                unified_item, 0, y_pos, item_draw_w, cfg.ROW_HEIGHT,
                is_selected=is_selected
            )

            current_row += row_count

        # Composite panel onto canvas
        panel.composite(self.canvas)

        # Draw scrollbar on top if needed
        if needs_scrollbar:
            list_y = box_y + cfg.ROW_HEIGHT
            visible_rows = math.ceil(avail_list_h / cfg.ROW_HEIGHT)
            sb_h = avail_list_h
            self.canvas.paste(create_dithered_strip(8, sb_h), (box_x + box_w - 8, list_y))
            if total_rows > 0:
                handle_h = max(4, int(sb_h * (visible_rows / total_rows)))
                handle_y = list_y + int((sb_h - handle_h) * (scroll_idx / total_rows))
                self.draw.rectangle(
                    (box_x + box_w - 8, handle_y, box_x + box_w, handle_y + handle_h),
                    fill=cfg.WHITE, outline=cfg.BLACK
                )

        return self.canvas

    def render_volume(self, title, volume_level):
        """Render volume control view."""
        self.clear()

        panel_w = 160
        panel_h = cfg.ROW_HEIGHT * 2
        x = (cfg.SCREEN_WIDTH - panel_w) // 2
        y = (cfg.SCREEN_HEIGHT - panel_h) // 2

        self.draw_panel(x, y, panel_w, panel_h, header=f"{title} {int(volume_level)}%")
        self.draw_text_box('-', x, y + cfg.ROW_HEIGHT, cfg.ROW_HEIGHT, cfg.ROW_HEIGHT,
                          padding=(4, 0), font=cfg.FONT_HEADER)
        self.draw_text_box('+', x + panel_w - cfg.ROW_HEIGHT, y + cfg.ROW_HEIGHT,
                          cfg.ROW_HEIGHT, cfg.ROW_HEIGHT, padding=(4, 0), font=cfg.FONT_HEADER)

        # Draw volume bar fill
        bar_w = panel_w - (cfg.ROW_HEIGHT * 2)
        fill_w = int(bar_w * (volume_level / 100.0))
        bar_x = x + cfg.ROW_HEIGHT
        bar_y = y + cfg.ROW_HEIGHT
        bar_h = cfg.ROW_HEIGHT

        if fill_w > 0:
            self.draw.rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), fill=cfg.BLACK)

        return self.canvas
