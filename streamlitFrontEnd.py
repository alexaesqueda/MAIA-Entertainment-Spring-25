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
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "https://maia-entertainment-spring-25.onrender.com").rstrip("/")
# Navigate to your project folder first
# cp /Users/shrey/Downloads/stanzalogo.png /mount/src/maia-entertainment-spring-25/

# # Copy the image from Downloads to your project
# cd /mount/src/maia-entertainment-spring-25/
# git add stanzalogo.png
#PAGE_TITLE = [Alt text](stanzalogo.png)
PAGE_TITLE = "‎‎ ‎ ‎ ‎ Stanza"
PAGE_ICON = "🎵"

st.set_page_config(page_title="Stanza", page_icon=PAGE_ICON, layout="wide")

# ------------------ Complete Styling ------------------

st.markdown(
    """
    <style>
      .stApp {
        background: linear-gradient(179deg, #0f1015 10%, #5568d3, #6a3f8f 100%);
        background-attachment: fixed;
      }
      
      .main {
        background: transparent;
      }
      /* PRIMARY ACTION BUTTONS - High contrast */
      .stButton>button[kind="primary"] {
        border-radius: 16px;
        padding: 0.75rem 2rem;
        font-weight: 700;
        border: none;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        font-size: 1.1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
      }
      
      .stButton>button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
      }
      
      /* SECONDARY BUTTONS - Clear contrast */
      .stButton>button {
        border-radius: 12px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        border: 2px solid #667eea;
        background: white;
        color: #667eea !important;
        font-size: 1rem;
        transition: all 0.3s ease;
      }
      
      .stButton>button:hover {
        background: #667eea;
        color: white !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
      }
      
      /* CARD STYLES - ADDED */
      .card {
        border: 1px solid #ececec;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 10px;
        background: white;
        transition: all 0.3s ease;
      }
      
      .card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
      }
      
      /* Section headers - bolder */
      /* Only style h2 in main content, NOT in custom divs */
      .main > div > h2 {
        color: #4c51bf !important;
        font-weight: 800 !important;
        margin-top: 2rem !important;
        font-size: 1.8rem !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.05);
      }
      
      /* Force white text in welcome box */
      div[style*="background: linear-gradient(135deg, #065f46"] h2,
      div[style*="background: linear-gradient(135deg, #065f46"] p {
        color: #ffffff !important;
      }
      
      /* Body text - stronger contrast (but not in welcome box) */
      .main p:not([style*="color: white"]), 
      .stMarkdown, 
      label {
        color: #ffffff !important;
        font-size: 1rem;
      }
      
      /* Force white for welcome box content */
      div[style*="linear-gradient(135deg, #065f46"] h2,
      div[style*="linear-gradient(135deg, #065f46"] p {
        color: white !important;
        text-shadow: 0 1px 3px rgba(0,0,0,0.3);
      }
      
      /* Captions - more visible */
      .stCaption, caption, small {
        color: #8b94a6 !important;
        font-weight: 500;
      }
      
      /* Status indicators */
      .ok { 
        color: #10b981;
        font-weight: 600;
      }
      
      .err { 
        color: #5906bf;
        font-weight: 600;
      }
      
      /* Link buttons - high visibility */
      .stLinkButton>a {
        border-radius: 16px;
        padding: 0.75rem 2rem;
        font-weight: 700;
        border: none;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: white !important;
        font-size: 1.1rem;
        text-decoration: none !important;
        display: inline-block;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
      }
      
      .stLinkButton>a:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6);
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
      }
      
      /* Input labels - darker for readability */
      .stTextInput>label, .stTextArea>label, .stSelectbox>label, .stSlider>label {
        color: #dae2ed !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
      }
      
      /* Toggle labels */
      .stCheckbox>label, [data-testid="stWidgetLabel"] {
        color: #dae2ed !important;
        font-weight: 600 !important;
      }
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
    qp = st.query_params
    code = qp.get("code")
    state = qp.get("state")
    
    if st.session_state.spotify_user_id:
        return True
    
    if code and state:
        with st.spinner("🔐 Completing Spotify sign‑in..."):
            try:
                data = api_get("/callback", params={"code": code, "state": state})
                if data.get("ok") and data.get("spotify_user_id"):
                    st.session_state.spotify_user_id = data["spotify_user_id"]
                    st.query_params.clear()
                    st.success("✅ You're  to Spotify!")
                    time.sleep(1)
                    st.rerun()
                    return True
                else:
                    st.error("❌ Login callback returned an unexpected response.")
            except Exception as e:
                st.error(f"❌ Spotify sign‑in failed: {str(e)}")
                with st.expander("🔍 Debug Info"):
                    st.code(str(e))
                    st.write(f"Backend: {BACKEND_BASE_URL}")
        return False
    
    # Show login prompt
    st.markdown(
       """
      <div style='text-align:center; padding:60px 40px; margin:40px 0;'>
          <h2 style='color: white !important; margin-bottom:16px !important; font-weight:800 !important; margin-top:0 !important; font-size: 3rem !important; text-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;'>
              🎵 Welcome to Your Vibe Music Recommender!
          </h2>
          <p style='font-size:1.1rem !important; color: white !important; font-weight:500 !important; margin-bottom:32px !important; text-shadow: 0 1px 2px rgba(0,0,0,0.2) !important;'>
              Connect your Spotify account to discover AI-powered music recommendations<br>
              tailored perfectly to your mood.
          </p>
      </div>
      """,
      unsafe_allow_html=True
     )
    
    try:
        auth = api_get("/login")
        auth_url = auth.get("auth_url")
        
        # Button code moved INSIDE the try block
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
             st.markdown(
                 f"""
                 <a href="{auth_url}" target="_self" style="
                     display: block;
                     text-decoration: none;
                     text-align: center;
                     padding: 0.75rem 2rem;
                     border-radius: 32px;
                     background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                     color: white;
                     font-weight: 700;
                     font-size: 1.1rem;
                     box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
                     transition: all 0.3s ease;
                 ">
                     <img src="https://m.media-amazon.com/images/I/51rttY7a+9L.png" 
                          style="width: 23px; height: 23px; vertical-align: middle; margin-right: 8px;">
                     Sign in
                 </a>
                 """,
                 unsafe_allow_html=True
             )
            
    except Exception as e:
        st.error(f"❌ Unable to get login URL from backend: {e}")
        return False
    
    return False

# ------------------ Data fetchers ------------------

@st.cache_data(show_spinner=False, ttl=300)
def fetch_vibes():
    try:
        vib = api_get("/vibes")
        return vib.get("vibes", []), vib.get("details", {})
    except Exception:
        return ["mellow", "energetic", "sad", "happy", "focus", "epic"], {}

# ------------------ UI Blocks ------------------

def header():
    # Create columns for title and connected status
    left, right = st.columns([0.99, 0.01])
    
    with left:
        # Center the title and tagline
        st.markdown(
            f"""
            <h1 style='text-align:center; font-size:3rem; font-weight:800; margin-bottom:0.5rem;'>
                {PAGE_TITLE}
            </h1>
            <p style='font-size:1.2rem; color:#abb3c4; text-align:center; margin-top:-10px;'>
                ✨ AI‑driven Spotify recommendations by vibe. Build the perfect playlist in seconds.
            </p>
            """,
            unsafe_allow_html=True
        )
    
    with right:
        # Connected status box (top right)
        if st.session_state.spotify_user_id:
            st.markdown(
                f"""
                <div style='display:inline-block; width:fit-content; margin-left:auto; float:right;
                text-align:center; padding:10px 14px; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius:12px; color:white; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3); margin-top:20px;'>
                    <div style='font-size:0.8rem; opacity:0.9; white-space:nowrap;'>🎧 Connected</div>
                    <div style='font-weight:700; font-size:0.95rem; margin-top:2px; white-space:nowrap;'>{st.session_state.spotify_user_id}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    # Divider
    st.markdown("<div style='height:2px; background:linear-gradient(90deg, transparent, #667eea, transparent); margin:2rem 0;'></div>", unsafe_allow_html=True)





