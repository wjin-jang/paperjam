"""
Welcome application for first-run experience.

Handles the initial setup flow:
1. Welcome screen with options to scan or shutdown
2. Library scanning with progress display
3. Tiled album art welcome screen
"""
import time
from typing import Callable, Optional, Dict

from ui.renderer import UIRenderer
from ui.menu import MenuController
import config as cfg
from core.i18n import t
from core.logger import setup_logger
from apps.base import AppBase

logger = setup_logger()


class WelcomeApp(AppBase):
    """First-run welcome and setup application."""

    def __init__(self, library_manager, input_handler):
        super().__init__(name="Welcome")
        self.lib = library_manager
        self.inputs = input_handler
        self.renderer = UIRenderer()

        self.running = True
        self.view = 'CHOICE'  # CHOICE, SCANNING, WELCOME
        self.first_render = True
        
        # Menu Controllers
        self.choice_menu = MenuController([])
        
        # Callback for system operations
        self._shutdown_callback: Optional[Callable] = None
        self._display_callback: Optional[Callable] = None

        # Cache for welcome screen covers (loaded once)
        self._welcome_covers = None

    def set_shutdown_callback(self, callback: Callable):
        """Set callback for shutdown action."""
        self._shutdown_callback = callback

    def set_display_callback(self, callback: Callable):
        """Set callback for display updates."""
        self._display_callback = callback

    def get_callbacks(self) -> Dict[str, Callable]:
        """Get input callbacks for current view."""
        if self.view == 'CHOICE':
            return {
                'up': lambda: self.choice_menu.move_selection(-1),
                'down': lambda: self.choice_menu.move_selection(1),
                'enter': self._choice_enter
            }
        elif self.view == 'WELCOME':
            return {
                'enter': self._welcome_continue,
                'up': lambda: None,
                'down': lambda: None
            }
        return {}

    def _choice_enter(self):
        item = self.choice_menu.get_selected_item()
        if not item: return
        
        if item.get('action') == 'SCAN':
            # Scan now
            self.view = 'SCANNING'
            self.lib.scan_async(force=True)
        elif item.get('action') == 'SHUTDOWN':
            # Shutdown to add music
            if self._shutdown_callback:
                self._shutdown_callback()
            else:
                self.running = False

    def _welcome_continue(self):
        self.running = False

    def update(self) -> bool:
        """Update app state."""
        if self.view == 'SCANNING':
            if not self.lib.is_scanning:
                # Scan complete - show welcome screen
                self.view = 'WELCOME'
                self.first_render = True
        return self.running

    def get_frame(self):
        """Render current view."""
        if self.view == 'CHOICE':
            return self._render_choice()
        elif self.view == 'SCANNING':
            return self._render_scanning()
        elif self.view == 'WELCOME':
            return self._render_welcome()
        return self.renderer.render_menu(t('welcome.welcome'), [t('general.loading')], 0, 0)

    def _render_choice(self):
        """Render choice screen with multi-line info."""
        # Truncate path if too long
        music_path = str(cfg.MUSIC_PATH)
        if len(music_path) > 22:
            music_path = music_path[:22]

        if not self.choice_menu.items:
            # Build menu items
            items = [
                {'name': t('welcome.music_found', path=music_path), 'type': 'info', 'lines': [t('welcome.music_found', path=music_path)]},
                {'name': t('welcome.scan_now'), 'type': 'file', 'action': 'SCAN'},
                {'name': t('welcome.shutdown_add_music'), 'type': 'file', 'action': 'SHUTDOWN'}
            ]
            self.choice_menu.set_items(items)

        return self.renderer.render_menu(
            t('welcome.welcome'), **self.choice_menu.get_render_args()
        )

    def _render_scanning(self):
        """Render scanning progress."""
        items = [
            {'name': t('welcome.scanning_tracks', count=self.lib.scan_track_count), 'type': 'info'},
            {'name': f"{t('settings.library.albums')}: {self.lib.scan_album_count}", 'type': 'info'},
            {'name': f"{t('settings.library.artists')}: {self.lib.scan_artist_count}", 'type': 'info'}
        ]

        if self.lib.scan_current_file:
            current = self.lib.scan_current_file[:22]
            items.append({'name': f"{t('welcome.file')}: {current}", 'type': 'info'})

        return self.renderer.render_menu(
            t('welcome.scanning'), items, -1, 0, info_indices=[0, 1, 2, 3] # Still passed manually for pure info screen
        )

    def _render_welcome(self):
        """Render tiled album art welcome screen."""
        # Load covers only once to avoid lag
        if self._welcome_covers is None:
            self._welcome_covers = self.lib.get_random_covers(count=15, small=True)

        return self.renderer.render_welcome_tiled(
            self._welcome_covers,
            dialog_text=t('welcome.title'),
            button_text=t('welcome.continue')
        )

    def on_enter(self):
        """Called when app starts."""
        self.running = True
        self.view = 'CHOICE'
        self.choice_menu.selected_index = 0
        self.choice_menu.set_items([]) # Clear to rebuild with correct path
        self.first_render = True
        self._welcome_covers = None  # Reset cover cache for fresh load

        # Create music directory if it doesn't exist
        if not cfg.MUSIC_PATH.exists():
            try:
                cfg.MUSIC_PATH.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created music directory: {cfg.MUSIC_PATH}")
            except (OSError, PermissionError) as e:
                logger.error(f"Failed to create music directory: {e}")

    def on_exit(self):
        """Called when app exits."""
        pass