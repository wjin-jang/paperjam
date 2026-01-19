"""
Weather application for PaperJam.

Displays current weather, hourly forecasts, and weekly outlook.
Fetches data from Open-Meteo API and caches locally.
"""
import time
from typing import Dict, Callable, List

from PIL import Image

from apps.base import AppBase
from core.i18n import t
from core.weather import WeatherManager
from ui.views.weather_view import (
    WeatherViewRenderer, SECTION_CURRENT, SECTION_TEMPERATURE,
    SECTION_PRECIPITATION, SECTION_WEEKLY, SECTION_COUNT
)
import config as cfg


class WeatherApp(AppBase):
    """Weather application displaying forecasts."""

    # Character set for location search input
    CHAR_SET = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        " -'.,0123456789"
    )

    # Maximum days to show (limited by API data)
    MAX_DAYS = 7

    # Chart scroll limits
    MAX_CHART_SCROLL = 16  # 24 hours - 8 visible

    def __init__(self):
        super().__init__(name=t('menu.weather'))
        self.weather = WeatherManager()
        self.renderer = WeatherViewRenderer()

        # View state
        self.view = 'MAIN'  # MAIN, SETUP
        self.last_update_check = 0
        self.update_check_interval = 60  # Check every minute

        # Navigation state
        self.selected_section = SECTION_CURRENT
        self.day_offset = 0  # 0=Today, 1=Tomorrow, etc.
        self.chart_scroll = 0  # Scroll offset for bar charts

        # Setup state
        self.search_query = ""
        self.search_results: List[dict] = []
        self.selected_result_idx = 0
        self.is_searching = False
        self.char_index = 0  # Current character in CHAR_SET

    def on_enter(self):
        """Called when app becomes active."""
        super().on_enter()

        # Reset navigation state
        self.selected_section = SECTION_CURRENT
        self.day_offset = 0
        self.chart_scroll = 0

        # Check if location is configured
        if not self.weather.is_configured:
            self.view = 'SETUP'
            self.search_query = ""
            self.search_results = []
        else:
            self.view = 'MAIN'
            # Trigger update if data is stale
            if self.weather.needs_update():
                self.weather.update_async()

    def get_callbacks(self) -> Dict[str, Callable]:
        """Return input callbacks based on current view."""
        if self.view == 'SETUP':
            return {
                'up': self._setup_char_up,
                'down': self._setup_char_down,
                'enter': self._setup_enter,
                'enter_long': self._setup_search,
                'back': self._setup_back,
                'next': self._setup_char_up,
                'prev': self._setup_char_down,
            }

        # Main view callbacks
        return {
            'up': self._nav_up,
            'down': self._nav_down,
            'next': self._nav_right,
            'prev': self._nav_left,
            'enter': self._nav_action,
            'enter_long': self._open_setup,
            'back': self._exit,
        }

    def _nav_up(self):
        """Navigate up through sections."""
        if self.selected_section > 0:
            self.selected_section -= 1
            # Reset chart scroll when changing sections
            self.chart_scroll = 0

    def _nav_down(self):
        """Navigate down through sections."""
        if self.selected_section < SECTION_COUNT - 1:
            self.selected_section += 1
            # Reset chart scroll when changing sections
            self.chart_scroll = 0

    def _nav_left(self):
        """Navigate left - scroll chart or change day."""
        if self.selected_section in (SECTION_TEMPERATURE, SECTION_PRECIPITATION):
            # Scroll chart left
            if self.chart_scroll > 0:
                self.chart_scroll -= 1
        elif self.selected_section == SECTION_CURRENT:
            # Change day (previous)
            if self.day_offset > 0:
                self.day_offset -= 1
                self.chart_scroll = 0

    def _nav_right(self):
        """Navigate right - scroll chart or change day."""
        if self.selected_section in (SECTION_TEMPERATURE, SECTION_PRECIPITATION):
            # Scroll chart right
            if self.chart_scroll < self.MAX_CHART_SCROLL:
                self.chart_scroll += 1
        elif self.selected_section == SECTION_CURRENT:
            # Change day (next)
            if self.day_offset < self.MAX_DAYS - 1:
                self.day_offset += 1
                self.chart_scroll = 0

    def _nav_action(self):
        """Action on current selection."""
        if self.selected_section == SECTION_CURRENT:
            # Refresh weather data
            if not self.weather.is_updating:
                self.weather.update_async()

    def _refresh(self):
        """Manually refresh weather data."""
        if not self.weather.is_updating:
            self.weather.update_async()

    def _open_setup(self):
        """Open location setup."""
        self.view = 'SETUP'
        self.search_query = ""
        self.search_results = []
        self.selected_result_idx = 0
        self.char_index = 0

    def _exit(self):
        """Exit the app."""
        self.running = False

    # --- Setup view callbacks ---

    def _setup_char_up(self):
        """Cycle to previous character or move selection up."""
        if self.search_results:
            # Navigate results
            self.selected_result_idx = max(0, self.selected_result_idx - 1)
        else:
            # Cycle character
            self.char_index = (self.char_index - 1) % len(self.CHAR_SET)

    def _setup_char_down(self):
        """Cycle to next character or move selection down."""
        if self.search_results:
            # Navigate results
            self.selected_result_idx = min(len(self.search_results) - 1, self.selected_result_idx + 1)
        else:
            # Cycle character
            self.char_index = (self.char_index + 1) % len(self.CHAR_SET)

    def _setup_enter(self):
        """Add character or select result."""
        if self.search_results:
            # Select location
            result = self.search_results[self.selected_result_idx]
            display_name = f"{result['name']}, {result.get('admin1', '')}"
            if result.get('country'):
                display_name += f", {result['country']}"

            self.weather.set_location(
                display_name[:30],
                result['latitude'],
                result['longitude']
            )

            # Fetch weather for new location
            self.weather.update_async()

            # Return to main view
            self.view = 'MAIN'
            self.search_query = ""
            self.search_results = []
            self.selected_section = SECTION_CURRENT
            self.day_offset = 0
            self.chart_scroll = 0
        else:
            # Add current character to query
            self.search_query += self.CHAR_SET[self.char_index]

    def _setup_search(self):
        """Perform location search."""
        if len(self.search_query) >= 2:
            self.is_searching = True
            self.search_results = self.weather.search_location(self.search_query)
            self.is_searching = False
            self.selected_result_idx = 0

    def _setup_back(self):
        """Delete character or exit setup."""
        if self.search_results:
            # Clear results to go back to input
            self.search_results = []
        elif self.search_query:
            # Delete last character
            self.search_query = self.search_query[:-1]
        else:
            # Exit setup (return to main or exit app if no location)
            if self.weather.is_configured:
                self.view = 'MAIN'
            else:
                self.running = False

    def update(self) -> bool:
        """Update app state."""
        # Periodic update check
        now = time.time()
        if now - self.last_update_check > self.update_check_interval:
            self.last_update_check = now
            if self.weather.needs_update() and not self.weather.is_updating:
                self.weather.update_async()

        return self.running

    def get_frame(self) -> Image.Image:
        """Render current frame."""
        if self.view == 'SETUP':
            return self.renderer.render_location_setup(
                self.search_results,
                self.selected_result_idx,
                self.search_query + f"[{self.CHAR_SET[self.char_index]}]" if not self.search_results else self.search_query,
                self.is_searching
            )

        # Main weather view
        weather_data = self.weather.data
        title = self.weather.config.location_name or t('menu.weather')

        return self.renderer.render(
            weather_data,
            title,
            selected_section=self.selected_section,
            day_offset=self.day_offset,
            chart_scroll=self.chart_scroll,
            updating=self.weather.is_updating,
            error=self.weather.last_error if not weather_data else None
        )
