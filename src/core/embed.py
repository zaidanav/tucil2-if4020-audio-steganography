from pathlib import Path
from .mp3_parser import MP3Stream
from .metadata import build_header, EmbedConfig
from .seed_rng import seed_from_key, shuffled_indices
from .bitops import iter_bits
from .capacity import compute_capacity_bits
from .psnr import psnr_from_mp3_paths
import struct

class CapacityError(Exception): ...
class FormatError(Exception): ...

def _write_bits_into_private(mp3_mut: bytearray, st: MP3Stream, bits, randomized: bool, seed: int):
    positions = list(st.iter_private_bits_positions())
    if randomized:
        order = shuffled_indices(len(positions), seed)
        positions = [positions[i] for i in order]
    
    bit_iter = iter(bits)
    for _, byte_off, bit_count in positions:
        take = []
        try:
            for _ in range(bit_count):
                take.append(next(bit_iter))
        except StopIteration:
            break
        b = mp3_mut[byte_off]
        for j, bit in enumerate(take):
            b = (b & ~(1 << j)) | ((bit & 1) << j)
        mp3_mut[byte_off] = b
    
    try:
        next(bit_iter)
        raise CapacityError("Payload exceeds capacity during write.")
    except StopIteration:
        return

def embed_bytes(cover_mp3: bytes, payload: bytes, key: str, n_lsb: int, use_encryption: bool, use_random_start: bool, filename: str, extension: str) -> bytes:
    if not (1 <= n_lsb <= 4):
        raise ValueError("n_lsb must be 1..4")
    st = MP3Stream(cover_mp3)
    if not st.frames:
        raise FormatError("No MPEG1 Layer III frames detected.")
    
    cfg = EmbedConfig(encrypted=use_encryption, randomized=use_random_start, n_lsb=n_lsb, filename=filename, extension=extension, payload_len=len(payload))
    header = build_header(cfg)
    full = header + payload
    if use_encryption:
        from .vigenere256 import encrypt
        full = header + encrypt(payload, key.encode('utf-8'))
    
    full_with_len = struct.pack(">I", len(full)) + full
    cap_bits = compute_capacity_bits(cover_mp3)
    total_bits = len(full_with_len) * 8
    if total_bits > cap_bits:
        raise CapacityError(f"Capacity {cap_bits} bits insufficient for {total_bits} bits payload.")
    
    bits = list(iter_bits(full_with_len))
    out = bytearray(cover_mp3)
    seed = seed_from_key(key) if use_random_start else 0
    _write_bits_into_private(out, st, bits, randomized=use_random_start, seed=seed)
    return bytes(out)

def embed_file(cover_path: str, secret_path: str, out_path: str, key: str, n_lsb: int, use_encryption: bool, use_random_start: bool):
    cover = Path(cover_path).read_bytes()
    payload = Path(secret_path).read_bytes()
    name = Path(secret_path).name
    if "." in name:
        filename = name.rsplit(".", 1)[0]
        ext = "." + name.rsplit(".", 1)[1]
    else:
        filename = name; ext = ""
    stego = embed_bytes(cover, payload, key, n_lsb, use_encryption, use_random_start, filename, ext)
    Path(out_path).write_bytes(stego)
    try:
        psnr = psnr_from_mp3_paths(cover_path, out_path)
    except Exception:
        psnr = None
    return psnr
