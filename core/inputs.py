"""
Input device handling using evdev.

Features:
- Auto-detection of keyboards, IR remotes, Bluetooth media buttons
- Long-press detection for context menus
- Debouncing and key repeat handling
- Hot-plugging support (detects disconnected devices)

Works without X11/Wayland - reads directly from /dev/input.
"""
import time
import evdev
import select
from evdev import ecodes
import config as cfg
from core.logger import setup_logger

logger = setup_logger()


class InputHandler:
    def __init__(self, callbacks=None):
        self.callbacks = callbacks if callbacks else {}
        self.devices = []  # Support multiple input devices
        self.last_action_time = 0

        self.debounce_interval = 0.15
        self.press_start_times = {}
        self.long_press_fired = set()

        self._find_devices()

    def set_callbacks(self, callbacks):
        self.callbacks = callbacks

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

    def has_pending_input(self):
        """Check if there's any pending input without processing it."""
        if not self.devices:
            return False
        fds = [dev.fd for dev in self.devices]
        r, w, x = select.select(fds, [], [], 0.0)
        return len(r) > 0

    def check_inputs(self):
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

        # Play/pause keys
        elif code in (ecodes.KEY_KP5, ecodes.KEY_P, ecodes.KEY_PLAYPAUSE,
                      ecodes.KEY_PLAYCD, ecodes.KEY_PAUSECD, ecodes.KEY_PLAY):
            action = 'play_pause_long' if is_long else 'play_pause'

        # Next track keys
        elif code in (ecodes.KEY_KP6, ecodes.KEY_RIGHT, ecodes.KEY_NEXTSONG):
            action = 'next'

        # Previous track keys
        elif code in (ecodes.KEY_KP4, ecodes.KEY_LEFT, ecodes.KEY_PREVIOUSSONG):
            action = 'prev'

        # Volume keys
        elif code == ecodes.KEY_VOLUMEUP:
            action = 'vol_up'
        elif code == ecodes.KEY_VOLUMEDOWN:
            action = 'vol_down'

        if action and action in self.callbacks:
            self.callbacks[action]()
