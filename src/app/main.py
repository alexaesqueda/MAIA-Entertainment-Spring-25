# src/app/main.py

from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .apple_music import (
    recommend_tracks_for_vibe,
    create_library_playlist,   # can be stubbed if not implemented yet
)
from .student_tracks import list_vibes


app = FastAPI(title="Stanza – Apple Music Backend")

# --------------------------------------------------
# CORS – allow your Streamlit domain to call this API
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later to your Streamlit URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Pydantic models
# --------------------------------------------------

class RecommendIn(BaseModel):
    """
    Body for POST /recommend and /apple/recommend
    Streamlit sends: { "vibe": "focus", "limit": 10 }
    """
    vibe: str
    limit: int = 25
    storefront: str = "us"


class RecommendOutTrack(BaseModel):
    id: str
    name: Optional[str] = None
    artist_name: Optional[str] = None
    album_name: Optional[str] = None
    preview_url: Optional[str] = None
    apple_music_url: Optional[str] = None
    features: Dict[str, Any] = {}
    similarity: float = 0.0


class RecommendOut(BaseModel):
    ok: bool
    vibe: str
    count: int
    tracks: List[RecommendOutTrack]


class PlaylistIn(BaseModel):
    """
    Body for POST /playlist and /apple/playlist

    Streamlit sends:
      {
        "vibe": "focus",
        "track_ids": ["id1", "id2", ...],
        "name": "...",
        "description": "..."
      }
    """
    vibe: str
    track_ids: List[str]
    name: Optional[str] = None
    description: Optional[str] = None

    # Optional for future real Apple library playlists
    storefront: str = "us"
    user_token: Optional[str] = None  # Music-User-Token


class PlaylistOut(BaseModel):
    ok: bool
    url: Optional[str] = None
    playlist_id: Optional[str] = None


# --------------------------------------------------
# Health
# --------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "stanza-apple-music"}


# --------------------------------------------------
# Vibes catalog
# --------------------------------------------------

@app.get("/vibes")
def get_vibes():
    """
    Return the set of vibes for which we have student tracks.

    Streamlit expects:
      { "vibes": [...], "details": {...} }
    """
    vibes = list_vibes()
    return {"vibes": vibes, "details": {}}


# --------------------------------------------------
# Core recommend logic
# --------------------------------------------------

def _do_recommend(body: RecommendIn) -> RecommendOut:
    if body.limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")

    raw_tracks: List[Dict[str, Any]] = recommend_tracks_for_vibe(
        vibe=body.vibe,
        storefront=body.storefront,
        limit=body.limit,
    )

    normalized: List[RecommendOutTrack] = []
    for raw in raw_tracks:
        track_id = str(raw.get("id"))
        if not track_id:
            continue

        name = raw.get("name") or raw.get("title")
        artist_name = raw.get("artist_name") or raw.get("artist")
        album_name = raw.get("album_name")
        preview_url = raw.get("preview_url")
        apple_music_url = (
            raw.get("apple_music_url")
            or raw.get("apple_url")
            or raw.get("url")
        )
        features = raw.get("features") or {}
        similarity = float(raw.get("similarity", 0.0))

        normalized.append(
            RecommendOutTrack(
                id=track_id,
                name=name,
                artist_name=artist_name,
                album_name=album_name,
                preview_url=preview_url,
                apple_music_url=apple_music_url,
                features=features,
                similarity=similarity,
            )
        )

    return RecommendOut(
        ok=True,
        vibe=body.vibe,
        count=len(normalized),
        tracks=normalized,
    )


# ------------------ Public recommend endpoints ------------------

@app.post("/recommend", response_model=RecommendOut)
def recommend(body: RecommendIn):
    """
    Main endpoint used by Streamlit (or alias).
    """
    return _do_recommend(body)


@app.post("/apple/recommend", response_model=RecommendOut)
def apple_recommend(body: RecommendIn):
    """
    Alias so older or alternate frontends that call /apple/recommend still work.
    """
    return _do_recommend(body)


# --------------------------------------------------
# Core playlist logic
# --------------------------------------------------

def _do_playlist(body: PlaylistIn) -> PlaylistOut:
    if not body.track_ids:
        raise HTTPException(status_code=400, detail="No track_ids provided.")

    playlist_id: Optional[str] = None
    playlist_url: Optional[str] = None

    # If you implement real Apple Music library playlist creation later:
    if body.user_token:
        try:
            playlist_id = create_library_playlist(
                user_token=body.user_token,
                storefront=body.storefront,
                name=body.name or f"{body.vibe.capitalize()} mix",
                description=body.description
                or f"Auto-generated {body.vibe} playlist by Stanza",
                track_ids=body.track_ids,
            )
            # If create_library_playlist ever returns a URL directly,
            # you can assign playlist_url here.
        except Exception as e:
            print("[Playlist] Apple library playlist creation failed:", repr(e))

    return PlaylistOut(ok=True, url=playlist_url, playlist_id=playlist_id)


# ------------------ Public playlist endpoints ------------------

@app.post("/playlist", response_model=PlaylistOut)
def playlist(body: PlaylistIn):
    """
    Main endpoint that Streamlit calls.
    """
    return _do_playlist(body)


@app.post("/apple/playlist", response_model=PlaylistOut)
def apple_playlist(body: PlaylistIn):
    """
    Alias endpoint if you ever decide to call /apple/playlist from frontend.
    """
    return _do_playlist(body)
