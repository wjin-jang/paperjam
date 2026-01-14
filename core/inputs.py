import time
import evdev
import select
from evdev import ecodes
import config as cfg

class InputHandler:
    def __init__(self, callbacks=None):
        self.callbacks = callbacks if callbacks else {}
        self.device = None
        self.last_action_time = 0
        
        self.debounce_interval = 0.15
        self.press_start_times = {} 
        self.long_press_fired = set() 
        
        self._find_keyboard()

    def set_callbacks(self, callbacks):
        self.callbacks = callbacks

    def _find_keyboard(self):
        print("Scanning for input devices...")
        try:
            paths = evdev.list_devices()
            devices = [evdev.InputDevice(path) for path in paths]
        except Exception as e:
            print(f"Scan Error: {e}")
            return

        devices.sort(key=lambda d: 1 if 'keyboard' in d.name.lower() or 'remote' in d.name.lower() else 2)

        for dev in devices:
            name = dev.name.lower()
            if any(x in name for x in ['audio', 'avrcp', 'headset', 'hdmi', 'vc4', 'video', 'button']):
                continue
            
            cap = dev.capabilities()
            if ecodes.EV_KEY in cap:
                print(f"Input: Found {dev.name} ({dev.path})")
                self.device = dev
                return

        print("WARNING: No valid keyboard found!")

    def check_inputs(self):
        if not self.device: return True

        r, w, x = select.select([self.device.fd], [], [], 0.0)
        if not r: return True 

        try:
            for event in self.device.read():
                if event.type == ecodes.EV_KEY:
                    self._process_event(event)
                    if event.code == ecodes.KEY_ESC and event.value == 1:
                        return False
        except OSError:
            print("Device disconnected.")
            self.device = None
            
        return True

    def _process_event(self, event):
        code = event.code
        val = event.value # 0=Up, 1=Down, 2=Repeat
        now = time.time()

        # 1. KEY DOWN: Start Timer
        if val == 1:
            self.press_start_times[code] = now
            if code in self.long_press_fired:
                self.long_press_fired.remove(code)

            if code not in [ecodes.KEY_ENTER, ecodes.KEY_KPENTER]:
                 self._trigger_action(code, is_long=False)

        # 2. KEY REPEAT: Handle Scroll AND Long Press Hold
        elif val == 2:
            # Handle Enter Long Press
            if code in [ecodes.KEY_ENTER, ecodes.KEY_KPENTER]:
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
            
            if code in [ecodes.KEY_ENTER, ecodes.KEY_KPENTER]:
                if code in self.long_press_fired:
                    self.long_press_fired.remove(code) 
                else:
                    self._trigger_action(code, is_long=False)

    def _trigger_action(self, code, is_long=False):
        self.last_action_time = time.time()
        
        action = None
        if code == ecodes.KEY_KP8 or code == ecodes.KEY_UP: action = 'up'
        elif code == ecodes.KEY_KP2 or code == ecodes.KEY_DOWN: action = 'down'
        elif code == ecodes.KEY_KPDOT or code == ecodes.KEY_BACKSPACE: action = 'back'
        elif code == ecodes.KEY_KP0 or code == ecodes.KEY_P: action = 'play_pause'
        elif code == ecodes.KEY_KP6 or code == ecodes.KEY_RIGHT: action = 'next'
        elif code == ecodes.KEY_KP4 or code == ecodes.KEY_LEFT: action = 'prev'
        
        elif code == ecodes.KEY_KPENTER or code == ecodes.KEY_ENTER: 
            action = 'enter_long' if is_long else 'enter'

        if action and action in self.callbacks:
            self.callbacks[action]()
