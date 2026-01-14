"""
Main UI renderer - orchestrates view components.
"""
from PIL import Image

from ui.views.music_view import MusicViewRenderer
from ui.views.menu_view import MenuViewRenderer
from ui.views.screensaver_view import ScreensaverRenderer


class UIRenderer:
    """
    Main UI renderer that delegates to specialized view renderers.

    This class maintains backward compatibility while using modular
    view components internally.
    """

    def __init__(self):
        self._music_view = MusicViewRenderer()
        self._menu_view = MenuViewRenderer()
        self._screensaver_view = ScreensaverRenderer()

    def render_volume(self, title, volume_level) -> Image.Image:
        """Render volume control view."""
        return self._menu_view.render_volume(title, volume_level)

    def render_screensaver(self, state) -> Image.Image:
        """Render screensaver view."""
        return self._screensaver_view.render_screensaver(state)

    def render_music_view(self, state, view_items) -> Image.Image:
        """Render music player view."""
        return self._music_view.render(state, view_items)

    def render_menu(self, title, items, sel_idx, scroll_idx) -> Image.Image:
        """Render menu view."""
        return self._menu_view.render_menu(title, items, sel_idx, scroll_idx)

    def render_shutdown(self, image=None) -> Image.Image:
        """Render shutdown screen."""
        return self._screensaver_view.render_shutdown(image)

    def render_context_menu(self, state) -> Image.Image:
        """Render context menu overlay."""
        return self._music_view.render_context_menu(state)
