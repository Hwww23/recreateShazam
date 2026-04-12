import librosa
import numpy as np
import matplotlib.pyplot as plt
import subprocess
from scipy.ndimage import maximum_filter

def load_audio(filepath, sr=22050):
    """
    Load an audio file and return the samples and sample rate.
    
    sr=22050 means we resample everything to 22050Hz.
    This caps our frequency range at 11025Hz (Nyquist theorem:
    max detectable frequency = sr / 2), which covers all musically
    relevant sound and halves our data size vs 44100Hz.
    """
    # If file is webm, convert to wav first using ffmpeg
    if filepath.endswith(".webm"):
        wav_path = filepath.replace(".webm", ".wav")
        subprocess.run([
            "ffmpeg", "-y",          # -y = overwrite output if exists
            "-i", filepath,          # input file
            "-ar", str(sr),          # set sample rate
            "-ac", "1",              # mono
            wav_path
        ], check=True, capture_output=True)
        filepath = wav_path          # use the converted file

    samples, sample_rate = librosa.load(filepath, sr=sr, mono=True)
    print(f'Loaded {filepath}: {len(samples)} samples at {sample_rate}')
    print(f'Duration: {len(samples) / sample_rate:.2f} seconds')
    return samples, sample_rate

def compute_spectrogram(samples, sample_rate):
    """
    Convert raw audio samples into a spectrogram using STFT.
    
    n_fft=4096        → window size. Larger = better frequency resolution,
                        worse time resolution. 4096 is a good balance.
    hop_length=2048   → how many samples to slide forward each step.
                        hop = n_fft/2 means 50% overlap between windows.
    window='hamming'  → smooths the edges of each window to avoid
                        sharp cutoff artifacts in the FFT output.
    """
    n_fft = 4096
    hop_length = 2048

    stft = librosa.stft(samples, n_fft=n_fft, hop_length=hop_length, window='hamming')
    spectrogram = np.abs(stft)

    print(f'Spectrogram shape: {spectrogram.shape}')

    return spectrogram, hop_length, sample_rate

def plot_spectrogram(spectrogram, sample_rate, hop_length):
    """
    Plot the spectrogram so we can see what we're working with.
    """
    # Convert amplitude to decibels for better visual contrast
    spectrogram_db = librosa.amplitude_to_db(spectrogram, ref=np.max)
    
    plt.figure(figsize=(14, 6))
    librosa.display.specshow(
        spectrogram_db,
        sr=sample_rate,
        hop_length=hop_length,
        x_axis='time',
        y_axis='hz',
        cmap='magma'
    )
    plt.colorbar(format='%+2.0f dB')
    plt.title('Spectrogram')
    plt.tight_layout()
    plt.savefig('spectrogram.png')
    print("Saved spectrogram.png — open it to see your spectrogram!")

def extract_peaks(spectrogram, sample_rate, hop_length,
                  neighborhood_size=20, threshold_abs=10):
    """
    Find the 'constellation' of peaks in the spectrogram.
    
    neighborhood_size  → a peak must be the loudest point within
                         a (neighborhood_size x neighborhood_size)
                         box of time-frequency neighbors.
                         Larger = fewer, more spread out peaks.
    
    threshold_abs      → minimum amplitude (in dB) a peak must have.
                         Filters out quiet background noise peaks.
    """

    # Step 1 — convert to dB scale for better peak contrast
    spectrogram_db = librosa.amplitude_to_db(spectrogram, ref=np.max)

    # Step 2 — for every point, find the maximum within its neighborhood
    # If a point equals the neighborhood max, it IS a local peak
    local_max = maximum_filter(spectrogram_db, size=neighborhood_size)
    is_peak = (spectrogram_db == local_max)

    # Step 3 — discard peaks that are too quiet
    is_loud_enough = (spectrogram_db > threshold_abs - 80)
    # note: librosa's amplitude_to_db with ref=np.max means the loudest
    # point = 0dB, everything else is negative. So threshold_abs=10
    # means we keep peaks above -70dB relative to the loudest point.

    peaks = is_peak & is_loud_enough

    # Step 4 — get the coordinates of all surviving peaks
    freq_indices, time_indices = np.where(peaks)

    # Step 5 — convert indices back to real units for readability
    times = librosa.frames_to_time(time_indices, sr=sample_rate, hop_length=hop_length)
    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=4096)[freq_indices]

    print(f"Found {len(freq_indices)} peaks")
    return list(zip(time_indices, freq_indices, times, freqs))
    # each peak is (time_index, freq_index, time_seconds, freq_hz)

