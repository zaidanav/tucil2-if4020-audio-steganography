from dataclasses import dataclass
from typing import List, Iterator

BITRATES = {
    0b0001: 32, 0b0010: 40, 0b0011: 48, 0b0100: 56,
    0b0101: 64, 0b0110: 80, 0b0111: 96, 0b1000: 112,
    0b1001: 128, 0b1010: 160, 0b1011: 192, 0b1100: 224,
    0b1101: 256, 0b1110: 320
}
SAMPLERATES = {0b00: 44100, 0b01: 48000, 0b10: 32000}

@dataclass
class Frame:
    offset: int
    size: int
    channels: int
    padding: int

class MP3Stream:
    def __init__(self, data: bytes):
        self.data = data
        self.frames: List[Frame] = []
        self._scan()

    def _scan(self):
        i = 0; n = len(self.data)
        if n >= 10 and self.data[:3] == b"ID3":
            sz = ((self.data[6] & 0x7F) << 21) | ((self.data[7] & 0x7F) << 14) | ((self.data[8] & 0x7F) << 7) | (self.data[9] & 0x7F)
            i = 10 + sz
        while i + 4 <= n:
            if self.data[i] == 0xFF and (self.data[i+1] & 0xE0) == 0xE0:
                h = self.data[i:i+4]
                version_id = (h[1] >> 3) & 0b11
                layer = (h[1] >> 1) & 0b11
                br = (h[2] >> 4) & 0b1111
                sr = (h[2] >> 2) & 0b11
                pad = (h[2] >> 1) & 0b1
                ch_mode = (h[3] >> 6) & 0b11
                if version_id != 0b11 or layer != 0b01:
                    i += 1; continue
                if br == 0 or br == 0b1111 or sr == 0b11:
                    i += 1; continue
                bitrate = BITRATES[br] * 1000
                samplerate = SAMPLERATES[sr]
                frame_len = int((144*bitrate)//samplerate + pad)
                if frame_len <= 0 or i + frame_len > n:
                    i += 1; continue
                ch = 1 if ch_mode == 0b11 else 2
                self.frames.append(Frame(offset=i, size=frame_len, channels=ch, padding=pad))
                i += frame_len
            else:
                i += 1

    def iter_padding_slots(self) -> Iterator[int]:
        """Yield absolute byte offsets for padding bytes (end of frames with padding=1)."""
        for fr in self.frames:
            if fr.padding == 1:
                yield fr.offset + fr.size - 1

    def stats(self):
        total = len(self.frames)
        padded = sum(1 for _ in self.iter_padding_slots())
        stereo = any(fr.channels == 2 for fr in self.frames)
        return {"total_frames": total, "padded_frames": padded, "stereo": stereo, "valid": total>0}
