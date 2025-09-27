def iter_bits(data: bytes):
    for byte in data:
        for i in range(8):
            yield (byte >> (7 - i)) & 1

def pack_bits_to_bytes(bits):
    out = bytearray()
    cur = 0
    cnt = 0
    for b in bits:
        cur = (cur << 1) | (b & 1)
        cnt += 1
        if cnt == 8:
            out.append(cur); cur = 0; cnt = 0
    if cnt:
        out.append(cur << (8 - cnt))
    return bytes(out)
