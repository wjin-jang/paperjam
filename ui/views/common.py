"""
Common rendering utilities shared across view components.
"""
from PIL import Image, ImageDraw
import config as cfg


class Panel:
    """A clipped rendering panel with shadow support.

    Items drawn to a panel are automatically clipped to the panel bounds.
    When composited, the panel renders with a drop shadow effect.
    """

    def __init__(self, x: int, y: int, w: int, h: int, header: str = None):
        """Create a new panel.

        Args:
            x: X position on parent canvas
            y: Y position on parent canvas
            w: Panel width
            h: Panel height
            header: Optional header text
        """
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.header = header

        # Header takes up one row
        self.content_y = cfg.ROW_HEIGHT if header else 0
        self.content_h = h - self.content_y

        # Create panel canvas (content area only)
        self.canvas = Image.new('1', (w, h), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

        # Draw header if present
        if header:
            self.draw.rectangle((0, 0, w - 1, cfg.ROW_HEIGHT), fill=cfg.BLACK)
            self.draw.text((5, 0), header, font=cfg.FONT_HEADER, fill=cfg.WHITE)

    def draw_text_box(self, text: str, x: int, y: int, w: int, h: int,
                      invert: bool = False, padding: tuple = (5, 3),
                      center: bool = False, font=None):
        """Draw a text box on the panel, clipped to panel bounds.

        Args:
            text: Text to draw
            x: X position relative to panel content area
            y: Y position relative to panel content area
            w: Box width
            h: Box height
            invert: Whether to invert colors
            padding: (x, y) padding tuple
            center: Whether to center text
            font: Optional font override
        """
        if h < 1 or w < 1:
            return

        if font is None:
            font = cfg.FONT_MAIN

        # Offset y by content area
        abs_y = y + self.content_y

        # Clip to panel bounds
        if abs_y >= self.h or abs_y + h <= self.content_y:
            return  # Completely outside

        # Clip height to panel bounds
        if abs_y + h > self.h:
            h = self.h - abs_y
        if abs_y < self.content_y:
            clip_top = self.content_y - abs_y
            abs_y = self.content_y
            h -= clip_top
            y += clip_top

        if h < 1:
            return

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
        self.canvas.paste(text_layer, (x, abs_y))

    def paste_image(self, img: Image.Image, x: int, y: int):
        """Paste an image onto the panel, clipped to bounds.

        Args:
            img: Image to paste
            x: X position relative to panel
            y: Y position relative to panel content area
        """
        abs_y = y + self.content_y

        # Clip to panel bounds
        if abs_y >= self.h or x >= self.w:
            return
        if abs_y + img.height <= self.content_y or x + img.width <= 0:
            return

        self.canvas.paste(img, (x, abs_y))

    def composite(self, target: Image.Image, shadow: bool = True):
        """Composite the panel onto a target canvas.

        Args:
            target: Target canvas to draw on
            shadow: Whether to draw drop shadow
        """
        target_draw = ImageDraw.Draw(target)

        # Draw shadow first (offset by 1 pixel)
        if shadow:
            target_draw.rectangle(
                (self.x + 1, self.y + 1, self.x + self.w + 1, self.y + self.h + 1),
                outline=cfg.BLACK
            )

        # Draw panel border
        target_draw.rectangle(
            (self.x, self.y, self.x + self.w, self.y + self.h),
            outline=cfg.BLACK
        )

        # Paste panel content
        target.paste(self.canvas, (self.x, self.y))


class RenderBase:
    """Base class with common rendering utilities."""

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

    def clear(self):
        """Clear the canvas."""
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def create_panel(self, x: int, y: int, w: int, h: int, header: str = None) -> Panel:
        """Create a new Panel for clipped rendering.

        Args:
            x: X position on canvas
            y: Y position on canvas
            w: Panel width
            h: Panel height
            header: Optional header text

        Returns:
            Panel object for drawing items
        """
        return Panel(x, y, w, h, header)

    def draw_panel(self, x, y, w, h, header=None):
        """Draw a panel with optional header (legacy method)."""
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
