import vlc
import os
import subprocess

class AudioEngine:
    def __init__(self):
        self.instance = vlc.Instance()
        
        # Try to use PulseAudio, but don't hang if it's broken
        try:
            # Run pactl with a 1-second timeout
            subprocess.run(["pactl", "info"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL, 
                         timeout=1)
            self.instance = vlc.Instance('--aout=pulse')
            print("Audio: PulseAudio selected")
        except Exception:
            print("Audio: Fallback to default")
            self.instance = vlc.Instance()
             
        self.player = self.instance.media_player_new()
        self.current_media_path = None

    def play(self, path):
        self.current_media_path = path
        media = self.instance.media_new(str(path))
        self.player.set_media(media)
        self.player.play()

    def toggle_pause(self):
        if self.player.is_playing():
            self.player.pause()
            return False 
        else:
            self.player.play()
            return True 

    def stop(self):
        self.player.stop()

    def is_playing(self):
        return self.player.is_playing()

    def has_ended(self):
        return self.player.get_state() == vlc.State.Ended

    def is_paused(self):
        return self.player.get_state() == vlc.State.Paused

    def is_stopped(self):
        state = self.player.get_state()
        return state in (vlc.State.Stopped, vlc.State.NothingSpecial, vlc.State.Ended)

    def get_state(self):
        """Return the current playback state as a string."""
        state = self.player.get_state()
        state_map = {
            vlc.State.NothingSpecial: 'stopped',
            vlc.State.Opening: 'loading',
            vlc.State.Buffering: 'loading',
            vlc.State.Playing: 'playing',
            vlc.State.Paused: 'paused',
            vlc.State.Stopped: 'stopped',
            vlc.State.Ended: 'ended',
            vlc.State.Error: 'error'
        }
        return state_map.get(state, 'unknown')
