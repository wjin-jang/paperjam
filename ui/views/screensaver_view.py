from PIL import Image, ImageDraw
import config as cfg
from core.i18n import t
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
        panel_w = img_w + 1
        panel_h = img_h + 1

        x = cfg.SCREEN_WIDTH - panel_w - 108
        y = (cfg.SCREEN_HEIGHT - panel_h) // 2

        # Create panel
        panel = Panel(x, y, panel_w, panel_h)
        menu = panel.create_menu()

        art_item = Item(show_image=True, image=img)
        art_item.set_height(panel_h - 2)
        menu.items = [art_item]

        panel.render(self.canvas)

        # If playing a track, show track info panel
        if state.playing_path:
            self._render_track_info_panel(state)

        return self.canvas

    def _render_track_info_panel(self, state):
        """Render track info panel with title, album, artist, and status."""
        # Get status text with icon
        status_key = state.get_status_text()
        status_icon = cfg.STATUS_ICONS.get(status_key, '')

        # Get track info
        title = state.playing_title or ""
        artist = state.playing_artist or ""
        album = state.playing_album or ""

        # Panel dimensions
        info_w = 96
        info_h = cfg.ROW_HEIGHT * 3
        info_x = cfg.SCREEN_WIDTH - info_w - 4
        info_y = cfg.SCREEN_HEIGHT - info_h - 4

        # Create panel
        info_panel = Panel(info_x, info_y, info_w, info_h)
        info_menu = info_panel.create_menu()

        # Add items for status, title, artist, album
        info_menu.items = [
            Item(columns=[title,status_icon], font=cfg.FONT_HEADER, padding=(2, 0), selectable=False, sanitize=False),
            Item(text=album, padding=(2,3), selectable=False),
            Item(text=artist, padding=(2,3), selectable=False),
        ]

        info_panel.render(self.canvas)

    def render_shutdown(self, image=None):
        """Render shutdown screen."""
        self.clear()

        # Draw "POWER OFF" text
        text = "POWER OFF"
        w, h = 64, cfg.ROW_HEIGHT
        x = (cfg.SCREEN_WIDTH - w) - 8
        
        # If image provided, put text at bottom, image above
        if image:
            y_text = cfg.SCREEN_HEIGHT - h - 8
            # Image panel
            img_w, img_h = image.size
            img_x = (cfg.SCREEN_WIDTH - img_w - 2) // 2
            img_y = (cfg.SCREEN_HEIGHT - img_h - 2) // 2
            
            panel_img = Panel(img_x, img_y, img_w + 1, img_h + 1)
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

        # 1. Draw tiled background at original size, offset by half
        if covers:
            # Use original image size (no resizing)
            tile_w = covers[0].width
            tile_h = covers[0].height

            # Offset by half the tile size
            offset_x = tile_w // 2
            offset_y = tile_h // 2

            # Calculate how many tiles fit on screen (accounting for offset)
            cols = (cfg.SCREEN_WIDTH + offset_x) // tile_w + 1
            rows = (cfg.SCREEN_HEIGHT + offset_y) // tile_h + 1

            # Only show as many unique covers as we have (no repeating)
            idx = 0
            for r in range(rows):
                for c in range(cols):
                    if idx >= len(covers):
                        break
                    img = covers[idx]
                    if img:
                        try:
                            x = c * tile_w - offset_x
                            y = r * tile_h - offset_y
                            self.canvas.paste(img, (x, y))
                        except Exception:
                            pass
                    idx += 1
                if idx >= len(covers):
                    break

        # 2. Draw small panel with header
        panel_w = 130
        panel_h = cfg.ROW_HEIGHT * 2  # Header + one item row
        x = (cfg.SCREEN_WIDTH - panel_w) // 2
        y = (cfg.SCREEN_HEIGHT - panel_h) // 2

        panel = Panel(x, y, panel_w, panel_h, header=dialog_text)
        menu = panel.create_menu()
        menu.items = [Item(text=button_text, selectable=True)]
        menu.cursor.row = 0

        panel.render(self.canvas)

        return self.canvas
