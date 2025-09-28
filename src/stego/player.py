from typing import Optional
import numpy as np

try:
    import pygame
    from pygame import sndarray
except Exception:
    pygame = None
    sndarray = None

from pydub import AudioSegment

class AudioPlayer:
    def __init__(self):
        self.seg: Optional[AudioSegment] = None
        self.sound = None
        self.channel = None
        self.loaded_path: Optional[str] = None

    def _ensure_pygame(self):
        if pygame is None or sndarray is None:
            raise RuntimeError("Module 'pygame' is required. Install with: pip install pygame")

    def load(self, path: str):
        self._ensure_pygame()
        seg = AudioSegment.from_file(path)
        if seg.sample_width != 2:
            seg = seg.set_sample_width(2)
        arr = np.frombuffer(seg._data, dtype=np.int16).copy()
        arr = arr.reshape((-1, seg.channels))

        try:
            pygame.mixer.quit()
        except Exception:
            pass
        pygame.mixer.init(frequency=seg.frame_rate, size=-16, channels=seg.channels, buffer=1024)

        self.sound = sndarray.make_sound(arr)
        self.seg = seg
        self.loaded_path = path

    def play(self, path: Optional[str] = None):
        self._ensure_pygame()
        if path and (self.loaded_path != path or self.sound is None):
            self.load(path)
        if self.sound is None:
            raise RuntimeError("No audio loaded")
        self.stop()
        self.channel = self.sound.play()

    def stop(self):
        try:
            if self.channel is not None and self.channel.get_busy():
                self.channel.stop()
        finally:
            self.channel = None

    def is_playing(self) -> bool:
        return bool(self.channel and self.channel.get_busy())

    @property
    def duration_seconds(self) -> float:
        return float(self.seg.duration_seconds) if self.seg else 0.0
