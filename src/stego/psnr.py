def psnr_mp3_paths(cover_path: str, stego_path: str):
    try:
        from pydub import AudioSegment
    except Exception:
        return None
    try:
        a = AudioSegment.from_mp3(cover_path).get_array_of_samples()
        b = AudioSegment.from_mp3(stego_path).get_array_of_samples()
    except Exception:
        return None
    import numpy as np
    ax = np.array(a, dtype=float)
    bx = np.array(b, dtype=float)
    n = min(len(ax), len(bx))
    ax = ax[:n]; bx = bx[:n]
    mse = ((ax - bx) ** 2).mean()
    if mse == 0: return float('inf')
    MAX = 32767.0
    import math
    return 10.0 * math.log10((MAX*MAX)/mse)
