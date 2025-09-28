def _keystream(key: bytes, n: int) -> bytes:
    if not key: return b""
    out = bytearray()
    while len(out) < n:
        out.extend(key)
    return bytes(out[:n])

def vigenere256_encrypt(data: bytes, key: bytes) -> bytes:
    ks = _keystream(key, len(data))
    return bytes(((d + ks[i]) & 0xFF) for i, d in enumerate(data))

def vigenere256_decrypt(data: bytes, key: bytes) -> bytes:
    ks = _keystream(key, len(data))
    return bytes(((d - ks[i]) & 0xFF) for i, d in enumerate(data))
