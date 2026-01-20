"""
Base class for settings categories.

This module defines the abstract base class that all settings categories
must inherit from. Each category represents a group of related settings
(Audio, Library, Display, Network, System).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from config import setup_logger
from ui.views.items import Item

if TYPE_CHECKING:
    from core.settings_manager import SettingsManager

logger = setup_logger()


class SettingsCategory(ABC):
    """Abstract base class for settings categories.

    Each category manages a group of related settings and provides:
    - Menu items for display in the settings UI
    - Action handlers for user interaction
    - Refresh capability when settings change

    Subclasses must implement:
    - build_menu(): Return list of Item objects for the category
    - handle_action(): Process user selection on a menu item

    Attributes:
        name: Display name for this category (localized).
        settings: Reference to the SettingsManager for persistent storage.
        items: Current list of menu items (populated by build_menu).
    """

    def __init__(self, name: str, settings_manager: "SettingsManager") -> None:
        """Initialize a settings category.

        Args:
            name: Localized display name for this category.
            settings_manager: Reference to the app's SettingsManager.
        """
        self.name = name
        self.settings = settings_manager
        self.items: list[Item] = []

    @abstractmethod
    def build_menu(self) -> list[Item]:
        """Build and return the menu items for this category.

        Returns:
            List of Item objects representing the settings in this category.
        """
        pass

    @abstractmethod
    def handle_action(self, item_index: int) -> str | None:
        """Handle action for the selected item.

        Called when the user presses enter/select on a menu item.

        Args:
            item_index: Index of the selected item in self.items.

        Returns:
            View name to switch to (e.g., 'VOLUME', 'BT_SAVED'),
            or None to stay in the current submenu.
        """
        pass

    def get_info_indices(self) -> list[int]:
        """Return indices of non-selectable (info-only) items.

        Used by the menu renderer to skip these items during navigation.

        Returns:
            List of indices for items with selectable=False.
        """
        return [i for i, item in enumerate(self.items) if not item.selectable]

    def refresh(self) -> None:
        """Refresh the menu items.

        Call this after settings change to rebuild the menu with updated values.
        """
        self.items = self.build_menu()
