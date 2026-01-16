"""
Main UI renderer - orchestrates view components.
"""
from typing import Optional, Dict, Callable
from PIL import Image

from ui.views.music_view import MusicViewRenderer
from ui.views.menu_view import MenuViewRenderer
from ui.views.screensaver_view import ScreensaverRenderer
from ui.views.popup import PopupManager
from ui.overlays import OverlayRenderer


class UIRenderer:
    """
    Main UI renderer that delegates to specialized view renderers.

    Uses the new Panel → Menu → Item hierarchy internally while
    maintaining backward compatibility with existing API.
    """

    def __init__(self):
        self._music_view = MusicViewRenderer()
        self._menu_view = MenuViewRenderer()
        self._screensaver_view = ScreensaverRenderer()
        self.overlays = OverlayRenderer()
        self.popups = PopupManager()

    def render_volume(self, title, volume_level) -> Image.Image:
        """Render volume control view."""
        return self._menu_view.render_volume(title, volume_level)

    def render_screensaver(self, state) -> Image.Image:
        """Render screensaver view."""
        return self._screensaver_view.render_screensaver(state)

    def render_music_view(self, state, view_items) -> Image.Image:
        """Render music player view."""
        return self._music_view.render(state, view_items)

    def render_menu(self, title, items, sel_idx, scroll_idx, info_indices=None) -> Image.Image:
        """Render menu view."""
        return self._menu_view.render_menu(title, items, sel_idx, scroll_idx, info_indices=info_indices)

    def render_shutdown(self, image=None) -> Image.Image:
        """Render shutdown screen with cover art and POWER OFF text."""
        return self._screensaver_view.render_shutdown(image)

    def render_welcome_tiled(self, covers, dialog_text="WELCOME TO PAPERJAM", button_text="Continue...") -> Image.Image:
        """Render welcome screen with tiled album art and dialog box."""
        return self._screensaver_view.render_welcome_tiled(covers, dialog_text, button_text)

    def render_context_menu(self, state) -> Image.Image:
        """Render context menu overlay."""
        return self._music_view.render_context_menu(state)

    def render_with_popups(self, frame: Image.Image) -> Image.Image:
        """Apply popup overlays to a rendered frame.

        Args:
            frame: Base frame to render popups onto

        Returns:
            Frame with popups rendered
        """
        return self.popups.render(frame)

    def get_popup_callbacks(self) -> Optional[Dict[str, Callable]]:
        """Get callbacks if a popup is active.

        Returns:
            Callback dict for active popup, or None
        """
        return self.popups.get_callbacks()

    def has_active_popup(self) -> bool:
        """Check if there's an active popup.

        Returns:
            True if popup is active
        """
        return self.popups.has_active_popup()

    def popup_needs_refresh(self) -> bool:
        """Check if a popup expired and needs a display refresh.

        Returns:
            True if refresh needed (consumes the flag)
        """
        return self.popups.consume_refresh_flag()
