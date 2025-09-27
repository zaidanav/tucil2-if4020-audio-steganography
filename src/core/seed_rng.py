import hashlib, random

def seed_from_key(key: str) -> int:
    h = hashlib.sha256(key.encode('utf-8')).digest()
    return int.from_bytes(h[:8], 'big', signed=False)

def shuffled_indices(n: int, seed: int) -> list[int]:
    idx = list(range(n))
    rng = random.Random(seed)
    rng.shuffle(idx)
    return idx
