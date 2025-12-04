"""
Streamlit Frontend — STANZA (Apple Music version)
=====================================================

This frontend:
- Talks to your FastAPI backend (BACKEND_BASE_URL) to:
    * GET /vibes   -> list available vibes + details
    * POST /recommend -> get tracks for a chosen vibe

The backend:
- Uses student musician tracks as reference audio.
- Extracts audio features (librosa).
- Finds sonically similar songs in Apple Music.
- Returns tracks with:
    - name
    - artists
    - preview_url (Apple 30s preview)
    - external_url (Apple Music track URL)
    - features (tempo, energy, etc.)

No Spotify login or user tokens are needed.
"""

import os
import time
import requests
import streamlit as st
from dotenv import load_dotenv

# ------------------ Config ------------------
load_dotenv(override=True)

# URL of your FastAPI backend (Render)
BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL",
    "https://maia-entertainment-spring-25.onrender.com"
).rstrip("/")

PAGE_TITLE = "‎‎ ‎ ‎ ‎ Stanza"
PAGE_ICON = "🎵"

st.set_page_config(page_title="Stanza", page_icon=PAGE_ICON, layout="wide")

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

      /* CARDS */
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

      /* Section headers */
      .main > div > h2 {
        color: #e5e7ff !important;
        font-weight: 800 !important;
        margin-top: 2rem !important;
        font-size: 1.8rem !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2);
      }

      /* Body text */
      .main p, .stMarkdown, label {
        color: #ffffff !important;
        font-size: 1rem;
      }

      .stCaption, caption, small {
        color: #c3c9d8 !important;
        font-weight: 500;
      }

      .ok { color: #10b981; font-weight: 600; }
      .err { color: #bf0631; font-weight: 600; }

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

      .stTextInput>label, .stTextArea>label, .stSelectbox>label, .stSlider>label {
        color: #dae2ed !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
      }
      .stCheckbox>label, [data-testid="stWidgetLabel"] {
        color: #dae2ed !important;
        font-weight: 600 !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------ Session State ------------------
# No spotify_user_id anymore — Apple Music recs don't require user login
if "vibes" not in st.session_state:
    st.session_state.vibes = []
if "vibe_details" not in st.session_state:
    st.session_state.vibe_details = {}
if "rec_tracks" not in st.session_state:
    st.session_state.rec_tracks = []
if "selected_ids" not in st.session_state:
    st.session_state.selected_ids = set()

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

# ------------------ Data fetchers ------------------

@st.cache_data(show_spinner=False, ttl=300)
def fetch_vibes():
    """
    Ask backend for list of vibes and their feature specs.

    Expected backend response:
    {
      "vibes": ["focus", "creative", "mellow", ...],
      "details": {
         "focus": { "target_energy": ..., "min_tempo": ..., ... },
         ...
      }
    }
    """
    try:
        vib = api_get("/vibes")
        return vib.get("vibes", []), vib.get("details", {})
    except Exception:
        # fallback if backend not yet ready
        return ["focus", "creative", "mellow", "energetic", "happy", "sad"], {}

# ------------------ UI Blocks ------------------

def header():
    left_pad, center, _ = st.columns([0.1, 0.8, 0.1])
    with center:
        st.markdown(
            f"""
            <h1 style='text-align:center; font-size:3rem; font-weight:800; margin-bottom:0.5rem;'>
                {PAGE_TITLE}
            </h1>
            <p style='font-size:1.2rem; color:#e5e7ff; text-align:center; margin-top:-10px;'>
                ✨ Task-based Apple Music recommendations using student-curated reference tracks.
            </p>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        "<div style='height:2px; background:linear-gradient(90deg, transparent, #667eea, transparent); margin:2rem 0;'></div>",
        unsafe_allow_html=True,
    )

def vibe_controls():
    st.subheader("1) Choose your vibe / task")

    if not st.session_state.vibes:
        vibes, details = fetch_vibes()
        st.session_state.vibes = vibes
        st.session_state.vibe_details = details

    c1, c2, c3 = st.columns([0.4, 0.3, 0.3])
    with c1:
        vibe = st.selectbox(
            "Vibe / Task",
            options=st.session_state.vibes,
            index=0,
            help="For example: focus, creative, mellow, energetic..."
        )
    with c2:
        lyrical = st.toggle(
            "Prefer vocals (lyrical)?",
            value=True,
            help="Turn off for instrumental / non-lyrical tracks."
        )
    with c3:
        limit = st.slider(
            "Track count",
            min_value=5,
            max_value=50,
            value=20,
            step=1,
            help="How many tracks should we recommend?"
        )

    if st.session_state.vibe_details.get(vibe):
        spec = st.session_state.vibe_details[vibe]
        st.caption(
            f"Reference profile → "
            f"Energy: {spec.get('target_energy')}, "
            f"Valence: {spec.get('target_valence')}, "
            f"Tempo: {spec.get('min_tempo')}–{spec.get('max_tempo')} BPM"
        )
    else:
        st.caption("Using default feature profile for this vibe.")

    return vibe, lyrical, limit

def recommend_action(vibe: str, lyrical: bool, limit: int):
    st.subheader("2) Get recommendations")

    btn = st.button("✨ RECOMMEND TRACKS", type="primary", use_container_width=True)
    if not btn:
        return

    with st.spinner("🎵 Analyzing student reference tracks and searching Apple Music..."):
        try:
            payload = {
                "vibe": vibe,
                "lyrical": lyrical,
                "limit": limit,
            }
            # Backend Apple endpoint: POST /recommend
            data = api_post("/recommend", payload)
            st.session_state.rec_tracks = data.get("tracks", [])
            # we keep IDs (or URLs) as our "selected" handle
            st.session_state.selected_ids = set(
                t.get("id") or t.get("external_url") or t.get("name")
                for t in st.session_state.rec_tracks
            )
            st.success(f"🎉 Got {len(st.session_state.rec_tracks)} tracks for '{vibe}'.")
        except Exception as e:
            st.error(f"❌ Recommendation failed: {e}")

def tracks_table():
    tracks = st.session_state.rec_tracks or []
    if not tracks:
        st.info("🎵 No tracks yet. Click **RECOMMEND TRACKS** above.")
        return

    st.subheader("3) Review & pick tracks")
    st.caption(
        "Uncheck any songs you don't want in your playlist. "
        "You can preview 30s Apple samples when available."
    )

    # Bulk selectors
    c1, c2, _ = st.columns([0.2, 0.2, 0.6])
    with c1:
        if st.button("✅ SELECT ALL"):
            st.session_state.selected_ids = set(
                t.get("id") or t.get("external_url") or t.get("name")
                for t in tracks
            )
            st.rerun()
    with c2:
        if st.button("❌ CLEAR ALL"):
            st.session_state.selected_ids = set()
            st.rerun()

    for idx, t in enumerate(tracks, 1):
        tid = t.get("id") or t.get("external_url") or t.get("name")
        name = t.get("name")
        artists = ", ".join(t.get("artists", []))
        preview = t.get("preview_url")
        link = t.get("external_url")   # Apple Music track URL
        f = t.get("features", {})

        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = tid in st.session_state.selected_ids
            new_val = st.checkbox(
                "",
                value=checked,
                key=f"chk_{tid}",
                label_visibility="collapsed"
            )
            if new_val != checked:
                if new_val:
                    st.session_state.selected_ids.add(tid)
                else:
                    st.session_state.selected_ids.discard(tid)

        with col2:
            st.markdown(
                f"<div class='card'><b>#{idx} {name}</b> — {artists}</div>",
                unsafe_allow_html=True
            )

            metrics = [
                ("Energy", f.get("energy")),
                ("Valence", f.get("valence")),
                ("Danceability", f.get("danceability")),
                ("Tempo", f.get("tempo")),
                ("Instrumentalness", f.get("instrumentalness")),
            ]
            st.caption(
                "  •  ".join(
                    [
                        f"{m}: {v:.2f}" if isinstance(v, (int, float)) else f"{m}: —"
                        for m, v in metrics
                    ]
                )
            )

            if preview:
                st.audio(preview, format="audio/mp3")

            tiny_bits = []
            if link:
                tiny_bits.append(
                    f"<a href='{link}' target='_blank'>🎵 Open in Apple Music</a>"
                )
            if tid:
                tiny_bits.append(f"ID: <code>{tid}</code>")

            if tiny_bits:
                st.markdown(" | ".join(tiny_bits), unsafe_allow_html=True)

def export_playlist_block():
    tracks = st.session_state.rec_tracks or []
    selected_ids = st.session_state.selected_ids

    st.subheader("4) Export playlist")

    if not tracks:
        st.info("Generate recommendations first, then you can export.")
        return

    selected_tracks = [
        t for t in tracks
        if (t.get("id") or t.get("external_url") or t.get("name")) in selected_ids
    ]

    st.caption(
        "We can’t auto-write into your Apple Music library from Streamlit, "
        "but you can quickly build a playlist by opening these links or copying them."
    )

    urls = [t.get("external_url") for t in selected_tracks if t.get("external_url")]
    urls_text = "\n".join(urls)

    st.text_area(
        "Apple Music track URLs (copy-paste into Apple Music to build your playlist):",
        value=urls_text,
        height=200,
    )

    if urls:
        st.download_button(
            "💾 Download URLs as text file",
            data=urls_text,
            file_name="stanza_playlist_urls.txt",
            mime="text/plain",
        )

# ------------------ Main App ------------------

def main():
    header()
    vibe, lyrical, limit = vibe_controls()
    recommend_action(vibe, lyrical, limit)
    tracks_table()
    export_playlist_block()

if __name__ == "__main__":
    main()
