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
