"""
System hardware management for PaperJam.

Controls:
- Waveshare e-paper display (2.13" V4)
- System operations (shutdown, reboot)
- Battery monitoring integration
- Display sleep/wake for power saving

Falls back to headless mode if e-paper drivers unavailable.
"""
import os
import time
import subprocess
from pathlib import Path
import config as cfg
from core.battery import get_battery_monitor
from core.logger import setup_logger

logger = setup_logger()

try:
    from waveshare_epd import epd2in13_V4
    HAS_EPAPER = True
except ImportError:
    HAS_EPAPER = False
    logger.warning("E-Paper drivers not found - running in headless mode")

class SystemManager:
    """
    Manages system-level hardware and operations.
    - E-Paper Display initialization
    - Battery monitoring
    - Shutdown/Reboot
    - HDMI control
    """
    def __init__(self):
        self.epd = self._init_display()
        self.battery = get_battery_monitor()
        self._last_battery_check = 0
        self._low_battery_threshold = 12  # Shutdown at 12%

        # Shutdown callback
        self.on_shutdown_request = None

        # Disable HDMI by default to save power
        self.disable_hdmi()

    def _init_display(self):
        if HAS_EPAPER:
            try:
                epd = epd2in13_V4.EPD()
                epd.init()
                epd.Clear(0xFF)
                logger.info("E-Paper display initialized")
                return epd
            except Exception as e:
                logger.error(f"E-Paper display init failed: {e}")
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
            logger.warning(f"Low battery ({pct}%)")
            if self.on_shutdown_request:
                self.on_shutdown_request(reason="LOW BATTERY")

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

    def is_hdmi_enabled(self) -> bool:
        """Check if HDMI output is enabled."""
        try:
            result = subprocess.check_output(
                ["tvservice", "-s"], text=True, stderr=subprocess.DEVNULL, timeout=2
            ).strip()
            # "state 0x120006" means off, other states mean on
            return "off" not in result.lower() and "0x120006" not in result
        except (subprocess.SubprocessError, OSError):
            return True  # Assume on if we can't check

    def disable_hdmi(self):
        """Disable HDMI output to save power."""
        try:
            subprocess.run(
                ["sudo", "tvservice", "-o"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            logger.debug("HDMI disabled")
        except (subprocess.SubprocessError, OSError):
            pass  # tvservice may not be available on all systems

    def enable_hdmi(self):
        """Enable HDMI output."""
        try:
            subprocess.run(
                ["sudo", "tvservice", "-p"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            # Restore framebuffer after turning on
            subprocess.run(
                ["sudo", "fbset", "-depth", "8"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            subprocess.run(
                ["sudo", "fbset", "-depth", "16"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
            )
            logger.debug("HDMI enabled")
        except (subprocess.SubprocessError, OSError):
            pass

    def toggle_hdmi(self):
        """Toggle HDMI output on/off."""
        if self.is_hdmi_enabled():
            self.disable_hdmi()
        else:
            self.enable_hdmi()

    def shutdown(self):
        logger.info("System shutting down")
        self.sleep_display()
        try:
            subprocess.run(["/usr/bin/sudo", "/usr/sbin/shutdown", "now"], timeout=10)
        except subprocess.TimeoutExpired:
            logger.error("Shutdown command timed out")
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Shutdown failed: {e}")

    def reboot(self):
        logger.info("System rebooting")
        self.sleep_display()
        try:
            subprocess.run(["/usr/bin/sudo", "/usr/sbin/reboot"], timeout=10)
        except subprocess.TimeoutExpired:
            logger.error("Reboot command timed out")
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Reboot failed: {e}")

    def check_for_updates(self):
        """Check if updates are available from git.

        Returns:
            Tuple of (has_updates: bool, message: str)
        """
        try:
            # Fetch from remote
            result = subprocess.run(
                ["git", "fetch"],
                cwd=Path(__file__).parent.parent,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Check for network errors
            if result.returncode != 0:
                error_msg = result.stderr.lower() if result.stderr else ""
                if "could not resolve" in error_msg or "unable to access" in error_msg:
                    return False, "No internet"
                if "connection refused" in error_msg or "connection timed out" in error_msg:
                    return False, "Connection failed"
                return False, "Fetch failed"

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
        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except (subprocess.SubprocessError, OSError) as e:
            return False, f"Error: {str(e)[:20]}"

    def perform_update(self):
        """Pull updates from git and restart the application.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            repo_path = Path(__file__).parent.parent

            # Stash any local changes to avoid merge conflicts
            subprocess.run(
                ["git", "stash"],
                cwd=repo_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10
            )

            # Git pull
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=repo_path,
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
            logger.info("Update successful, restarting")
            self.sleep_display()

            # Use systemctl to restart the service if running as service
            # Otherwise just reboot
            try:
                subprocess.run(
                    ["/usr/bin/systemctl", "--user", "restart", "paperjam"],
                    timeout=5
                )
            except (subprocess.SubprocessError, OSError):
                # If service restart fails, do a full reboot
                try:
                    subprocess.run(["/usr/bin/sudo", "/usr/sbin/reboot"], timeout=10)
                except (subprocess.SubprocessError, OSError) as e:
                    logger.error(f"Reboot after update failed: {e}")

            return True, "Updated, restarting..."

        except subprocess.TimeoutExpired:
            return False, "Update timed out"
        except (subprocess.SubprocessError, OSError) as e:
            return False, f"Error: {str(e)[:20]}"
