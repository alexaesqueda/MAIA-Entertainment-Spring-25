from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from .spotify import auth_url, exchange_code_for_tokens, parse_state, get_me, get_or_create_user
from .db import get_db, Base, engine

router = APIRouter(prefix="", tags=["auth"])

# Make sure DB tables exist on import
Base.metadata.create_all(bind=engine)

@router.get("/login")
def login():
    return {"auth_url": auth_url()}

@router.get("/callback")
def callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    try:
        _ = parse_state(state)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid state")

    tokens = exchange_code_for_tokens(code)
    me = get_me(tokens["access_token"])
    ut = get_or_create_user(db, me["id"], tokens)
    # For simplicity, we return a success message. Frontend can store spotify_user_id
    return {"ok": True, "spotify_user_id": ut.spotify_user_id}