#     # Center the title and tagline
#     st.markdown(
#         f"""
#         <h1 style='text-align:center; font-size:3rem; font-weight:800; margin-bottom:0.5rem;'>
#             {PAGE_TITLE}
#         </h1>
#         <p style='font-size:1.2rem; color:#abb3c4; text-align:center; margin-top:-10px;'>
#             ✨ AI‑driven Spotify recommendations by vibe. Build the perfect playlist in seconds.
#         </p>
#         """,
#         unsafe_allow_html=True
#     )

    
    # #  status box (centered below)
    # if st.session_state.spotify_user_id:
    #     st.markdown(
    #         f"""
    #         <div style='display:block; width:fit-content; margin:20px auto;
    #         text-align:center; padding:10px 14px; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
    #         border-radius:12px; color:white; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);'>
    #             <div style='font-size:0.8rem; opacity:0.9; white-space:nowrap;'>🎧 Connected</div>
    #             <div style='font-weight:700; font-size:0.95rem; margin-top:2px; white-space:nowrap;'>{st.session_state.spotify_user_id}</div>
    #         </div>
    #         """,
    #         unsafe_allow_html=True,
    #     )
    
    # # Divider
    # st.markdown("<div style='height:2px; background:linear-gradient(90deg, transparent, #667eea, transparent); margin:2rem 0;'></div>", unsafe_allow_html=True)


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
        market = st.text_input("Market", value="US", help="Optional e.g. US, GB, AU")

    if st.session_state.vibe_details.get(vibe):
        spec = st.session_state.vibe_details[vibe]
        st.caption(
            f"Energy: {spec.get('target_energy')}, Valence: {spec.get('target_valence')}, "
            f"Tempo: {spec.get('min_tempo')}–{spec.get('max_tempo')}"
        )

    return vibe, lyrical, limit, (market or None)


