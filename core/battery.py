"""
Battery monitoring for SugarPi 3 (IP5312 chip).
"""
import threading
import time
from config import setup_logger

logger = setup_logger()

# I2C address for IP5312 (SugarPi 3)
I2C_ADDR = 0x57

class BatteryMonitor:
    """Monitor battery status from PiSugar 3."""

    def __init__(self):
        self._percentage = -1
        self._charging = False
        self._lock = threading.Lock()
        self._i2c_lock = threading.Lock()  # Separate lock for I2C operations
        self._running = False
        self._bus = None
        self._init_i2c()

    def _init_i2c(self):
        """Initialize I2C bus."""
        try:
            import smbus2
            self._bus = smbus2.SMBus(1)
            logger.info("Battery monitor I2C initialized")
        except ImportError:
            logger.warning("smbus2 not available - battery monitoring disabled")
            self._bus = None
        except Exception as e:
            logger.error(f"Battery I2C init failed: {e}")
            self._bus = None

    def _read_battery(self):
        """Read battery percentage and charging status from PiSugar 3."""
        if not self._bus:
            return -1, False

        # Use I2C lock to prevent concurrent I2C access
        with self._i2c_lock:
            try:
                # Read battery percentage from 0x2A
                pct = self._bus.read_byte_data(I2C_ADDR, 0x2A)
                pct = max(0, min(100, pct))

                # Read charging status from register 0x02
                # Bit 7 (0x80) indicates external power connected
                status = self._bus.read_byte_data(I2C_ADDR, 0x02)
                charging = bool(status & 0x80)

                self._consecutive_failures = 0
                return pct, charging
            except Exception as e:
                self._consecutive_failures = getattr(self, '_consecutive_failures', 0) + 1
                # Only log occasionally to avoid spam
                if self._consecutive_failures == 1 or self._consecutive_failures % 10 == 0:
                    logger.warning(f"Battery I2C read failed ({self._consecutive_failures}x): {e}")
                return -1, False

    def start(self):
        """Start background battery monitoring."""
        if self._running:
            return
        self._running = True

        # Immediate first read
        pct, charging = self._read_battery()
        with self._lock:
            self._percentage = pct
            self._charging = charging

        def monitor():
            while self._running:
                time.sleep(30)  # Update every 30 seconds
                pct, charging = self._read_battery()
                with self._lock:
                    self._percentage = pct
                    self._charging = charging

        t = threading.Thread(target=monitor, daemon=True)
        t.start()

    def stop(self):
        """Stop battery monitoring."""
        self._running = False

    @property
    def percentage(self) -> int:
        """Get current battery percentage (-1 if unavailable)."""
        with self._lock:
            return self._percentage

    @property
    def charging(self) -> bool:
        """Check if battery is charging."""
        with self._lock:
            return self._charging

    def get_display_text(self) -> str:
        """Get formatted battery text for display."""
        pct = self.percentage
        if pct < 0:
            return ""
        charging_icon = "+" if self.charging else ""
        return f"{charging_icon}{pct}%"


# Global instance
_battery_monitor = None

def get_battery_monitor() -> BatteryMonitor:
    """Get the global battery monitor instance."""
    global _battery_monitor
    if _battery_monitor is None:
        _battery_monitor = BatteryMonitor()
        _battery_monitor.start()
    return _battery_monitor
