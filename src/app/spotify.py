# src/app/spotify.py  — guaranteed seed-free, with debug prints

import os, time, base64
from pathlib import Path
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed
from itsdangerous import URLSafeSerializer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .models import UserToken
from .vibes import VIBE_FEATURES, instrumental_filter_threshold, VIBE_SEED_GENRES
# from functools import lru_cache

# ---- Load .env BEFORE reading any env vars ----
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH, override=True)

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API = "https://api.spotify.com/v1"

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret")
BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

SERIALIZER = URLSafeSerializer(APP_SECRET_KEY, salt="state-salt")

SCOPES = [
    "playlist-modify-private",
    "playlist-modify-public",
    "user-read-email",
    "user-read-private",
]
SCOPE_STR = " ".join(SCOPES)

# prove which spotify.py is loaded
print(">>> USING spotify.py FROM:", __file__)

class TrackOut(BaseModel):
    id: str
    uri: str
    name: str
    artists: List[str]
    preview_url: Optional[str] = None
    external_url: Optional[str] = None
    features: Dict[str, Any]


def encode_basic_auth(client_id: str, client_secret: str) -> str:
    token = f"{client_id}:{client_secret}".encode("utf-8")
    return base64.b64encode(token).decode("utf-8")


def auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

def build_state(payload: Dict[str, Any]) -> str:
    return SERIALIZER.dumps(payload)


def parse_state(state: str) -> Dict[str, Any]:
    return SERIALIZER.loads(state)


def auth_url() -> str:
    import urllib.parse as up
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE_STR,
        "state": build_state({"t": int(time.time())}),
        "show_dialog": "false",
    }
    return "https://accounts.spotify.com/authorize?" + up.urlencode(params)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    headers = {"Authorization": "Basic " + encode_basic_auth(CLIENT_ID, CLIENT_SECRET)}
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    with httpx.Client(timeout=15.0) as client:
        r = client.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
        r.raise_for_status()
        return r.json()


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    headers = {"Authorization": "Basic " + encode_basic_auth(CLIENT_ID, CLIENT_SECRET)}
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    with httpx.Client(timeout=15.0) as client:
        r = client.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
        r.raise_for_status()
        return r.json()


def ensure_valid_token(db: Session, user: UserToken) -> UserToken:
    if time.time() < user.token_expires_at - 30:
        return user
    refreshed = refresh_access_token(user.refresh_token)
    user.access_token = refreshed["access_token"]
    user.token_expires_at = int(time.time()) + int(refreshed.get("expires_in", 3600))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_me(access_token: str) -> Dict[str, Any]:
    with httpx.Client(timeout=15.0) as client:
        r = client.get(f"{SPOTIFY_API}/me", headers=auth_header(access_token))
        r.raise_for_status()
        return r.json()


