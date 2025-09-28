def bits_from_bytes(data: bytes):
    for b in data:
        for i in range(7,-1,-1):
            yield (b >> i) & 1

def bytes_from_bits(bits):
    out = bytearray()
    cur = 0; cnt = 0
    for bit in bits:
        cur = (cur<<1) | (bit & 1)
        cnt += 1
        if cnt == 8:
            out.append(cur); cur = 0; cnt = 0
    if cnt:
        out.append(cur << (8-cnt))
    return bytes(out)
