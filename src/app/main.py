# src/app/main.py

from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from .apple_music import (
    recommend_tracks_for_vibe,
    create_library_playlist,
)
from .student_tracks import list_vibes

app = FastAPI(title="Stanza – Apple Music Backend")

# CORS – allow your Streamlit domain to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Pydantic models ----------

class AppleRecommendIn(BaseModel):
    user_token: Optional[str] = None   # Music-User-Token, not strictly required for catalog search
    vibe: str
    storefront: str = "us"
    limit: int = 25


class AppleRecommendOutTrack(BaseModel):
    id: str
    name: Optional[str]
    artist_name: Optional[str]
    album_name: Optional[str]
    preview_url: Optional[str]
    apple_music_url: Optional[str]
    features: Dict[str, Any]
    similarity: float


class AppleRecommendOut(BaseModel):
    ok: bool
    vibe: str
    count: int
    tracks: List[AppleRecommendOutTrack]


class ApplePlaylistIn(BaseModel):
    user_token: str
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

@app.get("/__whoami")
def whoami():
    return {
        "title": app.title,
        "routes": [r.path for r in app.routes],
    }
