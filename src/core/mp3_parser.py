from dataclasses import dataclass
from typing import List, Tuple, Iterator

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
    channels: int  # 1 mono, 2 stereo
    side_info_len: int  # 17 mono, 32 stereo
    header: bytes

class MP3Stream:
    def __init__(self, data: bytes):
        self.data = data
        self.frames: List[Frame] = []
        self._parse()
    
    def _parse(self):
        i = 0; n = len(self.data)
        if n >= 10 and self.data[0:3] == b"ID3":
            size_bytes = self.data[6:10]
            id3_size = ((size_bytes[0] & 0x7F) << 21) | ((size_bytes[1] & 0x7F) << 14) | ((size_bytes[2] & 0x7F) << 7) | (size_bytes[3] & 0x7F)
            i = 10 + id3_size
        
        while i + 4 <= n:
            if self.data[i] == 0xFF and (self.data[i+1] & 0xE0) == 0xE0:
                header = self.data[i:i+4]
                version_id = (header[1] >> 3) & 0b11
                layer = (header[1] >> 1) & 0b11
                bitrate_idx = (header[2] >> 4) & 0b1111
                samplerate_idx = (header[2] >> 2) & 0b11
                padding = (header[2] >> 1) & 0b1
                channel_mode = (header[3] >> 6) & 0b11
                
                if version_id != 0b11 or layer != 0b01:
                    i += 1; continue
                if bitrate_idx == 0 or bitrate_idx == 0b1111 or samplerate_idx == 0b11:
                    i += 1; continue
                bitrate = {k:v for k,v in BITRATES.items()}[bitrate_idx] * 1000
                samplerate = {k:v for k,v in SAMPLERATES.items()}[samplerate_idx]
                frame_len = int((144 * bitrate) // samplerate + padding)
                if i + frame_len > n or frame_len <= 0:
                    i += 1; continue
                
                channels = 1 if channel_mode == 0b11 else 2
                side_info_len = 17 if channels == 1 else 32
                self.frames.append(Frame(offset=i, size=frame_len, channels=channels, side_info_len=side_info_len, header=header))
                i += frame_len
            else:
                i += 1

    def iter_private_bits_positions(self) -> Iterator[Tuple[int, int, int]]:
        for idx, fr in enumerate(self.frames):
            side_off = fr.offset + 4
            yield (idx, side_off, 1 if fr.channels == 1 else 2)
