"""
Screen overlay rendering for status indicators.

Renders on top of the main frame:
- Status icons (headphones, WiFi, Bluetooth) in top-left
- Battery indicator (percentage or icon) in top-right
"""
from PIL import ImageDraw
import config as cfg
from core.battery import get_battery_monitor


class OverlayRenderer:
    def __init__(self):
        self.battery = get_battery_monitor()

    def draw_status_icons(self, img, audio_connected, wifi_connected, bt_enabled):
        """Draw status icons (Headphones, WiFi, Bluetooth) on the image."""
        if not cfg.FONT_ICONS:
            return img

        icons = ""
        if audio_connected: icons += "H"
        if wifi_connected: icons += "W"
        if bt_enabled: icons += "B"

        if icons:
            draw = ImageDraw.Draw(img)
            draw.text((8, 0), icons, font=cfg.FONT_ICONS, fill=cfg.BLACK)

        return img

    def draw_battery(self, img):
        """Draw battery indicator on the image."""
        pct = self.battery.percentage
        if pct < 0:
            return img

        if cfg.FONT_ICONS:
            adjusted_pct = pct - cfg.BATTERY_SHUTDOWN_THRESHOLD
            steps = ((100-cfg.BATTERY_SHUTDOWN_THRESHOLD)/8) # 8 battery icons
            
            icon_num = min(8, max(0, round(adjusted_pct / steps)))
            if icon_num == 0: 
                icon_num = 1  # Avoid empty unless critical
            
            icon = str(icon_num)
            if self.battery.charging:
                icon = "C" + icon

            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), icon, font=cfg.FONT_ICONS)
            text_w = bbox[2] - bbox[0]
            x = cfg.SCREEN_WIDTH - text_w - 8
            
            draw.text((x, 0), icon, font=cfg.FONT_ICONS, fill=cfg.BLACK)
        else:
            text = f"{int(pct)}%"
            draw = ImageDraw.Draw(img)
            bbox = draw.textbbox((0, 0), text, font=cfg.FONT_MAIN)
            text_w = bbox[2] - bbox[0]
            x = cfg.SCREEN_WIDTH - text_w - 4
            
            draw.text((x, 0), text, font=cfg.FONT_MAIN, fill=cfg.BLACK)

        return img
