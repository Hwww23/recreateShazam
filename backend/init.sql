CREATE TABLE IF NOT EXISTS songs (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    artist      VARCHAR(255),
    album       VARCHAR(255),
    duration    FLOAT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fingerprints (
    id          SERIAL PRIMARY KEY,
    song_id     INTEGER NOT NULL,
    hash        VARCHAR(20) NOT NULL,
    time_index  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fingerprints_hash ON fingerprints(hash);