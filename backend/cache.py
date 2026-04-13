import redis
import json
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Create a connection pool — reuses connections instead of
# opening a new one for every cache call
client = redis.from_url(REDIS_URL, decode_responses=True)

# How long to keep cached results (in seconds)
# 24 hours — fingerprints don't change unless we re-ingest
TTL = 60 * 60 * 24

def get_cached_hashes(hash_list):
    """
    Look up a list of hashes in Redis.
    Returns a dict of { hash: [(db_time, song_id), ...] }
    for hashes that were found in cache.
    """
    if not hash_list:
        return {}

    # Redis pipeline sends all commands in one round trip
    # instead of one network call per hash — much faster
    pipe = client.pipeline()
    for h in hash_list:
        pipe.get(f"hash:{h}")
    results = pipe.execute()

    cached = {}
    for h, val in zip(hash_list, results):
        if val is not None:
            cached[h] = json.loads(val)

    return cached

def cache_hashes(matches):
    """
    Store hash lookup results in Redis.
    matches is a list of (hash, db_time, song_id) from PostgreSQL.
    We group them by hash before storing.
    """
    # Group matches by hash
    grouped = {}
    for db_hash, db_time, song_id in matches:
        if db_hash not in grouped:
            grouped[db_hash] = []
        grouped[db_hash].append([int(db_time), int(song_id)])

    # Store each hash's results as a JSON list
    pipe = client.pipeline()
    for h, values in grouped.items():
        pipe.setex(f"hash:{h}", TTL, json.dumps(values))
    pipe.execute()

def test_connection():
    client.ping()
    print("Redis connected!")

if __name__ == "__main__":
    test_connection()