"""
Weather view renderer for the e-ink display.

Layout with day selection rows and scrollable charts:
┌─────────────────────────────────────────┐
│ [Location Name - Header]               ▐│
├─────────────────────────────────────────┤
│ Today      22° Clear   Precip 30%      ▐│ <- Day row (selected = active day)
│ Tomorrow   18° Rain    Precip 80%      ▐│
│ Wednesday  20° Cloudy  Precip 20%      ▐│
├─────────────────────────────────────────┤
│ TEMPERATURE                            ▐│ <- Section row (L/R scrolls chart)
│  22  24  26  28  26  24  22  20        │
│  ██  ████████████████  ██  ██          │
│  09  10  11  12  13  14  15  16        │
├─────────────────────────────────────────┤
│ PRECIPITATION                          ▐│
│   0  20  40  60  40  20  10   0        │
│      ██  ████████████  ██              │
│  09  10  11  12  13  14  15  16        │
├─────────────────────────────────────────┤
│ THIS WEEK                              ▐│
│  MO  TU  WE  TH  FR  SA  SU            │
│   ○   ●   ○   ○   ○   ●   ○            │
│  15  12  18  20  22  14  16            │
└─────────────────────────────────────────┘
"""
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw
from typing import List, Optional

import config as cfg
from core.i18n import t
from core.weather import WeatherData, HourlyForecast, DailyForecast
from ui.graphics import draw_text_with_cjk, get_text_width_with_cjk
from ui.views.core import Panel

# Weather icons directory
WEATHER_ICONS_DIR = Path(__file__).parent.parent.parent / "assets" / "weather"

# Short condition names for display
SHORT_CONDITIONS = {
    'clear': 'Clear',
    'mostly_clear': 'Clear',
    'partly_cloudy': 'Cloudy',
    'overcast': 'Cloudy',
    'fog': 'Fog',
    'drizzle': 'Drizzle',
    'rain': 'Rain',
    'freezing_drizzle': 'F.Rain',
    'freezing_rain': 'F.Rain',
    'heavy_rain': 'H.Rain',
    'rain_showers': 'Showers',
    'heavy_showers': 'Showers',
    'snow': 'Snow',
    'heavy_snow': 'H.Snow',
    'snow_grains': 'Snow',
    'snow_showers': 'Snow',
    'thunderstorm': 'Storm',
    'thunderstorm_hail': 'Storm',
    'unknown': '???',
}

# Map condition names to icon files
CONDITION_ICONS = {
    'clear': 'clear.png',
    'mostly_clear': 'clear.png',
    'partly_cloudy': 'partly_cloudy.png',
    'overcast': 'cloudy.png',
    'fog': 'fog.png',
    'drizzle': 'drizzle.png',
    'rain': 'rain.png',
    'freezing_drizzle': 'rain.png',
    'freezing_rain': 'rain.png',
    'heavy_rain': 'heavy_rain.png',
    'rain_showers': 'rain.png',
    'heavy_showers': 'heavy_rain.png',
    'snow': 'snow.png',
    'heavy_snow': 'snow.png',
    'snow_grains': 'snow.png',
    'snow_showers': 'snow.png',
    'thunderstorm': 'thunderstorm.png',
    'thunderstorm_hail': 'thunderstorm.png',
    'unknown': 'unknown.png',
}

# Navigation sections
SECTION_TODAY = 0
SECTION_TOMORROW = 1
SECTION_WEEKDAY = 2
SECTION_TEMPERATURE = 3
SECTION_PRECIPITATION = 4
SECTION_WEEKLY = 5
SECTION_COUNT = 6


def load_weather_icon(condition: str) -> Optional[Image.Image]:
    """Load a weather icon for the given condition."""
    icon_file = CONDITION_ICONS.get(condition, 'unknown.png')
    icon_path = WEATHER_ICONS_DIR / icon_file
    if icon_path.exists():
        try:
            img = Image.open(icon_path).convert('1')
            return img
        except Exception:
            pass
    return None


