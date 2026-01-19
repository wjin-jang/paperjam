"""
Weather view renderer for the e-ink display.

Layout (with Panel, 8px padding, top bar space):
┌─────────────────────────────────────────┐ y=8
│ [Location Name - Panel Header]          │
├─────────────────────────────────────────┤
│ [ICON] TEMP    │ Precip XX%             │
│        Condition│ Humid  XX%            │
│                │ Wind   XX              │
├─────────────────────────────────────────┤
│ TEMP  [bar chart with 8 hours]          │
├─────────────────────────────────────────┤
│ RAIN  [bar chart with 8 hours]          │
├─────────────────────────────────────────┤
│ WEEK  MON TUE WED THU FRI SAT SUN       │
│       ○   ●   ○   ○   ○   ●   ○         │
│       15° 12° 18° 20° 22° 14° 16°       │
└─────────────────────────────────────────┘
"""
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
    """Renderer for weather display using Panel structure."""

    # Layout constants (accounting for top bar at y=0-7)
    PANEL_X = 8
    PANEL_Y = 8  # Below top bar
    PANEL_W = cfg.SCREEN_WIDTH - 16  # 8px padding on each side
    PANEL_H = cfg.SCREEN_HEIGHT - 16  # 8px padding top and bottom

    # Internal layout
    CURRENT_H = 26  # Height for current conditions section
    CHART_H = 22  # Height for each bar chart
    WEEKLY_H = 26  # Height for weekly section

    # Bar chart settings
    CHART_HOURS = 8  # Show 8 hours to fit better

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

    def render(self, weather: Optional[WeatherData], title: str, updating: bool = False,
               error: Optional[str] = None) -> Image.Image:
        """Render the weather view with Panel."""
        self.clear()

        # Create main panel with location as header
        header = title[:20] if title else t('menu.weather')
        if updating:
            header = f"{header[:15]}..."

        panel = Panel(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H, header=header)

        # Draw panel border and header
        self._draw_panel_frame(panel)

        if error and not weather:
            self._draw_error(panel, error)
            return self.canvas

        if not weather or not weather.current:
            self._draw_no_data(panel)
            return self.canvas

        # Content area starts after header
        content_y = self.PANEL_Y + cfg.ROW_HEIGHT + 1
        content_x = self.PANEL_X + 1
        content_w = self.PANEL_W - 2

        # Draw current conditions
        self._draw_current(weather, content_x, content_y, content_w)

        # Divider
        div_y = content_y + self.CURRENT_H
        self.draw.line((content_x, div_y, content_x + content_w - 1, div_y), fill=cfg.BLACK)

        # Draw temperature chart
        chart_y = div_y + 1
        self._draw_bar_chart(
            weather.hourly, chart_y, content_x, content_w,
            label=t('weather.temperature')[:4],
            value_fn=lambda h: h.temperature,
            format_fn=lambda v: f"{int(v)}°"
        )

        # Divider
        div_y = chart_y + self.CHART_H
        self.draw.line((content_x, div_y, content_x + content_w - 1, div_y), fill=cfg.BLACK)

        # Draw precipitation chart
        chart_y = div_y + 1
        self._draw_bar_chart(
            weather.hourly, chart_y, content_x, content_w,
            label=t('weather.precipitation')[:4],
            value_fn=lambda h: h.precipitation_probability,
            format_fn=lambda v: f"{int(v)}",
            is_percentage=True
        )

        # Divider
        div_y = chart_y + self.CHART_H
        self.draw.line((content_x, div_y, content_x + content_w - 1, div_y), fill=cfg.BLACK)

        # Draw weekly forecast
        weekly_y = div_y + 1
        self._draw_weekly(weather.daily, weekly_y, content_x, content_w)

        return self.canvas

    def _draw_panel_frame(self, panel: Panel):
        """Draw panel border and header manually (not using Menu)."""
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
        # Header
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

    def _draw_current(self, weather: WeatherData, x: int, y: int, w: int):
        """Draw current weather conditions section."""
        current = weather.current
        condition_name, _ = current.condition

        # Left side: Icon + Temperature + Condition
        icon = self._get_icon(condition_name)
        icon_w = 16 if icon else 0

        # Draw icon
        if icon:
            self.canvas.paste(icon, (x + 2, y + 2))

        # Temperature (large)
        temp_x = x + icon_w + 4
        temp_text = f"{int(current.temperature)}°"
        self.draw.text((temp_x, y + 1), temp_text, font=cfg.FONT_HEADER, fill=cfg.BLACK)

        # Condition text (short)
        cond_text = SHORT_CONDITIONS.get(condition_name, condition_name[:6])
        draw_text_with_cjk(
            self.draw, (temp_x, y + 14), cond_text[:8],
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        # Vertical divider
        div_x = x + 70
        self.draw.line((div_x, y + 1, div_x, y + self.CURRENT_H - 2), fill=cfg.BLACK)

        # Right side: Stats
        stats_x = div_x + 4
        stats = [
            (t('weather.precip')[:5], f"{current.precipitation_probability}%"),
            (t('weather.humidity')[:5], f"{current.humidity}%"),
            (t('weather.wind')[:4], f"{int(current.wind_speed)}"),
        ]

        for i, (label, value) in enumerate(stats):
            stat_y = y + 1 + (i * 8)
            draw_text_with_cjk(
                self.draw, (stats_x, stat_y), f"{label} {value}",
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )

    def _draw_bar_chart(self, hourly: List[HourlyForecast], y: int, x: int, w: int,
                        label: str, value_fn, format_fn, is_percentage: bool = False):
        """Draw a horizontal bar chart for hourly data."""
        if not hourly:
            return

        hours = hourly[:self.CHART_HOURS]
        if not hours:
            return

        # Draw label on left
        draw_text_with_cjk(
            self.draw, (x + 1, y + 1), label,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        # Chart area (after label)
        label_w = 22
        chart_x = x + label_w
        chart_w = w - label_w - 2
        bar_w = chart_w // self.CHART_HOURS
        chart_h = self.CHART_H - 10  # Leave room for hour labels

        # Get values and calculate range
        values = [value_fn(h) for h in hours]

        if is_percentage:
            min_val, max_val = 0, 100
        else:
            min_val = min(values)
            max_val = max(values)
            # Add padding to range
            val_range = max_val - min_val
            if val_range == 0:
                val_range = 1

        val_range = max_val - min_val if max_val != min_val else 1

        for i, (h, val) in enumerate(zip(hours, values)):
            bx = chart_x + i * bar_w

            # Calculate bar height
            if is_percentage:
                normalized = val / 100
            else:
                normalized = (val - min_val) / val_range

            bar_h = max(1, int(normalized * chart_h))
            bar_y = y + 1 + chart_h - bar_h

            # Draw bar
            if bar_h > 0:
                self.draw.rectangle(
                    (bx + 1, bar_y, bx + bar_w - 2, y + chart_h),
                    fill=cfg.BLACK
                )

            # Draw value text
            val_text = format_fn(val)
            text_w = cfg.FONT_MAIN.getbbox(val_text)[2]
            text_x = bx + (bar_w - text_w) // 2
            text_y = bar_y - 8

            # Invert text if overlapping bar
            if bar_h > chart_h - 8:
                text_y = bar_y + 1
                self.draw.text((text_x, text_y), val_text, font=cfg.FONT_MAIN, fill=cfg.WHITE)
            else:
                self.draw.text((text_x, text_y), val_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Draw hour label at bottom
            hour_text = h.hour[:2]
            hour_w = cfg.FONT_MAIN.getbbox(hour_text)[2]
            hour_x = bx + (bar_w - hour_w) // 2
            self.draw.text((hour_x, y + chart_h + 1), hour_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_weekly(self, daily: List[DailyForecast], y: int, x: int, w: int):
        """Draw weekly forecast section."""
        if not daily:
            return

        days = daily[:7]
        if not days:
            return

        # Label
        draw_text_with_cjk(
            self.draw, (x + 1, y + 1), t('weather.this_week')[:4],
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        # Days area (after label)
        label_w = 22
        days_x = x + label_w
        days_w = w - label_w - 2
        day_w = days_w // len(days)

        for i, d in enumerate(days):
            dx = days_x + i * day_w

            # Day name (short)
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
        error_short = error[:28] if len(error) > 28 else error
        draw_text_with_cjk(
            self.draw, (panel.x + 8, y + 12), error_short,
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
        self._draw_panel_frame(panel)

        content_y = self.PANEL_Y + cfg.ROW_HEIGHT + 2
        content_x = self.PANEL_X + 4

        # Search input
        search_display = f"{t('weather.search')}: {search_query}"
        draw_text_with_cjk(
            self.draw, (content_x, content_y), search_display[:32],
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
                loc_text = f"{r['name']}, {r.get('country', '')[:8]}"
                loc_text = loc_text[:30]

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
