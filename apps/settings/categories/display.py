"""
Display settings category.

Manages display-related settings including:
- Color inversion
- Screensaver timeout
- Language/locale selection
- Weather location configuration
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from config import setup_logger
from core.i18n import t
from core.settings_manager import format_duration
from core.weather import WeatherManager
from ui.views.items import Item, TextInput, CHARSET_LOCATION

from .base import SettingsCategory

if TYPE_CHECKING:
    from core.settings_manager import SettingsManager

logger = setup_logger()


class DisplayCategory(SettingsCategory):
    """Display settings category.

    Handles visual settings like color inversion, screensaver timeout,
    language selection, and weather location configuration.

    The weather location search uses the Open-Meteo geocoding API to
    find locations by name.

    Attributes:
        weather: WeatherManager instance for location search/config.
        location_input: TextInput for entering location search query.
        location_results: List of location search results.
        location_result_idx: Currently selected result index.
        is_searching: True while location search is in progress.
    """

    def __init__(self, settings_manager: "SettingsManager") -> None:
        """Initialize display settings.

        Args:
            settings_manager: Reference to the app's SettingsManager.
        """
        super().__init__(t('settings.categories.display'), settings_manager)
        self._locale_callback: Callable[[str], None] | None = None

        # Weather location state
        self.weather = WeatherManager()
        self.location_input = TextInput(charset=CHARSET_LOCATION)
        self.location_results: list[dict] = []
        self.location_result_idx: int = 0
        self.is_searching: bool = False

    def set_locale_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback to be called when locale changes.

        Args:
            callback: Function that receives the new locale code.
        """
        self._locale_callback = callback

    def _get_language_name(self, locale: str) -> str:
        """Get the display name for a locale.

        Args:
            locale: Locale code (e.g., 'en', 'ko').

        Returns:
            Localized language name.
        """
        return t(f'languages.{locale}', default=locale)

    def _get_weather_location(self) -> str:
        """Get current weather location name.

        Returns:
            Location name or 'Not set' placeholder.
        """
        return self.weather.config.location_name or t('settings.display.not_set')

    def build_menu(self) -> list[Item]:
        """Build the display settings menu."""
        invert = self.settings.get('invert_colors', False)
        state = t('general.on') if invert else t('general.off')
        ss_timeout = self.settings.get('screensaver_timeout', 60)
        current_locale = self.settings.get('locale', 'en')
        lang_name = self._get_language_name(current_locale)
        weather_loc = self._get_weather_location()

        return [
            Item(columns=[t('settings.display.invert_colors'), state], selectable=True),
            Item(columns=[t('settings.display.screensaver'), format_duration(ss_timeout)], selectable=True),
            Item(columns=[t('settings.display.language'), lang_name], selectable=True),
            Item(columns=[t('settings.display.weather_location'), weather_loc], selectable=True)
        ]

    def handle_action(self, item_index: int) -> str | None:
        """Handle display settings menu selection."""
        from core.i18n import set_locale

        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.display.invert_colors') in item_text:
            self.settings.toggle('invert_colors')
            self.refresh()
        elif t('settings.display.screensaver') in item_text:
            self.settings.cycle('screensaver_timeout')
            self.refresh()
        elif t('settings.display.language') in item_text:
            # Cycle through available locales
            new_locale = self.settings.cycle('locale')
            set_locale(new_locale)
            # Update category name with new translation
            self.name = t('settings.categories.display')
            self.refresh()
            # Notify callback if set
            if self._locale_callback:
                self._locale_callback(new_locale)
        elif t('settings.display.weather_location') in item_text:
            # Enter weather location setup
            self.reset_location_search()
            return 'WEATHER_LOCATION'

        return None

    # --- Weather Location Helpers ---

    def reset_location_search(self) -> None:
        """Reset location search state for a new search."""
        self.location_input.reset()
        self.location_results = []
        self.location_result_idx = 0
        self.is_searching = False

    def search_location(self) -> None:
        """Search for locations matching current input.

        Requires at least 2 characters to search.
        Results are stored in self.location_results.
        """
        if len(self.location_input.text) >= 2:
            self.is_searching = True
            self.location_results = self.weather.search_location(self.location_input.text)
            self.is_searching = False
            self.location_result_idx = 0

    def select_location(self, result: dict) -> None:
        """Select a location from search results.

        Args:
            result: Location dict with name, latitude, longitude, etc.
        """
        # Build display name from location parts
        display_name = f"{result['name']}, {result.get('admin1', '')}"
        if result.get('country'):
            display_name += f", {result['country']}"

        self.weather.set_location(
            display_name[:30],
            result['latitude'],
            result['longitude']
        )
        self.weather.update_async()
        self.reset_location_search()
        self.refresh()
