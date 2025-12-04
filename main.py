# src/app/main.py

from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .apple_music import (
    recommend_tracks_for_vibe,
    create_library_playlist,
)
from .student_tracks import list_vibes


app = FastAPI(title="Stanza – Apple Music Backend")

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can tighten this later to your Streamlit URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic models ----------

class AppleRecommendIn(BaseModel):
    """
    Request body for recommending tracks for a vibe.
    """
    user_token: Optional[str] = None   # reserved if you ever need it; not used for catalog search
    vibe: str
    storefront: str = "us"            # Apple storefront e.g. "us", "in"
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
    # NOTE: required only if you actually call Apple’s library APIs.
    # If you’re just returning a URL template, you may not need this yet.
    user_token: Optional[str] = None
    storefront: str = "us"
    vibe: str
    name: str
    description: str
    track_ids: List[str]


class ApplePlaylistOut(BaseModel):
    ok: bool
    playlist_id: Optional[str] = None
    url: Optional[str] = None


# ---------- Health ----------

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
    # you can extend this later with per-vibe details if you want
    return {"vibes": vibes, "details": {}}


# ---------- Apple Music recommendations ----------
# IMPORTANT: expose BOTH /recommend and /apple/recommend
# so your Streamlit can call either path without 404.

@app.post("/apple/recommend", response_model=AppleRecommendOut)
@app.post("/recommend", response_model=AppleRecommendOut)
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
# Same trick: BOTH /playlist and /apple/playlist exist.

@app.post("/apple/playlist", response_model=ApplePlaylistOut)
@app.post("/playlist", response_model=ApplePlaylistOut)
def apple_playlist(body: ApplePlaylistIn):
    if not body.track_ids:
        raise HTTPException(status_code=400, detail="No track_ids provided.")

    # If you’re not yet calling real Apple Music library APIs,
    # you can just build a shareable URL from track_ids.
    playlist_id, url = create_library_playlist(
        user_token=body.user_token,
        storefront=body.storefront,
        name=body.name,
        description=body.description,
        track_ids=body.track_ids,
    )

    if not playlist_id and not url:
        raise HTTPException(status_code=500, detail="Failed to create playlist in Apple Music")

    return ApplePlaylistOut(ok=True, playlist_id=playlist_id, url=url)
