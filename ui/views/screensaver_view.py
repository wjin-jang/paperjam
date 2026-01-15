"""
Screensaver and shutdown view rendering.
"""
import config as cfg
from ui.views.common import RenderBase


class ScreensaverRenderer(RenderBase):
    """Renderer for screensaver and shutdown views."""

    def render_screensaver(self, state):
        """Render screensaver with album art."""
        self.clear()

        img = state.screensaver_image
        if not img:
            self.draw_text_box("IDLE", 0, 73, 104, 20, center=True, font=cfg.FONT_HEADER)
        else:
            x = (cfg.SCREEN_WIDTH - img.width + 1) // 2
            y = (cfg.SCREEN_HEIGHT - img.height + 1) // 2
            self.draw_panel(x - 1, y - 1, img.width + 1, img.height + 1)
            self.canvas.paste(img, (x, y))

            # Draw status indicator with icon
            raw_status = state.get_status_text()
            icon = cfg.STATUS_ICONS.get(raw_status, 'Ⓘ')
            status_text = f"{icon}"

            pw = cfg.ROW_HEIGHT
            ph = cfg.ROW_HEIGHT
            px = x + img.width + 8
            py = y + img.height - ph

            self.draw_panel(px, py, pw, ph)
            self.draw_text_box(status_text, px, py, pw, ph, invert=False, padding=(2, 0), font=cfg.FONT_HEADER)

        return self.canvas

    def render_shutdown(self, image=None):
        """Render shutdown screen with cover art and POWER OFF text."""
        self.clear()

        # Draw background cover art
        if image:
            x = (cfg.SCREEN_WIDTH - image.width) // 2
            y = (cfg.SCREEN_HEIGHT - image.height) // 2
            self.draw_panel(x - 1, y - 1, image.width + 1, image.height + 1)
            self.canvas.paste(image, (x, y))

        # Draw "POWER OFF" text in bottom right with 8px padding
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
            # Offset between rows - stagger by half width
            x_spacing = cover_size + 4
            y_spacing = cover_size + 4
            row_offset = cover_size // 2 + 2

            # Start position - outside top-right corner
            start_x = cfg.SCREEN_WIDTH + 10
            start_y = -cover_size // 2

            cover_idx = 0
            row = 0
            y = start_y

            while y < cfg.SCREEN_HEIGHT + cover_size:
                # Offset every other row
                x = start_x - (row * row_offset)

                while x > -cover_size:
                    if cover_idx < len(covers) and covers[cover_idx]:
                        self.canvas.paste(covers[cover_idx], (x, y))
                    cover_idx = (cover_idx + 1) % max(1, len(covers))
                    x -= x_spacing

                row += 1
                y += y_spacing

        # Draw dialog box in center
        dialog_w = 140
        dialog_h = 36
        dialog_x = (cfg.SCREEN_WIDTH - dialog_w) // 2
        dialog_y = (cfg.SCREEN_HEIGHT - dialog_h) // 2

        self.draw_panel(dialog_x, dialog_y, dialog_w, dialog_h, header=dialog_text)

        # Draw button text
        self.draw_text_box(
            button_text, dialog_x, dialog_y + cfg.ROW_HEIGHT,
            dialog_w, cfg.ROW_HEIGHT * 2, center=True, invert=True
        )

        return self.canvas
