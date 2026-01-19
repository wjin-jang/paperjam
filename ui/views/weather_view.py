"""
Weather view renderer using Panel/Menu/Item system.

Uses the standard UI components for consistent rendering.
Bar charts and weather conditions are rendered as images.
"""
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw
from typing import List, Optional

import config as cfg
from core.i18n import t
from core.weather import WeatherData, HourlyForecast, DailyForecast
from ui.views.core import Panel, Menu
from ui.views.items import Item

# Weather icons directory
WEATHER_ICONS_DIR = Path(__file__).parent.parent.parent / "assets" / "weather"

# Short condition names
SHORT_CONDITIONS = {
    'clear': 'Clear', 'mostly_clear': 'Clear', 'partly_cloudy': 'Cloudy',
    'overcast': 'Cloudy', 'fog': 'Fog', 'drizzle': 'Drizzle', 'rain': 'Rain',
    'freezing_drizzle': 'F.Rain', 'freezing_rain': 'F.Rain', 'heavy_rain': 'H.Rain',
    'rain_showers': 'Showers', 'heavy_showers': 'Showers', 'snow': 'Snow',
    'heavy_snow': 'H.Snow', 'snow_grains': 'Snow', 'snow_showers': 'Snow',
    'thunderstorm': 'Storm', 'thunderstorm_hail': 'Storm', 'unknown': '???',
}

