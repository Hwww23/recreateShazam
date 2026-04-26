# SoundMatch 🎵

A Shazam-like song identification system built from scratch. Record audio from your microphone or system, and SoundMatch will identify the song within seconds.

![demo](demo.gif)

## How it works

SoundMatch uses audio fingerprinting — the same technique behind Shazam.

**1. Fingerprinting**
Each song is converted into a spectrogram using the Short-Time Fourier Transform (STFT) with a Hamming window. The spectrogram represents frequency content over time. A constellation of peaks is extracted from the spectrogram — points that are locally the loudest in their time-frequency neighborhood.

**2. Hashing**
For each peak, its 5 nearest neighbors in time are paired with it to form a hash of `(peak_frequency, neighbor_frequency, time_delta)`. Using time_delta instead of absolute time makes the hash time-invariant — the same pair of peaks produces the same hash regardless of where in the song they appear. These hashes are stored across sharded PostgreSQL instances.

**3. Matching**
When a short clip is recorded, its hashes are looked up in the database. For each matching hash, an offset is computed: `offset = db_time - query_time`. A true match produces many hashes that all agree on the same offset. The song with the most votes at a single offset wins.

## Tech stack

| Layer | Technology |
|---|---|
| Audio processing | Python, librosa, numpy, scipy |
| Backend API | FastAPI |
| Job queue | Celery |
| Cache + broker | Redis |
| Database | PostgreSQL (4 shards) |
| Frontend | React + Vite |
| Deployment | Docker, Docker Compose |

## Project structure

```
soundmatch/
├── backend/
│   ├── main.py           # FastAPI routes
│   ├── fingerprint.py    # Spectrogram + peak extraction + hashing
│   ├── matcher.py        # Offset voting algorithm
│   ├── store.py          # Database reads and writes
│   ├── database.py       # SQLAlchemy connection (shard 0)
│   ├── shards.py         # Shard routing by hash prefix
│   ├── cache.py          # Redis cache layer
│   ├── tasks.py          # Celery async tasks
│   └── init.sql          # Database schema
├── frontend/
│   └── src/
│       ├── App.jsx        # Main UI
│       └── App.css        # Styles
└── docker-compose.yml
```

## Running with Docker (recommended)

```bash
docker-compose up --build
```

Open `http://localhost:5173`

This starts all services: 4 PostgreSQL shards, Redis, Celery worker, FastAPI backend, and React frontend.

## Running locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL (4 instances on ports 5433–5436)
- Redis
- ffmpeg

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Celery worker (separate terminal)

```bash
cd backend
source venv/bin/activate
celery -A tasks worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

## Usage

**Adding songs** — click "+ Add song to library" and upload an mp3. Name your file `Artist - Title.mp3` for automatic metadata parsing.

**Identify by microphone** — click "Tap to listen" and play music near your mic.

**Identify system audio** — click "Identify what's playing" and share a browser tab that's playing music.

**Identify by file** — click "Upload clip to identify" and upload a short audio clip.

## Algorithm accuracy

Tested on 10-second clips with background noise added. Match scores above 50 votes are reliable. Typical scores on clean audio range from 200–1000+ votes.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend                        │
└───────────────────────────┬─────────────────────────────────┘
                            │ POST /recognize → 202 immediately
                            │ GET  /results/{job_id} (polling)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
└───────────────────────────┬─────────────────────────────────┘
                            │ enqueue job
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Redis (job broker)                        │
└───────────────────────────┬─────────────────────────────────┘
                            │ dequeue job
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Celery Worker                           │
│           (fingerprint audio + match hashes)                 │
└───────────────────────────┬─────────────────────────────────┘
                            │
               ┌────────────▼────────────┐
               │      Redis Cache        │ ← check here first
               │  (hot hash lookup)      │   (microseconds)
               └────────────┬────────────┘
                            │ cache miss → query shards
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Shard 0    │  │   Shard 1    │  │   Shard 2    │  │   Shard 3    │
│  prefix 0-3  │  │  prefix 4-7  │  │  prefix 8-b  │  │  prefix c-f  │
│ + songs table│  │              │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘

Each shard receives ~25% of fingerprints (SHA1 uniform distribution).
Queries only hit the shard matching the hash prefix — no broadcast needed.
Redis cache serves repeated lookups in microseconds, bypassing all shards.
```

# SoundMatch 🎵

![CI](https://github.com/Hwww23/recreateShazam/actions/workflows/ci.yml/badge.svg)