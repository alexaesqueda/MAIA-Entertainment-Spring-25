# src/app/apple.py

from typing import Dict, List, Any, Optional

import httpx
import numpy as np
from pydantic import BaseModel

from .audio_features import extract_features_from_url
from .student_tracks import (
    get_reference_features_for_task,
    get_student_tracks_for_task,
)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


class TrackOut(BaseModel):
    """
    Track representation returned to the frontend (Apple tracks).
    """
    id: str
    uri: str
    name: str
    artists: List[str]
    preview_url: Optional[str] = None
    external_url: Optional[str] = None
    features: Dict[str, Any]


class StudentTrackOut(BaseModel):
    """
    Representation of a student musician track (reference).
    """
    id: str
    name: str
    artist: str
    task: str
    audio_url: str
    features: Optional[Dict[str, Any]] = None


def search_itunes_tracks(term: str, limit: int = 80, country: str = "US") -> List[Dict[str, Any]]:
    """
    Call iTunes Search API to get candidate tracks.
    Docs: https://itunes.apple.com/search
    """
    params = {
        "term": term,
        "media": "music",
        "entity": "song",
        "limit": limit,
        "country": country,
    }
    with httpx.Client(timeout=15.0) as client:
        r = client.get(ITUNES_SEARCH_URL, params=params)
        r.raise_for_status()
        data = r.json()
    results = data.get("results", [])
    print(f"[iTunes] Search term='{term}', country='{country}', results={len(results)}")
    return results


def _vectorize(feats: Dict[str, Any]) -> np.ndarray:
    """
    Convert features dict into numeric vector for distance.
    """
    return np.array(
        [
            float(feats.get("tempo", 0.0)),
            float(feats.get("energy", 0.0)),
            float(feats.get("valence", 0.0)),
            float(feats.get("acousticness", 0.0)),
            float(feats.get("danceability", 0.0)),
            float(feats.get("instrumentalness", 0.0)),
        ],
        dtype=float,
    )


def _similarity_score(ref_feats: Dict[str, Any], cand_feats: Dict[str, Any]) -> float:
    """
    Higher score = more similar (negative Euclidean distance).
    """
    ref_vec = _vectorize(ref_feats)
    cand_vec = _vectorize(cand_feats)
    dist = np.linalg.norm(ref_vec - cand_vec)
    return -float(dist)


def recommend_from_task(
    task: str,
    limit: int = 25,
    market: Optional[str] = "US",
) -> Dict[str, Any]:
    """
    Main pipeline:
    1) Get reference features from student tracks for the task.
    2) iTunes Search for candidates by keyword.
    3) Extract features from each candidate's previewUrl.
    4) Rank by similarity to reference.
    5) Return reference + top-N candidates.
    """
    task = task.lower()

    ref_feats = get_reference_features_for_task(task)
    if not ref_feats:
        raise ValueError(f"No valid student reference features for task '{task}'")

    # Map tasks to search terms (tweak as you like)
    default_terms = {
        "productivity": "focus study lofi",
        "creative": "creative electronic experimental",
        "relax": "chill relax ambient",
    }
    search_term = default_terms.get(task, task + " music")

    country = (market or "US").upper()
    raw_results = search_itunes_tracks(search_term, limit=80, country=country)

    # Build candidate list with features
    candidates: List[TrackOut] = []
    for r in raw_results:
        preview = r.get("previewUrl")
        if not preview:
            continue

        feats = extract_features_from_url(preview)
        if not feats:
            continue

        track = TrackOut(
            id=str(r.get("trackId")),
            uri=r.get("trackViewUrl") or "",
            name=r.get("trackName") or "Unknown",
            artists=[r.get("artistName") or "Unknown"],
            preview_url=preview,
            external_url=r.get("trackViewUrl"),
            features=feats,
        )
        candidates.append(track)

    print(f"[Recommender] Task='{task}', candidates with features: {len(candidates)}")

    if not candidates:
        return {
            "task": task,
            "reference_track": None,
            "count": 0,
            "tracks": [],
        }

    # Rank by similarity
    candidates.sort(key=lambda t: _similarity_score(ref_feats, t.features), reverse=True)
    top_tracks = candidates[:limit]

    # Choose a student reference track for display
    student_tracks = get_student_tracks_for_task(task)
    ref_student = student_tracks[0] if student_tracks else None

    student_out: Optional[StudentTrackOut] = None
    if ref_student:
        student_out = StudentTrackOut(
            id=ref_student["id"],
            name=ref_student["name"],
            artist=ref_student["artist"],
            task=ref_student["task"],
            audio_url=ref_student["audio_url"],
            features=ref_feats,
        )

    return {
        "task": task,
        "reference_track": student_out,
        "count": len(top_tracks),
        "tracks": top_tracks,
    }
