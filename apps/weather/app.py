"""
Weather application for PaperJam.

Displays current weather, hourly forecasts, and weekly outlook.
"""
import time
from typing import Dict, Callable, List

from PIL import Image

from apps.base import AppBase
from core.i18n import t
from core.weather import WeatherManager
from ui.views.weather_view import (
    WeatherViewRenderer,
    SECTION_DAY, SECTION_TEMPERATURE, SECTION_PRECIPITATION, SECTION_WEEKLY,
    SECTION_COUNT
)
from ui.views.items import TextInput, CHARSET_LOCATION
import config as cfg


class WeatherApp(AppBase):
    """Weather application displaying forecasts."""

    # Navigation limits
    MAX_CHART_SCROLL = cfg.WEATHER_CHART_TOTAL_HOURS - cfg.WEATHER_CHART_VISIBLE_HOURS  # 16
    MAX_DAY_OFFSET = 2  # Today, tomorrow, day after

    def __init__(self):
        super().__init__(name=t('menu.weather'))
        self.weather = WeatherManager()
        self.renderer = WeatherViewRenderer()

        self.view = 'MAIN'
        self.last_update_check = 0
        self.update_check_interval = cfg.WEATHER_UPDATE_CHECK_INTERVAL

        # Navigation state
        self.selected_section = SECTION_DAY
        self.day_offset = 0
        self.day_hover = 0  # Hover index within day selector
        self.chart_scroll = 0
        self.menu_scroll = 0

        # Setup state using TextInput
        self.search_input = TextInput(charset=CHARSET_LOCATION)
        self.search_results: List[dict] = []
        self.selected_result_idx = 0
        self.is_searching = False

    def on_enter(self):
        super().on_enter()
        self.selected_section = SECTION_DAY
        self.day_offset = 0
        self.day_hover = 0
        self.chart_scroll = 0
        self.menu_scroll = 0

        if not self.weather.is_configured:
            self.view = 'SETUP'
            self.search_input.reset()
            self.search_results = []
        else:
            self.view = 'MAIN'
            # Always attempt refresh when app opens
            if not self.weather.is_updating:
                self.weather.update_async()

    def get_callbacks(self) -> Dict[str, Callable]:
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
        """Navigate up - change hover or move to previous section.

        Day selector uses hover+select: up/down changes hovered day,
        wrapping to THIS WEEK when moving up from first row.
        """
        if self.selected_section == SECTION_DAY:
            if self.day_hover > 0:
                # Move hover to previous day
                self.day_hover -= 1
            else:
                # At first day row - wrap to THIS WEEK section
                self.selected_section = SECTION_WEEKLY
        elif self.selected_section == SECTION_TEMPERATURE:
            # Move back to day selector (preserves current day_offset, sync hover)
            self.selected_section = SECTION_DAY
            self.day_hover = self.day_offset
        else:
            # Move to previous section
            section_order = [SECTION_DAY, SECTION_TEMPERATURE, SECTION_PRECIPITATION, SECTION_WEEKLY]
            idx = section_order.index(self.selected_section)
            if idx > 0:
                self.selected_section = section_order[idx - 1]

    def _nav_down(self):
        """Navigate down - change hover or move to next section.

        Day selector uses hover+select: up/down changes hovered day,
        moving to TEMPERATURE when moving down from last row.
        """
        if self.selected_section == SECTION_DAY:
            if self.day_hover < self.MAX_DAY_OFFSET:
                # Move hover to next day
                self.day_hover += 1
            else:
                # At last day row - move to TEMPERATURE section
                self.selected_section = SECTION_TEMPERATURE
        elif self.selected_section == SECTION_WEEKLY:
            # Wrap from THIS WEEK back to day selector (sync hover to selected)
            self.selected_section = SECTION_DAY
            self.day_hover = self.day_offset
        else:
            # Move to next section
            section_order = [SECTION_DAY, SECTION_TEMPERATURE, SECTION_PRECIPITATION, SECTION_WEEKLY]
            idx = section_order.index(self.selected_section)
            if idx < len(section_order) - 1:
                self.selected_section = section_order[idx + 1]

    def _nav_left(self):
        """Scroll chart left or move from day selector to sections."""
        if self.selected_section == SECTION_DAY:
            # Move to sections
            pass
        elif self.selected_section in (SECTION_TEMPERATURE, SECTION_PRECIPITATION):
            if self.chart_scroll > 0:
                self.chart_scroll -= 1

    def _nav_right(self):
        """Scroll chart right or move to day selector."""
        if self.selected_section == SECTION_DAY:
            # Move to first section header
            self.selected_section = SECTION_TEMPERATURE
        elif self.selected_section in (SECTION_TEMPERATURE, SECTION_PRECIPITATION):
            if self.chart_scroll < self.MAX_CHART_SCROLL:
                self.chart_scroll += 1

    def _nav_action(self):
        """Action on current selection - select the hovered day."""
        if self.selected_section == SECTION_DAY:
            # Select the hovered day
            self.day_offset = self.day_hover
            self.chart_scroll = 0 if self.day_offset == 0 else cfg.WEATHER_FUTURE_DAY_START_HOUR

    def _open_setup(self):
        self.view = 'SETUP'
        self.search_input.reset()
        self.search_results = []
        self.selected_result_idx = 0

    def _exit(self):
        self.running = False

    # Setup callbacks

    def _setup_char_up(self):
        if self.search_results:
            self.selected_result_idx = max(0, self.selected_result_idx - 1)
        else:
            self.search_input.prev_char()

    def _setup_char_down(self):
        if self.search_results:
            self.selected_result_idx = min(len(self.search_results) - 1, self.selected_result_idx + 1)
        else:
            self.search_input.next_char()

    def _setup_enter(self):
        if self.search_results:
            result = self.search_results[self.selected_result_idx]
            display_name = f"{result['name']}, {result.get('admin1', '')}"
            if result.get('country'):
                display_name += f", {result['country']}"

            self.weather.set_location(
                display_name,
                result['latitude'],
                result['longitude']
            )
            self.weather.update_async()

            self.view = 'MAIN'
            self.search_input.reset()
            self.search_results = []
            self.selected_section = SECTION_DAY
            self.day_offset = 0
            self.day_hover = 0
            self.chart_scroll = 0
        else:
            self.search_input.confirm_char()

    def _setup_search(self):
        if len(self.search_input.text) >= cfg.WEATHER_MIN_SEARCH_LENGTH:
            self.is_searching = True
            self.search_results = self.weather.search_location(self.search_input.text)
            self.is_searching = False
            self.selected_result_idx = 0

    def _setup_back(self):
        if self.search_results:
            self.search_results = []
        elif self.search_input.text:
            self.search_input.delete_char()
        else:
            if self.weather.is_configured:
                self.view = 'MAIN'
            else:
                self.running = False

    def update(self) -> bool:
        now = time.time()
        if now - self.last_update_check > self.update_check_interval:
            self.last_update_check = now
            if self.weather.needs_update() and not self.weather.is_updating:
                self.weather.update_async()
        return self.running

    def get_frame(self) -> Image.Image:
        if self.view == 'SETUP':
            # Pass TextInput for cursor rendering when no results yet
            return self.renderer.render_location_setup(
                self.search_results,
                self.selected_result_idx,
                self.search_input if not self.search_results else None,
                self.search_input.text,
                self.is_searching
            )

        weather_data = self.weather.data
        title = self.weather.config.location_name or t('menu.weather')

        frame, self.menu_scroll = self.renderer.render(
            weather_data,
            title,
            selected_section=self.selected_section,
            day_offset=self.day_offset,
            day_hover=self.day_hover,
            chart_scroll=self.chart_scroll,
            menu_scroll=self.menu_scroll,
            updating=self.weather.is_updating,
            error=self.weather.last_error if not weather_data else None
        )
        return frame
