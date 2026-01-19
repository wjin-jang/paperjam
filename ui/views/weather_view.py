"""
Weather view renderer using Panel/Menu/Item system.

Layout:
┌─────────────────────────────────────────────────────────┐
│ Location Name                                           │
├─────────────────────────────────────────────────────────┤
│ [ICON] 22°  │ Precip 30%  │ ██Today██                  │
│       Clear │ Humid  65%  │   Tomorrow                  │
│             │ Wind   12   │   Wednesday                 │
├─────────────────────────────────────────────────────────┤
│ TEMPERATURE                                             │
│ 22   24   26   28   26   24   22   20                   │
│ ██   ████████████████████   ██   ██                     │
│ 09   10   11   12   13   14   15   16                   │
├─────────────────────────────────────────────────────────┤
│ PRECIPITATION                                           │
│  0   20   40   60   40   20   10    0                   │
│      ██   ████████████████   ██                         │
│ 09   10   11   12   13   14   15   16                   │
├─────────────────────────────────────────────────────────┤
│ THIS WEEK                                               │
│ [☀]  [☁]  [☂]  [☀]  [☀]  [☁]  [☂]                      │
│  MO   TU   WE   TH   FR   SA   SU                      │
│  15°  12°  10°  14°  16°  13°  11°                     │
└─────────────────────────────────────────────────────────┘
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

# Icon directories
WEATHER_ICONS_DIR = Path(__file__).parent.parent.parent / "assets" / "weather"
SMALL_ICONS_DIR = WEATHER_ICONS_DIR / "small"

# Condition names
SHORT_CONDITIONS = {
    'clear': 'Clear', 'mostly_clear': 'Clear', 'partly_cloudy': 'Cloudy',
    'overcast': 'Cloudy', 'fog': 'Fog', 'drizzle': 'Drizzle', 'rain': 'Rain',
    'freezing_drizzle': 'F.Rain', 'freezing_rain': 'F.Rain', 'heavy_rain': 'H.Rain',
    'rain_showers': 'Showers', 'heavy_showers': 'Showers', 'snow': 'Snow',
    'heavy_snow': 'H.Snow', 'snow_grains': 'Snow', 'snow_showers': 'Snow',
    'thunderstorm': 'Storm', 'thunderstorm_hail': 'Storm', 'unknown': '???',
}

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
SECTION_DAY = 0
SECTION_TEMPERATURE = 1
SECTION_PRECIPITATION = 2
SECTION_WEEKLY = 3
SECTION_COUNT = 4


def load_icon(condition: str, small: bool = False) -> Optional[Image.Image]:
    """Load weather icon."""
    icon_file = CONDITION_ICONS.get(condition, 'unknown.png')
    icon_dir = SMALL_ICONS_DIR if small else WEATHER_ICONS_DIR
    icon_path = icon_dir / icon_file
    if icon_path.exists():
        try:
            return Image.open(icon_path).convert('1')
        except Exception:
            pass
    return None


def render_current_section(weather: WeatherData, width: int, height: int,
                           day_offset: int, selected: bool) -> Image.Image:
    """Render the current conditions section as an image."""
    img = Image.new('1', (width, height), cfg.WHITE)
    draw = ImageDraw.Draw(img)

    # Get data for selected day
    if day_offset == 0:
        temp = weather.current.temperature
        condition_name, _ = weather.current.condition
        precip = weather.current.precipitation_probability
        humid = weather.current.humidity
        wind = weather.current.wind_speed
    elif day_offset < len(weather.daily):
        day = weather.daily[day_offset]
        temp = day.avg_temperature
        condition_name, _ = day.condition
        precip = day.precipitation_probability
        humid = 0
        wind = 0
    else:
        return img

    # Equal column widths
    col_w = width // 3

    # Column 1: Icon, temperature, condition
    icon = load_icon(condition_name)
    if icon:
        img.paste(icon, (2, 2))

    temp_text = f"{int(temp)}°"
    draw.text((20, 0), temp_text, font=cfg.FONT_HEADER, fill=cfg.BLACK)

    cond_text = SHORT_CONDITIONS.get(condition_name, '???').upper()
    draw.text((20, 14), cond_text, font=cfg.FONT_HEADER, fill=cfg.BLACK)

    # Vertical divider
    draw.line((col_w, 0, col_w, height - 1), fill=cfg.BLACK)

    # Column 2: Stats (using row heights)
    stats_x = col_w + 5
    stats = [
        (t('weather.precip'), f"{precip}%"),
        (t('weather.humidity'), f"{humid}%"),
        (t('weather.wind'), f"{int(wind)}"),
    ]
    for i, (label, value) in enumerate(stats):
        row_y = i * cfg.ROW_HEIGHT + 3
        draw.text((stats_x, row_y), f"{label} {value}", font=cfg.FONT_MAIN, fill=cfg.BLACK)

    # Vertical divider
    draw.line((col_w * 2, 0, col_w * 2, height - 1), fill=cfg.BLACK)

    # Column 3: Day selector (full day names as rows with borders)
    day_x = col_w * 2
    day_col_w = col_w

    # Get day labels (full day names)
    day_labels = [t('weather.today'), t('weather.tomorrow')]
    if len(weather.daily) > 2:
        day_labels.append(weather.daily[2].day_name_full)
    else:
        day_labels.append("???")

    for i, label in enumerate(day_labels):
        row_y = i * cfg.ROW_HEIGHT
        is_selected = (i == day_offset)

        # Draw row with border
        bg = cfg.BLACK if is_selected else cfg.WHITE
        fg = cfg.WHITE if is_selected else cfg.BLACK
        draw.rectangle((day_x, row_y, day_x + day_col_w, row_y + cfg.ROW_HEIGHT),
                      fill=bg, outline=cfg.BLACK)
        draw.text((day_x + 5, row_y + 3), label, font=cfg.FONT_MAIN, fill=fg)

    return img


def render_bar_chart(hourly: List[HourlyForecast], width: int, height: int,
                     value_fn, format_fn, label: str = None,
                     is_percentage: bool = False,
                     scroll_offset: int = 0, visible_hours: int = 8,
                     min_range: float = 10.0) -> Image.Image:
    """Render bar chart as an image.

    Args:
        label: Label to draw in top left corner (e.g., "TEMPERATURE")
        min_range: Minimum range for scaling (prevents over-exaggeration of small differences)
    """
    img = Image.new('1', (width, height), cfg.WHITE)
    draw = ImageDraw.Draw(img)

    if not hourly:
        return img

    visible = hourly[scroll_offset:scroll_offset + visible_hours]
    if not visible:
        return img

    bar_w = width // visible_hours
    bar_area_h = height - 8  # Only time at bottom (8)
    bar_area_y = 0  # Bar area starts from top

    all_values = [value_fn(h) for h in hourly]
    values = [value_fn(h) for h in visible]

    if is_percentage:
        min_val, max_val = 0, 100
    else:
        # Use all hourly data for consistent scaling
        data_min = min(all_values) if all_values else 0
        data_max = max(all_values) if all_values else 1
        data_range = data_max - data_min

        # Ensure minimum range to prevent over-exaggeration
        if data_range < min_range:
            center = (data_max + data_min) / 2
            min_val = center - min_range / 2
            max_val = center + min_range / 2
        else:
            min_val = data_min
            max_val = data_max

    val_range = max_val - min_val if max_val != min_val else 1

    # Draw all bars first
    for i, (h, val) in enumerate(zip(visible, values)):
        bx = i * bar_w
        center = bx + bar_w // 2

        # Calculate bar dimensions
        if is_percentage:
            normalized = val / 100
        else:
            normalized = max(0, min(1, (val - min_val) / val_range))

        bar_h = max(1, int(normalized * bar_area_h))
        bar_y = bar_area_y + bar_area_h - bar_h
        bar_x1 = bx + 2
        bar_x2 = bx + bar_w - 3

        # Draw bar
        draw.rectangle((bar_x1, bar_y, bar_x2, bar_area_y + bar_area_h), fill=cfg.BLACK)

        # Time at bottom - use full format (12:00)
        hour_text = h.hour
        hour_w = cfg.FONT_MAIN.getbbox(hour_text)[2]
        draw.text((center - hour_w // 2, height - 8), hour_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

    # Draw label in top left corner with partial inversion
    if label:
        label_text = label.upper()
        text_bbox = cfg.FONT_MAIN.getbbox(label_text)
        text_w = text_bbox[2]
        text_h = text_bbox[3]
        text_x = 2
        text_y = 0

        # Create text image
        text_img = Image.new('1', (text_w, text_h), cfg.WHITE)
        text_draw = ImageDraw.Draw(text_img)
        text_draw.text((0, 0), label_text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

        # Draw each pixel, inverting where it overlaps with black (bar)
        for py in range(text_h):
            for px in range(text_w):
                img_x = text_x + px
                img_y = text_y + py
                if img_x < width and img_y < height:
                    text_pixel = text_img.getpixel((px, py))
                    bg_pixel = img.getpixel((img_x, img_y))
                    if text_pixel == 0:  # Text is black
                        # Invert: white on black, black on white
                        img.putpixel((img_x, img_y), cfg.WHITE if bg_pixel == 0 else cfg.BLACK)

    return img


def render_weekly(daily: List[DailyForecast], width: int, height: int) -> Image.Image:
    """Render weekly forecast with small icons."""
    img = Image.new('1', (width, height), cfg.WHITE)
    draw = ImageDraw.Draw(img)

    if not daily:
        return img

    days = daily[:7]
    day_w = width // len(days)

    for i, d in enumerate(days):
        dx = i * day_w
        center = dx + day_w // 2

        # Row 1: Icon + Day name inline (FONT_MAIN)
        condition_name, _ = d.condition
        icon = load_icon(condition_name, small=True)
        day_name = d.day_name[:3].upper()
        name_w = cfg.FONT_MAIN.getbbox(day_name)[2]

        # Calculate total width of icon + day name
        icon_w = icon.width if icon else 0
        total_w = icon_w + 2 + name_w  # 2px gap between icon and text
        start_x = center - total_w // 2

        if icon:
            img.paste(icon, (start_x, 1))
        draw.text((start_x + icon_w + 2, 1), day_name, font=cfg.FONT_MAIN, fill=cfg.BLACK)

        # Row 2: Temperature (FONT_HEADER)
        temp_text = f"{int(d.avg_temperature)}°"
        temp_w = cfg.FONT_HEADER.getbbox(temp_text)[2]
        draw.text((center - temp_w // 2, 12), temp_text, font=cfg.FONT_HEADER, fill=cfg.BLACK)

    return img


class WeatherViewRenderer:
    """Renderer for weather display."""

    PANEL_X = 8
    PANEL_Y = 8
    PANEL_W = cfg.SCREEN_WIDTH - 16
    PANEL_H = cfg.SCREEN_HEIGHT - 16

    CURRENT_H = cfg.ROW_HEIGHT * 3
    CHART_H = 28
    WEEKLY_H = 28

    CHART_HOURS = 8
    TOTAL_HOURS = 24

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self._icon_cache = {}

    def render(self, weather: Optional[WeatherData], title: str,
               selected_section: int = 0, day_offset: int = 0,
               chart_scroll: int = 0, updating: bool = False,
               error: Optional[str] = None) -> Image.Image:
        """Render weather view."""
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

        items = []
        content_w = panel.content_width - 2

        # Current conditions section (3-column layout)
        current_img = render_current_section(
            weather, content_w, self.CURRENT_H,
            day_offset, selected=selected_section == SECTION_DAY
        )
        current_item = Item(image=current_img, show_image=True, selectable=True,
                           id={'section': SECTION_DAY})
        current_item.set_height(self.CURRENT_H)
        items.append(current_item)

        # Get hourly data for selected day
        hourly = self._get_hourly(weather.hourly, day_offset)

        # Temperature chart (label drawn on chart)
        temp_chart = render_bar_chart(
            hourly, content_w, self.CHART_H,
            value_fn=lambda h: h.temperature,
            format_fn=lambda v: f"{int(v)}",
            label=t('weather.temperature'),
            scroll_offset=chart_scroll,
            min_range=10.0  # Minimum 10 degree range
        )
        temp_item = Item(image=temp_chart, show_image=True, selectable=True,
                        id={'section': SECTION_TEMPERATURE})
        temp_item.set_height(self.CHART_H)
        items.append(temp_item)

        # Precipitation chart (label drawn on chart)
        precip_chart = render_bar_chart(
            hourly, content_w, self.CHART_H,
            value_fn=lambda h: h.precipitation_probability,
            format_fn=lambda v: f"{int(v)}",
            label=t('weather.precipitation'),
            is_percentage=True,
            scroll_offset=chart_scroll
        )
        precip_item = Item(image=precip_chart, show_image=True, selectable=True,
                          id={'section': SECTION_PRECIPITATION})
        precip_item.set_height(self.CHART_H)
        items.append(precip_item)

        # This Week section
        items.append(Item(text=t('weather.this_week'), heading=True,
                         id={'section': SECTION_WEEKLY}))

        weekly_img = render_weekly(weather.daily, content_w, self.WEEKLY_H)
        weekly_item = Item(image=weekly_img, show_image=True, selectable=False)
        weekly_item.set_height(self.WEEKLY_H)
        items.append(weekly_item)

        menu.set_items(items)

        # Map section to row
        row_map = {
            SECTION_DAY: 0,
            SECTION_TEMPERATURE: 1,
            SECTION_PRECIPITATION: 2,
            SECTION_WEEKLY: 3,
        }
        menu.cursor.row = row_map.get(selected_section, 0)
        menu._ensure_visible()

        panel.render(self.canvas)
        return self.canvas

    def _get_hourly(self, hourly: List[HourlyForecast], day_offset: int) -> List[HourlyForecast]:
        """Get hourly data for selected day."""
        if not hourly:
            return []

        now = datetime.now()

        if day_offset == 0:
            # Today: start from current hour
            start_idx = now.hour
        else:
            # Future days: start from beginning of that day
            # Day 1 = tomorrow = hours 24-47
            # Day 2 = day after = hours 48-71
            start_idx = day_offset * 24

        # Make sure we don't go past available data
        if start_idx >= len(hourly):
            return []

        end_idx = min(start_idx + self.TOTAL_HOURS, len(hourly))
        return hourly[start_idx:end_idx]

    def render_location_setup(self, results: List[dict], selected_idx: int,
                               search_query: str, is_searching: bool) -> Image.Image:
        """Render location setup screen."""
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)

        panel = Panel(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H,
                      header=t('weather.setup_title'))
        menu = panel.create_menu()

        items = [
            Item(text=f"{t('weather.search')}: {search_query}", selectable=False)
        ]

        if is_searching:
            items.append(Item(text=t('weather.searching'), selectable=False))
        elif results:
            for r in results[:4]:
                loc_text = f"{r['name']}, {r.get('country', '')}"
                items.append(Item(text=loc_text, selectable=True, id={'result': r}))
        elif search_query and len(search_query) >= 2:
            items.append(Item(text=t('weather.no_results'), selectable=False))

        items.append(Item(text=t('weather.setup_hint'), selectable=False))

        menu.set_items(items)
        if results:
            menu.cursor.row = 1 + selected_idx

        panel.render(self.canvas)
        return self.canvas
