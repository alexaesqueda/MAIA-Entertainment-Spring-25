# src/app/student_vibes.py

from __future__ import annotations

import io
from typing import List, Dict, Any, Optional, Set

import httpx
import numpy as np
import librosa


# -------------------------------------------------------------------
# 1) Hard-coded / seed data for student musician tracks
#    In production, you’d load this from a DB instead.
# -------------------------------------------------------------------
STUDENT_TRACKS: List[Dict[str, Any]] = [
    {
        "id": "student_focus_1",
        "title": "Takes a While",
        "artist": "Alexine Sakkers",
        "vibe": "focus",
        "audio_url": "https://drive.google.com/uc?export=download&id=11DTWdZNWDLgpPjhxGC5XssqBS0cog5t6",
    },
    {
        "id": "student_creative_1",
        "title": "Idea Flow",
        "artist": "Student B",
        "vibe": "creative",
        "audio_url": "https://example.com/student_creative_1.mp3",
    },
    {
        "id": "student_mellow_1",
        "title": "Calm Evening",
        "artist": "Student C",
        "vibe": "mellow",
        "audio_url": "https://example.com/student_mellow_1.mp3",
    },
    # Add more as you collect them
]

# Cache so we don't re-download & re-analyze the same student track
_STUDENT_FEATURE_CACHE: Dict[str, Dict[str, float]] = {}


# -------------------------------------------------------------------
# 2) Basic helpers
# -------------------------------------------------------------------
def list_vibes() -> List[str]:
    """
    Return unique vibes for which we have at least one student track.
    """
    vibes: Set[str] = set()
    for t in STUDENT_TRACKS:
        v = t.get("vibe")
        if v:
            vibes.add(v.lower())
    return sorted(vibes)


def get_student_tracks_for_vibe(vibe: str) -> List[Dict[str, Any]]:
    """
    All student tracks whose vibe label matches (case-insensitive).
    """
    vibe = vibe.lower()
    return [t for t in STUDENT_TRACKS if t.get("vibe", "").lower() == vibe]


# -------------------------------------------------------------------
# 3) Audio feature extraction (librosa) for *both* student and Apple tracks
# -------------------------------------------------------------------
def extract_features_from_audio_bytes(data: bytes, sr: int = 22050) -> Dict[str, float]:
    """
    Given raw audio bytes (e.g. from an MP3 preview), compute a
    small, consistent feature vector.

    We keep it simple & fast:
      - tempo (BPM)
      - energy (mean RMS)
      - zcr (mean zero-crossing rate)
      - centroid (mean spectral centroid)
      - bandwidth (mean spectral bandwidth)
    """
    # librosa can read from a file-like object
    audio_buffer = io.BytesIO(data)
    y, sr = librosa.load(audio_buffer, sr=sr, mono=True)

    if y.size == 0:
        raise ValueError("Empty audio signal")

    # Tempo
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

    # RMS energy
    rms = librosa.feature.rms(y=y)
    energy = float(np.mean(rms))

    # Zero-crossing rate
    zcr = librosa.feature.zero_crossing_rate(y=y)
    zcr_mean = float(np.mean(zcr))

    # Spectral centroid & bandwidth
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    centroid_mean = float(np.mean(centroid))
    bandwidth_mean = float(np.mean(bandwidth))

    return {
        "tempo": float(tempo),
        "energy": energy,
        "zcr": zcr_mean,
        "centroid": centroid_mean,
        "bandwidth": bandwidth_mean,
    }


def get_features_for_student_track(track_id: str, audio_url: str) -> Optional[Dict[str, float]]:
    """
    Download & analyze a single student track, with caching.
    """
    if track_id in _STUDENT_FEATURE_CACHE:
        return _STUDENT_FEATURE_CACHE[track_id]

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(audio_url)
            r.raise_for_status()
            feats = extract_features_from_audio_bytes(r.content)
    except Exception as e:
        print(f"[StudentFeatures] Failed to fetch/analyze {track_id} from {audio_url}: {e}")
        return None

    _STUDENT_FEATURE_CACHE[track_id] = feats
    return feats


# -------------------------------------------------------------------
# 4) Reference feature vector per vibe
# -------------------------------------------------------------------
def get_reference_features_for_vibe(vibe: str) -> Optional[Dict[str, float]]:
    """
    For a given vibe, average features across all student tracks with that label.
    This 'average vector' becomes the reference sound for that vibe.
    """
    candidates = get_student_tracks_for_vibe(vibe)
    if not candidates:
        print(f"[StudentFeatures] No student tracks for vibe '{vibe}'")
        return None

    feature_list: List[Dict[str, float]] = []
    for t in candidates:
        feats = get_features_for_student_track(t["id"], t["audio_url"])
        if feats:
            feature_list.append(feats)

    if not feature_list:
        print(f"[StudentFeatures] No valid features for vibe '{vibe}'")
        return None

    keys = ["tempo", "energy", "zcr", "centroid", "bandwidth"]
    avg: Dict[str, float] = {}
    n = len(feature_list)
    for k in keys:
        s = sum(float(f.get(k, 0.0)) for f in feature_list)
        avg[k] = s / n

    print(f"[StudentFeatures] Reference vector for vibe '{vibe}': {avg}")
    return avg
