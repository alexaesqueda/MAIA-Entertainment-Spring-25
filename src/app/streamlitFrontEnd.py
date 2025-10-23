"""
Streamlit Frontend — STANZA
=====================================================
--------------------------------------
**CRITICAL ENV SETUP (do this once):**
--------------------------------------
1) In your **.env** (same one your backend reads), set:
   - `SPOTIFY_REDIRECT_URI` = the public URL of THIS Streamlit app (e.g., https://your-app.streamlit.app)
     This must be whitelisted in your Spotify Developer Dashboard.
   - `APP_BASE_URL` (optional, your backend already reads it)

2) In this Streamlit app, set `BACKEND_BASE_URL` below, or via an env var BACKEND_BASE_URL.
   Example: `http://127.0.0.1:8000` or your deployed FastAPI URL.

3) Flow:
   - Streamlit calls your backend `/login` to get the **Spotify authorize URL**.
   - Spotify redirects the user back to **this Streamlit URL** with `code` and `state`.
   - Streamlit immediately calls your backend `/callback` with those params to finish login.
   - Backend returns `{ ok: True, spotify_user_id }`, which we store in session.

--------------------------------------
Run locally:
--------------------------------------
$ pip install streamlit requests python-dotenv
$ streamlit run streamlit_frontend_app.py
--------------------------------------
"""

import os
import time
import json
import requests
from urllib.parse import urlencode
import streamlit as st
from dotenv import load_dotenv

# ------------------ Config ------------------
load_dotenv(override=True)
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
PAGE_TITLE = "Vibe Music Recommender"
PAGE_ICON = "🎵"

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")

