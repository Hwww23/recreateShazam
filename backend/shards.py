import os
from sqlalchemy import create_engine

# Each shard handles a quarter of the hash space
# SHA1 hashes are hex — first character determines the shard
SHARD_MAP = {
    '0': 0, '1': 0, '2': 0, '3': 0,
    '4': 1, '5': 1, '6': 1, '7': 1,
    '8': 2, '9': 2, 'a': 2, 'b': 2,
    'c': 3, 'd': 3, 'e': 3, 'f': 3,
}

SHARD_URLS = [
    os.getenv("SHARD_0_URL", "postgresql://postgres:postgres@localhost:5433/soundmatch"),
    os.getenv("SHARD_1_URL", "postgresql://postgres:postgres@localhost:5434/soundmatch"),
    os.getenv("SHARD_2_URL", "postgresql://postgres:postgres@localhost:5435/soundmatch"),
    os.getenv("SHARD_3_URL", "postgresql://postgres:postgres@localhost:5436/soundmatch"),
]

# Create one engine per shard — connection pools are reused
engines = [create_engine(url) for url in SHARD_URLS]

def get_shard_index(hash_str):
    """
    Given a hash string, return which shard index it belongs to.
    We look at the first character of the hash.
    e.g. 'a3f9c...' → 'a' → shard 2
    """
    first_char = hash_str[0].lower()
    return SHARD_MAP[first_char]

def get_shard_connection(hash_str):
    """
    Return a database connection for the shard that owns this hash.
    """
    idx = get_shard_index(hash_str)
    return engines[idx].connect()

def get_all_shard_connections():
    """
    Return connections to all shards — used during ingestion
    to write to each shard.
    """
    return [engine.connect() for engine in engines]

def group_hashes_by_shard(hashes):
    """
    Given a list of (hash, time_index) tuples, group them by shard.
    Returns a dict: { shard_index: [(hash, time_index), ...] }
    
    This lets us batch all hashes for a shard into one query
    instead of querying each shard once per hash.
    """
    groups = {0: [], 1: [], 2: [], 3: []}
    for h, t in hashes:
        shard_idx = get_shard_index(h)
        groups[shard_idx].append((h, t))
    return groups