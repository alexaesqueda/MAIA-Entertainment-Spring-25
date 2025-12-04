# src/app/apple_music.py

from __future__ import annotations

import math
from typing import List, Dict, Any, Optional

import httpx
from pydantic import BaseModel

from src.app.student_vibes import (
    extract_features_from_audio_bytes,
    get_reference_features_for_vibe,
)

import jwt
import time
import os

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

TEAM_ID = os.getenv("APPLE_MUSIC_TEAM_ID")
KEY_ID = os.getenv("APPLE_MUSIC_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("APPLE_MUSIC_PRIVATE_KEY_PATH")
STORE_FRONT = os.getenv("APPLE_MUSIC_STORE_FRONT", "us")

with open(PRIVATE_KEY_PATH, "r") as f:
    PRIVATE_KEY = f.read()

def get_developer_token() -> str:
    headers = {
        "alg": "ES256",
        "kid": KEY_ID,
    }
    payload = {
        "iss": TEAM_ID,
        "iat": int(time.time()),
        "exp": int(time.time()) + 60 * 60 * 12,  # 12 hours
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="ES256", headers=headers)

def apple_music_search(query: str, limit: int = 25):
    token = get_developer_token()
    url = f"https://api.music.apple.com/v1/catalog/{STORE_FRONT}/search"
    params = {"term": query, "limit": limit, "types": "songs"}
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=15.0) as client:
        r = client.get(url, params=params, headers=headers)
        r.raise_for_status()
        return r.json()


class TrackOut(BaseModel):
    id: str
    name: str
    artists: List[str]
    preview_url: Optional[str]
    external_url: Optional[str]
    features: Dict[str, Any]


def search_apple_candidates_for_vibe(
    vibe: str,
    country: str = "us",
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Use iTunes Search API to pull a rough candidate set of songs for this vibe.
    We'll refine later based on audio similarity.
    """
    params = {
        "term": vibe,
        "media": "music",
        "entity": "song",
        "country": country,
        "limit": limit,
    }
    with httpx.Client(timeout=20.0) as client:
        r = client.get(ITUNES_SEARCH_URL, params=params)
        r.raise_for_status()
        data = r.json()
        return data.get("results", [])


def recommend_tracks_for_vibe(
    vibe: str,
    limit: int = 25,
    country: str = "us",
) -> List[TrackOut]:
    """
    Main recommendation function:
      1) Get reference features from student tracks for this vibe.
      2) Search Apple Music/iTunes for candidates.
      3) For each candidate with a previewUrl, download audio and compute features.
      4) Rank candidates by distance to reference features.
    """
    ref = get_reference_features_for_vibe(vibe)
    if not ref:
        raise ValueError(f"No reference features available for vibe '{vibe}'")

    candidates = search_apple_candidates_for_vibe(vibe, country=country, limit=80)

    scored: List[tuple[float, TrackOut]] = []

    keys = list(ref.keys())

    def distance(feat: Dict[str, float]) -> float:
        # Euclidean distance in feature space
        s = 0.0
        for k in keys:
            s += (float(feat.get(k, 0.0)) - float(ref.get(k, 0.0))) ** 2
        return math.sqrt(s)

    with httpx.Client(timeout=30.0) as client:
        for item in candidates:
            preview_url = item.get("previewUrl")
            if not preview_url:
                continue

            try:
                audio_resp = client.get(preview_url)
                audio_resp.raise_for_status()
                feats = extract_features_from_audio_bytes(audio_resp.content)
            except Exception as e:
                print(f"[AppleReco] Failed preview for track {item.get('trackId')}: {e}")
                continue

            d = distance(feats)
            t = TrackOut(
                id=str(item.get("trackId")),
                name=item.get("trackName", "Unknown title"),
                artists=[item.get("artistName", "Unknown artist")],
                preview_url=preview_url,
                external_url=item.get("trackViewUrl"),
                features=feats,
            )
            scored.append((d, t))

    # Sort by ascending distance (closest = most similar)
    scored.sort(key=lambda x: x[0])

    # Return top N
    top_tracks = [t for _, t in scored[:limit]]
    print(f"[AppleReco] Returning {len(top_tracks)} tracks for vibe '{vibe}'")
    return top_tracks
