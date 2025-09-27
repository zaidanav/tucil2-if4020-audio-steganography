def psnr_from_mp3_paths(cover_path: str, stego_path: str):
    try:
        import numpy as np
        from pydub import AudioSegment
    except Exception:
        return None
    try:
        a = AudioSegment.from_mp3(cover_path).get_array_of_samples()
        b = AudioSegment.from_mp3(stego_path).get_array_of_samples()
    except Exception:
        return None
    import numpy as np
    ax = np.array(a, dtype=np.float64)
    bx = np.array(b, dtype=np.float64)
    n = min(len(ax), len(bx))
    ax = ax[:n]; bx = bx[:n]
    mse = np.mean((ax - bx) ** 2)
    if mse == 0:
        return float('inf')
    MAX = 32767.0
    return 10 * np.log10((MAX * MAX) / mse)
