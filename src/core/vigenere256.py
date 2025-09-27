from typing import ByteString

def _key_stream(key: bytes, length: int) -> bytes:
    if not key:
        return b""
    out = bytearray()
    while len(out) < length:
        out.extend(key)
    return bytes(out[:length])

def encrypt(data: ByteString, key: ByteString) -> bytes:
    k = _key_stream(bytes(key), len(data))
    return bytes(((d + k[i]) % 256) for i, d in enumerate(data))

def decrypt(data: ByteString, key: ByteString) -> bytes:
    k = _key_stream(bytes(key), len(data))
    return bytes(((d - k[i]) % 256) for i, d in enumerate(data))
