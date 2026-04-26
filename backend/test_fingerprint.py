import numpy as np
from fingerprint import load_audio, compute_spectrogram, extract_peaks, generate_hashes

def test_generate_hashes_is_deterministic():
    """Same audio always produces same hashes"""
    # Create a simple sine wave instead of loading a real file
    sr = 22050
    duration = 5  # seconds
    t = np.linspace(0, duration, sr * duration)
    samples = np.sin(2 * np.pi * 440 * t).astype(np.float32)  # 440Hz tone

    spec, hop, sr = compute_spectrogram(samples, sr)
    peaks = extract_peaks(spec, sr, hop)
    hashes1 = generate_hashes(peaks)
    hashes2 = generate_hashes(peaks)

    assert hashes1 == hashes2, "Hashes should be deterministic"
    print(f"Generated {len(hashes1)} hashes — determinism check passed")

def test_generate_hashes_returns_list_of_tuples():
    """Hashes should be a list of (hash_string, time_index) tuples"""
    sr = 22050
    t = np.linspace(0, 5, sr * 5)
    samples = np.sin(2 * np.pi * 440 * t).astype(np.float32)

    spec, hop, sr = compute_spectrogram(samples, sr)
    peaks = extract_peaks(spec, sr, hop)
    hashes = generate_hashes(peaks)

    assert isinstance(hashes, list)
    assert len(hashes) > 0
    assert isinstance(hashes[0], tuple)
    assert len(hashes[0]) == 2
    assert isinstance(hashes[0][0], str)   # hash string
    print("Hash format check passed")

def test_different_audio_produces_different_hashes():
    """Different audio should produce mostly different hashes"""
    sr = 22050
    t = np.linspace(0, 5, sr * 5)

    # Use richer signals with multiple harmonics so we get more peaks
    samples_low = (
        np.sin(2 * np.pi * 261 * t) +   # C4
        np.sin(2 * np.pi * 329 * t) +   # E4
        np.sin(2 * np.pi * 392 * t)     # G4
    ).astype(np.float32)

    samples_high = (
        np.sin(2 * np.pi * 523 * t) +   # C5
        np.sin(2 * np.pi * 659 * t) +   # E5
        np.sin(2 * np.pi * 784 * t)     # G5
    ).astype(np.float32)

    spec1, hop, sr = compute_spectrogram(samples_low, sr)
    spec2, _, _    = compute_spectrogram(samples_high, sr)

    peaks1 = extract_peaks(spec1, sr, hop)
    peaks2 = extract_peaks(spec2, sr, hop)

    hashes1 = set(h for h, t in generate_hashes(peaks1))
    hashes2 = set(h for h, t in generate_hashes(peaks2))

    overlap = hashes1 & hashes2
    overlap_ratio = len(overlap) / len(hashes1) if hashes1 else 0

    # Two completely different chords should share less than 50% of hashes
    assert overlap_ratio < 0.5, (
        f"Expected mostly different hashes but got {overlap_ratio:.0%} overlap "
        f"({len(overlap)} shared out of {len(hashes1)})"
    )
    print(f"Distinctness check passed — overlap: {len(overlap)}/{len(hashes1)} ({overlap_ratio:.0%})")

if __name__ == "__main__":
    test_generate_hashes_is_deterministic()
    test_generate_hashes_returns_list_of_tuples()
    test_different_audio_produces_different_hashes()
    print("All tests passed!")