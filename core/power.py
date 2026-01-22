"""
Dynamic power management for PaperJam OS.

Provides intelligent power state management to maximize battery life on the
Raspberry Pi Zero 2 W. Adjusts CPU frequency, WiFi, and other hardware based
on current activity.

Power States:
    IDLE: Screensaver active, minimum power consumption
    BROWSING: User navigating menus, moderate responsiveness needed
    PLAYBACK: Audio playing, CPU needs headroom for decoding
    NETWORK: Network activity required (weather, updates)

Features:
    - Dynamic CPU governor switching (powersave/conservative/ondemand)
    - Automatic WiFi power management
    - Network context manager for temporary WiFi enable
    - Low battery power reduction mode
"""

import os
import subprocess
from enum import Enum
from threading import Lock
from typing import Optional, Callable
from config import setup_logger

logger = setup_logger()


class PowerState(Enum):
    """System power states for dynamic power management."""
    IDLE = "idle"           # Screensaver active, minimal power
    BROWSING = "browsing"   # Menu navigation, moderate power
    PLAYBACK = "playback"   # Audio playback active
    NETWORK = "network"     # Network activity needed


class PowerManager:
    """
    Dynamic power management controller.

    Adjusts system power settings based on current activity to maximize
    battery life while maintaining responsive user experience.

    Attributes:
        state: Current power state.
        wifi_enabled: Whether WiFi is currently enabled.
        low_power_mode: Whether low power mode is active (battery <15%).
    """

    # CPU governor and max frequency settings per power state
    # (governor, max_freq_mhz) - Pi Zero 2 W supports 250-1000 MHz
    CPU_SETTINGS = {
        PowerState.IDLE: ("powersave", 250),
        PowerState.BROWSING: ("conservative", 600),
        PowerState.PLAYBACK: ("ondemand", 800),
        PowerState.NETWORK: ("ondemand", 1000),
    }

    # Low power mode overrides (battery <15%)
    LOW_POWER_CPU_SETTINGS = {
        PowerState.IDLE: ("powersave", 250),
        PowerState.BROWSING: ("powersave", 400),
        PowerState.PLAYBACK: ("conservative", 600),
        PowerState.NETWORK: ("conservative", 600),
    }

    # Path to sysfs CPU frequency interface
    CPU_FREQ_PATH = "/sys/devices/system/cpu/cpu0/cpufreq"

    def __init__(self):
        """Initialize power manager with default IDLE state."""
        self._state = PowerState.IDLE
        self._lock = Lock()
        self._wifi_enabled = True  # Assume WiFi starts enabled
        self._low_power_mode = False
        self._state_change_callback: Optional[Callable[[PowerState], None]] = None

        # Check if we're running on actual hardware
        self._has_cpu_control = os.path.exists(self.CPU_FREQ_PATH)
        self._has_wifi_control = self._check_wifi_available()

        if self._has_cpu_control:
            logger.info("Power manager: CPU frequency control available")
        else:
            logger.info("Power manager: Running in simulation mode (no CPU control)")

        if self._has_wifi_control:
            logger.info("Power manager: WiFi control available")

    @property
    def state(self) -> PowerState:
        """Get current power state."""
        return self._state

    @property
    def wifi_enabled(self) -> bool:
        """Check if WiFi is enabled."""
        return self._wifi_enabled

    @property
    def low_power_mode(self) -> bool:
        """Check if low power mode is active."""
        return self._low_power_mode

    def set_state_change_callback(self, callback: Callable[[PowerState], None]) -> None:
        """Set callback for power state changes.

        Args:
            callback: Function called with new PowerState when state changes.
        """
        self._state_change_callback = callback

    def set_state(self, state: PowerState) -> None:
        """Set power state and apply corresponding hardware settings.

        Args:
            state: New power state to apply.
        """
        with self._lock:
            if state == self._state:
                return

            old_state = self._state
            self._state = state
            logger.debug(f"Power state: {old_state.value} -> {state.value}")

            # Apply CPU settings
            settings = (self.LOW_POWER_CPU_SETTINGS if self._low_power_mode
                       else self.CPU_SETTINGS)
            governor, max_freq = settings[state]
            self._set_cpu_governor(governor)
            self._set_cpu_max_freq(max_freq)

            # Auto WiFi management
            if state == PowerState.PLAYBACK:
                # Disable WiFi during playback for power savings
                self._set_wifi_power_save(True)
            elif state == PowerState.NETWORK:
                # Ensure WiFi is fully active for network operations
                self._set_wifi_power_save(False)
            elif state == PowerState.IDLE:
                # Enable aggressive WiFi power save during idle
                self._set_wifi_power_save(True)

            # Notify callback
            if self._state_change_callback:
                try:
                    self._state_change_callback(state)
                except Exception as e:
                    logger.error(f"Power state callback error: {e}")

    def set_low_power_mode(self, enabled: bool) -> None:
        """Enable or disable low power mode.

        Low power mode is activated when battery is low (<15%) to extend
        remaining runtime. Reduces CPU frequencies and disables non-essential
        features.

        Args:
            enabled: Whether to enable low power mode.
        """
        with self._lock:
            if enabled == self._low_power_mode:
                return

            self._low_power_mode = enabled
            if enabled:
                logger.info("Low power mode enabled")
            else:
                logger.info("Low power mode disabled")

            # Re-apply current state with new power settings
            state = self._state
            self._state = None  # Force re-apply

        # Release lock before calling set_state (which acquires it)
        self.set_state(state)

    def _set_cpu_governor(self, governor: str) -> None:
        """Set CPU frequency governor.

        Args:
            governor: Governor name (powersave, conservative, ondemand, performance).
        """
        if not self._has_cpu_control:
            return

        try:
            # Apply to all CPU cores
            for cpu_id in range(4):  # Pi Zero 2 W has 4 cores
                path = f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_governor"
                if os.path.exists(path):
                    with open(path, 'w') as f:
                        f.write(governor)
            logger.debug(f"CPU governor set to: {governor}")
        except (IOError, OSError) as e:
            logger.warning(f"Failed to set CPU governor: {e}")

    def _set_cpu_max_freq(self, freq_mhz: int) -> None:
        """Set CPU maximum frequency.

        Args:
            freq_mhz: Maximum frequency in MHz.
        """
        if not self._has_cpu_control:
            return

        try:
            freq_khz = freq_mhz * 1000
            for cpu_id in range(4):
                path = f"/sys/devices/system/cpu/cpu{cpu_id}/cpufreq/scaling_max_freq"
                if os.path.exists(path):
                    with open(path, 'w') as f:
                        f.write(str(freq_khz))
            logger.debug(f"CPU max freq set to: {freq_mhz} MHz")
        except (IOError, OSError) as e:
            logger.warning(f"Failed to set CPU max freq: {e}")

    def _check_wifi_available(self) -> bool:
        """Check if WiFi interface is available."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", "wlan0"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False

    def _set_wifi_power_save(self, enabled: bool) -> None:
        """Set WiFi power save mode.

        Args:
            enabled: Whether to enable power save.
        """
        if not self._has_wifi_control:
            return

        try:
            mode = "on" if enabled else "off"
            subprocess.run(
                ["iw", "wlan0", "set", "power_save", mode],
                capture_output=True,
                timeout=5
            )
            logger.debug(f"WiFi power save: {mode}")
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to set WiFi power save: {e}")

    def enable_wifi(self) -> None:
        """Enable WiFi interface and disable power save."""
        if not self._has_wifi_control:
            return

        with self._lock:
            if self._wifi_enabled:
                return

            try:
                # Unblock WiFi
                subprocess.run(
                    ["rfkill", "unblock", "wifi"],
                    capture_output=True,
                    timeout=5
                )
                # Bring up interface
                subprocess.run(
                    ["ip", "link", "set", "wlan0", "up"],
                    capture_output=True,
                    timeout=5
                )
                # Disable power save for active use
                subprocess.run(
                    ["iw", "wlan0", "set", "power_save", "off"],
                    capture_output=True,
                    timeout=5
                )
                self._wifi_enabled = True
                logger.info("WiFi enabled")
            except (subprocess.SubprocessError, OSError) as e:
                logger.error(f"Failed to enable WiFi: {e}")

    def disable_wifi(self) -> None:
        """Disable WiFi interface for maximum power savings."""
        if not self._has_wifi_control:
            return

        with self._lock:
            if not self._wifi_enabled:
                return

            try:
                # Soft block WiFi
                subprocess.run(
                    ["rfkill", "block", "wifi"],
                    capture_output=True,
                    timeout=5
                )
                self._wifi_enabled = False
                logger.info("WiFi disabled")
            except (subprocess.SubprocessError, OSError) as e:
                logger.error(f"Failed to disable WiFi: {e}")

    def request_network(self) -> 'NetworkContext':
        """Request temporary network access.

        Returns a context manager that ensures WiFi is enabled for the
        duration of the network operation, then restores previous state.

        Usage:
            with power_manager.request_network():
                # Perform network operations
                fetch_weather_data()

        Returns:
            NetworkContext for use with 'with' statement.
        """
        return NetworkContext(self)

    def get_cpu_frequency(self) -> Optional[int]:
        """Get current CPU frequency in MHz.

        Returns:
            Current frequency in MHz, or None if unavailable.
        """
        if not self._has_cpu_control:
            return None

        try:
            with open(f"{self.CPU_FREQ_PATH}/scaling_cur_freq", 'r') as f:
                freq_khz = int(f.read().strip())
                return freq_khz // 1000
        except (IOError, OSError, ValueError):
            return None

    def get_stats(self) -> dict:
        """Get current power management statistics.

        Returns:
            Dict with current state, CPU frequency, WiFi status, etc.
        """
        return {
            'state': self._state.value,
            'low_power_mode': self._low_power_mode,
            'wifi_enabled': self._wifi_enabled,
            'cpu_freq_mhz': self.get_cpu_frequency(),
        }


class NetworkContext:
    """Context manager for temporary network access.

    Enables WiFi, sets power state to NETWORK, then restores previous
    state on exit.
    """

    def __init__(self, pm: PowerManager):
        """Initialize with reference to power manager.

        Args:
            pm: PowerManager instance.
        """
        self.pm = pm
        self._previous_state: Optional[PowerState] = None

    def __enter__(self) -> 'NetworkContext':
        """Enter network context - enable WiFi and set network power state."""
        self._previous_state = self.pm.state
        self.pm.enable_wifi()
        self.pm.set_state(PowerState.NETWORK)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit network context - restore previous power state.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Exception traceback if raised.

        Returns:
            False to propagate any exceptions.
        """
        if self._previous_state:
            self.pm.set_state(self._previous_state)
        return False


# Global power manager instance (singleton)
_power_manager: Optional[PowerManager] = None


def get_power_manager() -> PowerManager:
    """Get or create the global power manager instance.

    Returns:
        Global PowerManager singleton.
    """
    global _power_manager
    if _power_manager is None:
        _power_manager = PowerManager()
    return _power_manager
