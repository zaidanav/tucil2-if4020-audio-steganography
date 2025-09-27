from pathlib import Path
from .mp3_parser import MP3Stream

def compute_capacity_bits(mp3_bytes: bytes) -> int:
    st = MP3Stream(mp3_bytes)
    cap = 0
    for _, _, bit_count in st.iter_private_bits_positions():
        cap += bit_count
    return cap

def compute_capacity_bits_for_file(path: str) -> int:
    data = Path(path).read_bytes()
    return compute_capacity_bits(data)
