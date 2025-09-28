import hashlib, random

def seed_from_key(key: str) -> int:
    h = hashlib.sha256(key.encode('utf-8')).digest()
    return int.from_bytes(h[:8], 'big', signed=False)

def start_index_from_seed(total_slots: int, seed: int) -> int:
    if total_slots <= 0: return 0
    return seed % total_slots
