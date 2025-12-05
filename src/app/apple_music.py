import os
import time
import jwt  # PyJWT
import httpx
from typing import Dict, Any, List, Optional
import base64

APPLE_MUSIC_KEY_ID = os.getenv("APPLE_MUSIC_KEY_ID")       # from Apple dev portal
APPLE_MUSIC_TEAM_ID = os.getenv("APPLE_MUSIC_TEAM_ID")     # from Apple dev portal
APPLE_MUSIC_PRIVATE_KEY = os.getenv("APPLE_MUSIC_PRIVATE_KEY")  # PEM string or path
APPLE_MUSIC_STORE_FRONT = os.getenv("APPLE_MUSIC_STORE_FRONT", "us")

APPLE_MUSIC_API = "https://api.music.apple.com/v1"


# --- Change in apple_music.py ---

def _load_private_key() -> str:
    # 1. Try to load the Base64 encoded key first
    pk_b64 = os.getenv("APPLE_MUSIC_PRIVATE_KEY_B64") 
    
    if pk_b64:
        # Decode the Base64 string back into the original PEM format
        try:
            # The decode() step restores the correct newlines internally
            decoded_key = base64.b64decode(pk_b64).decode('utf-8')
            print("[AppleMusic] Successfully loaded key from Base64 variable.")
            return decoded_key
        except Exception as e:
            print(f"[AppleMusic] ERROR decoding Base64 key: {e}")
            pass # Fall through to the old method as a backup

    # 2. Fallback to the original (and failing) escaped string method
    #    You can remove this block if you are confident in the B64 fix.
    pk_escaped = os.getenv("APPLE_MUSIC_PRIVATE_KEY")
    if pk_escaped:
        pk_escaped = pk_escaped.strip().replace('\\n', '\n')
        if "BEGIN PRIVATE KEY" in pk_escaped:
            print("[AppleMusic] Falling back to escaped key method.")
            return pk_escaped

    raise RuntimeError("APPLE_MUSIC_PRIVATE_KEY_B64 or APPLE_MUSIC_PRIVATE_KEY is not set correctly.")


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
