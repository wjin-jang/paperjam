"""
Weather view renderer for the e-ink display.

Layout (with Panel, 8px padding, navigation):
┌─────────────────────────────────────────┐ y=8
│ [Location Name]            Today ►      │ <- Day selector top right
├─────────────────────────────────────────┤
│ [ICON] TEMP    │ Precip XX%             │ <- Current conditions
│        Condition│ Humid  XX%            │
│                │ Wind   XX              │
├─────────────────────────────────────────┤
│ TEMPERATURE    [bar chart scrollable]  ▐│ <- Selectable row
├─────────────────────────────────────────┤
│ PRECIPITATION  [bar chart scrollable]  ▐│ <- Selectable row
├─────────────────────────────────────────┤
│ THIS WEEK      MON TUE WED ...         ▐│ <- Selectable row
└─────────────────────────────────────────┘
"""
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw
from typing import List, Optional, Tuple

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
SECTION_CURRENT = 0
SECTION_TEMPERATURE = 1
SECTION_PRECIPITATION = 2
SECTION_WEEKLY = 3
SECTION_COUNT = 4


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


def get_day_label(day_offset: int, daily: List[DailyForecast]) -> str:
    """Get display label for day offset (0=Today, 1=Tomorrow, 2+=day name)."""
    if day_offset == 0:
        return t('weather.today')
    elif day_offset == 1:
        return t('weather.tomorrow')
    elif day_offset < len(daily):
        return daily[day_offset].day_name
    return "???"