class WeatherViewRenderer:
    """Renderer for weather display with navigation support."""

    # Layout constants
    PANEL_X = 8
    PANEL_Y = 8
    PANEL_W = cfg.SCREEN_WIDTH - 16
    PANEL_H = cfg.SCREEN_HEIGHT - 16

    # Row heights
    HEADER_H = cfg.ROW_HEIGHT
    DAY_ROW_H = 10
    SECTION_ROW_H = 10
    CHART_H = 18
    WEEKLY_H = 24

    # Bar chart settings
    CHART_HOURS = 8
    TOTAL_HOURS = 24

    # Scrollbar
    SCROLLBAR_W = 4

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)
        self._icon_cache = {}

    def clear(self):
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def _get_icon(self, condition: str) -> Optional[Image.Image]:
        if condition not in self._icon_cache:
            self._icon_cache[condition] = load_weather_icon(condition)
        return self._icon_cache[condition]

    def render(self, weather: Optional[WeatherData], title: str,
               selected_section: int = 0, day_offset: int = 0,
               chart_scroll: int = 0, updating: bool = False,
               error: Optional[str] = None) -> Image.Image:
        """Render the weather view."""
        self.clear()

        header = title if title else t('menu.weather')
        if updating:
            header = f"{header}..."

        panel = Panel(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H, header=header)
        self._draw_panel_frame(panel)

        if error and not weather:
            self._draw_error(panel, error)
            return self.canvas

        if not weather or not weather.current:
            self._draw_no_data(panel)
            return self.canvas

        content_y = self.PANEL_Y + self.HEADER_H + 1
        content_x = self.PANEL_X + 1
        content_w = self.PANEL_W - 2 - self.SCROLLBAR_W

        # Day selection rows
        for i in range(3):
            selected = (selected_section == i)
            active = (day_offset == i)
            self._draw_day_row(weather, i, content_x, content_y, content_w, selected, active)
            content_y += self.DAY_ROW_H

        # Divider
        self.draw.line((content_x, content_y, content_x + content_w - 1, content_y), fill=cfg.BLACK)
        content_y += 1

        # Get hourly data for selected day
        hourly = self._get_hourly_from_current(weather.hourly, day_offset)

        # Temperature section
        self._draw_row(t('weather.temperature'), content_x, content_y, content_w,
                      selected=(selected_section == SECTION_TEMPERATURE))
        content_y += self.SECTION_ROW_H
        self._draw_bar_chart(hourly, content_y, content_x, content_w,
                            value_fn=lambda h: h.temperature,
                            format_fn=lambda v: f"{int(v)}",
                            scroll_offset=chart_scroll)
        content_y += self.CHART_H

        # Divider
        self.draw.line((content_x, content_y, content_x + content_w - 1, content_y), fill=cfg.BLACK)
        content_y += 1

        # Precipitation section
        self._draw_row(t('weather.precipitation'), content_x, content_y, content_w,
                      selected=(selected_section == SECTION_PRECIPITATION))
        content_y += self.SECTION_ROW_H
        self._draw_bar_chart(hourly, content_y, content_x, content_w,
                            value_fn=lambda h: h.precipitation_probability,
                            format_fn=lambda v: f"{int(v)}",
                            is_percentage=True,
                            scroll_offset=chart_scroll)
        content_y += self.CHART_H

        # Divider
        self.draw.line((content_x, content_y, content_x + content_w - 1, content_y), fill=cfg.BLACK)
        content_y += 1

        # This Week section
        self._draw_row(t('weather.this_week'), content_x, content_y, content_w,
                      selected=(selected_section == SECTION_WEEKLY))
        content_y += self.SECTION_ROW_H
        self._draw_weekly_content(weather.daily, content_y, content_x, content_w)

        # Scrollbar
        scrollbar_x = self.PANEL_X + self.PANEL_W - self.SCROLLBAR_W - 1
        scrollbar_y = self.PANEL_Y + self.HEADER_H + 1
        scrollbar_h = self.PANEL_H - self.HEADER_H - 2
        self._draw_scrollbar(scrollbar_x, scrollbar_y, self.SCROLLBAR_W, scrollbar_h,
                            selected_section, SECTION_COUNT, 1)

        return self.canvas

    def _get_hourly_from_current(self, hourly: List[HourlyForecast], day_offset: int) -> List[HourlyForecast]:
        if not hourly:
            return []

        now = datetime.now()
        if day_offset == 0:
            start_idx = now.hour
        else:
            start_idx = day_offset * 24

        return hourly[start_idx:start_idx + self.TOTAL_HOURS]

    def _draw_panel_frame(self, panel: Panel):
        self.draw.rectangle(
            (panel.x + 1, panel.y + 1, panel.x + panel.width + 1, panel.y + panel.height + 1),
            outline=cfg.BLACK
        )
        self.draw.rectangle(
            (panel.x, panel.y, panel.x + panel.width, panel.y + panel.height),
            fill=cfg.WHITE, outline=cfg.BLACK
        )
        if panel.header:
            self.draw.rectangle(
                (panel.x, panel.y, panel.x + panel.width, panel.y + cfg.ROW_HEIGHT),
                fill=cfg.BLACK
            )
            draw_text_with_cjk(
                self.draw, (panel.x + 4, panel.y),
                panel.header,
                cfg.FONT_HEADER, cfg.FONT_CJK_HEADER, fill=cfg.WHITE, cjk_y_offset=1
            )

    def _draw_row(self, label: str, x: int, y: int, w: int, selected: bool = False):
        """Draw a standard menu row."""
        if selected:
            self.draw.rectangle((x, y, x + w - 1, y + self.SECTION_ROW_H - 1), fill=cfg.BLACK)
            draw_text_with_cjk(self.draw, (x + 2, y + 1), label,
                              cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.WHITE)
        else:
            draw_text_with_cjk(self.draw, (x + 2, y + 1), label,
                              cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)

    def _draw_day_row(self, weather: WeatherData, day_idx: int, x: int, y: int, w: int,
                     selected: bool, active: bool):
        """Draw a day selection row with weather summary."""
        # Get day label
        if day_idx == 0:
            day_label = t('weather.today')
            temp = weather.current.temperature
            condition_name, _ = weather.current.condition
            precip = weather.current.precipitation_probability
        elif day_idx < len(weather.daily):
            day = weather.daily[day_idx]
            if day_idx == 1:
                day_label = t('weather.tomorrow')
            else:
                day_label = day.day_name
            temp = day.avg_temperature
            condition_name, _ = day.condition
            precip = day.precipitation_probability
        else:
            return

        cond_text = SHORT_CONDITIONS.get(condition_name, '???')

        # Build row text
        row_text = f"{day_label:<10} {int(temp):>3}° {cond_text:<7} {precip:>3}%"

        # Draw with selection/active indicator
        if selected:
            self.draw.rectangle((x, y, x + w - 1, y + self.DAY_ROW_H - 1), fill=cfg.BLACK)
            draw_text_with_cjk(self.draw, (x + 2, y + 1), row_text,
                              cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.WHITE)
        else:
            # Show bullet for active day
            prefix = ">" if active else " "
            draw_text_with_cjk(self.draw, (x + 2, y + 1), prefix + row_text,
                              cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)

    def _draw_bar_chart(self, hourly: List[HourlyForecast], y: int, x: int, w: int,
                        value_fn, format_fn, is_percentage: bool = False,
                        scroll_offset: int = 0):
        """Draw bar chart with values and hours."""
        if not hourly:
            return

        visible_hours = hourly[scroll_offset:scroll_offset + self.CHART_HOURS]
        if not visible_hours:
            return

        bar_w = w // self.CHART_HOURS
        bar_area_h = 8

        all_values = [value_fn(h) for h in hourly]
        values = [value_fn(h) for h in visible_hours]

        if is_percentage:
            min_val, max_val = 0, 100
        else:
            min_val = min(all_values) if all_values else 0
            max_val = max(all_values) if all_values else 1

        val_range = max_val - min_val if max_val != min_val else 1

        for i, (h, val) in enumerate(zip(visible_hours, values)):
            bx = x + i * bar_w
            center = bx + bar_w // 2

            # Value
            val_text = format_fn(val)
            text_w = cfg.FONT_MAIN.getbbox(val_text)[2]
            self.draw.text((center - text_w // 2, y), val_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Bar
            if is_percentage:
                normalized = val / 100
            else:
                normalized = (val - min_val) / val_range

            bar_h = max(1, int(normalized * bar_area_h))
            bar_y = y + 8 + bar_area_h - bar_h

            self.draw.rectangle((bx + 2, bar_y, bx + bar_w - 3, y + 8 + bar_area_h), fill=cfg.BLACK)

            # Hour
            hour_text = h.hour[:2]
            hour_w = cfg.FONT_MAIN.getbbox(hour_text)[2]
            self.draw.text((center - hour_w // 2, y + 9 + bar_area_h), hour_text,
                          font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_weekly_content(self, daily: List[DailyForecast], y: int, x: int, w: int):
        if not daily:
            return

        days = daily[:7]
        day_w = w // len(days)

        for i, d in enumerate(days):
            dx = x + i * day_w
            center = dx + day_w // 2

            # Day name
            day_name = d.day_name[:2]
            name_w = cfg.FONT_MAIN.getbbox(day_name)[2]
            self.draw.text((center - name_w // 2, y), day_name, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Condition
            condition_name, _ = d.condition
            indicator = "●" if condition_name in ['rain', 'snow', 'thunderstorm', 'heavy_rain', 'drizzle'] else "○"
            ind_w = cfg.FONT_MAIN.getbbox(indicator)[2]
            self.draw.text((center - ind_w // 2, y + 8), indicator, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Temp
            avg_temp = f"{int(d.avg_temperature)}°"
            temp_w = cfg.FONT_MAIN.getbbox(avg_temp)[2]
            self.draw.text((center - temp_w // 2, y + 16), avg_temp, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_scrollbar(self, x: int, y: int, w: int, h: int,
                        position: int, total: int, visible: int):
        self.draw.rectangle((x, y, x + w - 1, y + h - 1), outline=cfg.BLACK)

        if total <= visible:
            thumb_h = h - 2
            thumb_y = y + 1
        else:
            thumb_h = max(8, (visible / total) * (h - 2))
            max_pos = total - visible
            thumb_y = y + 1 + (position / max(1, max_pos)) * (h - 2 - thumb_h)

        self.draw.rectangle((x + 1, int(thumb_y), x + w - 2, int(thumb_y + thumb_h)), fill=cfg.BLACK)

    def _draw_error(self, panel: Panel, error: str):
        y = panel.y + panel.height // 2 - 10
        draw_text_with_cjk(self.draw, (panel.x + 8, y), t('weather.error'),
                          cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)
        draw_text_with_cjk(self.draw, (panel.x + 8, y + 12), error,
                          cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)

    def _draw_no_data(self, panel: Panel):
        y = panel.y + panel.height // 2 - 10
        draw_text_with_cjk(self.draw, (panel.x + 8, y), t('weather.no_data'),
                          cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)
        draw_text_with_cjk(self.draw, (panel.x + 8, y + 12), t('weather.setup_location'),
                          cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)

    def render_location_setup(self, results: List[dict], selected_idx: int,
                               search_query: str, is_searching: bool) -> Image.Image:
        self.clear()

        panel = Panel(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H,
                      header=t('weather.setup_title'))
        self._draw_panel_frame(panel)

        content_y = self.PANEL_Y + cfg.ROW_HEIGHT + 2
        content_x = self.PANEL_X + 4

        search_display = f"{t('weather.search')}: {search_query}"
        draw_text_with_cjk(self.draw, (content_x, content_y), search_display,
                          cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)
        content_y += 12

        if is_searching:
            draw_text_with_cjk(self.draw, (content_x, content_y), t('weather.searching'),
                              cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)
        elif results:
            for i, r in enumerate(results[:4]):
                item_y = content_y + i * 12
                loc_text = f"{r['name']}, {r.get('country', '')}"

                if i == selected_idx:
                    self.draw.rectangle(
                        (self.PANEL_X + 1, item_y - 1,
                         self.PANEL_X + self.PANEL_W - 1, item_y + 10),
                        fill=cfg.BLACK
                    )
                    draw_text_with_cjk(self.draw, (content_x, item_y), loc_text,
                                      cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.WHITE)
                else:
                    draw_text_with_cjk(self.draw, (content_x, item_y), loc_text,
                                      cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)
        elif search_query and len(search_query) >= 2:
            draw_text_with_cjk(self.draw, (content_x, content_y), t('weather.no_results'),
                              cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)

        inst_y = self.PANEL_Y + self.PANEL_H - 12
        draw_text_with_cjk(self.draw, (content_x, inst_y), t('weather.setup_hint'),
                          cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK)

        return self.canvas
