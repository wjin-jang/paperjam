"""
Abstract base class for applications in the PaperJam music player.
Defines a common interface for all apps to follow.
"""
from abc import ABC, abstractmethod
from typing import Dict, Callable, Optional
from PIL import Image

from ui.menu import MenuController

class AppBase(ABC):
    """
    Abstract base class that all applications must implement.

    This provides a consistent interface for the Launcher to interact
    with different apps (Music Player, Settings, etc.).
    """

    def __init__(self, name: str = "App"):
        self.running = True
        self._name = name
        # Helper for apps that use a single main menu
        self.menu = MenuController([])

    @property
    def name(self) -> str:
        """Return the display name of the app."""
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    def refresh_list(self):
        """
        Refresh the internal list or state.
        Optional to implement.
        """
        pass

    @abstractmethod
    def get_callbacks(self) -> Dict[str, Callable]:
        """
        Return the input callback handlers for this app.

        Returns:
            Dictionary mapping action names to callback functions.
            Common actions: 'up', 'down', 'enter', 'back', 'play_pause', etc.
        """
        pass

    @abstractmethod
    def update(self) -> bool:
        """
        Update the app state. Called on each iteration of the main loop.

        This is where apps should handle:
        - Time-based state changes (screensaver, timeouts)
        - Background task completion checks
        - Any periodic state updates

        Returns:
            True if the app should continue running, False to exit
        """
        pass

    @abstractmethod
    def get_frame(self) -> Image.Image:
        """
        Render and return the current frame to display.

        Returns:
            PIL Image object representing the current screen state
        """
        pass

    def on_enter(self):
        """
        Called when the app becomes active (selected from launcher).
        Override to perform initialization when app starts.
        """
        self.running = True

    def on_exit(self):
        """
        Called when the app is about to exit.
        Override to perform cleanup when app closes.
        """
        pass

    @property
    def is_running(self) -> bool:
        """Check if the app is still running."""
        return self.running

    def stop(self):
        """Signal the app to stop running."""
        self.running = False