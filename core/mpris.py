"""
MPRIS D-Bus adapter for Bluetooth media control support.

Registers as an MPRIS2-compliant media player on the D-Bus session bus,
allowing Bluetooth devices (headphones, car stereos, etc.) to control playback
via the AVRCP protocol.

Requires: dbus-python, PyGObject (for GLib main loop)
"""
import threading
from config import setup_logger

logger = setup_logger()

# Try to import D-Bus dependencies
try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.info("D-Bus not available - MPRIS media controls disabled")


MPRIS_INTERFACE = "org.mpris.MediaPlayer2"
MPRIS_PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
MPRIS_PATH = "/org/mpris/MediaPlayer2"


class MPRISAdapter:
    """MPRIS D-Bus adapter for receiving Bluetooth media control commands."""

    def __init__(self):
        self._callbacks = {}
        self._service = None
        self._loop = None
        self._thread = None

    def set_callbacks(self, callbacks):
        """Set the callback functions for media controls.

        Args:
            callbacks: Dict with keys like 'play_pause', 'next', 'prev', 'vol_up', 'vol_down'
        """
        self._callbacks = callbacks
        if self._service:
            self._service.set_callbacks(callbacks)

    def start(self):
        """Start the MPRIS service in a background thread."""
        if not DBUS_AVAILABLE:
            return

        def run_loop():
            try:
                DBusGMainLoop(set_as_default=True)
                bus = dbus.SessionBus()

                # Request bus name
                bus_name = dbus.service.BusName(
                    "org.mpris.MediaPlayer2.paperjam",
                    bus=bus
                )

                self._service = MPRISService(bus_name, self._callbacks)
                self._loop = GLib.MainLoop()

                logger.info("MPRIS service started")
                self._loop.run()
            except Exception as e:
                logger.warning(f"MPRIS service failed to start: {e}")

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the MPRIS service."""
        if self._loop:
            self._loop.quit()


if DBUS_AVAILABLE:
    class MPRISService(dbus.service.Object):
        """D-Bus service implementing MPRIS2 interfaces."""

        def __init__(self, bus_name, callbacks):
            super().__init__(bus_name, MPRIS_PATH)
            self._callbacks = callbacks or {}

        def set_callbacks(self, callbacks):
            self._callbacks = callbacks

        def _call(self, action):
            """Call a callback if it exists."""
            if action in self._callbacks:
                try:
                    self._callbacks[action]()
                except Exception as e:
                    logger.error(f"MPRIS callback error ({action}): {e}")

        # org.mpris.MediaPlayer2 interface
        @dbus.service.method(MPRIS_INTERFACE)
        def Raise(self):
            pass

        @dbus.service.method(MPRIS_INTERFACE)
        def Quit(self):
            pass

        # org.mpris.MediaPlayer2.Player interface
        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Next(self):
            logger.debug("MPRIS: Next")
            self._call('next')

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Previous(self):
            logger.debug("MPRIS: Previous")
            self._call('prev')

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Pause(self):
            logger.debug("MPRIS: Pause")
            self._call('play_pause')

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def PlayPause(self):
            logger.debug("MPRIS: PlayPause")
            self._call('play_pause')

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Stop(self):
            logger.debug("MPRIS: Stop")
            self._call('play_pause')

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Play(self):
            logger.debug("MPRIS: Play")
            self._call('play_pause')

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Seek(self, offset):
            pass

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def SetPosition(self, track_id, position):
            pass

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def OpenUri(self, uri):
            pass

        # Properties interface
        @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ss', out_signature='v')
        def Get(self, interface, prop):
            return self.GetAll(interface).get(prop, "")

        @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
        def GetAll(self, interface):
            if interface == MPRIS_INTERFACE:
                return {
                    'CanQuit': False,
                    'CanRaise': False,
                    'HasTrackList': False,
                    'Identity': 'PaperJam',
                    'SupportedUriSchemes': dbus.Array([], signature='s'),
                    'SupportedMimeTypes': dbus.Array([], signature='s'),
                }
            elif interface == MPRIS_PLAYER_INTERFACE:
                return {
                    'PlaybackStatus': 'Stopped',
                    'LoopStatus': 'None',
                    'Rate': 1.0,
                    'Shuffle': False,
                    'Metadata': dbus.Dictionary({}, signature='sv'),
                    'Volume': 1.0,
                    'Position': dbus.Int64(0),
                    'MinimumRate': 1.0,
                    'MaximumRate': 1.0,
                    'CanGoNext': True,
                    'CanGoPrevious': True,
                    'CanPlay': True,
                    'CanPause': True,
                    'CanSeek': False,
                    'CanControl': True,
                }
            return {}

        @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ssv')
        def Set(self, interface, prop, value):
            pass
