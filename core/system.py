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

    def check_for_updates(self):
        """Check if updates are available from git.

        Returns:
            Tuple of (has_updates: bool, message: str)
        """
        try:
            # Fetch from remote
            subprocess.run(
                ["git", "fetch"],
                cwd=Path(__file__).parent.parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30
            )

            # Check if we're behind origin/main
            result = subprocess.run(
                ["git", "status", "-uno"],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=10
            )

            if "Your branch is behind" in result.stdout:
                return True, "Updates available"
            elif "Your branch is up to date" in result.stdout:
                return False, "Up to date"
            else:
                return False, "Unknown status"
        except (subprocess.SubprocessError, OSError) as e:
            return False, f"Error: {str(e)[:20]}"

    def perform_update(self):
        """Pull updates from git and restart the application.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Git pull
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                return False, f"Git error: {result.stderr[:30]}"

            # Check if update was successful
            if "Already up to date" in result.stdout:
                return True, "Already up to date"

            # Restart the application
            print("Update successful, restarting...")
            self.sleep_display()

            # Use systemctl to restart the service if running as service
            # Otherwise just reboot
            try:
                subprocess.run(
                    ["systemctl", "--user", "restart", "paperjam"],
                    timeout=5
                )
            except (subprocess.SubprocessError, OSError):
                # If service restart fails, do a full reboot
                subprocess.run(["sudo", "reboot"])

            return True, "Updated, restarting..."

        except subprocess.TimeoutExpired:
            return False, "Update timed out"
        except (subprocess.SubprocessError, OSError) as e:
            return False, f"Error: {str(e)[:20]}"
