from celery import Celery
from fingerprint import load_audio, compute_spectrogram, extract_peaks, generate_hashes
from matcher import match
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Celery needs two things:
# broker  = where jobs are queued (Redis)
# backend = where results are stored (Redis too)
celery_app = Celery(
    "soundmatch",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,  # lets us report "in progress" status
)

@celery_app.task(bind=True)
def recognize_task(self, filepath):
    """
    Celery task that runs fingerprinting + matching in the background.
    
    bind=True gives us access to `self` which lets us update
    the task's state while it's running.
    """
    try:
        # from fingerprint import load_audio, compute_spectrogram, extract_peaks, generate_hashes
        # from matcher import match

        # Update state so frontend knows we're actively processing
        self.update_state(state="LOADING", meta={"status": "Loading audio..."})
        samples, sr = load_audio(filepath)

        self.update_state(state="FINGERPRINTING", meta={"status": "Fingerprinting..."})
        spec, hop, sr = compute_spectrogram(samples, sr)
        peaks = extract_peaks(spec, sr, hop)
        hashes = generate_hashes(peaks)

        self.update_state(state="MATCHING", meta={"status": "Matching..."})
        result = match(hashes)

        # Clean up temp file
        import os
        if os.path.exists(filepath):
            os.unlink(filepath)
        wav_path = filepath.replace(".webm", ".wav")
        if os.path.exists(wav_path):
            os.unlink(wav_path)

        if not result:
            return {"status": "not_found"}

        return {
            "status": "found",
            "title": result["song"]["title"],
            "artist": result["song"]["artist"],
            "score": result["score"],
            "offset_seconds": result["offset_seconds"]
        }

    except Exception as e:
        # Clean up on error too
        import os
        if os.path.exists(filepath):
            os.unlink(filepath)
        raise e