def get_audio_features(access_token: str, track_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not track_ids:
        return {}
    features_map: Dict[str, Dict[str, Any]] = {}
    with httpx.Client(timeout=20.0) as client:
        for i in range(0, len(track_ids), 100):
            ids = ",".join(track_ids[i : i + 100])
            r = client.get(f"{SPOTIFY_API}/audio-features", params={"ids": ids}, headers=auth_header(access_token))
            r.raise_for_status()
            for item in r.json().get("audio_features", []):
                if item and item.get("id"):
                    features_map[item["id"]] = item
    return features_map


def recommend_tracks(
    access_token: str,
    vibe: str,
    lyrical: bool,
    limit: int = 30,
    market: Optional[str] = None,
) -> List[TrackOut]:
    vibe = vibe.lower()

    # --- DEBUG: confirm token presence ---
    print("DEBUG token present:", bool(access_token),
          "len:", len(access_token) if access_token else 0)
    if not access_token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Spotify access token missing. Please reconnect.")
    # -------------------------------------

    if vibe not in VIBE_FEATURES:
        raise ValueError(f"Unsupported vibe '{vibe}'. Supported: {list(VIBE_FEATURES.keys())}")

    lo, hi = instrumental_filter_threshold(lyrical)

    # --- Build params WITHOUT seeds (seedless mode) ---
    vf = VIBE_FEATURES[vibe]
    avg_tempo = (vf["min_tempo"] + vf["max_tempo"]) / 2.0
    seed_list = VIBE_SEED_GENRES.get(vibe, ["pop"])
    seed_str = ",".join(seed_list[:5])
    params: Dict[str, Any] = {
        "limit": min(max(limit, 1), 100),
        "seed_genres": seed_str,  # required seed so Spotify accepts the request
        "target_energy": vf["target_energy"],
        "target_valence": vf["target_valence"],
        "target_acousticness": vf["target_acousticness"],
        "target_tempo": avg_tempo,
        "target_danceability": vf["target_danceability"],
        "target_instrumentalness": (lo + hi) / 2.0,
    }
    if market:
        params["market"] = market

    print(">>> RECO PARAMS (no min/max energy/valence):", params)

    with httpx.Client(timeout=20.0) as client:
        headers = auth_header(access_token)
        print("DEBUG sending headers:",
              {"Authorization": f"Bearer ...{access_token[-6:]}" if access_token else None})
        try:
            r = client.get(f"{SPOTIFY_API}/recommendations", params=params, headers=headers)
            r.raise_for_status()
            items = r.json().get("tracks", [])
        except httpx.HTTPStatusError as e:
            print("Recommendations failed:",
                  e.response.status_code if e.response else "?",
                  e.response.text if e.response else "")
            raise

    track_ids = [t["id"] for t in items if t.get("id")]
    features_map = get_audio_features(access_token, track_ids)
    # ------------------------------------

    track_ids = [t["id"] for t in items if t.get("id")]
    features_map = get_audio_features(access_token, track_ids)

    def score(feat: Dict[str, Any]) -> float:
        if not feat:
            return 0.0
        vf = VIBE_FEATURES[vibe]
        weights = {"energy": 2.0, "valence": 1.8, "acousticness": 1.2, "danceability": 1.4, "instrumentalness": 1.5, "tempo": 0.8}
        dist = 0.0
        dist += weights["energy"] * (feat.get("energy", 0) - vf["target_energy"]) ** 2
        dist += weights["valence"] * (feat.get("valence", 0) - vf["target_valence"]) ** 2
        dist += weights["acousticness"] * (feat.get("acousticness", 0) - vf["target_acousticness"]) ** 2
        dist += weights["danceability"] * (feat.get("danceability", 0) - vf["target_danceability"]) ** 2
        dist += weights["instrumentalness"] * (feat.get("instrumentalness", 0) - ((lo + hi) / 2.0)) ** 2
        tempo = feat.get("tempo", 120)
        if tempo < vf["min_tempo"]:
            dist += weights["tempo"] * ((vf["min_tempo"] - tempo) / 100.0) ** 2
        elif tempo > vf["max_tempo"]:
            dist += weights["tempo"] * ((tempo - vf["max_tempo"]) / 100.0) ** 2
        return -dist

    results: List[TrackOut] = []
    for t in items:
        fid = t["id"]
        f = features_map.get(fid)
        if not f:
            continue
        instr = f.get("instrumentalness", 0.0)
        if lyrical and instr > 0.6:
            continue
        if (not lyrical) and instr < 0.7:
            continue
        results.append(
            TrackOut(
                id=fid,
                uri=t["uri"],
                name=t["name"],
                artists=[a["name"] for a in t.get("artists", [])],
                preview_url=t.get("preview_url"),
                external_url=(t.get("external_urls", {}) or {}).get("spotify"),
                features=f,
            )
        )

    results.sort(key=lambda x: score(x.features), reverse=True)
    return results[:limit]


def create_playlist(access_token: str, user_id: str, name: str, description: str, public: bool) -> str:
    payload = {"name": name, "description": description, "public": public}
    with httpx.Client(timeout=15.0) as client:
        r = client.post(f"{SPOTIFY_API}/users/{user_id}/playlists", json=payload, headers=auth_header(access_token))
        r.raise_for_status()
        return r.json()["id"]


def add_tracks_to_playlist(access_token: str, playlist_id: str, uris: List[str]):
    if not uris:
        return
    with httpx.Client(timeout=15.0) as client:
        r = client.post(f"{SPOTIFY_API}/playlists/{playlist_id}/tracks", json={"uris": uris}, headers=auth_header(access_token))
        r.raise_for_status()


def get_or_create_user(db: Session, spotify_user_id: str, tokens: Dict[str, Any]) -> UserToken:
    from sqlalchemy import select

    stmt = select(UserToken).where(UserToken.spotify_user_id == spotify_user_id)
    existing = db.execute(stmt).scalars().first()
    expires_at = int(time.time()) + int(tokens["expires_in"])
    if existing:
        existing.access_token = tokens["access_token"]
        existing.token_expires_at = expires_at
        if "refresh_token" in tokens and tokens["refresh_token"]:
            existing.refresh_token = tokens["refresh_token"]
        existing.token_scope = tokens.get("scope", "")
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    ut = UserToken(
        spotify_user_id=spotify_user_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_scope=tokens.get("scope", ""),
        token_expires_at=expires_at,
    )
    db.add(ut)
    db.commit()
    db.refresh(ut)
    return ut