class WeatherViewRenderer:
    """Renderer for weather display with navigation support."""

    # Layout constants (accounting for top bar at y=0-7)
    PANEL_X = 8
    PANEL_Y = 8  # Below top bar
    PANEL_W = cfg.SCREEN_WIDTH - 16  # 8px padding on each side
    PANEL_H = cfg.SCREEN_HEIGHT - 16  # 8px padding top and bottom

    # Internal layout
    HEADER_H = cfg.ROW_HEIGHT  # Panel header height
    CURRENT_H = 26  # Height for current conditions section
    CHART_H = 22  # Height for each bar chart
    WEEKLY_H = 26  # Height for weekly section

    # Bar chart settings
    CHART_HOURS = 8  # Visible hours at once
    TOTAL_HOURS = 24  # Total hours available for scrolling

    # Scrollbar
    SCROLLBAR_W = 3

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)
        self._icon_cache = {}

    def clear(self):
        """Clear the canvas."""
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def _get_icon(self, condition: str) -> Optional[Image.Image]:
        """Get cached weather icon."""
        if condition not in self._icon_cache:
            self._icon_cache[condition] = load_weather_icon(condition)
        return self._icon_cache[condition]

    def render(self, weather: Optional[WeatherData], title: str,
               selected_section: int = 0, day_offset: int = 0,
               chart_scroll: int = 0, updating: bool = False,
               error: Optional[str] = None) -> Image.Image:
        """Render the weather view with navigation.

        Args:
            weather: Weather data to display
            title: Location name for header
            selected_section: Currently selected section (0-3)
            day_offset: Day to show (0=today, 1=tomorrow, etc.)
            chart_scroll: Scroll offset for bar charts
            updating: Whether data is being updated
            error: Error message if any
        """
        self.clear()

        # Create main panel with location as header
        header = title if title else t('menu.weather')
        if updating:
            header = f"{header}..."

        panel = Panel(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H, header=header)

        # Draw panel border and header with day selector
        self._draw_panel_frame(panel, weather, day_offset if weather else 0)

        if error and not weather:
            self._draw_error(panel, error)
            return self.canvas

        if not weather or not weather.current:
            self._draw_no_data(panel)
            return self.canvas

        # Content area starts after header
        content_y = self.PANEL_Y + self.HEADER_H + 1
        content_x = self.PANEL_X + 1
        content_w = self.PANEL_W - 2

        # Get hourly data starting from current hour
        hourly = self._get_hourly_from_current(weather.hourly, day_offset)

        # Draw current conditions
        self._draw_current(weather, content_x, content_y, content_w, day_offset,
                          selected=selected_section == SECTION_CURRENT)

        # Divider
        div_y = content_y + self.CURRENT_H
        self.draw.line((content_x, div_y, content_x + content_w - 1, div_y), fill=cfg.BLACK)

        # Draw temperature chart
        chart_y = div_y + 1
        self._draw_bar_chart(
            hourly, chart_y, content_x, content_w,
            label=t('weather.temperature'),
            value_fn=lambda h: h.temperature,
            format_fn=lambda v: f"{int(v)}",
            scroll_offset=chart_scroll,
            selected=selected_section == SECTION_TEMPERATURE
        )

        # Divider
        div_y = chart_y + self.CHART_H
        self.draw.line((content_x, div_y, content_x + content_w - 1, div_y), fill=cfg.BLACK)

        # Draw precipitation chart
        chart_y = div_y + 1
        self._draw_bar_chart(
            hourly, chart_y, content_x, content_w,
            label=t('weather.precipitation'),
            value_fn=lambda h: h.precipitation_probability,
            format_fn=lambda v: f"{int(v)}",
            is_percentage=True,
            scroll_offset=chart_scroll,
            selected=selected_section == SECTION_PRECIPITATION
        )

        # Divider
        div_y = chart_y + self.CHART_H
        self.draw.line((content_x, div_y, content_x + content_w - 1, div_y), fill=cfg.BLACK)

        # Draw weekly forecast
        weekly_y = div_y + 1
        self._draw_weekly(weather.daily, weekly_y, content_x, content_w,
                         selected=selected_section == SECTION_WEEKLY)

        return self.canvas

    def _get_hourly_from_current(self, hourly: List[HourlyForecast], day_offset: int) -> List[HourlyForecast]:
        """Get hourly data starting from current hour or day start."""
        if not hourly:
            return []

        now = datetime.now()
        current_hour = now.hour

        if day_offset == 0:
            # Today: start from current hour
            start_idx = current_hour
        else:
            # Other days: start from midnight of that day
            start_idx = day_offset * 24

        # Return slice of hourly data
        return hourly[start_idx:start_idx + self.TOTAL_HOURS]

    def _draw_panel_frame(self, panel: Panel, weather: Optional[WeatherData], day_offset: int):
        """Draw panel border, header, and day selector."""
        # Shadow
        self.draw.rectangle(
            (panel.x + 1, panel.y + 1, panel.x + panel.width + 1, panel.y + panel.height + 1),
            outline=cfg.BLACK
        )
        # Main border
        self.draw.rectangle(
            (panel.x, panel.y, panel.x + panel.width, panel.y + panel.height),
            fill=cfg.WHITE, outline=cfg.BLACK
        )
        # Header background
        if panel.header:
            self.draw.rectangle(
                (panel.x, panel.y, panel.x + panel.width, panel.y + cfg.ROW_HEIGHT),
                fill=cfg.BLACK
            )
            # Location name on left
            draw_text_with_cjk(
                self.draw, (panel.x + 4, panel.y),
                panel.header,
                cfg.FONT_HEADER, cfg.FONT_CJK_HEADER, fill=cfg.WHITE, cjk_y_offset=1
            )

            # Day selector on right
            if weather and weather.daily:
                day_label = get_day_label(day_offset, weather.daily)
                day_text = f"< {day_label} >"
                day_w = get_text_width_with_cjk(day_text, cfg.FONT_MAIN, cfg.FONT_CJK_MAIN)
                day_x = panel.x + panel.width - day_w - 4
                draw_text_with_cjk(
                    self.draw, (day_x, panel.y + 2), day_text,
                    cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.WHITE
                )

    def _draw_current(self, weather: WeatherData, x: int, y: int, w: int,
                     day_offset: int, selected: bool = False):
        """Draw current weather conditions section."""
        # Get appropriate data for the day
        if day_offset == 0:
            current = weather.current
            condition_name, _ = current.condition
            temp = current.temperature
            precip = current.precipitation_probability
            humid = current.humidity
            wind = current.wind_speed
        elif day_offset < len(weather.daily):
            day = weather.daily[day_offset]
            condition_name, _ = day.condition
            temp = day.avg_temperature
            precip = day.precipitation_probability
            humid = 0  # Not available in daily
            wind = 0  # Not available in daily
        else:
            return

        # Left side: Icon + Temperature + Condition
        icon = self._get_icon(condition_name)
        icon_w = 16 if icon else 0

        # Draw icon
        if icon:
            self.canvas.paste(icon, (x + 2, y + 2))

        # Temperature (large)
        temp_x = x + icon_w + 4
        temp_text = f"{int(temp)}°"
        self.draw.text((temp_x, y + 1), temp_text, font=cfg.FONT_HEADER, fill=cfg.BLACK)

        # Condition text
        cond_text = SHORT_CONDITIONS.get(condition_name, condition_name)
        draw_text_with_cjk(
            self.draw, (temp_x, y + 14), cond_text,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        # Vertical divider
        div_x = x + 70
        self.draw.line((div_x, y + 1, div_x, y + self.CURRENT_H - 2), fill=cfg.BLACK)

        # Right side: Stats
        stats_x = div_x + 4
        stats = [
            (t('weather.precip'), f"{precip}%"),
            (t('weather.humidity'), f"{humid}%"),
            (t('weather.wind'), f"{int(wind)}"),
        ]

        for i, (label, value) in enumerate(stats):
            stat_y = y + 1 + (i * 8)
            draw_text_with_cjk(
                self.draw, (stats_x, stat_y), f"{label} {value}",
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )

    def _draw_bar_chart(self, hourly: List[HourlyForecast], y: int, x: int, w: int,
                        label: str, value_fn, format_fn, is_percentage: bool = False,
                        scroll_offset: int = 0, selected: bool = False):
        """Draw a horizontal bar chart for hourly data with scrolling."""
        # Draw row label (full text, not truncated)
        label_w = get_text_width_with_cjk(label, cfg.FONT_MAIN, cfg.FONT_CJK_MAIN)

        if selected:
            # Invert the label area when selected
            self.draw.rectangle(
                (x, y, x + label_w + 2, y + 10),
                fill=cfg.BLACK
            )
            draw_text_with_cjk(
                self.draw, (x + 1, y + 1), label,
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.WHITE
            )
        else:
            draw_text_with_cjk(
                self.draw, (x + 1, y + 1), label,
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )

        if not hourly:
            return

        # Chart area (after label)
        chart_label_w = label_w + 4
        chart_x = x + chart_label_w
        chart_w = w - chart_label_w - self.SCROLLBAR_W - 2
        chart_h = self.CHART_H - 10  # Leave room for hour labels

        # Get visible slice with scroll
        visible_hours = hourly[scroll_offset:scroll_offset + self.CHART_HOURS]
        if not visible_hours:
            return

        bar_w = chart_w // self.CHART_HOURS

        # Get values and calculate range
        all_values = [value_fn(h) for h in hourly]
        values = [value_fn(h) for h in visible_hours]

        if is_percentage:
            min_val, max_val = 0, 100
        else:
            min_val = min(all_values) if all_values else 0
            max_val = max(all_values) if all_values else 1

        val_range = max_val - min_val if max_val != min_val else 1

        for i, (h, val) in enumerate(zip(visible_hours, values)):
            bx = chart_x + i * bar_w

            # Calculate bar height
            if is_percentage:
                normalized = val / 100
            else:
                normalized = (val - min_val) / val_range

            bar_h = max(1, int(normalized * chart_h))
            bar_y = y + 1 + chart_h - bar_h
            bar_bottom = y + chart_h

            # Draw bar
            if bar_h > 0:
                self.draw.rectangle(
                    (bx + 1, bar_y, bx + bar_w - 2, bar_bottom),
                    fill=cfg.BLACK
                )

            # Draw value text in top left of bar cell
            val_text = format_fn(val)
            text_x = bx + 2
            text_y = y + 1

            # Draw text with partial inversion where it overlaps the bar
            self._draw_text_with_bar_inversion(
                text_x, text_y, val_text,
                bx + 1, bar_y, bx + bar_w - 2, bar_bottom
            )

            # Draw hour label at bottom
            hour_text = h.hour[:2]
            hour_w = cfg.FONT_MAIN.getbbox(hour_text)[2]
            hour_x = bx + (bar_w - hour_w) // 2
            self.draw.text((hour_x, y + chart_h + 1), hour_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

        # Draw scrollbar
        self._draw_scrollbar(
            x + w - self.SCROLLBAR_W - 1, y + 1,
            self.SCROLLBAR_W, self.CHART_H - 2,
            scroll_offset, len(hourly), self.CHART_HOURS
        )

    def _draw_text_with_bar_inversion(self, text_x: int, text_y: int, text: str,
                                       bar_x1: int, bar_y1: int, bar_x2: int, bar_y2: int):
        """Draw text with inversion where it overlaps a black bar."""
        # Get text dimensions
        bbox = cfg.FONT_MAIN.getbbox(text)
        text_w = bbox[2]
        text_h = bbox[3]
        text_bottom = text_y + text_h

        # Check if text overlaps with bar
        if text_y < bar_y2 and text_bottom > bar_y1 and text_x < bar_x2 and text_x + text_w > bar_x1:
            # Text overlaps bar - need to handle inversion
            # For simplicity, draw character by character
            char_x = text_x
            for char in text:
                char_bbox = cfg.FONT_MAIN.getbbox(char)
                char_w = char_bbox[2]
                char_right = char_x + char_w

                # Check if this character overlaps the bar
                char_overlaps = (char_x < bar_x2 and char_right > bar_x1 and
                               text_y < bar_y2 and text_bottom > bar_y1)

                if char_overlaps:
                    # Draw white on black
                    self.draw.text((char_x, text_y), char, font=cfg.FONT_MAIN, fill=cfg.WHITE)
                else:
                    # Draw black on white
                    self.draw.text((char_x, text_y), char, font=cfg.FONT_MAIN, fill=cfg.BLACK)

                char_x += char_w
        else:
            # No overlap, draw normally
            self.draw.text((text_x, text_y), text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_scrollbar(self, x: int, y: int, w: int, h: int,
                        offset: int, total: int, visible: int):
        """Draw a vertical scrollbar."""
        if total <= visible:
            return

        # Calculate thumb size and position
        thumb_h = max(4, (visible / total) * h)
        max_offset = total - visible
        thumb_y = y + (offset / max_offset) * (h - thumb_h) if max_offset > 0 else y

        # Draw track
        self.draw.rectangle((x, y, x + w - 1, y + h - 1), outline=cfg.BLACK)

        # Draw thumb
        self.draw.rectangle(
            (x + 1, int(thumb_y), x + w - 2, int(thumb_y + thumb_h)),
            fill=cfg.BLACK
        )

    def _draw_weekly(self, daily: List[DailyForecast], y: int, x: int, w: int,
                    selected: bool = False):
        """Draw weekly forecast section."""
        # Draw row label (full text)
        label = t('weather.this_week')
        label_w = get_text_width_with_cjk(label, cfg.FONT_MAIN, cfg.FONT_CJK_MAIN)

        if selected:
            # Invert the label area when selected
            self.draw.rectangle(
                (x, y, x + label_w + 2, y + 10),
                fill=cfg.BLACK
            )
            draw_text_with_cjk(
                self.draw, (x + 1, y + 1), label,
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.WHITE
            )
        else:
            draw_text_with_cjk(
                self.draw, (x + 1, y + 1), label,
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )

        if not daily:
            return

        days = daily[:7]
        if not days:
            return

        # Days area (after label)
        days_label_w = label_w + 4
        days_x = x + days_label_w
        days_w = w - days_label_w - 2
        day_w = days_w // len(days)

        for i, d in enumerate(days):
            dx = days_x + i * day_w

            # Day name (short, 2 chars)
            day_name = d.day_name[:2]
            name_w = cfg.FONT_MAIN.getbbox(day_name)[2]
            name_x = dx + (day_w - name_w) // 2
            self.draw.text((name_x, y + 1), day_name, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Condition indicator
            condition_name, _ = d.condition
            indicator = "●" if condition_name in ['rain', 'snow', 'thunderstorm', 'heavy_rain', 'drizzle'] else "○"
            ind_w = cfg.FONT_MAIN.getbbox(indicator)[2]
            ind_x = dx + (day_w - ind_w) // 2
            self.draw.text((ind_x, y + 9), indicator, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Average temperature
            avg_temp = f"{int(d.avg_temperature)}°"
            temp_w = cfg.FONT_MAIN.getbbox(avg_temp)[2]
            temp_x = dx + (day_w - temp_w) // 2
            self.draw.text((temp_x, y + 17), avg_temp, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_error(self, panel: Panel, error: str):
        """Draw error message inside panel."""
        y = panel.y + panel.height // 2 - 10
        draw_text_with_cjk(
            self.draw, (panel.x + 8, y), t('weather.error'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        draw_text_with_cjk(
            self.draw, (panel.x + 8, y + 12), error,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

    def _draw_no_data(self, panel: Panel):
        """Draw no data message inside panel."""
        y = panel.y + panel.height // 2 - 10
        draw_text_with_cjk(
            self.draw, (panel.x + 8, y), t('weather.no_data'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        draw_text_with_cjk(
            self.draw, (panel.x + 8, y + 12), t('weather.setup_location'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

    def render_location_setup(self, results: List[dict], selected_idx: int,
                               search_query: str, is_searching: bool) -> Image.Image:
        """Render location setup screen."""
        self.clear()

        # Create panel
        panel = Panel(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H,
                      header=t('weather.setup_title'))
        self._draw_panel_frame(panel, None, 0)

        content_y = self.PANEL_Y + cfg.ROW_HEIGHT + 2
        content_x = self.PANEL_X + 4

        # Search input
        search_display = f"{t('weather.search')}: {search_query}"
        draw_text_with_cjk(
            self.draw, (content_x, content_y), search_display,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        content_y += 12

        if is_searching:
            draw_text_with_cjk(
                self.draw, (content_x, content_y), t('weather.searching'),
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )
        elif results:
            # Draw results list
            for i, r in enumerate(results[:4]):
                item_y = content_y + i * 12
                loc_text = f"{r['name']}, {r.get('country', '')}"

                if i == selected_idx:
                    # Highlight selected
                    self.draw.rectangle(
                        (self.PANEL_X + 1, item_y - 1,
                         self.PANEL_X + self.PANEL_W - 1, item_y + 10),
                        fill=cfg.BLACK
                    )
                    draw_text_with_cjk(
                        self.draw, (content_x, item_y), loc_text,
                        cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.WHITE
                    )
                else:
                    draw_text_with_cjk(
                        self.draw, (content_x, item_y), loc_text,
                        cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
                    )
        elif search_query and len(search_query) >= 2:
            draw_text_with_cjk(
                self.draw, (content_x, content_y), t('weather.no_results'),
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )

        # Instructions at bottom
        inst_y = self.PANEL_Y + self.PANEL_H - 12
        draw_text_with_cjk(
            self.draw, (content_x, inst_y), t('weather.setup_hint'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        return self.canvas
