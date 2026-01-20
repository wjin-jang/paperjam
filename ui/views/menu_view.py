from ui.views.core import Panel
from ui.views.items import Item
from PIL import Image, ImageDraw
import config as cfg
from core.i18n import t


class MenuViewRenderer:
    """Renderer for menu views using the new Panel/Menu system."""

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

    def clear(self):
        """Clear the canvas."""
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def render_menu(self, title, items, sel_idx, scroll_idx=0):
        """Render a menu with title and items.

        Args:
            title: Menu title
            items: List of Item objects
            sel_idx: Selected index (-1 for no selection)
            scroll_idx: Initial scroll offset in pixels

        Returns:
            Tuple of (Rendered canvas image, Updated scroll offset)
        """
        self.clear()

        # Calculate panel dimensions
        box_w = cfg.MENU_PANEL_WIDTH

        # Ensure all items are Item objects first (needed for height calculation)
        new_items = []
        for item in items:
            if isinstance(item, Item):
                new_items.append(item)
            elif isinstance(item, dict):
                new_items.append(Item(
                    text=item.get('name', ''),
                    heading=item.get('heading', False),
                    id=item.get('id'),
                    selectable=item.get('selectable', True)
                ))
            else:
                new_items.append(Item(text=str(item)))

        # Calculate actual content height based on item heights
        content_width = box_w - 2  # Account for borders
        full_content_h = sum(item.get_height(content_width) for item in new_items) + cfg.ROW_HEIGHT
        box_h = min(cfg.PANEL_H, full_content_h)
        box_x = (cfg.SCREEN_WIDTH - box_w) // 2
        box_y = (cfg.SCREEN_HEIGHT - box_h) // 2

        # Create panel and menu
        panel = Panel(box_x, box_y, box_w, box_h, header=title)
        menu = panel.create_menu()
        menu.scroll_offset = scroll_idx
        menu.items = new_items

        # Set cursor position based on sel_idx
        if sel_idx >= 0 and sel_idx < len(new_items):
            menu.cursor.row = sel_idx
            menu.cursor.col = 0
            # Auto-scroll to make selection visible
            menu._ensure_visible()
        else:
            menu.cursor.row = -1  # No selection

        # Render panel to canvas
        panel.render(self.canvas)

        return self.canvas, menu.scroll_offset

    def render_volume(self, title, volume_level):
        """Render volume control view using Panel → Menu → Item structure.

        Args:
            title: Title text (e.g., "VOLUME")
            volume_level: Volume level 0-100

        Returns:
            Rendered canvas image
        """
        self.clear()

        panel_w = cfg.MENU_PANEL_WIDTH
        panel_h = cfg.ROW_HEIGHT * 2
        x = (cfg.SCREEN_WIDTH - panel_w) // 2
        y = (cfg.SCREEN_HEIGHT - panel_h) // 2

        # Create panel with volume header
        header_text = f"{title or t('general.volume_popup')} {int(volume_level)}%"
        panel = Panel(x, y, panel_w, panel_h, header=header_text)
        menu = panel.create_menu()

        # Add volume bar item
        menu.items = [Item(show_volume=True, value=volume_level)]

        panel.render(self.canvas)

        return self.canvas