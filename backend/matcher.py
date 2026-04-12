from collections import defaultdict
from store import lookup_hashes, get_song

def match(query_hashes):
    """
    Given hashes from a short audio clip, find the best matching song.

    Steps:
    1. Look up all query hashes in the database
    2. For each match, compute offset = db_time - query_time
    3. Vote for (song_id, offset) pairs
    4. The pair with the most votes wins
    """

    # Step 1 — look up all hashes in the database
    # lookup_hashes returns list of (hash, db_time_index, song_id)
    db_matches = lookup_hashes(query_hashes)
    print(f"Found {len(db_matches)} raw hash matches in database")

    if not db_matches:
        return None

    # Build a dict so we can quickly find query_time for each hash
    # { hash_string: query_time_index }
    query_hash_map = {h: t for h, t in query_hashes}

    # Step 2 & 3 — compute offsets and vote
    # votes[(song_id, offset)] = count
    votes = defaultdict(int)

    for db_hash, db_time, song_id in db_matches:
        query_time = query_hash_map.get(db_hash)
        if query_time is None:
            continue

        offset = db_time - int(query_time)
        votes[(song_id, offset)] += 1

    if not votes:
        return None

    # Step 4 — find the winner
    best = max(votes, key=lambda k: votes[k])
    best_song_id, best_offset = best
    best_score = votes[best]

    print(f"Best match: song_id={best_song_id}, offset={best_offset}, score={best_score}")

    # Step 5 — fetch song metadata
    song = get_song(best_song_id)
    if not song:
        return None

    # Convert offset (time_index units) back to seconds
    # time_index * hop_length / sample_rate = seconds
    hop_length = 2048
    sample_rate = 22050
    offset_seconds = best_offset * hop_length / sample_rate

    return {
        "song": song,
        "score": best_score,
        "offset_seconds": round(offset_seconds, 2),
        "total_votes": len(votes)
    }