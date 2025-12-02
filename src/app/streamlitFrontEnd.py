"""
Streamlit Frontend — Vibe Music Recommender (Apple)
=====================================================

Run locally:
--------------------------------------
$ pip install streamlit requests python-dotenv
$ streamlit run streamlit_frontend_app.py
--------------------------------------
"""

import os
import time
import requests
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
if "vibes" not in st.session_state:
    st.session_state.vibes = []
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
    try:
        vib = api_get("/vibes")
        return vib.get("vibes", [])
    except Exception:
        # Fallback if backend isn't ready
        return ["focus", "creative", "mellow", "energetic"]


# ------------------ UI Blocks ------------------
def header():
    left, right = st.columns([0.8, 0.2])
    with left:
        st.title(PAGE_TITLE)
        st.caption("Student-driven Apple Music recommendations by vibe / task. Built from real audio features.")
    with right:
        st.markdown(
            "<div class='pill'>Backend</div>"
            f"<div class='subtle'>URL:</div><code>{BACKEND_BASE_URL}</code>",
            unsafe_allow_html=True,
        )


def vibe_controls():
    st.subheader("1) Choose your vibe / task")

    if not st.session_state.vibes:
        st.session_state.vibes = fetch_vibes()

    vibe = st.selectbox(
        "Vibe",
        options=st.session_state.vibes,
        index=0 if st.session_state.vibes else None,
        help="Pick the vibe or task (e.g., focus, creative, mellow).",
    )
    limit = st.slider("Track count", 5, 50, 25, step=1)
    country = st.text_input("Apple Music country code", value="us", help="e.g. us, gb, in, au")

    return vibe, limit, (country or "us")


def recommend_action(vibe: str, limit: int, country: str):
    st.subheader("2) Get recommendations")

    btn = st.button("✨ Recommend tracks", type="primary", use_container_width=True)
    if btn:
        with st.spinner("Fetching recommendations..."):
            try:
                payload = {
                    "vibe": vibe,
                    "limit": limit,
                    "country": country,
                }
                data = api_post("/recommend", payload)
                st.session_state.rec_tracks = data.get("tracks", [])
                st.session_state.selected_ids = set(t.get("id") for t in st.session_state.rec_tracks)
                st.success(f"Got {len(st.session_state.rec_tracks)} tracks.")
            except Exception as e:
                st.error(f"Recommendation failed: {e}")


def tracks_table():
    tracks = st.session_state.rec_tracks or []
    if not tracks:
        st.info("No tracks yet. Click **Recommend tracks** above.")
        return

    st.subheader("3) Review & pick tracks")

    st.caption("Uncheck any songs you don't want. You can listen to 30s previews and open tracks in Apple Music.")

    # Bulk selectors
    c1, c2, c3 = st.columns([0.2, 0.2, 0.6])
    with c1:
        if st.button("Select all"):
            st.session_state.selected_ids = set(t.get("id") for t in tracks)
    with c2:
        if st.button("Clear all"):
            st.session_state.selected_ids = set()

    # Render as cards
    for t in tracks:
        tid = t.get("id")
        name = t.get("name")
        artists = ", ".join(t.get("artists", []))
        preview = t.get("preview_url")
        link = t.get("external_url")
        f = t.get("features", {})
        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = tid in st.session_state.selected_ids
            new_val = st.checkbox("", value=checked, key=f"chk_{tid}")
            if new_val:
                st.session_state.selected_ids.add(tid)
            else:
                st.session_state.selected_ids.discard(tid)
        with col2:
            st.markdown(f"<div class='card'><b>{name}</b> — {artists}", unsafe_allow_html=True)
            # show a tiny summary of numeric features
            metrics = [
                ("Tempo", f.get("tempo")),
                ("Energy", f.get("energy")),
                ("ZCR", f.get("zcr")),
            ]
            st.caption(
                "  •  ".join(
                    [f"{m}: {v:.3f}" if isinstance(v, (int, float)) else f"{m}: —" for m, v in metrics]
                )
            )
            if preview:
                st.audio(preview, format="audio/mp3")
            tiny = []
            if link:
                tiny.append(f"<a href='{link}' target='_blank'>Open in Apple Music</a>")
            tiny.append(f"Track ID: <code>{tid}</code>")
            st.markdown(" \\| ".join(tiny), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)


def create_playlist_block():
    """
    For now, we can't auto-create Apple Music playlists via public API,
    so we just summarize the selected tracks and provide links.
    """
    tracks = st.session_state.rec_tracks or []
    selected_ids = st.session_state.selected_ids

    st.subheader("4) Use your playlist")

    if not tracks:
        st.info("No tracks to show.")
        return

    selected = [t for t in tracks if t.get("id") in selected_ids]
    st.write(f"You have selected **{len(selected)}** tracks.")

    if not selected:
        return

    with st.expander("Show selected track links"):
        for t in selected:
            name = t.get("name")
            artists = ", ".join(t.get("artists", []))
            link = t.get("external_url")
            if link:
                st.markdown(f"- {name} — {artists} — [Open in Apple Music]({link})")
            else:
                st.markdown(f"- {name} — {artists}")


# ------------------ Main App ------------------
def main():
    header()
    vibe, limit, country = vibe_controls()
    recommend_action(vibe, limit, country)
    tracks_table()
    create_playlist_block()


if __name__ == "__main__":
    main()
