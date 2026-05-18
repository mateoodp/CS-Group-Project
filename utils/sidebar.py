"""Shared sidebar. Kept very simple on purpose.

The sidebar holds exactly one control:

    * Risk tolerance: a single global slider that nudges every verdict
      shown in the app. Cautious users see harsher verdicts, bold users
      see softer ones. T4 routes and above still never display as SAFE,
      even at the boldest setting.

We used to have trail filters, date pickers, and a manual weather refresh
button in here too. They've all moved out: each page has its own widgets
now, and weather refreshes happen automatically in the background through
utils.data_health. The user never has to click "refresh".
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

import streamlit as st

from data import db_manager
from utils.constants import (
    DEFAULT_RISK_TOLERANCE,
    RISK_SLIDER_MAX,
    RISK_SLIDER_MIN,
)
from utils.i18n import t


def render_shared_sidebar() -> None:
    """Draw the simplified sidebar. Safe to call on every page."""
    st.sidebar.header(t("⚙️ Settings"))

    # The risk tolerance slider lives here. utils.predictions reads its
    # value and uses it to shift displayed verdicts: lower setting makes
    # things stricter (toward AVOID), higher setting makes things softer
    # (toward SAFE). The value is stored in session state so all pages
    # can read it.
    risk = st.sidebar.slider(
        t("Risk tolerance"),
        min_value=RISK_SLIDER_MIN,
        max_value=RISK_SLIDER_MAX,
        value=st.session_state.get("risk_tolerance", DEFAULT_RISK_TOLERANCE),
        help=t(
            "1 = very cautious (verdict shifts toward AVOID). "
            "5 = bold (toward SAFE). T4+ trails are still never marked SAFE, "
            "even at risk = 5."
        ),
        key="risk_slider",
    )
    # Streamlit session state pattern - https://docs.streamlit.io/library/api-reference/session-state
    # Save the slider value into session state. Session state is like a
    # dictionary that survives across reruns and across pages, so the
    # other pages can read this value without having to re-render the
    # sidebar themselves.
    st.session_state["risk_tolerance"] = risk

    st.sidebar.divider()
    # If the user has already chosen a trail somewhere else in the app
    # (on Find or Map), we show its name in the sidebar. This gives a
    # tiny bit of "you're working on this trail" feedback no matter
    # which page they're on.
    selected_id = st.session_state.get("selected_trail_id")
    if selected_id is None:
        st.sidebar.caption(
            t("ℹ️ Open **🧭 Find a hike** or **🗺️ Map** to choose a trail.")
        )
    else:
        trail = db_manager.get_trail(selected_id)
        if trail:
            st.sidebar.caption(t("📍 Selected: **{name}**", name=trail["name"]))
            st.sidebar.caption(
                t("Weather is fetched automatically — no refresh needed.")
            )
