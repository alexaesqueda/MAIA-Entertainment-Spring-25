"""
Streamlit Frontend — STANZA (Apple Music Version)
=================================================
Frontend for:
- Choosing a vibe (task)
- Asking backend for recommended tracks (student-seeded, Apple previews)
- Letting user review + pick tracks
- Creating an Apple Music playlist in the user’s library (via backend)

Backend expectations (Apple version):
-------------------------------------
- GET  /vibes
    -> { "vibes": ["focus", "creative", ...],
         "details": { "focus": { "note": "...", ...}, ... } }  (details optional)

- POST /apple/recommend
    Body: {
      "vibe": "focus",
      "limit": 25,
      "storefront": "us"
    }
    -> {
      "ok": true,
      "vibe": "focus",
      "count": 25,
      "tracks": [
        {
          "id": "apple_track_id",
          "name": "Song Name",
          "artist_name": "Artist Name",
          "album_name": "Album",
          "preview_url": "https://audio-preview-url.m4a",
          "apple_music_url": "https://music.apple.com/...",
          "features": { "tempo": ..., "energy": ..., ... },
          "similarity": 0.87
        }, ...
      ]
    }

- POST /apple/playlist
    Body: {
      "user_token": "<Apple Music user token>",
      "storefront": "us",
      "vibe": "focus",
      "name": "Playlist name",
      "description": "Playlist desc",
      "track_ids": ["apple_track_id1", "apple_track_id2", ...]
    }
    -> { "ok": true, "playlist_id": "..." }  (or plus a URL if your backend returns it)
"""

import os
import time
import textwrap
import requests
import streamlit as st
from dotenv import load_dotenv
import streamlit.components.v1 as components
import streamlit as st  # Ensure this is imported

