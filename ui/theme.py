"""
Theme and layout configuration for the UI.
Extracts display constants into a configurable structure.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
from pathlib import Path
from PIL import ImageFont


@dataclass
class LayoutConfig:
    """Screen layout measurements."""
    screen_width: int = 250
    screen_height: int = 122
    panel_x: int = 100
    panel_y: int = 8
    panel_w: int = 140
    panel_h: int = 104
    row_height: int = 12


@dataclass
class ColorConfig:
    """Color definitions for the display."""
    white: int = 255
    black: int = 0
    background: int = 255
    foreground: int = 0


@dataclass
class FontConfig:
    """Font configuration."""
    main_font: Optional[ImageFont.FreeTypeFont] = None
    header_font: Optional[ImageFont.FreeTypeFont] = None

    def __post_init__(self):
        if self.main_font is None or self.header_font is None:
            self._load_fonts()

    def _load_fonts(self):
        """Load fonts from assets directory."""
        base_path = Path(__file__).parent.parent / "assets"
        try:
            main_path = base_path / "BMmini.ttf"
            if main_path.exists():
                self.main_font = ImageFont.truetype(str(main_path), 9)
            else:
                self.main_font = ImageFont.load_default()

            header_path = base_path / "Nintendo-DS-BIOS.ttf"
            if header_path.exists():
                self.header_font = ImageFont.truetype(str(header_path), 16)
            else:
                self.header_font = ImageFont.load_default()
        except Exception:
            self.main_font = ImageFont.load_default()
            self.header_font = ImageFont.load_default()


@dataclass
class ThemeConfig:
    """Complete theme configuration combining layout, colors, and fonts."""
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    colors: ColorConfig = field(default_factory=ColorConfig)
    fonts: FontConfig = field(default_factory=FontConfig)

    # Convenience properties for backward compatibility
    @property
    def SCREEN_WIDTH(self) -> int:
        return self.layout.screen_width

    @property
    def SCREEN_HEIGHT(self) -> int:
        return self.layout.screen_height

    @property
    def PANEL_X(self) -> int:
        return self.layout.panel_x

    @property
    def PANEL_Y(self) -> int:
        return self.layout.panel_y

    @property
    def PANEL_W(self) -> int:
        return self.layout.panel_w

    @property
    def PANEL_H(self) -> int:
        return self.layout.panel_h

    @property
    def ROW_HEIGHT(self) -> int:
        return self.layout.row_height

    @property
    def WHITE(self) -> int:
        return self.colors.white

    @property
    def BLACK(self) -> int:
        return self.colors.black

    @property
    def FONT_MAIN(self) -> ImageFont.FreeTypeFont:
        return self.fonts.main_font

    @property
    def FONT_HEADER(self) -> ImageFont.FreeTypeFont:
        return self.fonts.header_font


# Global default theme instance
_default_theme: Optional[ThemeConfig] = None


def get_theme() -> ThemeConfig:
    """Get or create the default theme configuration."""
    global _default_theme
    if _default_theme is None:
        _default_theme = ThemeConfig()
    return _default_theme


def create_inverted_theme() -> ThemeConfig:
    """Create an inverted color theme."""
    return ThemeConfig(
        colors=ColorConfig(
            white=0,
            black=255,
            background=0,
            foreground=255
        )
    )
