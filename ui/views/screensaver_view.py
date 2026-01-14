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
        """Render shutdown screen."""
        self.clear()

        # Draw background image
        if image:
            x = (cfg.SCREEN_WIDTH - image.width) // 2
            y = (cfg.SCREEN_HEIGHT - image.height) // 2
            self.draw_panel(x - 1, y - 1, image.width + 1, image.height + 1)
            self.canvas.paste(image, (x, y))

        # Draw '0' battery icon in top right corner
        if cfg.FONT_BATTERY:
            icon = "0"
            bbox = self.draw.textbbox((0, 0), icon, font=cfg.FONT_BATTERY)
            text_w = bbox[2] - bbox[0]
            bx = cfg.SCREEN_WIDTH - text_w - 8
            by = 0
            self.draw.text((bx, by), icon, font=cfg.FONT_BATTERY, fill=cfg.BLACK)

        # Draw "power off" text
        text = "power off"
        font = cfg.FONT_MAIN

        bbox = self.draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        x = cfg.SCREEN_WIDTH - w - 8
        y = cfg.SCREEN_HEIGHT - h - 8

        # Draw white backing for text
        self.draw.rectangle((x - 3, y - 1, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)
        self.draw.text((x, y), text, font=font, fill=cfg.BLACK)

        return self.canvas