# Map conditions to icon files
CONDITION_ICONS = {
    'clear': 'clear.png', 'mostly_clear': 'clear.png',
    'partly_cloudy': 'partly_cloudy.png', 'overcast': 'cloudy.png',
    'fog': 'fog.png', 'drizzle': 'drizzle.png', 'rain': 'rain.png',
    'freezing_drizzle': 'rain.png', 'freezing_rain': 'rain.png',
    'heavy_rain': 'heavy_rain.png', 'rain_showers': 'rain.png',
    'heavy_showers': 'heavy_rain.png', 'snow': 'snow.png',
    'heavy_snow': 'snow.png', 'snow_grains': 'snow.png',
    'snow_showers': 'snow.png', 'thunderstorm': 'thunderstorm.png',
    'thunderstorm_hail': 'thunderstorm.png', 'unknown': 'unknown.png',
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
    """Load weather icon for condition."""
    icon_file = CONDITION_ICONS.get(condition, 'unknown.png')
    icon_path = WEATHER_ICONS_DIR / icon_file
    if icon_path.exists():
        try:
            return Image.open(icon_path).convert('1')
        except Exception:
            pass
    return None


def render_bar_chart(hourly: List[HourlyForecast], width: int, height: int,
                     value_fn, format_fn, is_percentage: bool = False,
                     scroll_offset: int = 0, visible_hours: int = 8) -> Image.Image:
    """Render bar chart as an image."""
    img = Image.new('1', (width, height), cfg.WHITE)
    draw = ImageDraw.Draw(img)

    if not hourly:
        return img

    visible = hourly[scroll_offset:scroll_offset + visible_hours]
    if not visible:
        return img

    bar_w = width // visible_hours
    bar_area_h = height - 16  # Leave room for value and hour labels

    # Get values and range
    all_values = [value_fn(h) for h in hourly]
    values = [value_fn(h) for h in visible]

    if is_percentage:
        min_val, max_val = 0, 100
    else:
        min_val = min(all_values) if all_values else 0
        max_val = max(all_values) if all_values else 1

    val_range = max_val - min_val if max_val != min_val else 1

    for i, (h, val) in enumerate(zip(visible, values)):
        bx = i * bar_w
        center = bx + bar_w // 2

        # Value text at top
        val_text = format_fn(val)
        text_w = cfg.FONT_MAIN.getbbox(val_text)[2]
        draw.text((center - text_w // 2, 0), val_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

        # Bar
        if is_percentage:
            normalized = val / 100
        else:
            normalized = (val - min_val) / val_range

        bar_h = max(1, int(normalized * bar_area_h))
        bar_y = 8 + bar_area_h - bar_h
        draw.rectangle((bx + 2, bar_y, bx + bar_w - 3, 8 + bar_area_h), fill=cfg.BLACK)

        # Hour label at bottom
        hour_text = h.hour[:2]
        hour_w = cfg.FONT_MAIN.getbbox(hour_text)[2]
        draw.text((center - hour_w // 2, height - 8), hour_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    return img


def render_weekly_forecast(daily: List[DailyForecast], width: int, height: int) -> Image.Image:
    """Render weekly forecast as an image."""
    img = Image.new('1', (width, height), cfg.WHITE)
    draw = ImageDraw.Draw(img)

    if not daily:
        return img

    days = daily[:7]
    day_w = width // len(days)

    for i, d in enumerate(days):
        dx = i * day_w
        center = dx + day_w // 2

        # Day name
        day_name = d.day_name[:2]
        name_w = cfg.FONT_MAIN.getbbox(day_name)[2]
        draw.text((center - name_w // 2, 0), day_name, font=cfg.FONT_MAIN, fill=cfg.BLACK)

        # Weather icon or indicator
        condition_name, _ = d.condition
        icon = load_weather_icon(condition_name)
        if icon:
            ix = center - icon.width // 2
            img.paste(icon, (ix, 9))
        else:
            indicator = "●" if condition_name in ['rain', 'snow', 'thunderstorm', 'heavy_rain', 'drizzle'] else "○"
            ind_w = cfg.FONT_MAIN.getbbox(indicator)[2]
            draw.text((center - ind_w // 2, 10), indicator, font=cfg.FONT_MAIN, fill=cfg.BLACK)

        # Temperature
        avg_temp = f"{int(d.avg_temperature)}°"
        temp_w = cfg.FONT_MAIN.getbbox(avg_temp)[2]
        draw.text((center - temp_w // 2, height - 8), avg_temp, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    return img


def render_condition_image(condition: str, width: int, height: int) -> Image.Image:
    """Render condition with icon as an image."""
    img = Image.new('1', (width, height), cfg.WHITE)
    draw = ImageDraw.Draw(img)

    icon = load_weather_icon(condition)
    cond_text = SHORT_CONDITIONS.get(condition, '???')

    if icon:
        # Center icon and text
        icon_x = (width - icon.width - len(cond_text) * 6 - 4) // 2
        img.paste(icon, (icon_x, (height - icon.height) // 2))
        text_x = icon_x + icon.width + 4
    else:
        text_x = 4

    text_y = (height - 8) // 2
    draw.text((text_x, text_y), cond_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    return img


class WeatherViewRenderer:
    """Renderer for weather display using Panel/Menu/Item."""

    PANEL_X = 8
    PANEL_Y = 8
    PANEL_W = cfg.SCREEN_WIDTH - 16
    PANEL_H = cfg.SCREEN_HEIGHT - 16

    CHART_H = 32  # Height for bar chart images
    WEEKLY_H = 34  # Height for weekly image

    CHART_HOURS = 8
    TOTAL_HOURS = 24

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self._icon_cache = {}

    def _get_icon(self, condition: str) -> Optional[Image.Image]:
        if condition not in self._icon_cache:
            self._icon_cache[condition] = load_weather_icon(condition)
        return self._icon_cache[condition]

    def render(self, weather: Optional[WeatherData], title: str,
               selected_section: int = 0, day_offset: int = 0,
               chart_scroll: int = 0, updating: bool = False,
               error: Optional[str] = None) -> Image.Image:
        """Render weather view using Panel/Menu/Item."""
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)

        header = title if title else t('menu.weather')
        if updating:
            header = f"{header}..."

        panel = Panel(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H, header=header)
        menu = panel.create_menu()

        if error and not weather:
            menu.set_items([
                Item(text=t('weather.error'), selectable=False),
                Item(text=error, selectable=False),
            ])
            panel.render(self.canvas)
            return self.canvas

        if not weather or not weather.current:
            menu.set_items([
                Item(text=t('weather.no_data'), selectable=False),
                Item(text=t('weather.setup_location'), selectable=False),
            ])
            panel.render(self.canvas)
            return self.canvas

        # Build items list
        items = []

        # Content width for images
        content_w = panel.content_width - 2

        # Day selection rows
        for i in range(3):
            day_item = self._create_day_item(weather, i, day_offset, content_w)
            items.append(day_item)

        # Get hourly data for selected day
        hourly = self._get_hourly(weather.hourly, day_offset)

        # Temperature section
        items.append(Item(text=t('weather.temperature'), heading=True,
                         id={'section': SECTION_TEMPERATURE}))

        temp_chart = render_bar_chart(
            hourly, content_w, self.CHART_H,
            value_fn=lambda h: h.temperature,
            format_fn=lambda v: f"{int(v)}",
            scroll_offset=chart_scroll,
            visible_hours=self.CHART_HOURS
        )
        temp_item = Item(image=temp_chart, show_image=True, selectable=False)
        temp_item.set_height(self.CHART_H)
        items.append(temp_item)

        # Precipitation section
        items.append(Item(text=t('weather.precipitation'), heading=True,
                         id={'section': SECTION_PRECIPITATION}))

        precip_chart = render_bar_chart(
            hourly, content_w, self.CHART_H,
            value_fn=lambda h: h.precipitation_probability,
            format_fn=lambda v: f"{int(v)}",
            is_percentage=True,
            scroll_offset=chart_scroll,
            visible_hours=self.CHART_HOURS
        )
        precip_item = Item(image=precip_chart, show_image=True, selectable=False)
        precip_item.set_height(self.CHART_H)
        items.append(precip_item)

        # This Week section
        items.append(Item(text=t('weather.this_week'), heading=True,
                         id={'section': SECTION_WEEKLY}))

        weekly_img = render_weekly_forecast(weather.daily, content_w, self.WEEKLY_H)
        weekly_item = Item(image=weekly_img, show_image=True, selectable=False)
        weekly_item.set_height(self.WEEKLY_H)
        items.append(weekly_item)

        menu.set_items(items)

        # Set cursor position based on selected_section
        cursor_row = self._section_to_row(selected_section)
        menu.cursor.row = cursor_row
        menu._ensure_visible()

        panel.render(self.canvas)
        return self.canvas

    def _create_day_item(self, weather: WeatherData, day_idx: int,
                        active_day: int, width: int) -> Item:
        """Create a day selection item with icon."""
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
            return Item(text="???", selectable=True)

        # Get weather icon
        icon = self._get_icon(condition_name)
        cond_text = SHORT_CONDITIONS.get(condition_name, '???')

        # Format: "Today    22° Clear  30%"
        prefix = ">" if day_idx == active_day else " "
        text = f"{prefix}{day_label:<9} {int(temp):>3}° {cond_text:<7} {precip:>3}%"

        return Item(
            text=text,
            icon=icon,
            selectable=True,
            id={'day': day_idx}
        )

    def _get_hourly(self, hourly: List[HourlyForecast], day_offset: int) -> List[HourlyForecast]:
        if not hourly:
            return []

        now = datetime.now()
        if day_offset == 0:
            start_idx = now.hour
        else:
            start_idx = day_offset * 24

        return hourly[start_idx:start_idx + self.TOTAL_HOURS]

    def _section_to_row(self, section: int) -> int:
        """Map section index to menu row."""
        # Rows: 0=Today, 1=Tomorrow, 2=Weekday, 3=TEMP header, 4=temp chart,
        #       5=PRECIP header, 6=precip chart, 7=WEEK header, 8=week chart
        if section <= SECTION_WEEKDAY:
            return section
        elif section == SECTION_TEMPERATURE:
            return 3
        elif section == SECTION_PRECIPITATION:
            return 5
        elif section == SECTION_WEEKLY:
            return 7
        return 0

    def render_location_setup(self, results: List[dict], selected_idx: int,
                               search_query: str, is_searching: bool) -> Image.Image:
        """Render location setup screen using Panel/Menu/Item."""
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)

        panel = Panel(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H,
                      header=t('weather.setup_title'))
        menu = panel.create_menu()

        items = []

        # Search input
        items.append(Item(
            text=f"{t('weather.search')}: {search_query}",
            selectable=False
        ))

        if is_searching:
            items.append(Item(text=t('weather.searching'), selectable=False))
        elif results:
            for r in results[:4]:
                loc_text = f"{r['name']}, {r.get('country', '')}"
                items.append(Item(text=loc_text, selectable=True, id={'result': r}))
        elif search_query and len(search_query) >= 2:
            items.append(Item(text=t('weather.no_results'), selectable=False))

        # Instructions
        items.append(Item(text=t('weather.setup_hint'), selectable=False))

        menu.set_items(items)

        if results:
            menu.cursor.row = 1 + selected_idx  # Skip search input row

        panel.render(self.canvas)
        return self.canvas
