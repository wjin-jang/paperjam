from PIL import Image, ImageDraw
import config as cfg
from ui.views.core import Panel
from ui.views.items import Item


class ScreensaverRenderer:
    """Renderer for screensaver and shutdown views."""

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

    def clear(self):
        """Clear the canvas."""
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def render_screensaver(self, state):
        """Render screensaver with album art."""
        self.clear()

        # If no image, show simple IDLE text
        if not state.screensaver_image:
            panel = Panel(
                (cfg.SCREEN_WIDTH - 100) // 2,
                (cfg.SCREEN_HEIGHT - cfg.ROW_HEIGHT) // 2,
                100, cfg.ROW_HEIGHT
            )
            menu = panel.create_menu()
            menu.items = [Item(text="IDLE", selectable=False)]
            panel.render(self.canvas)
            return self.canvas

        # Render album art fullscreen or scaled
        img = state.screensaver_image
        img_w, img_h = img.size
                
        # Calculate panel size to fit image
        panel_w = img_w + 2
        panel_h = img_h + 2
        
        x = (cfg.SCREEN_WIDTH - panel_w) // 2
        y = (cfg.SCREEN_HEIGHT - panel_h) // 2
        
        # Create panel
        panel = Panel(x, y, panel_w, panel_h)
        menu = panel.create_menu()
        
        art_item = Item(show_image=True, image=img)
        art_item.set_height(panel_h - 2)
        menu.items = [art_item]
        
        panel.render(self.canvas)
        
        return self.canvas

    def render_shutdown(self, image=None):
        """Render shutdown screen."""
        self.clear()

        # Draw "POWER OFF" text
        text = "POWER OFF"
        w, h = 80, cfg.ROW_HEIGHT
        x = (cfg.SCREEN_WIDTH - w) - 8
        
        # If image provided, put text at bottom, image above
        if image:
            y_text = cfg.SCREEN_HEIGHT - h - 8
            # Image panel
            img_w, img_h = image.size
            img_x = (cfg.SCREEN_WIDTH - img_w - 2) // 2
            img_y = (cfg.SCREEN_HEIGHT - img_h - 2) // 2
            
            panel_img = Panel(img_x, img_y, img_w + 2, img_h + 2)
            menu_img = panel_img.create_menu()
            art_item = Item(show_image=True, image=image)
            art_item.set_height(img_h)
            menu_img.items = [art_item]
            panel_img.render(self.canvas)
        else:
            y_text = (cfg.SCREEN_HEIGHT - h) // 2

        # Text Panel
        panel_text = Panel(x, y_text, w, h)
        menu_text = panel_text.create_menu()
        menu_text.items = [Item(text=text, font=cfg.FONT_HEADER, padding=(2, 0), selectable=False)]
        panel_text.render(self.canvas)

        return self.canvas

    def render_welcome_tiled(self, covers, dialog_text, button_text):
        """Render tiled welcome screen with dialog."""
        self.clear()

        # 1. Draw tiled background
        cols = 5
        rows = 3
        tile_w = cfg.SCREEN_WIDTH // cols
        tile_h = cfg.SCREEN_HEIGHT // rows
        
        num_covers = len(covers)
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if num_covers > 0:
                    img = covers[idx]
                    if img:
                        # Resize if needed
                        if img.width != tile_w or img.height != tile_h:
                            img = img.resize((tile_w, tile_h))
                        self.canvas.paste(img, (c * tile_w, r * tile_h))
                    idx = (idx + 1) % num_covers

        # 2. Draw Dialog Overlay
        w = 180
        h = 96
        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - h) // 2

        # Create panel with white background (to cover tiles)
        panel = Panel(x, y, w, h, header=None)
        
        # Manually clear the area under the panel first
        self.draw.rectangle((x, y, x + w, y + h), fill=cfg.WHITE)
        
        menu = panel.create_menu()
        
        # Add text and button
        menu.items = [
            Item(text=dialog_text, padding=(5, 10), wrap_text=True, selectable=False),
            Item(text=button_text, selectable=True)
        ]
        
        # Select the button
        menu.cursor.row = 1
        menu.cursor.col = 0
        
        panel.render(self.canvas)

        return self.canvas
