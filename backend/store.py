from sqlalchemy import text
from database import get_connection
from cache import get_cached_hashes, cache_hashes

def insert_song(title, artist="", album="", duration=0.0):
    """
    Insert a song into the songs table and return its new id.
    """
    with get_connection() as conn:
        result = conn.execute(
            text("""
                INSERT INTO songs (title, artist, album, duration)
                VALUES (:title, :artist, :album, :duration)
                RETURNING id
            """),
            {"title": title, "artist": artist, "album": album, "duration": duration}
        )
        conn.commit()
        song_id = result.fetchone()[0]
        print(f"Inserted song '{title}' with id={song_id}")
        return song_id

def insert_fingerprints(song_id, hashes):
    """
    Bulk insert all fingerprint hashes for a song.
    We insert in bulk (all at once) rather than one by one —
    inserting 45000 rows one at a time would be very slow.
    """
    rows = [{"song_id": song_id, "hash": h, "time_index": int(t)} for h, t in hashes]

    with get_connection() as conn:
        conn.execute(
            text("""
                INSERT INTO fingerprints (song_id, hash, time_index)
                VALUES (:song_id, :hash, :time_index)
            """),
            rows  # sqlalchemy handles the list as a bulk insert
        )
        conn.commit()
        print(f"Inserted {len(rows)} fingerprints for song_id={song_id}")

def lookup_hashes(hashes):
    """
    Given a list of (hash, time_index) tuples from a query clip,
    find all matching fingerprints in the database.

    Returns a list of (hash, db_time_index, song_id) tuples.
    """
    # hash_list = [h for h, t in hashes]

    # with get_connection() as conn:
    #     result = conn.execute(
    #         text("""
    #             SELECT hash, time_index, song_id
    #             FROM fingerprints
    #             WHERE hash = ANY(:hashes)
    #         """),
    #         {"hashes": hash_list}
    #     )
    #     return result.fetchall()

    """
    Look up hashes — check Redis first, fall back to PostgreSQL.
    """
    hash_list = [h for h, t in hashes]

    # Step 1 — check cache
    cached = get_cached_hashes(hash_list)
    cached_hits = set(cached.keys())
    missed = [h for h in hash_list if h not in cached_hits]

    print(f"Cache hits: {len(cached_hits)}, misses: {len(missed)}")

    # Step 2 — query PostgreSQL for cache misses only
    db_results = []
    if missed:
        with get_connection() as conn:
            result = conn.execute(
                text("""
                    SELECT hash, time_index, song_id
                    FROM fingerprints
                    WHERE hash = ANY(:hashes)
                """),
                {"hashes": missed}
            )
            db_results = result.fetchall()

        # Step 3 — populate cache with what we just fetched
        if db_results:
            cache_hashes(db_results)

    # Step 4 — combine cached + db results into one flat list
    all_results = []

    for h, values in cached.items():
        for db_time, song_id in values:
            all_results.append((h, db_time, song_id))

    for row in db_results:
        all_results.append((row[0], row[1], row[2]))

    return all_results

def get_song(song_id):
    """
    Fetch song metadata by id.
    """
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT id, title, artist, album, duration FROM songs WHERE id = :id"),
            {"id": song_id}
        )
        row = result.fetchone()
        if row:
            return {"id": row[0], "title": row[1], "artist": row[2],
                    "album": row[3], "duration": row[4]}
        return None