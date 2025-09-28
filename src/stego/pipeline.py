
from pathlib import Path
import struct
from typing import Optional, Tuple, List

from .capability_exceptions import CapacityError, ExtractError
from .bitops import bits_from_bytes, bytes_from_bits
from .crypto import vigenere256_encrypt, vigenere256_decrypt
from .seed import seed_from_key, start_index_from_seed

MAGIC = b"STEG"
VER = 1
HDR_FMT = "<4s B B B I H B"
FLAG_ENC = 1 << 0
FLAG_RND = 1 << 1

def _build_header(encrypted: bool, randomized: bool, n_lsb: int, payload_len: int, name: str, ext: str) -> bytes:
    name_b = name.encode("utf-8")
    ext_b = ext.encode("utf-8")
    flags = (FLAG_ENC if encrypted else 0) | (FLAG_RND if randomized else 0)
    head = struct.pack(HDR_FMT, MAGIC, VER, flags, n_lsb, payload_len, len(name_b), len(ext_b))
    return head + name_b + ext_b

def _parse_header(buf: bytes):
    if len(buf) < struct.calcsize(HDR_FMT):
        raise ValueError("Header too small")
    magic, ver, flags, n_lsb, payload_len, name_len, ext_len = struct.unpack_from(HDR_FMT, buf, 0)
    if magic != MAGIC or ver != VER:
        raise ValueError("Header magic/version mismatch")
    off = struct.calcsize(HDR_FMT)
    if off + name_len + ext_len > len(buf):
        raise ValueError("Header truncated")
    name = buf[off:off+name_len].decode("utf-8"); off += name_len
    ext  = buf[off:off+ext_len].decode("utf-8"); off += ext_len
    return {"flags": flags, "n_lsb": n_lsb, "payload_len": payload_len, "name": name, "ext": ext, "header_len": off}

def _decode_to_samples(path: str):
    from pydub import AudioSegment
    import numpy as np
    seg = AudioSegment.from_file(path)  # mp3/wav/etc.
    arr = seg.get_array_of_samples()
    np_arr = np.frombuffer(arr, dtype=np.int16).copy()
    return np_arr, seg.channels, seg.frame_rate, seg.sample_width

def _encode_samples_to_wav(samples, channels: int, frame_rate: int, out_path: str):
    import wave, numpy as np
    pcm = np.asarray(samples, dtype=np.int16)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(int(channels))
        wf.setsampwidth(2)
        wf.setframerate(int(frame_rate))
        wf.writeframes(pcm.astype("<i2").tobytes())

def _capacity_bits_pcm(path: str, n_lsb: int) -> int:
    samples, ch, fr, sw = _decode_to_samples(path)
    return int(samples.size) * int(n_lsb)

def compute_capacity_for_file(cover_path: str, n_lsb: int) -> int:
    if n_lsb < 1 or n_lsb > 4:
        raise ValueError("n_lsb must be 1..4")
    return _capacity_bits_pcm(cover_path, n_lsb)

def analyze_cover_file(path: str):
    samples, ch, fr, sw = _decode_to_samples(path)
    total_frames = samples.size // ch
    duration_sec = total_frames / float(fr) if fr else 0.0
    return {
        "valid": True,
        "channels": ch,
        "samplerate": fr,
        "sample_width": sw,
        "total_samples": int(samples.size),
        "total_frames": int(total_frames),
        "stereo": bool(ch == 2),
        "duration_sec": float(duration_sec),
    }

def _embed_bits_into_samples(samples, bit_iter, n_lsb: int, start_seed_index: int):
    import numpy as np
    N = samples.size
    if N == 0:
        return 0
    mask = (1 << n_lsb) - 1
    start = start_seed_index % N if N else 0

    written = 0
    idx = start
    try:
        while True:
            val = 0
            for j in range(n_lsb):
                bit = next(bit_iter)
                val |= ((bit & 1) << j)
            s = int(samples[idx])
            s = (s & ~mask) | val
            samples[idx] = ((s + 0x8000) & 0xFFFF) - 0x8000
            written += n_lsb
            idx += 1
            if idx == N: idx = 0
    except StopIteration:
        pass
    return written

def _extract_bits_from_samples(samples, total_bits: int, n_lsb: int, start_seed_index: int) -> bytes:
    N = samples.size
    if N == 0: return b""
    mask = (1 << n_lsb) - 1
    start = start_seed_index % N
    bits = []
    idx = start
    need = int(total_bits)
    while len(bits) < need:
        s = int(samples[idx])
        val = s & mask
        for j in range(n_lsb):
            bits.append((val >> j) & 1)
            if len(bits) >= need:
                break
        idx += 1
        if idx == N: idx = 0
    out = bytearray()
    b = 0; cnt = 0
    for bit in bits:
        b = (b << 1) | (bit & 1)
        cnt += 1
        if cnt == 8:
            out.append(b); b = 0; cnt = 0
    if cnt:
        out.append(b << (8-cnt))
    return bytes(out)

