# src/app/main.py
import os
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Apple logic lives here:
from .apple import recommend_tracks_for_vibe, create_library_playlist
from .student_tracks import list_vibes  # your existing student_vibes/student_tracks helper
from src.app.apple_music import generate_developer_token
from fastapi.responses import HTMLResponse
from src.app.apple_music import generate_developer_token

# ---------- Create app ----------

app = FastAPI(title="Stanza – Apple Music Backend")

# CORS – allow your Streamlit domain to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Simple root + health ----------

@app.get("/")
def root():
    return {"message": "Backend is live!", "service": "stanza-apple-music"}


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

@app.get("/apple/token")
def get_apple_token():
    """Returns a fresh developer token for the frontend to use."""
    token = generate_developer_token()
    return {"token": token}

@app.get("/apple/auth", response_class=HTMLResponse)
def apple_auth_page():
    """
    Serves a dedicated login page to bypass iframe security restrictions.
    """
    dev_token = generate_developer_token()
    
    # ⚠️ REPLACE THIS with your exact Streamlit URL (must match Apple Developer Portal)
    RETURN_URL = "https://maia-entertainment-spring-25-mjyvcu5rn85he4zotwjzdh.streamlit.app/"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login to Stanza</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://js-cdn.music.apple.com/musickit/v1/musickit.js"></script>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(179deg, #0f1015 10%, #5568d3, #6a3f8f 100%);
                color: white; display: flex; flex-direction: column;
                align-items: center; justify-content: center; height: 100vh; margin: 0;
            }}
            button {{
                background-color: #FA2D48; color: white; border: none;
                padding: 15px 30px; border-radius: 12px; font-size: 18px; font-weight: 600;
                cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                transition: transform 0.2s;
            }}
            button:hover {{ transform: scale(1.05); }}
            .card {{
                background: rgba(255,255,255,0.1); padding: 40px; border-radius: 20px;
                text-align: center; backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.2);
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🎵 Stanza Login</h1>
            <p>Please authorize Apple Music to continue.</p>
            <br>
            <button id="login-btn">Login with Apple Music</button>
            <p id="status" style="margin-top:20px; font-size:14px; opacity:0.8;"></p>
        </div>

        <script>
            // 1. Initialize MusicKit
            document.addEventListener('musickitloaded', function() {{
                try {{
                    MusicKit.configure({{
                        developerToken: '{dev_token}',
                        app: {{ name: 'Stanza', build: '1.0.0' }}
                    }});
                }} catch (err) {{
                    document.getElementById('status').innerText = "Config Error: " + err;
                }}
            }});

            // 2. Handle Login Click
            document.getElementById('login-btn').addEventListener('click', async function() {{
                const music = MusicKit.getInstance();
                try {{
                    // Authorize (Opens Popup)
                    const token = await music.authorize();
                    
                    // Success! Redirect back to Streamlit
                    document.getElementById('status').innerText = "✅ Success! Redirecting...";
                    window.location.href = "{RETURN_URL}?token=" + encodeURIComponent(token);
                    
                }} catch (err) {{
                    document.getElementById('status').innerText = "❌ Error: " + err;
                }}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
# ---------- Pydantic models for Apple endpoints ----------

class AppleRecommendIn(BaseModel):
    """
    Request body for recommending tracks for a vibe.
    """
    user_token: Optional[str] = None   # optional; not needed for catalog search
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
    user_token: str             # Music-User-Token (required for library)
    storefront: str = "us"
    vibe: str
    name: str
    description: str
    track_ids: List[str]


class ApplePlaylistOut(BaseModel):
    ok: bool
    playlist_id: Optional[str]


# ---------- Apple Music recommendations ----------

@app.post("/apple/recommend", response_model=AppleRecommendOut)
def apple_recommend(body: AppleRecommendIn):
    if body.limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")

    # This calls your Apple-side logic in apple.py
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
