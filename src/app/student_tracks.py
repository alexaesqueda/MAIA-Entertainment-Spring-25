# src/app/student_tracks.py

from typing import Dict, Any, List, Optional
from functools import lru_cache

from .audio_features import extract_features_from_url

"""
Student musician tracks.

Replace the example entries with your actual student songs:
- audio_url: where the MP3/M4A is hosted
- task: 'productivity', 'creative', 'relax', etc.
"""

STUDENT_TRACKS: List[Dict[str, Any]] = [
    {
        "id": "student_prod_1",
        "name": "Deep Focus Jam",
        "artist": "Student A",
        "task": "productivity",
        "audio_url": "https://example.com/audio/student_prod_1.mp3",
    },
    {
        "id": "student_creative_1",
        "name": "Creative Flow",
        "artist": "Student B",
        "task": "creative",
        "audio_url": "https://example.com/audio/student_creative_1.mp3",
    },
    {
        "id": "student_relax_1",
        "name": "Calm Afternoon",
        "artist": "Student C",
        "task": "relax",
        "audio_url": "https://example.com/audio/student_relax_1.mp3",
    },
    # add more student tracks here
]


def list_tasks() -> List[str]:
    """
    All unique task labels from student tracks.
    """
    return sorted({t["task"] for t in STUDENT_TRACKS})


def get_student_tracks_for_task(task: str) -> List[Dict[str, Any]]:
    """
    Student tracks labeled with this task.
    """
    return [t for t in STUDENT_TRACKS if t["task"].lower() == task.lower()]


@lru_cache(maxsize=128)
def get_features_for_student_track(track_id: str, audio_url: str) -> Optional[Dict[str, Any]]:
    """
    Compute (and cache) audio features for a given student track.
    """
    print(f"[StudentFeatures] Extracting features for {track_id} from {audio_url}")
    feats = extract_features_from_url(audio_url)
    if not feats:
        print(f"[StudentFeatures] Failed to get features for {track_id}")
        return None
    return feats


def get_reference_features_for_task(task: str) -> Optional[Dict[str, Any]]:
    """
    For a task, average features across all student tracks with that label.
    This 'average vector' is the reference sound.
    """
    candidates = get_student_tracks_for_task(task)
    if not candidates:
        print(f"[StudentFeatures] No student tracks for task '{task}'")
        return None

    feature_list: List[Dict[str, Any]] = []
    for t in candidates:
        feats = get_features_for_student_track(t["id"], t["audio_url"])
        if feats:
            feature_list.append(feats)

    if not feature_list:
        print(f"[StudentFeatures] No valid features for task '{task}'")
        return None

    keys = ["tempo", "energy", "valence", "acousticness", "danceability", "instrumentalness"]
    avg: Dict[str, float] = {}
    n = len(feature_list)
    for k in keys:
        s = sum(float(f.get(k, 0.0)) for f in feature_list)
        avg[k] = s / n

    return avg
