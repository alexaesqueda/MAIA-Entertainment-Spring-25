# apple_main.py  (repo root)
#
# Thin entrypoint that exposes the Apple-Music-based API.
# It reuses your existing logic from src/app/apple_music.py and src/app/student_tracks.py

from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 👇 Import your existing Apple logic (adjust package path if needed)
from .apple import (
    recommend_tracks_for_vibe,
    create_library_playlist,
)
from src.app.student_tracks import list_vibes


# ---------- FastAPI app ----------

app = FastAPI(title="Stanza – Apple Music Backend")

# Allow Streamlit frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can tighten later to just your Streamlit domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic models ----------

class AppleRecommendIn(BaseModel):
    """
    Request body for recommending tracks for a vibe.
    """
    user_token: Optional[str] = None   # Music-User-Token (not required for catalog search)
    vibe: str
    storefront: str = "us"            # Apple storefront e.g. "us", "in"
    limit: int = 25


class AppleRecommendOutTrack(BaseModel):
    id: str
    name: Optional[str] = None
    artist_name: Optional[str] = None
    album_name: Optional[str] = None
    preview_url: Optional[str] = None
    apple_music_url: Optional[str] = None
    features: Dict[str, Any] = {}
    similarity: float = 0.0


class AppleRecommendOut(BaseModel):
    ok: bool
    vibe: str
    count: int
    tracks: List[AppleRecommendOutTrack]


class ApplePlaylistIn(BaseModel):
    user_token: str             # Music-User-Token (required for library)
    storefront: str = "us"
    vibe: str
    name: str
    description: str
    track_ids: List[str]


class ApplePlaylistOut(BaseModel):
    ok: bool
    playlist_id: Optional[str]


# ---------- Simple health ----------

@app.get("/health")
def health():
    return {"status": "ok", "service": "stanza-apple-music"}


# ---------- Vibes catalog ----------

@app.get("/vibes")
def get_vibes():
    """
    Return the set of vibes for which we have student tracks.
    """
    vibes = list_vibes()
    return {"vibes": vibes}


# ---------- Apple Music recommendations ----------

@app.post("/apple/recommend", response_model=AppleRecommendOut)
def apple_recommend(body: AppleRecommendIn):
    if body.limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")

    tracks = recommend_tracks_for_vibe(
        vibe=body.vibe,
        storefront=body.storefront,
        limit=body.limit,
    )

    out_tracks = [AppleRecommendOutTrack(**t) for t in tracks]
    return AppleRecommendOut(ok=True, vibe=body.vibe, count=len(out_tracks), tracks=out_tracks)


# ---------- Apple Music playlist creation ----------

@app.post("/apple/playlist", response_model=ApplePlaylistOut)
def apple_playlist(body: ApplePlaylistIn):
    if not body.user_token:
        raise HTTPException(status_code=400, detail="Apple Music user_token is required to create a playlist.")

    if not body.track_ids:
        raise HTTPException(status_code=400, detail="No track_ids provided.")

    playlist_id = create_library_playlist(
        user_token=body.user_token,
        storefront=body.storefront,
        name=body.name,
        description=body.description,
        track_ids=body.track_ids,
    )

    if not playlist_id:
        raise HTTPException(status_code=500, detail="Failed to create playlist in Apple Music")

    return ApplePlaylistOut(ok=True, playlist_id=playlist_id)
