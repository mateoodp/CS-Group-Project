"""Shared sidebar — minimalist version.

After the UX cleanup the sidebar owns **one** control:

    * **Risk tolerance** — a single global slider that biases every
      displayed verdict (cautious users see harsher verdicts; bold users
      see softer ones, with a hard safety lock for T4+ trails).

Trail selection, date selection, trail filtering, *and* manual weather
refresh have all been moved out: the date/trail come from each page's
own widgets, and weather is now refreshed automatically in the
background by :mod:`utils.data_health`. The user never has to click a
"refresh" button.
"""

from __future__ import annotations

import streamlit as st

from data import db_manager
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
            "ℹ️ Open **🧭 Find a hike** or **🗺️ Map** to choose a trail."
        )
    else:
        trail = db_manager.get_trail(selected_id)
        if trail:
            st.sidebar.caption(f"📍 Selected: **{trail['name']}**")
            st.sidebar.caption(
                "Weather is fetched automatically — no refresh needed."
            )
