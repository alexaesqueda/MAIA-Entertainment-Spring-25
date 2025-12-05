# src/app/apple_music.py

import os
import time
import math
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
import httpx

from .audio_features import extract_features_from_url
from .student_tracks import get_reference_features_for_vibe
from .apple_music import generate_developer_token

# Load env variables
load_dotenv(override=True)

APPLE_DEVELOPER_TOKEN = os.getenv("APPLE_DEVELOPER_TOKEN")

# If not in Env, generate it automatically!
if not APPLE_DEVELOPER_TOKEN:
    print("[AppleMusic] Token not in Env. Attempting to generate...")
    try:
        # This function handles the private key loading internally
        APPLE_DEVELOPER_TOKEN = generate_developer_token()
        print(f"[AppleMusic] ✅ Successfully generated developer token.")
    except Exception as e:
        print(f"[AppleMusic] ❌ Generation failed: {e}")

APPLE_MUSIC_BASE_URL = "https://api.music.apple.com"

if not APPLE_DEVELOPER_TOKEN:
    print("[AppleMusic] WARNING: APPLE_DEVELOPER_TOKEN not set. Apple APIs will fail.")


def apple_auth_headers(user_token: Optional[str] = None) -> Dict[str, str]:
    """
    Build headers for Apple Music API calls.
    Developer token is required. User token is optional (needed for library actions).
    """
    headers = {
        "Authorization": f"Bearer {APPLE_DEVELOPER_TOKEN}",
        "Accept": "application/json",
    }
    if user_token:
        headers["Music-User-Token"] = user_token
    return headers


def search_tracks_for_vibe(
    vibe: str,
    storefront: str,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    """
    Search Apple Music catalog for tracks roughly matching a vibe using keywords.
    This does NOT yet use audio features; it just returns catalog metadata.
    """
    # Simple keyword mapping; you can tune these later
    vibe_query_map = {
        "focus": "focus study instrumental",
        "creative": "creative thinking ambient",
        "mellow": "chill mellow lo-fi",
        "energetic": "high energy workout",
        "happy": "happy upbeat pop",
        "sad": "sad emotional piano",
        "epic": "epic cinematic orchestral",
    }
    query = vibe_query_map.get(vibe.lower(), vibe)

    params = {
        "term": query,
        "types": "songs",
        "limit": min(max(limit, 1), 50),
    }

    url = f"{APPLE_MUSIC_BASE_URL}/v1/catalog/{storefront}/search"
    print(f"[AppleMusic] Searching Apple Music for vibe='{vibe}', query='{query}' storefront='{storefront}'")

    with httpx.Client(timeout=20.0) as client:
        r = client.get(url, params=params, headers=apple_auth_headers())
        r.raise_for_status()
        data = r.json()

    songs = data.get("results", {}).get("songs", {}).get("data", [])
    print(f"[AppleMusic] Search returned {len(songs)} raw songs.")
    return songs


def extract_preview_features_for_track(track: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Given an Apple Music song object, find a preview URL, download it,
    and run it through the librosa feature extractor.
    """
    attrs = track.get("attributes", {})
    previews = attrs.get("previews") or []
    if not previews:
        return None

    # Usually the first preview is enough
    preview_url = previews[0].get("url")
    if not preview_url:
        return None

    feats = extract_features_from_url(preview_url)
    if not feats:
        return None

    # Attach preview URL into the feature dict so caller can reuse it
    feats["preview_url"] = preview_url
    return feats


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """
    Compute cosine similarity between two feature dicts with numeric values.
    Keys are assumed to overlap (we'll use the set of keys in vec_a).
    """
    keys = [k for k in vec_a.keys() if k in vec_b]
    if not keys:
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for k in keys:
        a = float(vec_a[k])
        b = float(vec_b[k])
        dot += a * b
        norm_a += a * a
        norm_b += b * b

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / math.sqrt(norm_a * norm_b)


def recommend_tracks_for_vibe(
    vibe: str,
    storefront: str,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """
    Core Apple Music recommendation logic:

    1. Get the reference feature vector for this vibe from student tracks.
    2. Search Apple Music for candidate tracks.
    3. For each track, try to extract audio features from its preview.
    4. Rank tracks by cosine similarity to the vibe reference.
    5. Return top-N with preview URLs + similarity scores.
    """
    ref_features = get_reference_features_for_vibe(vibe)
    if not ref_features:
        print(f"[AppleMusic] No reference features for vibe '{vibe}'")
        return []

    raw_candidates = search_tracks_for_vibe(vibe, storefront=storefront, limit=50)

    scored_tracks: List[Dict[str, Any]] = []
    for track in raw_candidates:
        feats = extract_preview_features_for_track(track)
        if not feats:
            continue

        # Remove preview_url from the feature vector used for similarity
        feature_vector = {
            k: float(v)
            for k, v in feats.items()
            if k in ref_features and isinstance(v, (int, float))
        }

        score = cosine_similarity(ref_features, feature_vector)
        attrs = track.get("attributes", {})

        scored_tracks.append(
            {
                "id": track.get("id"),
                "name": attrs.get("name"),
                "artist_name": attrs.get("artistName"),
                "album_name": attrs.get("albumName"),
                "preview_url": feats.get("preview_url"),
                "apple_music_url": attrs.get("url"),
                "features": feature_vector,
                "similarity": score,
            }
        )

    # Sort by similarity descending
    scored_tracks.sort(key=lambda t: t["similarity"], reverse=True)
    print(f"[AppleMusic] Returning {min(len(scored_tracks), limit)} tracks for vibe '{vibe}'.")

    return scored_tracks[:limit]


def create_library_playlist(
    user_token: str,
    storefront: str,
    name: str,
    description: str,
    track_ids: List[str],
) -> Optional[str]:
    """
    Given an authenticated Apple Music user (via Music-User-Token),
    create a library playlist and add the given Apple Music track IDs.
    Returns the playlist URL if successful.
    """
    if not track_ids:
        return None

    # 1) Create playlist
    url = f"{APPLE_MUSIC_BASE_URL}/v1/me/library/playlists"
    payload = {
        "attributes": {
            "name": name,
            "description": description,
        }
    }

    with httpx.Client(timeout=20.0) as client:
        r = client.post(url, json=payload, headers=apple_auth_headers(user_token))
        r.raise_for_status()
        playlist_data = r.json()

    playlist_id = playlist_data.get("data", [{}])[0].get("id")
    if not playlist_id:
        return None

    # 2) Add tracks to playlist
    relationships_url = f"{APPLE_MUSIC_BASE_URL}/v1/me/library/playlists/{playlist_id}/tracks"
    track_payload = {
        "data": [{"id": tid, "type": "songs"} for tid in track_ids]
    }

    with httpx.Client(timeout=20.0) as client:
        r = client.post(relationships_url, json=track_payload, headers=apple_auth_headers(user_token))
        r.raise_for_status()

    # A simple web URL to open the playlist in Apple Music is not always directly returned.
    # We can at least give the user the library playlist id.
    return playlist_id