def embed_to_file(cover_path: str, secret_path: str, out_path: str, key: str, n_lsb: int, encrypt: bool, use_rand_start: bool, compute_psnr: bool = True):
    if n_lsb < 1 or n_lsb > 4:
        raise ValueError("n_lsb must be 1..4")

    cover_path = str(cover_path); secret_path = str(secret_path); out_path = str(out_path)
    secret = Path(secret_path).read_bytes()
    name = Path(secret_path).stem
    ext  = ''.join(Path(secret_path).suffixes) or ''

    body = vigenere256_encrypt(secret, key.encode('utf-8')) if encrypt else secret

    hdr = _build_header(encrypted=encrypt, randomized=use_rand_start, n_lsb=n_lsb, payload_len=len(body), name=name, ext=ext)
    blob = hdr + body
    buf = struct.pack(">I", len(blob)) + blob

    cap = compute_capacity_for_file(cover_path, n_lsb)
    need = len(buf) * 8
    if need > cap:
        raise CapacityError(f"Capacity {cap} bits insufficient for {need} bits")

    samples, channels, frame_rate, sample_width = _decode_to_samples(cover_path)

    seed = seed_from_key(key) if use_rand_start else 0
    start = start_index_from_seed(samples.size, seed)

    total_written = _embed_bits_into_samples(samples, bits_from_bytes(buf), n_lsb=n_lsb, start_seed_index=start)
    if total_written < need:
        raise CapacityError("Unexpected: not all bits were written")

    # force .wav
    from pathlib import Path as _P
    if out_path.lower().endswith(".mp3"):
        out_path = str(_P(out_path).with_suffix(".wav"))
    if not out_path.lower().endswith(".wav"):
        out_path = out_path + ".wav"
    _encode_samples_to_wav(samples, channels, frame_rate, out_path)

    psnr = None
    if compute_psnr:
        try:
            psnr = _psnr_paths_generic(cover_path, out_path)
        except Exception:
            psnr = None
    return psnr

def _try_extract_with_params(samples, key: str, n_lsb: int, use_rand_start: bool):
    seed = seed_from_key(key) if use_rand_start else 0
    start = start_index_from_seed(samples.size, seed)

    raw_len = _extract_bits_from_samples(samples, 32, n_lsb=n_lsb, start_seed_index=start)
    if len(raw_len) < 4:
        return None
    total_len = struct.unpack(">I", raw_len[:4])[0]
    if total_len <= 0 or total_len > 128 * 1024 * 1024:
        return None

    total_bits = (4 + total_len) * 8
    raw_all = _extract_bits_from_samples(samples, total_bits, n_lsb=n_lsb, start_seed_index=start)
    blob = raw_all[4:4+total_len]

    try:
        meta = _parse_header(blob)
    except Exception:
        return None

    if meta["n_lsb"] != n_lsb:
        return None

    header_len = meta["header_len"]
    data = blob[header_len:]
    if (meta["flags"] & FLAG_ENC):
        data = vigenere256_decrypt(data, key.encode('utf-8'))
    return data, meta

def extract_to_file(stego_path: str, key: str, outdir: str):
    stego_path = str(stego_path); outdir = str(outdir)
    samples, channels, frame_rate, sample_width = _decode_to_samples(stego_path)

    for n in (1,2,3,4):
        for rnd in (True, False):
            attempt = _try_extract_with_params(samples, key, n_lsb=n, use_rand_start=rnd)
            if attempt is None:
                continue
            data, meta = attempt
            out_name = f"{meta['name']}{meta['ext']}" or "extracted.bin"
            op = Path(outdir) / out_name
            op.write_bytes(data)
            flags = {"encrypted": bool(meta["flags"] & FLAG_ENC), "randomized": bool(meta["flags"] & FLAG_RND), "n_lsb": meta["n_lsb"]}
            return str(op), flags

    raise ExtractError("Cannot locate header. Pastikan file stego adalah WAV hasil embed versi ini dan key tepat.")

def _psnr_paths_generic(p1: str, p2: str):
    try:
        from pydub import AudioSegment
        import numpy as np, math
        a = AudioSegment.from_file(p1).get_array_of_samples()
        b = AudioSegment.from_file(p2).get_array_of_samples()
        ax = np.array(a, dtype=float)
        bx = np.array(b, dtype=float)
        n = min(len(ax), len(bx))
        ax = ax[:n]; bx = bx[:n]
        mse = ((ax - bx) ** 2).mean()
        if mse == 0: return float('inf')
        MAX = 32767.0
        return 10.0 * math.log10((MAX*MAX)/mse)
    except Exception:
        return None
