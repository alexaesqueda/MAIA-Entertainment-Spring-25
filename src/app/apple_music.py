import os
import time
import jwt  # PyJWT
import httpx
from typing import Dict, Any, List, Optional

APPLE_MUSIC_KEY_ID = os.getenv("APPLE_MUSIC_KEY_ID")       # from Apple dev portal
APPLE_MUSIC_TEAM_ID = os.getenv("APPLE_MUSIC_TEAM_ID")     # from Apple dev portal
APPLE_MUSIC_PRIVATE_KEY = os.getenv("APPLE_MUSIC_PRIVATE_KEY")  # PEM string or path
APPLE_MUSIC_STORE_FRONT = os.getenv("APPLE_MUSIC_STORE_FRONT", "us")

APPLE_MUSIC_API = "https://api.music.apple.com/v1"


def _load_private_key() -> str:
    """
    Load your Apple Music private key.
    Easiest: store the full PEM as an env var APPLE_MUSIC_PRIVATE_KEY.

    Or, if you store it in a file, read that here.
    """
    pk = APPLE_MUSIC_PRIVATE_KEY
    if pk and "BEGIN PRIVATE KEY" in pk:
        return pk
    # else treat as a path (optional)
    if pk and os.path.exists(pk):
        with open(pk, "r") as f:
            return f.read()
    raise RuntimeError("APPLE_MUSIC_PRIVATE_KEY is not set correctly.")


def generate_developer_token(exp_mins: int = 30) -> str:
    """
    Create a short-lived developer token (JWT) for Apple Music API.
    """
    private_key = _load_private_key()
    now = int(time.time())
    payload = {
        "iss": APPLE_MUSIC_TEAM_ID,
        "iat": now,
        "exp": now + exp_mins * 60,
    }
    headers = {
        "alg": "ES256",
        "kid": APPLE_MUSIC_KEY_ID,
    }
    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
    # PyJWT may return bytes or str depending on version
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def apple_headers(dev_token: str, user_token: Optional[str] = None) -> Dict[str, str]:
    h = {
        "Authorization": f"Bearer {dev_token}",
        "Accept": "application/json",
    }
    if user_token:
        h["Music-User-Token"] = user_token
    return h


def search_tracks(
    dev_token: str,
    term: str,
    limit: int = 25,
    storefront: str = APPLE_MUSIC_STORE_FRONT,
) -> List[Dict[str, Any]]:
    """
    Simple catalog search for songs by term.
    This does NOT get audio features from Apple; it's just metadata.
    """
    url = f"{APPLE_MUSIC_API}/catalog/{storefront}/search"
    params = {"term": term, "types": "songs", "limit": limit}
    with httpx.Client(timeout=15.0) as client:
        r = client.get(url, params=params, headers=apple_headers(dev_token))
        r.raise_for_status()
        data = r.json()
    return data.get("results", {}).get("songs", {}).get("data", [])


def create_user_playlist(
    dev_token: str,
    user_token: str,
    name: str,
    description: str,
    track_ids: List[str],
    storefront: str = APPLE_MUSIC_STORE_FRONT,
) -> Dict[str, Any]:
    """
    Create a playlist in the user's library from a list of Apple Music track IDs.
    """
    url = f"{APPLE_MUSIC_API}/me/library/playlists"
    # Apple Music expects "library-music-videos" or "library-songs" etc.
    # For catalog songs, we wrap the catalog IDs.
    relationships = {
        "tracks": {
            "data": [
                {"id": tid, "type": "songs"} for tid in track_ids
            ]
        }
    }
    payload = {
        "attributes": {
            "name": name,
            "description": description,
        },
        "relationships": relationships,
    }

    with httpx.Client(timeout=15.0) as client:
        r = client.post(url, json={"data": [payload]}, headers=apple_headers(dev_token, user_token))
        r.raise_for_status()
        return r.json()
