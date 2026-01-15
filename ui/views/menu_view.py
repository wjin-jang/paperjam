"""
Menu view rendering using Panel → Menu → Item hierarchy.
"""
from PIL import Image, ImageDraw
import config as cfg
from ui.views.core import Panel
from ui.views.items import TextItem, InfoItem, ColumnItem, Column


class MenuViewRenderer:
    """Renderer for menu views using the new Panel/Menu system."""

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

    def clear(self):
        """Clear the canvas."""
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def _convert_legacy_item(self, item, is_info: bool):
        """Convert legacy item format to new Item classes.

        Args:
            item: String or dict in legacy format
            is_info: Whether item should be non-selectable info

        Returns:
            Item instance
        """
        # Already has 'type' field with 'info' and 'lines'
        if isinstance(item, dict) and item.get('type') == 'info' and item.get('lines'):
            return InfoItem(lines=item['lines'])

        # String item
        if isinstance(item, str):
            # Info item with colon notation -> columns
            if is_info and ':' in item:
                parts = item.split(':', 1)
                label = parts[0].strip()
                right_text = parts[1].strip() if len(parts) > 1 else ''
                if ',' in right_text:
                    right_cols = [c.strip() for c in right_text.split(',')]
                else:
                    right_cols = [right_text] if right_text else []
                return InfoItem(columns=[label] + right_cols)
            # Regular text
            if is_info:
                return InfoItem(text=item)
            return TextItem(item)

        # Dict with 'name' field
        if isinstance(item, dict):
            name = item.get('name', str(item))
            if is_info:
                return InfoItem(text=name)
            return TextItem(name)

        return TextItem(str(item))

    def _get_item_row_count(self, item) -> int:
        """Get the number of rows an item should span (legacy support)."""
        if isinstance(item, dict) and item.get('type') == 'info' and item.get('lines'):
            return len(item['lines'])
        return 1

    def _get_total_rows(self, items) -> int:
        """Get total row count including multi-line items."""
        return sum(self._get_item_row_count(item) for item in items)

    def render_menu(self, title, items, sel_idx, scroll_idx, info_indices=None):
        """Render a menu with title and items.

        Args:
            title: Menu title
            items: List of menu items (legacy format)
            sel_idx: Selected index (-1 for no selection)
            scroll_idx: Scroll offset (legacy, converted internally)
            info_indices: List of indices that are info-only

        Returns:
            Rendered canvas image
        """
        self.clear()
        if info_indices is None:
            info_indices = []

        # Calculate panel dimensions
        box_w = 160
        total_rows = self._get_total_rows(items)
        full_content_h = (total_rows * cfg.ROW_HEIGHT) + cfg.ROW_HEIGHT
        box_h = min(cfg.PANEL_H, full_content_h)
        box_x = (cfg.SCREEN_WIDTH - box_w) // 2
        box_y = (cfg.SCREEN_HEIGHT - box_h) // 2

        # Create panel and menu
        panel = Panel(box_x, box_y, box_w, box_h, header=title)
        menu = panel.create_menu()

        # Convert legacy items to new Item objects
        new_items = []
        for i, item in enumerate(items):
            is_info = i in info_indices
            new_items.append(self._convert_legacy_item(item, is_info))

        menu.items = new_items

        # Set cursor position based on sel_idx
        if sel_idx >= 0 and sel_idx < len(new_items):
            menu.cursor.row = sel_idx
            menu.cursor.col = 0
        else:
            menu.cursor.row = -1  # No selection

        # Set scroll offset
        menu.scroll_offset = scroll_idx

        # Render panel to canvas
        panel.render(self.canvas)

        return self.canvas

    def render_volume(self, title, volume_level):
        """Render volume control view.

        Args:
            title: Title text (e.g., "VOLUME")
            volume_level: Volume level 0-100

        Returns:
            Rendered canvas image
        """
        self.clear()

        panel_w = 160
        panel_h = cfg.ROW_HEIGHT * 2
        x = (cfg.SCREEN_WIDTH - panel_w) // 2
        y = (cfg.SCREEN_HEIGHT - panel_h) // 2

        # Create panel with header
        panel = Panel(x, y, panel_w, panel_h, header=f"{title} {int(volume_level)}%")
        menu = panel.create_menu()

        # Create volume bar as ColumnItem with 3 columns: [-] [bar] [+]
        bar_w = panel_w - (cfg.ROW_HEIGHT * 2)
        menu.items = [
            ColumnItem([
                Column(content="-", width=cfg.ROW_HEIGHT, align='center'),
                Column(content="", width=bar_w, align='left'),  # Bar placeholder
                Column(content="+", width=cfg.ROW_HEIGHT, align='center'),
            ], selectable=False)
        ]

        # Render panel
        panel.render(self.canvas)

        # Draw the volume bar fill on top (special case - progress bar)
        content_y = y + cfg.ROW_HEIGHT
        bar_x = x + cfg.ROW_HEIGHT
        fill_w = int(bar_w * (volume_level / 100.0))
        if fill_w > 0:
            self.draw.rectangle(
                (bar_x, content_y, bar_x + fill_w, content_y + cfg.ROW_HEIGHT),
                fill=cfg.BLACK
            )

        return self.canvas
