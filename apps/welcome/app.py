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
import config as cfg


class WelcomeApp:
    """First-run welcome and setup application."""

    def __init__(self, library_manager, input_handler):
        self.lib = library_manager
        self.inputs = input_handler
        self.renderer = UIRenderer()

        self.running = True
        self.view = 'CHOICE'  # CHOICE, SCANNING, WELCOME
        self.choice_idx = 0
        self.first_render = True

        # Callback for system operations
        self._shutdown_callback: Optional[Callable] = None
        self._display_callback: Optional[Callable] = None

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
                'up': self._choice_up,
                'down': self._choice_down,
                'enter': self._choice_enter
            }
        elif self.view == 'WELCOME':
            return {
                'enter': self._welcome_continue,
                'up': lambda: None,
                'down': lambda: None
            }
        return {}

    def _choice_up(self):
        self.choice_idx = (self.choice_idx - 1) % 2

    def _choice_down(self):
        self.choice_idx = (self.choice_idx + 1) % 2

    def _choice_enter(self):
        if self.choice_idx == 0:
            # Scan now
            self.view = 'SCANNING'
            self.lib.scan_async(force=True)
        else:
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
        return self.renderer.render_menu("WELCOME", ["Loading..."], 0, 0)

    def _render_choice(self):
        """Render choice screen with multi-line info."""
        # Truncate path if too long
        music_path = str(cfg.MUSIC_PATH)
        if len(music_path) > 22:
            music_path = music_path[:22]

        items = [
            {"type": "info", "lines": [
                "Music Library:",
                music_path
            ]},
            "Scan Library Now",
            "Shutdown (Add Music)"
        ]

        # Map choice_idx (0-1) to actual menu indices (1-2)
        sel_idx = self.choice_idx + 1

        return self.renderer.render_menu(
            "WELCOME", items, sel_idx, 0,
            info_indices=[0]
        )

    def _render_scanning(self):
        """Render scanning progress."""
        items = [
            f"Scanning: {self.lib.scan_track_count} tracks",
            f"Albums: {self.lib.scan_album_count}",
            f"Artists: {self.lib.scan_artist_count}"
        ]

        if self.lib.scan_current_file:
            current = self.lib.scan_current_file[:22]
            items.append(f"File: {current}")

        return self.renderer.render_menu(
            "SCANNING", items, -1, 0,
            info_indices=[0, 1, 2, 3]
        )

    def _render_welcome(self):
        """Render tiled album art welcome screen."""
        covers = self.lib.get_random_covers(count=15, small=True)
        return self.renderer.render_welcome_tiled(
            covers,
            dialog_text="WELCOME TO PAPERJAM",
            button_text="Continue..."
        )

    def on_enter(self):
        """Called when app starts."""
        self.running = True
        self.view = 'CHOICE'
        self.choice_idx = 0
        self.first_render = True

    def on_exit(self):
        """Called when app exits."""
        pass
