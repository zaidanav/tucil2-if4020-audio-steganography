from .mp3stream import MP3Stream
from .seed import start_index_from_seed
from .bitops import bits_from_bytes
from typing import Iterable

def embed_bits_into_padding(mp3_bytes: bytes, bitstream: Iterable[int], n_lsb: int, start_seed_index: int) -> bytes:
    """Embed bits into the LSBs of each padding byte, starting at a seed-based index."""
    st = MP3Stream(mp3_bytes)
    positions = list(st.iter_padding_slots())
    total_slots = len(positions)
    if total_slots == 0:
        raise ValueError("No padding bytes present; try another MP3 (CBR/320k recommended).")
    start = start_seed_index % total_slots
    order = positions[start:] + positions[:start]

    out = bytearray(mp3_bytes)
    bit_iter = iter(bitstream)

    for off in order:
        bits = []
        for _ in range(n_lsb):
            try:
                bits.append(next(bit_iter))
            except StopIteration:
                bits.append(0)
        b = out[off]
        for j, bit in enumerate(bits):
            mask = 1 << j
            b = (b & ~mask) | ((bit & 1) << j)
        out[off] = b
    return bytes(out)
