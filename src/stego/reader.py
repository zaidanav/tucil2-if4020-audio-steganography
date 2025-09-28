from .mp3stream import MP3Stream
from .seed import start_index_from_seed
from .bitops import bytes_from_bits

def extract_bits_from_padding(mp3_bytes: bytes, total_bits: int, n_lsb: int, start_seed_index: int) -> bytes:
    st = MP3Stream(mp3_bytes)
    positions = list(st.iter_padding_slots())
    total_slots = len(positions)
    if total_slots == 0:
        raise ValueError("No padding bytes present; cannot extract.")
    start = start_seed_index % total_slots
    order = positions[start:] + positions[:start]

    bits = []
    needed = total_bits
    for off in order:
        b = mp3_bytes[off]
        for j in range(n_lsb):
            bits.append((b >> j) & 1)
            if len(bits) >= needed:
                return bytes_from_bits(bits[:needed])
    return bytes_from_bits(bits)
