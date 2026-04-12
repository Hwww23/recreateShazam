from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import librosa
import tempfile
import os

from fingerprint import (
    load_audio,
    compute_spectrogram,
    extract_peaks,
    generate_hashes
)
from store import insert_song, insert_fingerprints
from matcher import match

app = FastAPI()

# CORS — allows your React frontend (running on localhost:3000)
# to talk to this backend (running on localhost:8000).
# Without this, the browser blocks cross-origin requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "SoundMatch API is running"}


# ─────────────────────────────────────────────
# INGEST A SONG
# ─────────────────────────────────────────────

@app.post("/songs")
async def ingest_song(file: UploadFile = File(...)):
    """
    Upload an mp3/wav file to fingerprint and store in the database.

    UploadFile = FastAPI's way of receiving a file from a POST request.
    File(...)  = the ... means this field is required (not optional).
    """

    # Save the uploaded file to a temp location on disk
    # We need a real file path because librosa.load() needs one
    suffix = os.path.splitext(file.filename)[1]  # get .mp3 or .wav
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Fingerprint it
        samples, sr = load_audio(tmp_path)
        spec, hop, sr = compute_spectrogram(samples, sr)
        peaks = extract_peaks(spec, sr, hop)
        hashes = generate_hashes(peaks)

        # Parse title and artist from filename
        # e.g. "ONE OK ROCK - Tiny Pieces.mp3" → artist="ONE OK ROCK", title="Tiny Pieces"
        name = os.path.splitext(file.filename)[0]
        if " - " in name:
            artist, title = name.split(" - ", 1)
        else:
            artist, title = "", name

        # Store in database
        song_id = insert_song(
            title=title.strip(),
            artist=artist.strip(),
            duration=len(samples) / sr
        )
        insert_fingerprints(song_id, hashes)

        return {
            "message": "Song ingested successfully",
            "song_id": song_id,
            "title": title.strip(),
            "artist": artist.strip(),
            "hashes": len(hashes)
        }

    finally:
        os.unlink(tmp_path)  # always delete the temp file when done
        # clean up converted wav if it exists
        wav_path = tmp_path.replace(".webm", ".wav")
        if os.path.exists(wav_path):
            os.unlink(wav_path)


# ─────────────────────────────────────────────
# RECOGNISE A CLIP
# ─────────────────────────────────────────────

@app.post("/recognize")
async def recognize(file: UploadFile = File(...)):
    """
    Upload a short audio clip and get back the matching song.
    """

    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        samples, sr = load_audio(tmp_path)
        spec, hop, sr = compute_spectrogram(samples, sr)
        peaks = extract_peaks(spec, sr, hop)
        hashes = generate_hashes(peaks)

        result = match(hashes)

        if not result:
            raise HTTPException(status_code=404, detail="No match found")

        return {
            "title": result["song"]["title"],
            "artist": result["song"]["artist"],
            "score": result["score"],
            "offset_seconds": result["offset_seconds"]
        }

    finally:
        os.unlink(tmp_path)
        # clean up converted wav if it exists
        wav_path = tmp_path.replace(".webm", ".wav")
        if os.path.exists(wav_path):
            os.unlink(wav_path)


# ─────────────────────────────────────────────
# LIST ALL SONGS
# ─────────────────────────────────────────────

@app.get("/songs")
def list_songs():
    """
    Return all songs in the database.
    """
    from store import get_connection
    from sqlalchemy import text

    with get_connection() as conn:
        result = conn.execute(text("SELECT id, title, artist, duration FROM songs ORDER BY id"))
        rows = result.fetchall()

    return [
        {"id": r[0], "title": r[1], "artist": r[2], "duration": r[3]}
        for r in rows
    ]