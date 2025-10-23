# src/app/main.py

from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import get_db, Base, engine
from .models import UserToken
from .auth import router as auth_router
from .spotify import (
    ensure_valid_token,
    get_me,
    recommend_tracks,
    create_playlist,
    add_tracks_to_playlist,
)
from .vibes import VIBE_FEATURES

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vibe Music Recommender", version="1.0.0")
app.include_router(auth_router)

# -------------------- DEBUG ROUTES --------------------
@app.get("/debug/ping")
def debug_ping():
    return {"ok": True}

@app.get("/debug/user/{sid}")
def debug_user(sid: str, db: Session = Depends(get_db)):
    ut = db.execute(select(UserToken).where(UserToken.spotify_user_id == sid)).scalars().first()
    if not ut:
        return {"found": False}
    return {
        "found": True,
        "expires_at": ut.token_expires_at,
        "scope": ut.token_scope,
        "has_refresh": bool(ut.refresh_token),
    }
# ------------------ END DEBUG ROUTES ------------------

class RecommendIn(BaseModel):
    spotify_user_id: str = Field(..., description="Spotify user id returned from /callback")
    vibe: str
    lyrical: bool = True
    limit: int = 30
    market: Optional[str] = None  # e.g., "US"

class PlaylistIn(BaseModel):
    spotify_user_id: str
    name: str
    description: str = ""
    public: bool = False
    track_uris: List[str]

class RecommendAndCreateIn(BaseModel):
    spotify_user_id: str
    vibe: str
    lyrical: bool = True
    limit: int = 30
    market: Optional[str] = None
    playlist_name: str
    playlist_description: str = ""
    public: bool = False

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/vibes")
def vibes():
    return {"vibes": list(VIBE_FEATURES.keys()), "details": VIBE_FEATURES}

def get_user_token(db: Session, spotify_user_id: str) -> UserToken:
    ut = db.execute(select(UserToken).where(UserToken.spotify_user_id == spotify_user_id)).scalars().first()
    if not ut:
        raise HTTPException(status_code=404, detail="User not authorized. Call /login then /callback first.")
    return ut

@app.post("/recommend")
def recommend(body: RecommendIn, db: Session = Depends(get_db)):
    ut = get_user_token(db, body.spotify_user_id)
    ut = ensure_valid_token(db, ut)
    tracks = recommend_tracks(
        access_token=ut.access_token,
        vibe=body.vibe,
        lyrical=body.lyrical,
        limit=body.limit,
        market=body.market
    )
    return {"count": len(tracks), "tracks": [t.model_dump() for t in tracks]}

@app.post("/playlist")
def playlist(body: PlaylistIn, db: Session = Depends(get_db)):
    ut = get_user_token(db, body.spotify_user_id)
    ut = ensure_valid_token(db, ut)
    me = get_me(ut.access_token)
    pid = create_playlist(ut.access_token, me["id"], body.name, body.description, body.public)
    add_tracks_to_playlist(ut.access_token, pid, body.track_uris)
    return {"ok": True, "playlist_id": pid, "url": f"https://open.spotify.com/playlist/{pid}"}

@app.post("/recommend-and-create")
def recommend_and_create(body: RecommendAndCreateIn, db: Session = Depends(get_db)):
    ut = get_user_token(db, body.spotify_user_id)
    ut = ensure_valid_token(db, ut)
    tracks = recommend_tracks(
        access_token=ut.access_token,
        vibe=body.vibe,
        lyrical=body.lyrical,
        limit=body.limit,
        market=body.market
    )
    me = get_me(ut.access_token)
    pid = create_playlist(ut.access_token, me["id"], body.playlist_name, body.playlist_description, body.public)
    add_tracks_to_playlist(ut.access_token, pid, [t.uri for t in tracks])
    return {
        "ok": True,
        "created": len(tracks),
        "playlist_id": pid,
        "url": f"https://open.spotify.com/playlist/{pid}",
        "tracks": [t.model_dump() for t in tracks],
    }
