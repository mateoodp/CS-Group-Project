"""Shared sidebar — minimalist version.

After the UX cleanup the sidebar only owns **two** controls:

    1. **Risk tolerance** — a single global slider that biases every
       displayed verdict (cautious users see harsher verdicts; bold users
       see softer ones, with a hard safety lock for T4+ trails).
    2. **Refresh weather** — manually re-pulls the forecast for whichever
       trail is currently selected.

Trail selection, date selection, and trail filtering have all moved onto
the pages that own them (Find, Trail Detail, Compare). This makes the
state model unambiguous: the page you're looking at is the page that owns
the inputs.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from data import db_manager, weather_fetcher
from utils.constants import (
    DEFAULT_RISK_TOLERANCE,
    RISK_SLIDER_MAX,
    RISK_SLIDER_MIN,
)


def render_shared_sidebar() -> None:
    """Render the simplified sidebar. Safe to call from every page."""
    st.sidebar.header("⚙️ Settings")

    risk = st.sidebar.slider(
        "Risk tolerance",
        min_value=RISK_SLIDER_MIN,
        max_value=RISK_SLIDER_MAX,
        value=st.session_state.get("risk_tolerance", DEFAULT_RISK_TOLERANCE),
        help=(
            "1 = very cautious (verdict shifts toward AVOID). "
            "5 = bold (toward SAFE). T4+ trails are still never marked SAFE, "
            "even at risk = 5."
        ),
        key="risk_slider",
    )
    st.session_state["risk_tolerance"] = risk

    st.sidebar.divider()
    selected_id = st.session_state.get("selected_trail_id")
    if selected_id is None:
        st.sidebar.caption(
            "ℹ️ No trail picked yet. Open **🧭 Find a hike** or **🗺️ Map** "
            "to choose one."
        )
    else:
        trail = db_manager.get_trail(selected_id)
        if trail:
            st.sidebar.caption(f"📍 Selected: **{trail['name']}**")
            if st.sidebar.button("🔄 Refresh weather"):
                with st.spinner("Fetching forecast…"):
                    try:
                        n = weather_fetcher.refresh_cache(
                            trail["id"], trail["lat"], trail["lon"], force=True
                        )
                        st.session_state["last_weather_refresh"] = (
                            f"{n} rows · {date.today().isoformat()}"
                        )
                        st.sidebar.success(f"Updated {n} days.")
                    except Exception as e:
                        st.sidebar.error(f"Refresh failed: {e}")
            last = st.session_state.get("last_weather_refresh")
            if last:
                st.sidebar.caption(f"Last refresh: {last}")
