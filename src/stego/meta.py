import struct
from dataclasses import dataclass

MAGIC = b"STEG"
VER = 1
HDR_FMT = "<4s B B B I H B"

FLAG_ENC = 1 << 0
FLAG_RND = 1 << 1

@dataclass
class HeaderCfg:
    encrypted: bool
    randomized: bool
    n_lsb: int
    payload_len: int
    name: str
    ext: str

def build_header(cfg: HeaderCfg) -> bytes:
    flags = (FLAG_ENC if cfg.encrypted else 0) | (FLAG_RND if cfg.randomized else 0)
    name_b = cfg.name.encode('utf-8')
    ext_b = cfg.ext.encode('utf-8')
    head = struct.pack(HDR_FMT, MAGIC, VER, flags, cfg.n_lsb, cfg.payload_len, len(name_b), len(ext_b))
    return head + name_b + ext_b

def parse_header(buf: bytes):
    MAGIC_LEN = 4
    if len(buf) < struct.calcsize(HDR_FMT):
        raise ValueError("Header too small")
    magic, ver, flags, n_lsb, payload_len, name_len, ext_len = struct.unpack_from(HDR_FMT, buf, 0)
    if magic != MAGIC:
        raise ValueError("Magic mismatch")
    off = struct.calcsize(HDR_FMT)
    name = buf[off:off+name_len].decode('utf-8'); off += name_len
    ext = buf[off:off+ext_len].decode('utf-8'); off += ext_len
    return {"ver": ver, "flags": flags, "n_lsb": n_lsb, "payload_len": payload_len, "name": name, "ext": ext, "header_len": off}
