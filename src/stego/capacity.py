from pathlib import Path
from .mp3stream import MP3Stream

def capacity_bits(data: bytes, n_lsb: int) -> int:
    st = MP3Stream(data)
    slots = sum(1 for _ in st.iter_padding_slots())
    return slots * n_lsb

def capacity_bits_for_file(path: str, n_lsb: int) -> int:
    b = Path(path).read_bytes()
    return capacity_bits(b, n_lsb)

def analyze_cover_file(path: str):
    b = Path(path).read_bytes()
    st = MP3Stream(b)
    return st.stats()
