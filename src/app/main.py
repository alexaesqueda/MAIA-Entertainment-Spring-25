# src/app/main.py

from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .student_tracks import list_tasks
from .apple import recommend_from_task, TrackOut, StudentTrackOut


app = FastAPI(
    title="Task-Based Music Recommender (Student + Apple)",
    version="1.0.0",
)


@app.get("/")
def home():
    return {"message": "Backend is live (Student + Apple Music style)!"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/tasks")
def tasks():
    """
    List all task labels that we have at least one student track for.
    """
    return {"tasks": list_tasks()}


class RecommendIn(BaseModel):
    task: str = Field(..., description="Task label, e.g. productivity, creative, relax")
    limit: int = Field(25, ge=1, le=100)
    market: Optional[str] = Field("US", description="Country code for Apple iTunes, e.g. US, GB, IN")


class RecommendOut(BaseModel):
    task: str
    reference_track: Optional[StudentTrackOut]
    count: int
    tracks: List[TrackOut]


@app.post("/recommend", response_model=RecommendOut)
def recommend(body: RecommendIn):
    """
    Recommend a student musician reference track + similar Apple tracks for the task.
    """
    try:
        result = recommend_from_task(
            task=body.task,
            limit=body.limit,
            market=body.market,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result
