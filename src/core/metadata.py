import struct
from dataclasses import dataclass

MAGIC = b"STEG"
HEADER_FMT = "<4sB B I H B"  
VERSION = 1

FLAG_ENCRYPTED = 1 << 0
FLAG_RANDOMIZED = 1 << 1

@dataclass
class EmbedConfig:
    encrypted: bool
    randomized: bool
    n_lsb: int
    filename: str
    extension: str
    payload_len: int

def build_header(cfg: EmbedConfig) -> bytes:
    flags = (FLAG_ENCRYPTED if cfg.encrypted else 0) | (FLAG_RANDOMIZED if cfg.randomized else 0)
    head = struct.pack(HEADER_FMT, MAGIC, VERSION, flags, cfg.payload_len, len(cfg.filename.encode('utf-8')), cfg.n_lsb)
    name_bytes = cfg.filename.encode('utf-8')
    ext = cfg.extension.encode('utf-8')
    if len(ext) > 255:
        raise ValueError("extension too long")
    return head + name_bytes + bytes([len(ext)]) + ext

def parse_header(buf: bytes):
    magic, version, flags, payload_len, name_len, n_lsb = struct.unpack_from(HEADER_FMT, buf, 0)
    if magic != MAGIC:
        raise ValueError("Magic not found")
    offset = struct.calcsize(HEADER_FMT)
    name = buf[offset:offset+name_len].decode('utf-8'); offset += name_len
    ext_len = buf[offset]; offset += 1
    ext = buf[offset:offset+ext_len].decode('utf-8'); offset += ext_len
    return {"version": version, "flags": flags, "payload_len": payload_len, "name": name, "ext": ext, "n_lsb": n_lsb, "header_len": offset}
