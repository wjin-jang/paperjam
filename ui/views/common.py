"""
Common rendering utilities shared across view components.
"""
from PIL import Image, ImageDraw
import config as cfg


class RenderBase:
    """Base class with common rendering utilities."""

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

    def clear(self):
        """Clear the canvas."""
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def draw_panel(self, x, y, w, h, header=None):
        """Draw a panel with optional header."""
        self.draw.rectangle((x + 1, y + 1, x + w + 1, y + h + 1), outline=cfg.BLACK)
        self.draw.rectangle((x, y, x + w, y + h), fill=cfg.WHITE, outline=cfg.BLACK)
        if header:
            self.draw.rectangle((x, y, x + w, y + cfg.ROW_HEIGHT), fill=cfg.BLACK)
            self.draw.text((x + 5, y), header, font=cfg.FONT_HEADER, fill=cfg.WHITE)

    def draw_text_box(self, text, x, y, w, h, invert=False, padding=(5, 3),
                      center=False, font=None):
        """Draw a text box with optional inversion."""
        if h < 1:
            return
        if font is None:
            font = cfg.FONT_MAIN

        bg = cfg.BLACK if invert else cfg.WHITE
        fg = cfg.WHITE if invert else cfg.BLACK

        text_layer = Image.new('1', (w + 1, h + 1), bg)
        text_draw = ImageDraw.Draw(text_layer)
        text_draw.rectangle((0, 0, w, h), outline=cfg.BLACK)

        if center:
            bbox = text_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            draw_x = (w - text_w) // 2 + 1
            draw_y = padding[1]
        else:
            draw_x = padding[0]
            draw_y = padding[1]

        text_draw.text((draw_x, draw_y), text, font=font, fill=fg)
        self.canvas.paste(text_layer, (x, y))

    def get_canvas(self) -> Image.Image:
        """Return the current canvas."""
        return self.canvas
