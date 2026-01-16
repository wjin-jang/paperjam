"""
Screensaver and shutdown view rendering using Panel → Menu → Item hierarchy.
"""
from PIL import Image, ImageDraw
import config as cfg
from ui.views.core import Panel
from ui.views.items import TextItem, ImageItem


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

        img = state.screensaver_image
        if not img:
            # No image - show IDLE text centered
            panel_w = 104
            panel_h = cfg.ROW_HEIGHT
            x = (cfg.SCREEN_WIDTH - panel_w) // 2
            y = (cfg.SCREEN_HEIGHT - panel_h) // 2

            panel = Panel(x, y, panel_w, panel_h)
            menu = panel.create_menu()
            menu.items = [TextItem("IDLE", selectable=False)]
            panel.render(self.canvas)
        else:
            # Show album art in a panel
            x = (cfg.SCREEN_WIDTH - img.width) // 2
            y = (cfg.SCREEN_HEIGHT - img.height) // 2

            art_panel = Panel(x, y, img.width + 1, img.height + 1)
            art_menu = art_panel.create_menu()
            art_item = ImageItem(image=img)
            art_item.set_height(img.height)
            art_menu.items = [art_item]
            art_panel.render(self.canvas)

            # Draw status indicator panel
            raw_status = state.get_status_text()
            icon = cfg.STATUS_ICONS.get(raw_status, 'Ⓘ')

            pw = cfg.ROW_HEIGHT
            ph = cfg.ROW_HEIGHT
            px = x + img.width + 8
            py = y + img.height - ph

            # Draw panel manually for this small indicator
            self.draw.rectangle((px + 1, py + 1, px + pw + 1, py + ph + 1), outline=cfg.BLACK)
            self.draw.rectangle((px, py, px + pw, py + ph), fill=cfg.WHITE, outline=cfg.BLACK)
            # Center the icon text
            bbox = self.draw.textbbox((0, 0), icon, font=cfg.FONT_HEADER)
            text_w = bbox[2] - bbox[0]
            text_x = px + (pw - text_w) // 2
            self.draw.text((text_x + 1, py), icon, font=cfg.FONT_HEADER, fill=cfg.BLACK)

        return self.canvas

    def render_shutdown(self, image=None):
        """Render shutdown screen with cover art and POWER OFF text."""
        self.clear()

        # Draw background cover art in a panel
        if image:
            x = (cfg.SCREEN_WIDTH - image.width) // 2
            y = (cfg.SCREEN_HEIGHT - image.height) // 2

            art_panel = Panel(x, y, image.width + 1, image.height + 1)
            art_menu = art_panel.create_menu()
            art_item = ImageItem(image=image)
            art_item.set_height(image.height)
            art_menu.items = [art_item]
            art_panel.render(self.canvas)

        # Draw "POWER OFF" text in bottom right
        text = "POWER OFF"
        font = cfg.FONT_HEADER

        bbox = self.draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        x = cfg.SCREEN_WIDTH - w - 8
        y = cfg.SCREEN_HEIGHT - h - 8

        # Draw white backing for text
        self.draw.rectangle((x - 4, y - 2, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)
        self.draw.text((x, y), text, font=font, fill=cfg.BLACK)

        return self.canvas

    def render_welcome_tiled(self, covers, dialog_text="WELCOME TO PAPERJAM", button_text="Continue..."):
        """Render welcome screen with tiled album art and dialog box.

        Args:
            covers: List of small cover art images to tile
            dialog_text: Title text for dialog box
            button_text: Button text
        """
        self.clear()

        # Tile covers with regular offset, starting outside top-right
        if covers:
            cover_size = covers[0].width if covers else 40
            x_spacing = cover_size + 4
            y_spacing = cover_size + 4
            row_offset = cover_size // 2 + 2

            start_x = cfg.SCREEN_WIDTH + 10
            start_y = -cover_size // 2

            cover_idx = 0
            row = 0
            y = start_y

            while y < cfg.SCREEN_HEIGHT + cover_size:
                x = start_x - (row * row_offset)

                while x > -cover_size:
                    if cover_idx < len(covers) and covers[cover_idx]:
                        self.canvas.paste(covers[cover_idx], (x, y))
                    cover_idx = (cover_idx + 1) % max(1, len(covers))
                    x -= x_spacing

                row += 1
                y += y_spacing

        # Draw dialog box as a Panel
        dialog_w = 140
        dialog_h = cfg.ROW_HEIGHT * 2
        dialog_x = (cfg.SCREEN_WIDTH - dialog_w) // 2
        dialog_y = (cfg.SCREEN_HEIGHT - dialog_h) // 2

        panel = Panel(dialog_x, dialog_y, dialog_w, dialog_h, header=dialog_text)
        menu = panel.create_menu()
        menu.items = [TextItem(button_text, selectable=True)]
        menu.cursor.row = 0  # Select the button
        panel.render(self.canvas)

        return self.canvas
