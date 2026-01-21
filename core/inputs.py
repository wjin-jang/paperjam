"""
Input device handling using evdev and GPIO.

Features:
- Auto-detection of keyboards, IR remotes, Bluetooth media buttons
- GPIO pin button support for physical buttons
- Long-press detection for context menus
- Debouncing and key repeat handling
- Hot-plugging support (detects disconnected and reconnected devices)

Works without X11/Wayland - reads directly from /dev/input and GPIO.
"""
import time
import evdev
import select
from evdev import ecodes
import config as cfg
from config import setup_logger

try:
    import gpiod
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

logger = setup_logger()

# How often to rescan for newly connected devices (seconds)
RESCAN_INTERVAL = 2.0

# GPIO pin to action mapping (directly mapped actions)
GPIO_PIN_MAP = {
    4: 'play_pause',
    5: 'prev',
    6: 'next',
    12: 'up',
    13: 'down',
    16: 'enter',
    19: 'back',
    20: 'vol_up',
    21: 'vol_down',
}

# GPIO pins that support long press
GPIO_LONG_PRESS_PINS = {16, 19, 4}  # enter, back, play_pause


class InputHandler:
    def __init__(self, callbacks=None):
        self.callbacks = callbacks if callbacks else {}
        self.devices = []  # Support multiple input devices
        self.last_action_time = 0
        self._last_rescan_time = 0  # Track last device rescan

        self.debounce_interval = 0.15
        self.press_start_times = {}
        self.long_press_fired = set()

        # GPIO state tracking
        self._gpio_chip = None
        self._gpio_lines = {}
        self._gpio_pressed = {}  # Track which GPIO buttons are currently pressed
        self._gpio_press_times = {}  # Track press start times for long press
        self._gpio_long_fired = set()  # Track which GPIO long presses have fired

        self._find_devices()
        self._init_gpio()

    def set_callbacks(self, callbacks):
        self.callbacks = callbacks

    def _init_gpio(self):
        """Initialize GPIO pins for button input."""
        if not GPIO_AVAILABLE:
            logger.info("GPIO not available (gpiod not installed)")
            return

        try:
            self._gpio_chip = gpiod.Chip('gpiochip0')
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Could not open GPIO chip: {e}")
            return

        for pin in GPIO_PIN_MAP:
            try:
                line = self._gpio_chip.get_line(pin)
                line.request(consumer="paperjam", type=gpiod.LINE_REQ_DIR_IN,
                             flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
                self._gpio_lines[pin] = line
                self._gpio_pressed[pin] = False
            except OSError as e:
                logger.warning(f"Could not configure GPIO pin {pin}: {e}")

        if self._gpio_lines:
            logger.info(f"GPIO buttons initialized: pins {list(self._gpio_lines.keys())}")

    def _check_gpio(self):
        """Check GPIO buttons for presses and releases."""
        if not self._gpio_lines:
            return

        now = time.time()

        for pin, line in self._gpio_lines.items():
            try:
                # Button pressed = LOW (0) due to pull-up resistor
                pressed = line.get_value() == 0
            except OSError:
                continue

            was_pressed = self._gpio_pressed[pin]
            action = GPIO_PIN_MAP[pin]

            # Button just pressed
            if pressed and not was_pressed:
                self._gpio_pressed[pin] = True
                self._gpio_press_times[pin] = now

                # Trigger immediately for non-long-press pins
                if pin not in GPIO_LONG_PRESS_PINS:
                    self._trigger_gpio_action(action, is_long=False)

            # Button held - check for long press
            elif pressed and was_pressed:
                if pin in GPIO_LONG_PRESS_PINS and pin not in self._gpio_long_fired:
                    press_start = self._gpio_press_times.get(pin, now)
                    if now - press_start > cfg.LONG_PRESS_DURATION:
                        self._trigger_gpio_action(action, is_long=True)
                        self._gpio_long_fired.add(pin)

            # Button released
            elif not pressed and was_pressed:
                self._gpio_pressed[pin] = False
                self._gpio_press_times.pop(pin, None)

                # For long-press pins, trigger short action if long press didn't fire
                if pin in GPIO_LONG_PRESS_PINS:
                    if pin in self._gpio_long_fired:
                        self._gpio_long_fired.discard(pin)
                    else:
                        self._trigger_gpio_action(action, is_long=False)

    def _trigger_gpio_action(self, action, is_long=False):
        """Trigger the callback for a GPIO action."""
        if is_long:
            action = action + '_long'

        if action in self.callbacks:
            self.last_action_time = time.time()
            self.callbacks[action]()

    def _find_devices(self):
        """Find all usable input devices (keyboard, remote, media controllers)."""
        logger.info("Scanning for input devices...")
        self.devices = []

        try:
            paths = evdev.list_devices()
            all_devices = [evdev.InputDevice(path) for path in paths]
        except Exception as e:
            logger.error(f"Input device scan error: {e}")
            return

        # Sort to prioritize keyboards/remotes
        all_devices.sort(key=lambda d: 1 if 'keyboard' in d.name.lower() or 'remote' in d.name.lower() else 2)

        for dev in all_devices:
            name = dev.name.lower()

            # Skip non-input audio/video devices
            if any(x in name for x in ['vc4', 'video']):
                continue

            cap = dev.capabilities()
            if ecodes.EV_KEY not in cap:
                continue

            keys = cap.get(ecodes.EV_KEY, [])

            # Check for media keys (Bluetooth/USB media controllers)
            has_media_keys = any(k in keys for k in [
                ecodes.KEY_PLAYPAUSE, ecodes.KEY_NEXTSONG, ecodes.KEY_PREVIOUSSONG,
                ecodes.KEY_VOLUMEUP, ecodes.KEY_VOLUMEDOWN, ecodes.KEY_MUTE,
                ecodes.KEY_STOPCD, ecodes.KEY_PLAYCD, ecodes.KEY_PAUSECD
            ])

            # Check for navigation keys (keyboard/remote)
            has_nav_keys = any(k in keys for k in [
                ecodes.KEY_UP, ecodes.KEY_DOWN, ecodes.KEY_LEFT, ecodes.KEY_RIGHT,
                ecodes.KEY_ENTER, ecodes.KEY_KP8, ecodes.KEY_KP2
            ])

            if has_media_keys or has_nav_keys:
                logger.info(f"Input device found: {dev.name} ({dev.path})")
                self.devices.append(dev)

        if not self.devices:
            logger.warning("No valid input devices found")

    def _rescan_devices(self):
        """Rescan for newly connected devices without touching existing ones."""
        try:
            paths = evdev.list_devices()
        except Exception as e:
            logger.error(f"Device rescan error: {e}")
            return

        # Get paths of currently tracked devices
        current_paths = {dev.path for dev in self.devices}

        for path in paths:
            if path in current_paths:
                continue  # Already tracking this device

            try:
                dev = evdev.InputDevice(path)
            except (OSError, IOError):
                continue  # Device not accessible

            name = dev.name.lower()

            # Skip non-input audio/video devices
            if any(x in name for x in ['vc4', 'video']):
                dev.close()
                continue

            cap = dev.capabilities()
            if ecodes.EV_KEY not in cap:
                dev.close()
                continue

            keys = cap.get(ecodes.EV_KEY, [])

            # Check for media keys (Bluetooth/USB media controllers)
            has_media_keys = any(k in keys for k in [
                ecodes.KEY_PLAYPAUSE, ecodes.KEY_NEXTSONG, ecodes.KEY_PREVIOUSSONG,
                ecodes.KEY_VOLUMEUP, ecodes.KEY_VOLUMEDOWN, ecodes.KEY_MUTE,
                ecodes.KEY_STOPCD, ecodes.KEY_PLAYCD, ecodes.KEY_PAUSECD
            ])

            # Check for navigation keys (keyboard/remote)
            has_nav_keys = any(k in keys for k in [
                ecodes.KEY_UP, ecodes.KEY_DOWN, ecodes.KEY_LEFT, ecodes.KEY_RIGHT,
                ecodes.KEY_ENTER, ecodes.KEY_KP8, ecodes.KEY_KP2
            ])

            if has_media_keys or has_nav_keys:
                logger.info(f"Input device connected: {dev.name} ({dev.path})")
                self.devices.append(dev)
            else:
                dev.close()

    def has_pending_input(self):
        """Check if there's any pending input without processing it."""
        # Check GPIO buttons
        for pin, line in self._gpio_lines.items():
            try:
                if line.get_value() == 0:  # Button pressed
                    return True
            except OSError:
                pass

        # Check evdev devices
        if not self.devices:
            return False
        fds = [dev.fd for dev in self.devices]
        r, w, x = select.select(fds, [], [], 0.0)
        return len(r) > 0

    def check_inputs(self):
        now = time.time()

        # Check GPIO buttons
        self._check_gpio()

        # Periodically rescan for newly connected devices
        if now - self._last_rescan_time >= RESCAN_INTERVAL:
            self._last_rescan_time = now
            self._rescan_devices()

        if not self.devices:
            return True

        # Check all devices for input
        fds = [dev.fd for dev in self.devices]
        r, w, x = select.select(fds, [], [], 0.0)
        if not r:
            return True

        disconnected = []
        for dev in self.devices:
            if dev.fd not in r:
                continue

            try:
                for event in dev.read():
                    if event.type == ecodes.EV_KEY:
                        self._process_event(event)
                        if event.code == ecodes.KEY_ESC and event.value == 1:
                            return False
            except OSError:
                logger.warning(f"Input device disconnected: {dev.name}")
                disconnected.append(dev)

        # Remove disconnected devices and close file descriptors
        for dev in disconnected:
            try:
                dev.close()
            except (OSError, IOError):
                pass
            self.devices.remove(dev)

        return True

    def _process_event(self, event):
        code = event.code
        val = event.value # 0=Up, 1=Down, 2=Repeat
        now = time.time()

        # Keys that support long press
        long_press_keys = [
            ecodes.KEY_ENTER, ecodes.KEY_KPENTER, ecodes.KEY_KP5, ecodes.KEY_BACKSPACE,
            ecodes.KEY_PLAYPAUSE, ecodes.KEY_P, ecodes.KEY_KP0, ecodes.KEY_PLAYCD, ecodes.KEY_PAUSECD,
            ecodes.KEY_PLAY
        ]

        # 1. KEY DOWN: Start Timer
        if val == 1:
            self.press_start_times[code] = now
            if code in self.long_press_fired:
                self.long_press_fired.remove(code)

            if code not in long_press_keys:
                 self._trigger_action(code, is_long=False)

        # 2. KEY REPEAT: Handle Scroll AND Long Press Hold
        elif val == 2:
            # Handle Long Press for supported keys
            if code in long_press_keys:
                start_time = self.press_start_times.get(code, now)

                # Check config for duration
                if (now - start_time > cfg.LONG_PRESS_DURATION) and (code not in self.long_press_fired):
                    self._trigger_action(code, is_long=True)
                    self.long_press_fired.add(code)

            # Handle Navigation Scroll
            else:
                if now - self.last_action_time > 0.1:
                    self._trigger_action(code, is_long=False)

        # 3. KEY UP: Logic Decision
        elif val == 0:
            self.press_start_times.pop(code, 0)

            if code in long_press_keys:
                if code in self.long_press_fired:
                    self.long_press_fired.remove(code)
                else:
                    self._trigger_action(code, is_long=False)

    def _trigger_action(self, code, is_long=False):
        self.last_action_time = time.time()

        action = None
        # Navigation keys
        if code == ecodes.KEY_KP8 or code == ecodes.KEY_UP:
            action = 'up'
        elif code == ecodes.KEY_KP2 or code == ecodes.KEY_DOWN:
            action = 'down'
        elif code == ecodes.KEY_KP0 or code == ecodes.KEY_BACKSPACE:
            action = 'back_long' if is_long else 'back'
        elif code == ecodes.KEY_KPENTER or code == ecodes.KEY_ENTER:
            action = 'enter_long' if is_long else 'enter'

        # Left/Right navigation (also triggers prev/next if no left/right callback)
        elif code in (ecodes.KEY_KP4, ecodes.KEY_LEFT):
            action = 'left' if 'left' in self.callbacks else 'prev'
        elif code in (ecodes.KEY_KP6, ecodes.KEY_RIGHT):
            action = 'right' if 'right' in self.callbacks else 'next'

        # Play/pause keys
        elif code in (ecodes.KEY_KP5, ecodes.KEY_P, ecodes.KEY_PLAYPAUSE,
                      ecodes.KEY_PLAYCD, ecodes.KEY_PAUSECD, ecodes.KEY_PLAY):
            action = 'play_pause_long' if is_long else 'play_pause'

        # Next/Previous track keys (dedicated media keys)
        elif code == ecodes.KEY_NEXTSONG:
            action = 'next'
        elif code == ecodes.KEY_PREVIOUSSONG:
            action = 'prev'

        # Volume keys
        elif code == ecodes.KEY_VOLUMEUP:
            action = 'vol_up'
        elif code == ecodes.KEY_VOLUMEDOWN:
            action = 'vol_down'

        if action and action in self.callbacks:
            self.callbacks[action]()
