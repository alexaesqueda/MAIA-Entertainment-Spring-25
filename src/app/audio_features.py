# src/app/audio_features.py

import io
import math
import tempfile
import os
from typing import Dict, Any, Optional

import httpx
import numpy as np
import librosa


def _estimate_energy(y: np.ndarray) -> float:
    """
    Crude 'energy' estimate: log-scaled RMS in [0, 1].
    """
    rms = float(librosa.feature.rms(y=y).mean())
    val = math.log10(1.0 + 9.0 * rms)  # 0 → 0, higher RMS → closer to 1
    return float(min(1.0, max(0.0, val)))


def _estimate_valence_like(y: np.ndarray, sr: int) -> float:
    """
    Rough 'valence-like' proxy using spectral centroid:
    brighter sounds → higher centroid → more 'positive'.
    """
    cent = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
    return float(min(1.0, max(0.0, cent / 8000.0)))


def _estimate_acousticness_like(y: np.ndarray, sr: int) -> float:
    """
    Crude acousticness proxy: invert spectral rolloff.
    More high-frequency content → less 'acoustic'.
    """
    rolloff = float(librosa.feature.spectral_rolloff(y=y, sr=sr).mean())
    nyquist = sr / 2.0
    norm = min(1.0, max(0.0, rolloff / nyquist))
    return float(1.0 - norm)


def _estimate_danceability_like(y: np.ndarray, sr: int) -> float:
    """
    Rough danceability proxy based on tempo + onset strength.
    """
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    beat_strength = float(onset_env.mean())

    # normalize tempo between 60 and 180 BPM
    tempo_norm = (tempo - 60.0) / (180.0 - 60.0)
    tempo_norm = float(min(1.0, max(0.0, tempo_norm)))

    # normalize beat strength with a heuristic divisor
    strength_norm = float(min(1.0, max(0.0, beat_strength / 10.0)))

    return 0.6 * tempo_norm + 0.4 * strength_norm


def extract_features_from_audio_bytes(audio_bytes: bytes, sr: int = 22050) -> Optional[Dict[str, Any]]:
    """
    Decode raw audio bytes (MP3/M4A/etc.) and extract a feature dict.
    Updated to use a temporary file to support M4A/AAC decoding.
    """
    # Create a temporary file to hold the audio data
    # We use a suffix like .m4a so librosa knows what format to expect
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_file_path = tmp_file.name

    try:
        # Load from the FILE PATH, not the memory buffer
        y, sr = librosa.load(tmp_file_path, sr=sr, mono=True)
    except Exception as e:
        print("Failed to decode audio bytes:", repr(e))
        return None
    finally:
        # Clean up: remove the temp file to save space
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

    if y.size < sr:
        return None

    # ... (Keep the rest of your feature extraction logic below) ...
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    energy = _estimate_energy(y)
    valence = _estimate_valence_like(y, sr)
    acousticness = _estimate_acousticness_like(y, sr)
    danceability = _estimate_danceability_like(y, sr)
    
    instrumentalness = 0.0

    return {
        "tempo": float(tempo),
        "energy": float(energy),
        "valence": float(valence),
        "acousticness": float(acousticness),
        "danceability": float(danceability),
        "instrumentalness": float(instrumentalness),
    }


def extract_features_from_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Download audio from a URL, then extract features.
    """
    if not url:
        return None

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(url)
            r.raise_for_status()
            audio_bytes = r.content
    except Exception as e:
        print("Failed to download audio from URL:", url, "error:", repr(e))
        return None

    return extract_features_from_audio_bytes(audio_bytes)