def plot_peaks(spectrogram, sample_rate, hop_length, peaks):
    """
    Plot spectrogram with peaks overlaid as red dots.
    This is your 'constellation map'.
    """
    spectrogram_db = librosa.amplitude_to_db(spectrogram, ref=np.max)

    plt.figure(figsize=(14, 6))
    librosa.display.specshow(
        spectrogram_db,
        sr=sample_rate,
        hop_length=hop_length,
        x_axis='time',
        y_axis='hz',
        cmap='magma'
    )
    plt.colorbar(format='%+2.0f dB')

    # overlay peaks as red dots
    times = [p[2] for p in peaks]
    freqs = [p[3] for p in peaks]
    plt.scatter(times, freqs, color='red', s=5, zorder=5, label='peaks')

    plt.title('Spectrogram with Peaks')
    plt.legend()
    plt.tight_layout()
    plt.savefig('peaks.png')
    print("Saved peaks.png")

import hashlib

def generate_hashes(peaks, fan_out=5, time_delta_max=200):
    """
    For each peak, pair it with its next `fan_out` neighbors in time,
    and hash each pair into a fingerprint.

    fan_out         → how many neighbors each peak is paired with.
                      Higher = more hashes = more accurate but slower.
                      5 is a good balance.

    time_delta_max  → maximum time gap (in time_index units) between
                      a peak and its neighbor. Prevents pairing peaks
                      that are too far apart in time to be meaningful.

    Returns a list of (hash_string, time_index) tuples.
    """

    hashes = []

    # Sort peaks by time so neighbors are naturally the next peaks
    peaks_sorted = sorted(peaks, key=lambda p: p[0])  # sort by time_index

    for i, peak in enumerate(peaks_sorted):
        time_i, freq_i, _, _ = peak

        # Look at the next `fan_out` peaks as neighbors
        for j in range(1, fan_out + 1):
            if i + j >= len(peaks_sorted):
                break  # no more peaks left

            neighbor = peaks_sorted[i + j]
            time_j, freq_j, _, _ = neighbor

            time_delta = time_j - time_i

            # Skip if neighbor is too far ahead in time
            if time_delta > time_delta_max:
                break

            # Create a hash from (my frequency, neighbor frequency, time gap)
            # This triplet uniquely describes the relationship between two peaks
            hash_input = f"{freq_i}|{freq_j}|{time_delta}"
            hash_str = hashlib.sha1(hash_input.encode()).hexdigest()[:20]
            # We take first 20 chars of SHA1 — long enough to be unique,
            # short enough to store efficiently

            hashes.append((hash_str, time_i))
            # time_i is stored so we can compute offset during matching

    print(f"Generated {len(hashes)} hashes")
    return hashes

if __name__ == "__main__":
    from store import insert_song, insert_fingerprints
    from matcher import match
    
    # samples, sr = load_audio("ONE OK ROCK - Tiny Pieces [OFFICIAL LYRIC VIDEO].mp3")
    # spec, hop, sr = compute_spectrogram(samples, sr)
    # #plot_spectrogram(spec, sr, hop)
    # peaks = extract_peaks(spec, sr, hop)
    # #plot_peaks(spec, sr, hop, peaks)
    # hashes = generate_hashes(peaks)

    # # Print a few example hashes to see what they look like
    # # print("\nSample hashes:")
    # # for h, t in hashes[:5]:
    # #     print(f"  hash={h}  at time_index={t}")

    # # hashes2 = generate_hashes(peaks)
    # # assert hashes1 == hashes2, "Hashes are not deterministic!"
    # # print("✓ Hashes are deterministic")

    # song_id = insert_song(
    #     title="Tiny Pieces",
    #     artist="ONE OK ROCK",
    #     duration=len(samples) / sr
    # )
    # insert_fingerprints(song_id, hashes)

    # --- QUERY --- simulate a 15 second clip starting at 30 seconds
    samples, sr = load_audio("trimmed.mp3")

    start_sec = 0
    end_sec = 10
    clip = samples[start_sec * sr : end_sec * sr]
    
    noise = np.random.normal(0, 0.005, len(clip))
    clip = clip + noise

    print(f"\nQuerying with a {end_sec - start_sec}s clip (t={start_sec}s to t={end_sec}s)...")

    # fingerprint the clip exactly like we do for full songs
    import numpy as np
    import librosa

    n_fft = 4096
    hop_length = 2048
    stft = librosa.stft(clip, n_fft=n_fft, hop_length=hop_length, window='hamming')
    spec_clip = np.abs(stft)

    peaks_clip = extract_peaks(spec_clip, sr, hop_length)
    hashes_clip = generate_hashes(peaks_clip)

    result = match(hashes_clip)

    if result:
        print(f"\n✓ Matched: '{result['song']['title']}' by {result['song']['artist']}")
        print(f"  Score: {result['score']} votes")
        print(f"  Clip starts at ~{result['offset_seconds']}s in the song")
    else:
        print("\n✗ No match found")
