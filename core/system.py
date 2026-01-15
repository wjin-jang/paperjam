import os
import time
import subprocess
from pathlib import Path
import config as cfg
from core.battery import get_battery_monitor

try:
    from waveshare_epd import epd2in13_V4
    HAS_EPAPER = True
except ImportError:
    HAS_EPAPER = False
    print("WARNING: E-Paper drivers not found. Running in headless/text mode.")

class SystemManager:
    """
    Manages system-level hardware and operations.
    - E-Paper Display initialization
    - Battery monitoring
    - Shutdown/Reboot
    """
    def __init__(self):
        self.epd = self._init_display()
        self.battery = get_battery_monitor()
        self._last_battery_check = 0
        self._low_battery_threshold = 12  # Shutdown at 12%
        
        # Shutdown callback
        self.on_shutdown_request = None

    def _init_display(self):
        if HAS_EPAPER:
            try:
                epd = epd2in13_V4.EPD()
                epd.init()
                epd.Clear(0xFF)
                return epd
            except Exception as e:
                print(f"EPD Init Error: {e}")
        return None

    def get_display(self):
        return self.epd

    def check_battery(self):
        """Check battery level and trigger shutdown if critical."""
        now = time.time()
        if now - self._last_battery_check < 60:
            return
        
        self._last_battery_check = now
        pct = self.battery.percentage
        
        if 0 <= pct <= self._low_battery_threshold and not self.battery.charging:
            print(f"LOW BATTERY ({pct}%) - Initiating safe shutdown...")
            if self.on_shutdown_request:
                self.on_shutdown_request(reason="LOW BATTERY")
            else:
                self.shutdown()

    def sleep_display(self):
        if self.epd:
            try:
                self.epd.sleep()
            except Exception:
                pass

    def wake_display(self):
        if self.epd:
            try:
                self.epd.init()
            except Exception:
                pass

    def clear_display(self):
        if self.epd:
            try:
                self.epd.init()
                self.epd.Clear(0xFF)
            except Exception:
                pass

    def shutdown(self):
        print("System shutting down...")
        self.sleep_display()
        subprocess.run(["sudo", "shutdown", "now"])

    def reboot(self):
        print("System rebooting...")
        self.sleep_display()
        subprocess.run(["sudo", "reboot"])