def recommend_action(vibe: str, lyrical: bool, limit: int, market: str | None):
    st.subheader("2) Get recommendations")

    btn = st.button("✨ RECOMMEND TRACKS", type="primary", use_container_width=True)
    if btn:
        if not st.session_state.spotify_user_id:
            st.warning("⚠️ Please connect Spotify first.")
            return
        with st.spinner("🎵 Fetching recommendations..."):
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
                st.success(f"🎉 Got {len(st.session_state.rec_tracks)} tracks!")
            except Exception as e:
                st.error(f"❌ Recommendation failed: {e}")


def tracks_table():
    tracks = st.session_state.rec_tracks or []
    if not tracks:
        st.info("🎵 No tracks yet. Click **Recommend tracks** above.")
        return

    st.subheader("3) Review & pick tracks")
    st.caption("Uncheck any songs you don't want in the playlist. Preview 30s samples when available.")

    # Bulk selectors
    c1, c2, c3 = st.columns([0.2, 0.2, 0.6])
    with c1:
        if st.button("✅ SELECT ALL"):
            st.session_state.selected_uris = set(t.get("uri") for t in tracks)
            st.rerun()
    with c2:
        if st.button("❌ CLEAR ALL"):
            st.session_state.selected_uris = set()
            st.rerun()

    # Render cards
    for idx, t in enumerate(tracks, 1):
        uri = t.get("uri")
        name = t.get("name")
        artists = ", ".join(t.get("artists", []))
        preview = t.get("preview_url")
        link = t.get("external_url")
        f = t.get("features", {})
        
        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = uri in st.session_state.selected_uris
            new_val = st.checkbox("", value=checked, key=f"chk_{uri}", label_visibility="collapsed")
            if new_val != checked:
                if new_val:
                    st.session_state.selected_uris.add(uri)
                else:
                    st.session_state.selected_uris.discard(uri)
        
        with col2:
            st.markdown(f"<div class='card'><b>#{idx} {name}</b> — {artists}</div>", unsafe_allow_html=True)
            
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
            
            if link:
                st.markdown(
                    f"<a href='{link}' target='_blank'>🎵 Open in Spotify</a> | <code>{uri}</code>",
                    unsafe_allow_html=True
                )


def create_playlist_block(vibe: str):
    tracks = st.session_state.rec_tracks or []
    selected = list(st.session_state.selected_uris)

    st.subheader("4) Create playlist")

    default_name = f"{vibe.capitalize()} • {time.strftime('%b %d, %Y')}"
    name = st.text_input("Playlist name", value=default_name)
    description = st.text_area("Description", value=f"Auto‑generated {vibe} playlist")
    
    colA, colB = st.columns(2)
    with colA:
        public = st.toggle("Public playlist", value=False)
    with colB:
        use_all = st.toggle("Use all shown tracks", value=True)

    create = st.button("🪄 CREATE PLAYLIST", type="primary", use_container_width=True)

    if create:
        if not st.session_state.spotify_user_id:
            st.warning("⚠️ Please connect Spotify first.")
            return
        
        try:
            with st.spinner("🎵 Creating your playlist..."):
                if use_all:
                    if not tracks:
                        st.warning("⚠️ Please fetch recommendations first.")
                        return
                    payload = {
                        "spotify_user_id": st.session_state.spotify_user_id,
                        "vibe": vibe,
                        "lyrical": True,
                        "limit": len(tracks),
                        "playlist_name": name,
                        "playlist_description": description,
                        "public": public,
                    }
                    res = api_post("/recommend-and-create", payload)
                    url = res.get("url")
                    st.success(f"✅ Playlist created with {res.get('created', 0)} tracks!")
                    if url:
                        st.link_button("🎧 Open in Spotify", url)
                else:
                    if not selected:
                        st.warning("⚠️ No tracks selected.")
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
                    st.success("✅ Playlist created from your selections!")
                    if url:
                        st.link_button("🎧 Open in Spotify", url)
        except Exception as e:
            st.error(f"❌ Playlist creation failed: {e}")

# ------------------ Main App ------------------

def main():
    header()
    if not ensure_logged_in():
           st.stop() 

    # with st.container(border=True):
        
           # st.markdown("<span class='ok'>✅ Spotify connected.</span>", unsafe_allow_html=True)
        # else:
            

    vibe, lyrical, limit, market = vibe_controls()
    recommend_action(vibe, lyrical, limit, market)
    tracks_table()
    create_playlist_block(vibe)


if __name__ == "__main__":
    main()