def apple_login_component(developer_token):
    """
    Renders the Login button. Upon success, it RELOADS the page 
    with the token in the URL parameters.
    """
    html_code = f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="utf-8">
        <script src="https://js-cdn.music.apple.com/musickit/v1/musickit.js"></script>
        <style>
          body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: transparent; }}
          #login-btn {{
            background: linear-gradient(135deg, #fa2d48 0%, #c81e36 100%);
            color: white; border: none; padding: 12px 24px;
            border-radius: 8px; font-weight: 600; font-size: 16px;
            cursor: pointer; transition: transform 0.2s;
          }}
          #login-btn:hover {{ transform: scale(1.02); }}
          .status {{ margin-top: 10px; font-size: 14px; color: #333; }}
        </style>
      </head>
      <body>
        <button id="login-btn"> Login with Apple Music</button>
        <p id="status" class="status"></p>

        <script>
          document.addEventListener('musickitloaded', function() {{
            MusicKit.configure({{
              developerToken: '{developer_token}',
              app: {{
                name: 'Stanza',
                build: '1.0.0'
              }}
            }});
          }});

          document.getElementById('login-btn').addEventListener('click', async function() {{
            const music = MusicKit.getInstance();
            try {{
              // 1. Open Popup and Wait for Login
              const token = await music.authorize();
              
              // 2. Success! Redirect the parent window to the same URL but WITH the token
              document.getElementById('status').innerText = "✅ Logged in! Redirecting...";
              
              // This grabs the current base URL (e.g. https://yourapp.com/)
              const currentUrl = window.top.location.href.split('?')[0];
              
              // Refresh page with the token attached
              window.top.location.href = currentUrl + "?token=" + encodeURIComponent(token);
              
            }} catch (err) {{
              document.getElementById('status').innerText = "❌ Error: " + err;
            }}
          }});
        </script>
      </body>
    </html>
    """
    components.html(html_code, height=150)

# ------------------ Config ------------------
load_dotenv(override=True)
BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL",
    "https://maia-entertainment-spring-25.onrender.com"
).rstrip("/")

PAGE_TITLE = "stanzavector.svg"
PAGE_ICON = "🎵"

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")

# ------------------ Styling ------------------
st.markdown(
    """
    <style>
      .stApp {
        background: linear-gradient(179deg, #0f1015 10%, #5568d3, #6a3f8f 100%);
        background-attachment: fixed;
      }
      .main { background: transparent; }

      /* PRIMARY ACTION BUTTONS */
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

      /* SECONDARY BUTTONS */
      .stButton>button {
        border-radius: 12px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        border: 2px solid #667eea;
        background: rgba(102, 126, 234, 0.1);
        color: #ffffff !important;
        font-size: 1rem;
        transition: all 0.3s ease;
      }
      .stButton>button:hover {
        background: #667eea;
        color: white !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
      }

      /* Cards */
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

      /* Main section headers */
      .main > div > h2 {
        color: #e5e7ff !important;
        font-weight: 800 !important;
        margin-top: 2rem !important;
        font-size: 1.8rem !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.15);
      }

      /* Body text */
      .main p,
      .stMarkdown,
      label {
        color: #ffffff !important;
        font-size: 1rem;
      }

      .stCaption, caption, small {
        color: #c7d0e3 !important;
        font-weight: 500;
      }

      .ok { color: #10b981; font-weight: 600; }
      .err { color: #bf0631; font-weight: 600; }

      .stTextInput>label,
      .stTextArea>label,
      .stSelectbox>label,
      .stSlider>label {
        color: #dae2ed !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
      }
      .stCheckbox>label,
      [data-testid="stWidgetLabel"] {
        color: #dae2ed !important;
        font-weight: 600 !important;
      }

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
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------ Session State ------------------
if "vibes" not in st.session_state:
    st.session_state.vibes = []
if "vibe_details" not in st.session_state:
    st.session_state.vibe_details = {}
if "rec_tracks" not in st.session_state:
    st.session_state.rec_tracks = []
if "selected_ids" not in st.session_state:
    st.session_state.selected_ids = set()
if "apple_user_token" not in st.session_state:
    st.session_state.apple_user_token = ""

# ------------------ Backend helpers ------------------

def api_get(path: str, params: dict | None = None, timeout: int = 20):
    url = f"{BACKEND_BASE_URL}{path}"
    r = requests.get(url, params=params, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"GET {path} failed: {r.status_code} {r.text}")
    return r.json()

def api_post(path: str, payload: dict, timeout: int = 120):
    url = f"{BACKEND_BASE_URL}{path}"
    r = requests.post(url, json=payload, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {path} failed: {r.status_code} {r.text}")
    return r.json()

# ------------------ Data fetchers ------------------

@st.cache_data(show_spinner=False, ttl=300)
def fetch_vibes():
    try:
        vib = api_get("/vibes")
        return vib.get("vibes", []), vib.get("details", {})
    except Exception:
        # Fallback if backend not ready
        return ["focus", "creative", "mellow", "energetic"], {}

# ------------------ UI Blocks ------------------



def vibe_controls():
    st.subheader("1) Choose your vibe (task)")
    if not st.session_state.vibes:
        vibes, details = fetch_vibes()
        st.session_state.vibes = vibes
        st.session_state.vibe_details = details

    c1, c2 = st.columns([0.5, 0.5])
    with c1:
        vibe = st.selectbox(
            "Vibe",
            options=st.session_state.vibes,
            index=0,
            help="Pick the task/mode you’re in (e.g., focus, creative, mellow).",
        )
    with c2:
        limit = st.slider(
            "Number of tracks",
            min_value=5,
            max_value=25,
            value=10,
            step=1,
            help="How many songs you want in your recommendation batch.",
        )

    details = st.session_state.vibe_details.get(vibe) or {}
    if details:
        note = details.get("note") or details.get("description")
        if note:
            st.caption(note)

    return vibe, limit


def recommend_action(vibe: str, limit: int):
    st.subheader("2) Get recommendations")

    btn = st.button("✨ RECOMMEND TRACKS", type="primary", use_container_width=True)
    if not btn:
        return

    with st.spinner("🎵 Analyzing student tracks and finding similar Apple Music songs..."):
        try:
            payload = {
                "vibe": vibe,
                "limit": limit,
                "storefront": "us",  # adjust if you support other storefronts
            }
            # 🔴 IMPORTANT: use Apple endpoint, not /recommend
            data = api_post("/apple/recommend", payload)
            tracks = data.get("tracks", [])
            st.session_state.rec_tracks = tracks
            st.session_state.selected_ids = set(t.get("id") for t in tracks if t.get("id"))
            if tracks:
                st.success(f"🎉 Got {len(tracks)} recommended tracks for “{vibe}”.")
            else:
                st.warning("No tracks found. Try another vibe or a smaller limit.")
        except Exception as e:
            st.error(f"❌ Recommendation failed: {e}")


def tracks_table():
    tracks = st.session_state.rec_tracks or []
    if not tracks:
        st.info("🎵 No tracks yet. Click **RECOMMEND TRACKS** above.")
        return

    st.subheader("3) Review & pick tracks")
    st.caption(
        "Uncheck any songs you don't want in the playlist. You can preview each one (Apple preview audio) if available."
    )

    c1, c2, _ = st.columns([0.2, 0.2, 0.6])
    with c1:
        select_all = st.button("✅ SELECT ALL", key="btn_select_all")
    with c2:
        clear_all = st.button("❌ CLEAR ALL", key="btn_clear_all")
    
    if select_all:
        st.session_state.selected_ids = set(t.get("id") for t in tracks if t.get("id"))
        st.rerun()
    
    if clear_all:
        st.session_state.selected_ids = set()
        st.rerun()

    for idx, t in enumerate(tracks, start=1):
        tid = t.get("id")
        
        # 1. Get standardized metadata (Matching your updated backend)
        title = t.get("name", "Unknown Title")
        artist = t.get("artist_name", "Unknown Artist")
        album = t.get("album_name", "")  # New field
        
        # 2. Get the Artwork URL (New field)
        image_url = t.get("artwork_url", "")
        
        preview = t.get("preview_url")
        link = t.get("apple_music_url")
        
        preview = t.get("preview_url")
        link = t.get("apple_music_url") or t.get("apple_url") or t.get("external_url")

        features = t.get("features", {}) or {}
        metrics = []
        for key in ["tempo", "energy", "zcr", "centroid", "bandwidth"]:
            val = features.get(key)
            if isinstance(val, (int, float)):
                metrics.append(f"{key.capitalize()}: {val:.2f}")

        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = tid in st.session_state.selected_ids
            new_val = st.checkbox(
                "",
                value=checked,
                key=f"chk_{tid}_{checked}",  # Dynamic key forces re-render
                label_visibility="collapsed",
            )
            if new_val and not checked and tid:
                st.session_state.selected_ids.add(tid)
                st.rerun()
            elif not new_val and checked and tid:
                st.session_state.selected_ids.discard(tid)
                st.rerun()

        with col2:
            # 1. Prepare Image Tag
            image_tag = f'<img src="{image_url}" width="60" style="border-radius: 8px;">' if image_url else ''
            
            # 2. HTML Card (ALL ON ONE LINE to prevent "Black Box" code blocks)
            card_html = f"<div class='card' style='display: flex; align-items: center; gap: 15px; margin-bottom: 10px; padding: 10px; border-radius: 10px; background-color: rgba(102, 126, 234, 0.3); border: 1px solid rgba(102, 126, 234, 0.3); color: #e5e7ff;'>{image_tag}<div style='flex-grow: 1;'><div style='font-size: 1.1rem; font-weight: 700; color: #ffffff;'>{title}</div><div style='font-size: 0.95rem; color: #e5e7ff;'>{artist}</div><div style='font-size: 0.8rem; color: #c7d0e3;'>{album}</div></div></div>"
            
            # 3. Render
            st.markdown(card_html, unsafe_allow_html=True)

            # ... (keep existing metrics/audio/link logic below) ...
            if metrics:
                st.caption(" • ".join(metrics))
            if preview:
                st.audio(preview, format="audio/mp3")
            if link:
                st.markdown(f"<a href='{link}' target='_blank' style='text-decoration: none; color: #FA2D48; font-weight: bold;'>🎵 Open in Apple Music</a>", unsafe_allow_html=True)


def create_playlist_block(vibe: str):
    tracks = st.session_state.rec_tracks or []
    selected_ids = list(st.session_state.selected_ids)

    st.subheader("4) Create Apple Music playlist (in your library)")

    default_name = f"{vibe.capitalize()} • {time.strftime('%b %d, %Y')}"
    name = st.text_input("Playlist name", value=default_name)
    description = st.text_area(
        "Description (optional)",
        value=f"Task-based {vibe} playlist generated by Stanza.",
    )

    colA, colB = st.columns(2)
    with colA:
        use_all = st.toggle("Use all recommended tracks", value=True)
    with colB:
        st.caption("If off, only tracks you left checked above will be used.")

    create = st.button("🪄 CREATE APPLE MUSIC PLAYLIST", type="primary", use_container_width=True)

    if not create:
        return

    # Determine which tracks to use
    if use_all:
        track_ids = [t.get("id") for t in tracks if t.get("id")]
    else:
        track_ids = selected_ids

    if not track_ids:
        st.warning("⚠️ No tracks to include. Please recommend tracks and/or select at least one.")
        return

    user_token = st.session_state.apple_user_token.strip()
    if not user_token:
        st.error("❌ Apple Music user token is required. Please login above.")
        return

    with st.spinner("🎧 Creating your Apple Music playlist..."):
        try:
            payload = {
                "user_token": user_token,
                "storefront": "us",  # adjust if needed
                "vibe": vibe,
                "name": name,
                "description": description,
                "track_ids": track_ids,
            }
            
            # --- START OF NEW LOGIC ---
            
            # 1. Call the API
            res = api_post("/apple/playlist", payload)
            
            # 2. Extract Data (ID and URL)
            playlist_id = res.get("playlist_id")
            playlist_url = res.get("playlist_url")

            # 3. Success Message
            st.success("✅ Playlist created in your Apple Music library!")
            
            # 4. Show the "Shazam-style" Open Button
            if playlist_url:
                st.link_button(
                    label="🎵 OPEN IN APPLE MUSIC", 
                    url=playlist_url, 
                    type="primary", 
                    use_container_width=True
                )
            
            # 5. Show ID for reference
            if playlist_id:
                st.caption(f"Playlist ID: {playlist_id}")
                
            # --- END OF NEW LOGIC ---

        except Exception as e:
            st.error(f"❌ Playlist creation failed: {e}")


# ------------------ Main App ------------------
def login_screen():
    """
    The landing page. Redirects user to the Backend Auth Page.
    """
    _, col, _ = st.columns([0.2, 0.6, 0.2])
    
    with col:
        st.image("stanzalogo.png", width=300)
        st.markdown(
            """
            <h1 style='text-align: center; color: white;'>Stanza</h1>
            <p style='text-align: center; color: #e5e7ff; font-size: 1.1rem; margin-bottom: 30px;'>
                Task-based music recommendations seeded by real student musicians.
            </p>
            """, 
            unsafe_allow_html=True
        )
        
        # 👇 THE NEW LOGIN BUTTON (It's just a link now!)
        # Replace this URL with your actual Render Backend URL
        AUTH_URL = "https://maia-entertainment-spring-25.onrender.com/apple/auth"
        
        st.markdown(
            f"""
            <div style="text-align: center;">
                <a href="{AUTH_URL}" target="_self" style="
                    background-color: #FA2D48; color: white; text-decoration: none;
                    padding: 15px 30px; border-radius: 10px; font-weight: bold; font-size: 18px;
                    display: inline-block; box-shadow: 0 4px 12px rgba(250, 45, 72, 0.4);">
                     Login with Apple Music
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

def main_app():
    """
    The actual application, only visible after login.
    """
    # 1. Mini Header (Logo + Logout)
    c1, c2 = st.columns([0.8, 0.2])
    with c1:
        st.image("stanzalogo.png", width=150)
    with c2:
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            st.session_state.apple_user_token = ""
            st.rerun()
            
    st.divider()

    # 2. Your Existing Logic
    # (These are the functions you already wrote)
    vibe, limit = vibe_controls()
    recommend_action(vibe, limit)
    tracks_table()
    create_playlist_block(vibe)

def main():
    # --- STEP A: HANDLE REDIRECT LOGIN (Seamless) ---
    # If the JS component reloaded the page with ?token=..., capture it now.
    query_params = st.query_params
    if "token" in query_params:
        st.session_state.apple_user_token = query_params["token"]
        st.query_params.clear()
        st.rerun()

    # --- STEP B: ROUTING ---
    if st.session_state.apple_user_token:
        # User has a token -> Show the App
        main_app()
    else:
        # User has NO token -> Show Login Screen
        login_screen()

# Run the app
if __name__ == "__main__":
    main()
