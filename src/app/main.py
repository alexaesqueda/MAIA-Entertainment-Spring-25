# src/app/main.py

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.app.apple_music import recommend_tracks_for_vibe, TrackOut
from src.app.student_vibes import (
    list_vibes,
    get_student_tracks_for_vibe,
    STUDENT_TRACKS,
)


app = FastAPI(title="Vibe Music Recommender (Apple)", version="1.0.0")


class RecommendIn(BaseModel):
    vibe: str
    limit: int = 25
    country: Optional[str] = "us"


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/vibes")
def vibes():
    """
    List the vibe labels for which we have student tracks.
    """
    return {"vibes": list_vibes()}


@app.get("/student-tracks")
def student_tracks(vibe: Optional[str] = None):
    """
    Debug endpoint: see student tracks, optionally filtered by vibe.
    """
    if vibe:
        tracks = get_student_tracks_for_vibe(vibe)
    else:
        tracks = STUDENT_TRACKS
    return {"count": len(tracks), "tracks": tracks}


@app.post("/recommend")
def recommend(body: RecommendIn):
    """
    Recommend Apple Music tracks for a vibe,
    based on similarity to student musician tracks.
    """
    try:
        tracks: List[TrackOut] = recommend_tracks_for_vibe(
            vibe=body.vibe,
            limit=body.limit,
            country=body.country or "us",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print("[/recommend] Unexpected error:", repr(e))
        raise HTTPException(status_code=500, detail="Internal recommendation error")

    return {"count": len(tracks), "tracks": [t.model_dump() for t in tracks]}
