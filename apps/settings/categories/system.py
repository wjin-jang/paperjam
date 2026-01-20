"""
System settings category.

Manages system-related settings including:
- Disk usage display
- Version information
- Power mode (optimized/normal)
- Long press duration
- Auto-update settings
- System actions (restart, reset, shutdown)
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import config as cfg
from config import setup_logger
from core.i18n import t
from ui.views.items import Item

from .base import SettingsCategory

if TYPE_CHECKING:
    from core.settings_manager import SettingsManager
    from .network import NetworkCategory

logger = setup_logger()


class SystemCategory(SettingsCategory):
    """System settings category.

    Handles system-level configuration and actions including power mode
    optimization, update checking, and system commands (restart, shutdown).

    The power mode toggle uses a script to enable/disable CPU frequency
    scaling and optionally disable WiFi for battery savings.

    Attributes:
        POWER_SCRIPT: Path to the power optimization script.
    """

    # Path to power optimization script
    POWER_SCRIPT: Path = Path(__file__).parent.parent.parent.parent / "scripts" / "power_optimise.sh"

    def __init__(self, settings_manager: "SettingsManager") -> None:
        """Initialize system settings.

        Args:
            settings_manager: Reference to the app's SettingsManager.
        """
        super().__init__(t('settings.categories.system'), settings_manager)

        # Callbacks for system actions
        self._screen_clear_callback: Callable[[], None] | None = None
        self._update_callback: Callable[[], None] | None = None
        self._reset_callback: Callable[[], None] | None = None
        self._update_status: str = ""

        # Reference to NetworkCategory for WiFi control during power optimization
        self._network_category: "NetworkCategory | None" = None

    def set_network_category(self, network_cat: "NetworkCategory") -> None:
        """Set reference to NetworkCategory for WiFi control.

        Args:
            network_cat: The NetworkCategory instance.
        """
        self._network_category = network_cat

    def set_screen_clear_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for screen clear shutdown.

        Args:
            callback: Function to call for screen clear + shutdown.
        """
        self._screen_clear_callback = callback

    def set_update_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for performing updates.

        Args:
            callback: Function to call when checking for updates.
        """
        self._update_callback = callback

    def set_reset_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for reset data action.

        Args:
            callback: Function to call when resetting data.
        """
        self._reset_callback = callback

    def _get_disk_usage(self) -> str:
        """Get available disk space.

        Returns:
            Human-readable string like "5.2G free".
        """
        try:
            result = subprocess.check_output(
                ["df", "-h", "/"],
                text=True, timeout=2
            )
            lines = result.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    return f"{parts[3]} {t('settings.system.free')}"
            return t('settings.system.unknown')
        except (subprocess.SubprocessError, OSError, IndexError) as e:
            logger.warning(f"Failed to get disk usage: {e}")
            return t('settings.system.unknown')

    def _get_cpu_governor(self) -> str:
        """Get current CPU frequency governor.

        Returns:
            Governor name (e.g., 'powersave', 'ondemand') or 'unknown'.
        """
        try:
            governor_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
            with open(governor_path, 'r') as f:
                return f.read().strip()
        except (OSError, IOError):
            return "unknown"

    def _is_power_optimised(self) -> bool:
        """Check if power optimizations are enabled.

        Returns:
            True if CPU is in powersave mode.
        """
        return self._get_cpu_governor() == "powersave"

    def _toggle_power_mode(self) -> None:
        """Toggle between optimised and normal power modes.

        Optimised mode:
        - Sets CPU governor to 'powersave'
        - Optionally disables WiFi

        Normal mode:
        - Sets CPU governor to 'ondemand' (or 'schedutil', 'performance')
        """
        try:
            if self._is_power_optimised():
                # Disable optimizations
                if self.POWER_SCRIPT.exists():
                    subprocess.run(
                        ["sudo", "bash", str(self.POWER_SCRIPT), "disable"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                    )
                else:
                    self._set_cpu_governor("ondemand")
                logger.info("Power optimizations disabled")
            else:
                # Enable optimizations
                if self.POWER_SCRIPT.exists():
                    subprocess.run(
                        ["sudo", "bash", str(self.POWER_SCRIPT), "enable"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
                    )
                else:
                    self._set_cpu_governor("powersave")

                # Disable WiFi as part of power optimization
                if self._network_category:
                    self._network_category.disable_wifi()

                logger.info("Power optimizations enabled")
        except (subprocess.SubprocessError, OSError) as e:
            logger.error(f"Failed to toggle power mode: {e}")

    def _set_cpu_governor(self, governor: str) -> None:
        """Set CPU governor for all CPUs.

        For 'normal' mode, tries governors in order: ondemand, schedutil, performance.
        For 'powersave' mode, uses powersave directly.

        Args:
            governor: Target governor name.
        """
        try:
            for cpu_path in Path("/sys/devices/system/cpu/").glob("cpu*/cpufreq/scaling_governor"):
                avail_path = cpu_path.parent / "scaling_available_governors"

                # For normal mode, try multiple governors
                if governor == "ondemand":
                    governors_to_try = ["ondemand", "schedutil", "performance"]
                else:
                    governors_to_try = [governor]

                for gov in governors_to_try:
                    # Check if governor is available
                    try:
                        avail = avail_path.read_text()
                        if gov not in avail:
                            continue
                    except OSError:
                        pass

                    result = subprocess.run(
                        ["sudo", "tee", str(cpu_path)],
                        input=gov, text=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                    )
                    if result.returncode == 0:
                        break
        except (subprocess.SubprocessError, OSError):
            pass

    def build_menu(self) -> list[Item]:
        """Build the system settings menu."""
        long_press = self.settings.get('long_press_duration', 0.5)
        auto_update = self.settings.get('auto_update', False)
        auto_update_str = t('general.on') if auto_update else t('general.off')
        power_mode = (
            t('settings.system.power_optimised')
            if self._is_power_optimised()
            else t('settings.system.power_normal')
        )
        disk = self._get_disk_usage()

        return [
            Item(columns=[t('settings.system.disk'), disk], selectable=False),
            Item(
                columns=[t('settings.system.version'), f"{cfg.VERSION} ({cfg.VERSION_DATE})"],
                selectable=False
            ),
            Item(columns=[t('settings.system.power_mode'), power_mode], selectable=True),
            Item(columns=[t('settings.system.long_press'), f"{long_press}s"], selectable=True),
            Item(columns=[t('settings.system.auto_update'), auto_update_str], selectable=True),
            Item(text=t('settings.system.check_updates')),
            Item(text=t('settings.system.restart')),
            Item(text=t('settings.system.reset_data')),
            Item(text=t('settings.system.shutdown'))
        ]

    def handle_action(self, item_index: int) -> str | None:
        """Handle system settings menu selection."""
        item = self.items[item_index]
        item_text = item.columns[0] if item.columns else item.text

        if t('settings.system.power_mode') in item_text:
            self._toggle_power_mode()
            self.refresh()
        elif t('settings.system.auto_update') in item_text:
            self.settings.toggle('auto_update')
            self.refresh()
        elif t('settings.system.check_updates') in item_text:
            if self._update_callback:
                self._update_callback()
        elif t('settings.system.restart') in item_text:
            subprocess.run(["sudo", "reboot"], timeout=5)
        elif t('settings.system.long_press') in item_text:
            self.settings.cycle('long_press_duration')
            self.refresh()
        elif t('settings.system.reset_data') in item_text:
            if self._reset_callback:
                self._reset_callback()
        elif t('settings.system.shutdown') in item_text:
            if self._screen_clear_callback:
                self._screen_clear_callback()

        return None
