"""
Weather view renderer for the e-ink display.

Layout:
- Current conditions with icon, temperature, and stats
- Hourly temperature bar chart
- Hourly precipitation bar chart
- Weekly forecast with condition icons
"""
from PIL import Image, ImageDraw
from typing import List, Optional, Tuple

import config as cfg
from core.i18n import t
from core.weather import WeatherData, HourlyForecast, DailyForecast
from ui.graphics import draw_text_with_cjk, get_text_width_with_cjk


class WeatherViewRenderer:
    """Renderer for weather display."""

    # Layout constants
    HEADER_HEIGHT = 12
    CURRENT_HEIGHT = 24
    DIVIDER_Y = HEADER_HEIGHT + CURRENT_HEIGHT
    CHART_HEIGHT = 28
    CHART_Y_TEMP = DIVIDER_Y + 2
    CHART_Y_PRECIP = CHART_Y_TEMP + CHART_HEIGHT + 2
    WEEKLY_Y = CHART_Y_PRECIP + CHART_HEIGHT + 2

    # Chart settings
    CHART_BAR_WIDTH = 20
    CHART_HOURS = 12  # Show 12 hours
    CHART_MARGIN_LEFT = 1

    # Weather condition icons (ASCII art style for e-ink)
    CONDITION_ICONS = {
        'clear': [
            "  ██  ",
            " ████ ",
            "██████",
            " ████ ",
            "  ██  ",
        ],
        'mostly_clear': [
            "  ██  ",
            " ████ ",
            "██████",
            "  ░░░ ",
            " ░░░░ ",
        ],
        'partly_cloudy': [
            "  ██  ",
            " ████░",
            "██░░░░",
            " ░░░░░",
            "░░░░░ ",
        ],
        'overcast': [
            " ░░░░ ",
            "░░░░░░",
            "░░░░░░",
            " ░░░░ ",
            "      ",
        ],
        'fog': [
            "░ ░ ░ ",
            " ░ ░ ░",
            "░ ░ ░ ",
            " ░ ░ ░",
            "░ ░ ░ ",
        ],
        'rain': [
            " ░░░░ ",
            "░░░░░░",
            " │ │ │",
            "│ │ │ ",
            " │ │  ",
        ],
        'drizzle': [
            " ░░░░ ",
            "░░░░░░",
            "  ·  ·",
            " ·  · ",
            "  ·   ",
        ],
        'heavy_rain': [
            "░░░░░░",
            "░░░░░░",
            "││││││",
            "││││││",
            "││││││",
        ],
        'snow': [
            " ░░░░ ",
            "░░░░░░",
            " * * *",
            "* * * ",
            " * *  ",
        ],
        'heavy_snow': [
            "░░░░░░",
            "░░░░░░",
            "******",
            "******",
            "******",
        ],
        'thunderstorm': [
            "░░░░░░",
            "░░██░░",
            " ██   ",
            "  ██  ",
            "   █  ",
        ],
        'unknown': [
            "  ??  ",
            " ???? ",
            "  ??  ",
            " ???? ",
            "  ??  ",
        ],
    }

    # Small icons for weekly view (3x5)
    SMALL_ICONS = {
        'clear': ["█", "█", "█"],
        'partly_cloudy': ["█", "░", "░"],
        'overcast': ["░", "░", "░"],
        'rain': ["░", "│", "│"],
        'drizzle': ["░", "·", "·"],
        'snow': ["░", "*", "*"],
        'thunderstorm': ["░", "█", " "],
        'unknown': ["?", "?", "?"],
    }

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

    def clear(self):
        """Clear the canvas."""
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def render(self, weather: Optional[WeatherData], title: str, updating: bool = False,
               error: Optional[str] = None) -> Image.Image:
        """Render the weather view."""
        self.clear()

        # Draw header
        self._draw_header(title, updating)

        if error:
            self._draw_error(error)
            return self.canvas

        if not weather or not weather.current:
            self._draw_no_data()
            return self.canvas

        # Draw current conditions
        self._draw_current(weather)

        # Draw divider
        self.draw.line((0, self.DIVIDER_Y, cfg.SCREEN_WIDTH, self.DIVIDER_Y), fill=cfg.BLACK)

        # Draw hourly temperature chart
        self._draw_temperature_chart(weather.hourly)

        # Draw hourly precipitation chart
        self._draw_precipitation_chart(weather.hourly)

        # Draw weekly forecast
        self._draw_weekly(weather.daily)

        return self.canvas

    def _draw_header(self, title: str, updating: bool):
        """Draw header with title and update status."""
        # Draw title
        draw_text_with_cjk(
            self.draw, (2, 1), title,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        # Draw updating indicator
        if updating:
            update_text = t('weather.updating')
            w = get_text_width_with_cjk(update_text, cfg.FONT_MAIN, cfg.FONT_CJK_MAIN)
            draw_text_with_cjk(
                self.draw, (cfg.SCREEN_WIDTH - w - 2, 1), update_text,
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )

        # Header divider
        self.draw.line((0, self.HEADER_HEIGHT - 1, cfg.SCREEN_WIDTH, self.HEADER_HEIGHT - 1), fill=cfg.BLACK)

    def _draw_current(self, weather: WeatherData):
        """Draw current weather conditions."""
        current = weather.current
        unit = "°F" if weather.longitude else "°C"  # Simplified - use config

        y_start = self.HEADER_HEIGHT + 1

        # Left section: Condition icon (simplified as text)
        condition_name, _ = current.condition
        # Draw large temperature
        temp_text = f"{int(current.temperature)}°"
        self.draw.text((2, y_start), temp_text, font=cfg.FONT_HEADER, fill=cfg.BLACK)

        # Condition text below
        condition_display = t(f'weather.conditions.{condition_name}', default=condition_name)
        draw_text_with_cjk(
            self.draw, (2, y_start + 12), condition_display[:12],
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        # Right section: Stats (precipitation, humidity, wind)
        stats_x = 90
        divider_x = stats_x - 2

        # Vertical divider
        self.draw.line((divider_x, y_start, divider_x, self.DIVIDER_Y - 1), fill=cfg.BLACK)

        # Precipitation
        precip_text = f"{t('weather.precip')} {current.precipitation_probability}%"
        draw_text_with_cjk(
            self.draw, (stats_x, y_start), precip_text,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        # Humidity
        humid_text = f"{t('weather.humidity')} {current.humidity}%"
        draw_text_with_cjk(
            self.draw, (stats_x, y_start + 8), humid_text,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        # Wind
        wind_text = f"{t('weather.wind')} {int(current.wind_speed)}"
        draw_text_with_cjk(
            self.draw, (stats_x, y_start + 16), wind_text,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

    def _draw_temperature_chart(self, hourly: List[HourlyForecast]):
        """Draw hourly temperature bar chart."""
        if not hourly:
            return

        hours = hourly[:self.CHART_HOURS]
        if not hours:
            return

        # Find min/max for scaling
        temps = [h.temperature for h in hours]
        min_temp = min(temps)
        max_temp = max(temps)
        temp_range = max_temp - min_temp if max_temp != min_temp else 1

        chart_y = self.CHART_Y_TEMP
        chart_h = self.CHART_HEIGHT - 10  # Leave room for labels
        bar_w = (cfg.SCREEN_WIDTH - self.CHART_MARGIN_LEFT) // self.CHART_HOURS

        # Label
        draw_text_with_cjk(
            self.draw, (1, chart_y), t('weather.temperature'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        chart_y += 9

        for i, h in enumerate(hours):
            x = self.CHART_MARGIN_LEFT + i * bar_w

            # Calculate bar height (relative to range)
            normalized = (h.temperature - min_temp) / temp_range
            bar_h = max(2, int(normalized * chart_h))

            # Bar position (bottom-aligned)
            bar_y = chart_y + chart_h - bar_h

            # Draw bar
            self.draw.rectangle(
                (x + 1, bar_y, x + bar_w - 2, chart_y + chart_h),
                fill=cfg.BLACK
            )

            # Draw temperature text on top of bar
            temp_str = f"{int(h.temperature)}"
            text_w = cfg.FONT_MAIN.getbbox(temp_str)[2]
            text_x = x + (bar_w - text_w) // 2
            text_y = bar_y - 8

            # If text would be on black bar, draw inverted
            if text_y >= bar_y - 2:
                text_y = bar_y + 1
                # Draw white text on black
                self.draw.text((text_x, text_y), temp_str, font=cfg.FONT_MAIN, fill=cfg.WHITE)
            else:
                self.draw.text((text_x, text_y), temp_str, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Draw hour label at bottom
            hour_str = h.hour[:2]  # Just hour number
            hour_w = cfg.FONT_MAIN.getbbox(hour_str)[2]
            hour_x = x + (bar_w - hour_w) // 2
            self.draw.text((hour_x, chart_y + chart_h + 1), hour_str, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_precipitation_chart(self, hourly: List[HourlyForecast]):
        """Draw hourly precipitation probability bar chart."""
        if not hourly:
            return

        hours = hourly[:self.CHART_HOURS]
        if not hours:
            return

        chart_y = self.CHART_Y_PRECIP
        chart_h = self.CHART_HEIGHT - 10
        bar_w = (cfg.SCREEN_WIDTH - self.CHART_MARGIN_LEFT) // self.CHART_HOURS

        # Label
        draw_text_with_cjk(
            self.draw, (1, chart_y), t('weather.precipitation'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        chart_y += 9

        for i, h in enumerate(hours):
            x = self.CHART_MARGIN_LEFT + i * bar_w

            # Calculate bar height (percentage)
            bar_h = max(1, int((h.precipitation_probability / 100) * chart_h))

            # Bar position (bottom-aligned)
            bar_y = chart_y + chart_h - bar_h

            # Draw bar
            self.draw.rectangle(
                (x + 1, bar_y, x + bar_w - 2, chart_y + chart_h),
                fill=cfg.BLACK
            )

            # Draw percentage text
            precip_str = f"{h.precipitation_probability}"
            text_w = cfg.FONT_MAIN.getbbox(precip_str)[2]
            text_x = x + (bar_w - text_w) // 2
            text_y = bar_y - 8

            # If text would overlap bar, draw inverted
            if bar_h > chart_h - 10 and h.precipitation_probability > 0:
                text_y = bar_y + 1
                self.draw.text((text_x, text_y), precip_str, font=cfg.FONT_MAIN, fill=cfg.WHITE)
            else:
                self.draw.text((text_x, text_y), precip_str, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_weekly(self, daily: List[DailyForecast]):
        """Draw weekly forecast."""
        if not daily:
            return

        # Show up to 7 days, but limit to fit screen
        days = daily[:7]
        if not days:
            return

        y = self.WEEKLY_Y
        day_w = cfg.SCREEN_WIDTH // len(days)

        # Label
        draw_text_with_cjk(
            self.draw, (1, y), t('weather.this_week'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        y += 9

        for i, d in enumerate(days):
            x = i * day_w

            # Day name
            day_name = d.day_name[:3]
            name_w = cfg.FONT_MAIN.getbbox(day_name)[2]
            name_x = x + (day_w - name_w) // 2
            self.draw.text((name_x, y), day_name, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Condition indicator (simple: filled for bad weather, empty for good)
            condition_name, _ = d.condition
            indicator = "●" if condition_name in ['rain', 'snow', 'thunderstorm', 'heavy_rain'] else "○"
            ind_w = cfg.FONT_MAIN.getbbox(indicator)[2]
            ind_x = x + (day_w - ind_w) // 2
            self.draw.text((ind_x, y + 8), indicator, font=cfg.FONT_MAIN, fill=cfg.BLACK)

            # Average temperature
            avg_temp = f"{int(d.avg_temperature)}°"
            temp_w = cfg.FONT_MAIN.getbbox(avg_temp)[2]
            temp_x = x + (day_w - temp_w) // 2
            self.draw.text((temp_x, y + 16), avg_temp, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    def _draw_error(self, error: str):
        """Draw error message."""
        y = cfg.SCREEN_HEIGHT // 2 - 10
        draw_text_with_cjk(
            self.draw, (10, y), t('weather.error'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        # Truncate error message
        error_short = error[:30] if len(error) > 30 else error
        draw_text_with_cjk(
            self.draw, (10, y + 12), error_short,
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

    def _draw_no_data(self):
        """Draw no data message."""
        y = cfg.SCREEN_HEIGHT // 2 - 10
        draw_text_with_cjk(
            self.draw, (10, y), t('weather.no_data'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        draw_text_with_cjk(
            self.draw, (10, y + 12), t('weather.setup_location'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

    def render_location_setup(self, results: List[dict], selected_idx: int,
                               search_query: str, is_searching: bool) -> Image.Image:
        """Render location setup screen."""
        self.clear()

        # Header
        draw_text_with_cjk(
            self.draw, (2, 1), t('weather.setup_title'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        self.draw.line((0, 11, cfg.SCREEN_WIDTH, 11), fill=cfg.BLACK)

        y = 14

        # Search input
        search_display = f"{t('weather.search')}: {search_query}_"
        draw_text_with_cjk(
            self.draw, (2, y), search_display[:35],
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )
        y += 12

        if is_searching:
            draw_text_with_cjk(
                self.draw, (2, y), t('weather.searching'),
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )
        elif results:
            # Draw results list
            for i, r in enumerate(results[:5]):
                item_y = y + i * 12
                prefix = ">" if i == selected_idx else " "
                location_text = f"{prefix}{r['name']}, {r.get('admin1', '')[:10]}, {r['country'][:10]}"
                location_text = location_text[:40]

                if i == selected_idx:
                    # Highlight selected
                    self.draw.rectangle((0, item_y, cfg.SCREEN_WIDTH, item_y + 11), fill=cfg.BLACK)
                    draw_text_with_cjk(
                        self.draw, (2, item_y), location_text,
                        cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.WHITE
                    )
                else:
                    draw_text_with_cjk(
                        self.draw, (2, item_y), location_text,
                        cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
                    )
        elif search_query:
            draw_text_with_cjk(
                self.draw, (2, y), t('weather.no_results'),
                cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
            )

        # Instructions at bottom
        inst_y = cfg.SCREEN_HEIGHT - 12
        draw_text_with_cjk(
            self.draw, (2, inst_y), t('weather.setup_hint'),
            cfg.FONT_MAIN, cfg.FONT_CJK_MAIN, fill=cfg.BLACK
        )

        return self.canvas
