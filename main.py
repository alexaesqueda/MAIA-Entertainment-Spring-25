# src/app/main.py  (only the top part changed to include a print)

from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.app.db import get_db, Base, engine
from src.app.models import UserToken
from src.app.auth import router as auth_router

# IMPORTANT: import the module itself so we can print its file path
from src.app import spotify as spotify_module
from src.app.spotify import (
    ensure_valid_token,
    get_me,
    recommend_tracks,
    create_playlist,
    add_tracks_to_playlist,
)
from src.app.vibes import VIBE_FEATURES

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vibe Music Recommender", version="1.0.0")
@app.get("/")
def home():
    return {"message": "Backend is live!"}
app.include_router(auth_router)

# PROVE WHICH FILES ARE RUNNING
print(">>> LOADED main.py FROM:", __file__)
print(">>> LOADED spotify.py FROM:", spotify_module.__file__)

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
    try:
        print("Received body:", body)
        ut = get_user_token(db, body.spotify_user_id)
        print("User token:", ut)
        ut = ensure_valid_token(db, ut)
        print("Validated token:", ut)

        genre_map = {
            "mellow": "soul",
            "energetic": "party",
            "sad": "sad",
            "happy": "pop",
            "focus": "ambient",
            "epic": "soundtracks"
        }
        seed_genre = genre_map.get(body.vibe.lower(), "pop")
        
        tracks = recommend_tracks(
            access_token=ut.access_token,
            vibe=body.vibe,
            lyrical=body.lyrical,
            limit=body.limit,
            market=body.market,
            seed_genres=seed_genre
        )
        print("Tracks generated:", tracks)
        return {"count": len(tracks), "tracks": [t.model_dump() for t in tracks]}
    except Exception as e:
        print("ERROR in /recommend:", e)
        raise HTTPException(status_code=500, detail=str(e))

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
