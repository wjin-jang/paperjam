"""
Library settings category.

Manages library-related settings including:
- Library statistics (tracks, albums, artists)
- Library rescanning
- Recent plays limit configuration
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from config import setup_logger
from core.i18n import t
from ui.views.items import Item

from .base import SettingsCategory

if TYPE_CHECKING:
    from core.library import LibraryManager
    from core.settings_manager import SettingsManager

logger = setup_logger()


class LibraryCategory(SettingsCategory):
    """Library settings category.

    Displays library statistics and provides options for rescanning
    the music library and configuring the recent plays limit.

    During a library scan, shows live progress (current file, counts).

    Attributes:
        lib: Reference to the LibraryManager.
    """

    def __init__(self, settings_manager: "SettingsManager", library_manager: "LibraryManager") -> None:
        """Initialize library settings.

        Args:
            settings_manager: Reference to the app's SettingsManager.
            library_manager: Reference to the LibraryManager.
        """
        super().__init__(t('settings.categories.library'), settings_manager)
        self.lib = library_manager

    def build_menu(self) -> list[Item]:
        """Build the library settings menu.

        Shows different content depending on whether a scan is in progress.
        """
        recents_limit = self.settings.get('recents_limit', 50)

        if self.lib.is_scanning:
            # Show scan progress
            return [
                Item(
                    columns=[t('settings.library.scanning'), self.lib.scan_current_file],
                    selectable=False
                ),
                Item(
                    columns=[t('settings.library.tracks'), str(self.lib.scan_track_count)],
                    selectable=False
                ),
                Item(
                    columns=[t('settings.library.albums'), str(self.lib.scan_album_count)],
                    selectable=False
                ),
                Item(
                    columns=[t('settings.library.artists'), str(self.lib.scan_artist_count)],
                    selectable=False
                ),
                Item(
                    columns=[t('settings.library.recents_limit'), str(recents_limit)],
                    selectable=False
                )
            ]
        else:
            # Show library stats
            tracks = self.lib.get_total_tracks()
            albums = len(self.lib.albums)
            artists = len(self.lib.artists)
            return [
                Item(
                    columns=[t('settings.library.tracks'), str(tracks)],
                    selectable=False
                ),
                Item(
                    columns=[t('settings.library.albums'), str(albums)],
                    selectable=False
                ),
                Item(
                    columns=[t('settings.library.artists'), str(artists)],
                    selectable=False
                ),
                Item(text=t('settings.library.rescan')),
                Item(
                    columns=[t('settings.library.recents_limit'), str(recents_limit)],
                    selectable=True
                )
            ]

    def handle_action(self, item_index: int) -> str | None:
        """Handle library settings menu selection."""
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.library.rescan') in item_text:
            self.lib.scan_async(force=True)
        elif t('settings.library.recents_limit') in item_text:
            self.settings.cycle('recents_limit')
            self.refresh()

        return None