# ------------------ Minimal styling ------------------
st.markdown(
    """
    <style>
      .stButton>button { border-radius: 12px; padding: 0.6rem 1rem; font-weight: 600; }
      .pill { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; background:#f0f2f6; margin-right:6px; }
      .ok { color:#0a7f2e; }
      .err { color:#a60f2d; }
      .subtle { color:#666; }
      .card { border:1px solid #ececec; border-radius:14px; padding:14px; margin-bottom:10px; background:white; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------ Session State ------------------
if "spotify_user_id" not in st.session_state:
    st.session_state.spotify_user_id = None
if "vibes" not in st.session_state:
    st.session_state.vibes = []
if "vibe_details" not in st.session_state:
    st.session_state.vibe_details = {}
if "rec_tracks" not in st.session_state:
    st.session_state.rec_tracks = []
if "selected_uris" not in st.session_state:
    st.session_state.selected_uris = set()

# ------------------ Backend helpers ------------------

def api_get(path: str, params: dict | None = None, timeout: int = 20):
    url = f"{BACKEND_BASE_URL}{path}"
    r = requests.get(url, params=params, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {path} failed: {r.status_code} {r.text}")
    return r.json()

def api_post(path: str, payload: dict, timeout: int = 30):
    url = f"{BACKEND_BASE_URL}{path}"
    r = requests.post(url, json=payload, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {path} failed: {r.status_code} {r.text}")
    return r.json()

# ------------------ OAuth handling ------------------

def ensure_logged_in():
    """If redirected from Spotify, finish login. Otherwise show a login button."""
    # If we just got redirected from Spotify, the URL will contain code & state
    qp = st.query_params
    code = qp.get("code")
    state = qp.get("state")

    if st.session_state.spotify_user_id:
        return True

    if code and state:
        with st.spinner("Completing Spotify sign‑in..."):
            try:
                data = api_get("/callback", params={"code": code, "state": state})
                if data.get("ok") and data.get("spotify_user_id"):
                    st.session_state.spotify_user_id = data["spotify_user_id"]
                    # Clear query params for a clean URL
                    st.query_params.clear()
                    st.success("You're connected to Spotify.")
                    return True
                else:
                    st.error("Login callback returned an unexpected response.")
            except Exception as e:
                st.error(f"Spotify sign‑in failed: {e}")
        return False

    # Otherwise we must initiate login
    st.info("Connect your Spotify account to continue.")
    try:
        auth = api_get("/login")
        auth_url = auth.get("auth_url")
    except Exception as e:
        st.error(f"Unable to get login URL from backend: {e}")
        return False

    st.link_button("🔐 Log in with Spotify", auth_url, use_container_width=True)
    return False

# ------------------ Data fetchers ------------------

@st.cache_data(show_spinner=False, ttl=300)
def fetch_vibes():
    try:
        vib = api_get("/vibes")
        return vib.get("vibes", []), vib.get("details", {})
    except Exception:
        # Fallback in case backend isn't ready
        return ["mellow", "energetic", "sad", "happy", "focus", "epic"], {}

# ------------------ UI Blocks ------------------

def header():
    left, right = st.columns([0.8, 0.2])
    with left:
        st.title(PAGE_TITLE)
        st.caption("AI‑driven Spotify recommendations by vibe. Build the perfect playlist in seconds.")
    with right:
        if st.session_state.spotify_user_id:
            st.markdown(
                f"<div class='pill'>Connected</div><div class='subtle'>User ID:</div><b>{st.session_state.spotify_user_id}</b>",
                unsafe_allow_html=True,
            )


def vibe_controls():
    st.subheader("1) Choose your vibe")
    if not st.session_state.vibes:
        vibes, details = fetch_vibes()
        st.session_state.vibes = vibes
        st.session_state.vibe_details = details

    c1, c2, c3, c4 = st.columns([0.35, 0.25, 0.2, 0.2])
    with c1:
        vibe = st.selectbox("Vibe", options=st.session_state.vibes, index=0, help="Pick the overall mood.")
    with c2:
        lyrical = st.toggle("Lyrical (vocals)", value=True, help="Turn off for instrumental / non‑lyrical tracks.")
    with c3:
        limit = st.slider("Track count", 5, 50, 25, step=1)
    with c4:
        market = st.text_input("Market", value="US", help="Optional e.g. US, GB, AU; leave blank to let Spotify decide.")

    # Show tiny spec for the vibe if available
    if st.session_state.vibe_details.get(vibe):
        spec = st.session_state.vibe_details[vibe]
        st.caption(
            f"Energy: {spec.get('target_energy')}, Valence: {spec.get('target_valence')}, Tempo: {spec.get('min_tempo')}–{spec.get('max_tempo')}"
        )

    return vibe, lyrical, limit, (market or None)


def recommend_action(vibe: str, lyrical: bool, limit: int, market: str | None):
    st.subheader("2) Get recommendations")

    btn = st.button("✨ Recommend tracks", type="primary", use_container_width=True)
    if btn:
        if not st.session_state.spotify_user_id:
            st.warning("Please connect Spotify first.")
            return
        with st.spinner("Fetching recommendations..."):
            try:
                payload = {
                    "spotify_user_id": st.session_state.spotify_user_id,
                    "vibe": vibe,
                    "lyrical": lyrical,
                    "limit": limit,
                    "market": market,
                }
                data = api_post("/recommend", payload)
                st.session_state.rec_tracks = data.get("tracks", [])
                st.session_state.selected_uris = set(t.get("uri") for t in st.session_state.rec_tracks)
                st.success(f"Got {len(st.session_state.rec_tracks)} tracks.")
            except Exception as e:
                st.error(f"Recommendation failed: {e}")


def tracks_table():
    tracks = st.session_state.rec_tracks or []
    if not tracks:
        st.info("No tracks yet. Click **Recommend tracks** above.")
        return

    st.subheader("3) Review & pick tracks")

    st.caption("Uncheck any songs you don't want in the playlist. You can preview 30s samples when available.")

    # Bulk selectors
    c1, c2, c3 = st.columns([0.2, 0.2, 0.6])
    with c1:
        if st.button("Select all"):
            st.session_state.selected_uris = set(t.get("uri") for t in tracks)
    with c2:
        if st.button("Clear all"):
            st.session_state.selected_uris = set()

    # Render as cards for readability
    for t in tracks:
        uri = t.get("uri")
        name = t.get("name")
        artists = ", ".join(t.get("artists", []))
        preview = t.get("preview_url")
        link = t.get("external_url")
        f = t.get("features", {})
        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = uri in st.session_state.selected_uris
            new_val = st.checkbox("", value=checked, key=f"chk_{uri}")
            if new_val:
                st.session_state.selected_uris.add(uri)
            else:
                st.session_state.selected_uris.discard(uri)
        with col2:
            st.markdown(f"<div class='card'><b>{name}</b> — {artists}  ", unsafe_allow_html=True)
            metrics = [
                ("Energy", f.get("energy")),
                ("Valence", f.get("valence")),
                ("Danceability", f.get("danceability")),
                ("Tempo", f.get("tempo")),
                ("Instrumentalness", f.get("instrumentalness")),
            ]
            st.caption(
                "  •  ".join(
                    [f"{m}: {v:.2f}" if isinstance(v, (int, float)) else f"{m}: —" for m, v in metrics]
                )
            )
            if preview:
                st.audio(preview, format="audio/mp3")
            tiny = []
            if link:
                tiny.append(f"<a href='{link}' target='_blank'>Open in Spotify</a>")
            tiny.append(f"URI: <code>{uri}</code>")
            st.markdown(" \\| ".join(tiny), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)


def create_playlist_block(vibe: str):
    tracks = st.session_state.rec_tracks or []
    selected = [u for u in st.session_state.selected_uris]

    st.subheader("4) Create playlist")

    default_name = f"{vibe.capitalize()} • {time.strftime('%b %d, %Y')}"
    name = st.text_input("Playlist name", value=default_name)
    description = st.text_area("Description", value=f"Auto‑generated {vibe} playlist")
    colA, colB, colC = st.columns([0.25, 0.25, 0.5])
    with colA:
        public = st.toggle("Public playlist", value=False)
    with colB:
        use_all = st.toggle("Use all shown tracks", value=True)

    create = st.button("🪄 Create playlist in Spotify", type="primary", use_container_width=True)

    if create:
        if not st.session_state.spotify_user_id:
            st.warning("Please connect Spotify first.")
            return
        try:
            with st.spinner("Creating your playlist..."):
                if use_all:
                    # Use backend convenience endpoint (recommend + create in one go)
                    if not tracks:
                        st.warning("Please fetch recommendations first.")
                        return
                    payload = {
                        "spotify_user_id": st.session_state.spotify_user_id,
                        "vibe": vibe,
                        "lyrical": True,  # Not strictly needed here; keeping explicit is clearer if you wire it up
                        "limit": len(tracks),
                        "playlist_name": name,
                        "playlist_description": description,
                        "public": public,
                    }
                    res = api_post("/recommend-and-create", payload)
                    url = res.get("url")
                    st.success(f"Playlist created with {res.get('created', 0)} tracks.")
                    if url:
                        st.link_button("Open playlist", url)
                else:
                    if not selected:
                        st.warning("No tracks selected.")
                        return
                    payload = {
                        "spotify_user_id": st.session_state.spotify_user_id,
                        "name": name,
                        "description": description,
                        "public": public,
                        "track_uris": selected,
                    }
                    res = api_post("/playlist", payload)
                    url = res.get("url")
                    st.success("Playlist created from your selections.")
                    if url:
                        st.link_button("Open playlist", url)
        except Exception as e:
            st.error(f"Playlist creation failed: {e}")

# ------------------ Main App ------------------

def main():
    header()

    with st.container(border=True):
        if ensure_logged_in():
            st.markdown("<span class='ok'>✅ Spotify connected.</span>", unsafe_allow_html=True)
        else:
            st.stop()  # Show only login if not connected

    vibe, lyrical, limit, market = vibe_controls()
    recommend_action(vibe, lyrical, limit, market)
    tracks_table()
    create_playlist_block(vibe)


if __name__ == "__main__":
    main()
