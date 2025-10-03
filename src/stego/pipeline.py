
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
    """Decode audio file into int16 PCM samples.
    
    For .wav (16-bit PCM), avoid external dependencies by using the stdlib
    wave module. For other formats (e.g., mp3), fall back to pydub which
    requires ffmpeg to be present in the environment.
    """
    import os
    import numpy as np
    
    ext = os.path.splitext(str(path))[1].lower()
    if ext == ".wav":
        import wave
        try:
            with wave.open(str(path), "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                frames = wf.readframes(nframes)
            
            if sampwidth != 2:
                # Fallback to pydub for non-16bit WAVs
                from pydub import AudioSegment
                seg = AudioSegment.from_file(path)
                arr = seg.get_array_of_samples()
                np_arr = np.frombuffer(arr, dtype=np.int16).copy()
                return np_arr, seg.channels, seg.frame_rate, seg.sample_width
            
            pcm = np.frombuffer(frames, dtype=np.int16)
            return pcm, channels, framerate, sampwidth
        except Exception:
            # If wave module fails, fallback to pydub
            pass
    
    # For non-WAV files or if wave module failed
    from pydub import AudioSegment
    seg = AudioSegment.from_file(path)  # mp3/others
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
    """Compute the steganographic capacity in bits for a given cover file.
    
    Args:
        cover_path: Path to the cover audio file
        n_lsb: Number of LSBs to use per sample (1-4)
        
    Returns:
        Maximum number of bits that can be embedded
        
    Raises:
        ValueError: If n_lsb is not in valid range
        Exception: If file cannot be decoded
    """
    if n_lsb < 1 or n_lsb > 4:
        raise ValueError(f"n_lsb must be 1..4, got {n_lsb}")
    
    try:
        capacity = _capacity_bits_pcm(cover_path, n_lsb)
        if capacity <= 0:
            raise ValueError("Cover file has no usable samples")
        return capacity
    except Exception as e:
        raise Exception(f"Cannot compute capacity for {cover_path}: {e}") from e

def calculate_payload_size(secret_path: str, key: str, n_lsb: int, encrypt: bool, use_rand_start: bool) -> int:
    """Calculate the total size in bits needed to embed a secret file.
    
    Args:
        secret_path: Path to the secret file
        key: Steganographic key
        n_lsb: Number of LSBs (affects header)
        encrypt: Whether encryption is used
        use_rand_start: Whether randomized start position is used
        
    Returns:
        Total bits needed including header and length prefix
    """
    secret = Path(secret_path).read_bytes()
    name = Path(secret_path).stem
    ext = ''.join(Path(secret_path).suffixes) or ''
    
    body = vigenere256_encrypt(secret, key.encode('utf-8')) if encrypt else secret
    hdr = _build_header(encrypted=encrypt, randomized=use_rand_start, n_lsb=n_lsb, 
                       payload_len=len(body), name=name, ext=ext)
    blob = hdr + body
    # Add 4 bytes for length prefix
    total_bytes = 4 + len(blob)
    return total_bytes * 8

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
    """Embed bits into audio samples using LSB steganography.
    
    Handles partial LSB groups gracefully by padding with zeros when
    the bit stream doesn't align with n_lsb boundaries.
    """
    import numpy as np
    N = samples.size
    if N == 0:
        return 0
    mask = (1 << n_lsb) - 1
    start = start_seed_index % N if N else 0

    written = 0
    idx = start
    
    while True:
        val = 0
        bits_in_group = 0
        
        # Fill one sample's LSBs; if iterator exhausts early, pad remaining with 0
        for j in range(n_lsb):
            try:
                bit = next(bit_iter)
                val |= ((bit & 1) << j)
                bits_in_group += 1
            except StopIteration:
                break
        
        if bits_in_group == 0:
            # No more bits to write
            break
        
        # Apply the LSB changes to the sample
        s = int(samples[idx])
        s = (s & ~mask) | val
        samples[idx] = ((s + 0x8000) & 0xFFFF) - 0x8000
        
        # Count only actual payload bits written for accuracy near capacity
        written += bits_in_group
        
        idx += 1
        if idx == N:
            idx = 0
        
        if bits_in_group < n_lsb:
            # Last partial group handled; we're done
            break
    
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
        # Calculate detailed capacity information for better error reporting
        margin = need - cap
        utilization = (need / cap) * 100 if cap > 0 else float('inf')
        raise CapacityError(
            f"File terlalu besar untuk cover audio:\n"
            f"  Diperlukan: {need:,} bits ({need // 8:,} bytes)\n"
            f"  Kapasitas: {cap:,} bits ({cap // 8:,} bytes)\n"
            f"  Kelebihan: {margin:,} bits ({margin // 8:,} bytes)\n"
            f"  Utilisasi: {utilization:.1f}%\n"
            f"  Coba gunakan file secret yang lebih kecil atau n_lsb yang lebih besar."
        )
    
    # Warn if using more than 80% of capacity (near limit)
    utilization = (need / cap) * 100
    if utilization > 95:
        print(f"Peringatan: Menggunakan {utilization:.1f}% kapasitas cover (sangat mendekati batas)")
    elif utilization > 80:
        print(f"Peringatan: Menggunakan {utilization:.1f}% kapasitas cover (mendekati batas)")

    samples, channels, frame_rate, sample_width = _decode_to_samples(cover_path)
    
    # Ensure samples array is writable
    import numpy as np
    samples = np.array(samples, copy=True)

    seed = seed_from_key(key) if use_rand_start else 0
    start = start_index_from_seed(samples.size, seed)

    total_written = _embed_bits_into_samples(samples, bits_from_bytes(buf), n_lsb=n_lsb, start_seed_index=start)
    if total_written < need:
        # This should not happen with improved partial group handling, but guard anyway
        actual_deficit = need - total_written
        raise CapacityError(
            f"Gagal menulis semua bit yang diperlukan:\n"
            f"  Diperlukan: {need:,} bits\n"
            f"  Berhasil ditulis: {total_written:,} bits\n"
            f"  Kekurangan: {actual_deficit:,} bits\n"
            f"  Kemungkinan penyebab: kapasitas cover tidak mencukupi atau error internal."
        )

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

def check_embed_feasibility(cover_path: str, secret_path: str, key: str, n_lsb: int, 
                          encrypt: bool = False, use_rand_start: bool = False) -> dict:
    """Check if a secret file can be embedded in a cover file.
    
    Args:
        cover_path: Path to cover audio file
        secret_path: Path to secret file to embed
        key: Steganographic key
        n_lsb: Number of LSBs to use (1-4)
        encrypt: Whether to encrypt the payload
        use_rand_start: Whether to use randomized start position
        
    Returns:
        Dict with keys:
        - capacity_bits: Total capacity in bits
        - need_bits: Required bits for this payload
        - fits: Boolean indicating if embedding is feasible
        - margin_bits: Remaining capacity (negative if exceeds)
        - utilization_percent: Capacity utilization percentage
        - recommendation: Text recommendation
    """
    try:
        capacity_bits = compute_capacity_for_file(cover_path, n_lsb)
        need_bits = calculate_payload_size(secret_path, key, n_lsb, encrypt, use_rand_start)
        
        fits = need_bits <= capacity_bits
        margin_bits = capacity_bits - need_bits
        utilization = (need_bits / capacity_bits) * 100 if capacity_bits > 0 else float('inf')
        
        # Generate recommendation
        if not fits:
            recommendation = f"❌ File terlalu besar. Kurangi ukuran secret atau gunakan n_lsb lebih besar."
        elif utilization > 95:
            recommendation = f"⚠️ Sangat mendekati batas ({utilization:.1f}%). Risiko kegagalan tinggi."
        elif utilization > 80:
            recommendation = f"⚠️ Mendekati batas ({utilization:.1f}%). Pertimbangkan file lebih kecil."
        else:
            recommendation = f"✅ Aman untuk embedding ({utilization:.1f}% kapasitas)."
        
        return {
            "capacity_bits": capacity_bits,
            "need_bits": need_bits,
            "fits": fits,
            "margin_bits": margin_bits,
            "utilization_percent": utilization,
            "recommendation": recommendation
        }
    except Exception as e:
        return {
            "capacity_bits": 0,
            "need_bits": 0,
            "fits": False,
            "margin_bits": 0,
            "utilization_percent": 0,
            "recommendation": f"❌ Error: {str(e)}"
        }
