from pathlib import Path
from .mp3_parser import MP3Stream
from .seed_rng import seed_from_key, shuffled_indices
from .bitops import pack_bits_to_bytes
from .metadata import parse_header, FLAG_ENCRYPTED
import struct

class ExtractError(Exception): ...
class FormatError(Exception): ...

def _read_bits_from_private(mp3_bytes: bytes, st: MP3Stream, randomized: bool, seed: int, total_bits: int):
    positions = list(st.iter_private_bits_positions())
    if randomized:
        order = shuffled_indices(len(positions), seed)
        positions = [positions[i] for i in order]
    bits = []
    for _, byte_off, bit_count in positions:
        b = mp3_bytes[byte_off]
        for j in range(bit_count):
            bits.append((b >> j) & 1)
            if len(bits) == total_bits:
                return bits
    return bits

def extract_bytes(stego_mp3: bytes, key: str):
    st = MP3Stream(stego_mp3)
    if not st.frames:
        raise FormatError("No MPEG1 Layer III frames detected.")
    prefix_bits = _read_bits_from_private(stego_mp3, st, randomized=False, seed=0, total_bits=32)
    if len(prefix_bits) < 32:
        raise ExtractError("Not enough bits to read payload length.")
    from .bitops import pack_bits_to_bytes
    length_prefix = pack_bits_to_bytes(prefix_bits)
    total_len = struct.unpack(">I", length_prefix)[0]

    total_bits = (4 + total_len) * 8
    bits = _read_bits_from_private(stego_mp3, st, randomized=False, seed=0, total_bits=total_bits)
    buf = pack_bits_to_bytes(bits)
    payload = buf[4:4+total_len]

    meta = parse_header(payload)
    randomized = bool(meta["flags"] & 0x02)
    encrypted = bool(meta["flags"] & 0x01)
    header_len = meta["header_len"]
    enc_payload = payload[header_len:]

    if randomized:
        bits = _read_bits_from_private(stego_mp3, st, randomized=True, seed=seed_from_key(key), total_bits=total_bits)
        buf = pack_bits_to_bytes(bits)
        payload = buf[4:4+total_len]
        meta = parse_header(payload)
        encrypted = bool(meta["flags"] & 0x01)
        header_len = meta["header_len"]
        enc_payload = payload[header_len:]
    
    data = enc_payload
    if encrypted:
        from .vigenere256 import decrypt
        data = decrypt(enc_payload, key.encode('utf-8'))
    
    return {"name": meta["name"], "ext": meta["ext"], "n_lsb": meta["n_lsb"], "randomized": randomized, "encrypted": encrypted, "payload": data}

def extract_file(stego_path: str, key: str, outdir: str):
    stego = Path(stego_path).read_bytes()
    res = extract_bytes(stego, key=key)
    outname = f"{res['name']}{res['ext']}"
    outpath = Path(outdir) / outname
    outpath.write_bytes(res["payload"])
    flags = {"encrypted": res["encrypted"], "randomized": res["randomized"], "n_lsb": res["n_lsb"]}
    return str(outpath), flags
