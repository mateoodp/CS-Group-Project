"""Swiss Alpine Hiking Condition Forecaster — Streamlit entry point.

Owner: TM1 (Project Lead)
Supporting: TM2, TM3

This file wires the multipage app together. Individual tab logic lives in
``pages/`` — Streamlit auto-discovers those files and renders them in the
sidebar.

Run with:
    streamlit run app.py

Docs:
    https://docs.streamlit.io/library/get-started/multipage-apps
"""

from __future__ import annotations

import streamlit as st

# Local imports — keep these light so the landing page loads fast.
from data.db_manager import setup_db
from utils.constants import APP_TITLE, APP_TAGLINE, DEFAULT_RISK_TOLERANCE

# ---------------------------------------------------------------------------
# Page config — MUST be the first Streamlit command in the script.
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def initialise_session_state() -> None:
    """Seed ``st.session_state`` with the keys shared across all pages.

    This is called once per session. Each page can safely assume these keys
    exist. If you need a new shared key (e.g. 'selected_date'), add it here
    so the whole team knows about it.
    """
    defaults: dict = {
        "selected_trail_id": None,
        "selected_date": None,
        "risk_tolerance": DEFAULT_RISK_TOLERANCE,   # 1 = cautious, 5 = bold
        "last_weather_refresh": None,
        "model_version": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def bootstrap() -> None:
    """One-time setup: create SQLite tables and seed the trails table.

    TODO (TM2): make ``setup_db`` idempotent so this is safe to call on every
    start. Should return quickly if the DB already exists.
    """
    setup_db()


def render_landing() -> None:
    """Landing view shown at ``app.py`` itself.

    The real UI lives in ``pages/``. This page just welcomes the user and
    points them to the sidebar.
    """
    st.title(f"🏔️ {APP_TITLE}")
    st.caption(APP_TAGLINE)

    st.markdown(
        """
        **Welcome!** Use the sidebar to navigate:

        1. **Dashboard** — interactive map of Swiss trails with today's verdict
        2. **Forecast** — 7-day risk timeline for the selected trail
        3. **Compare** — side-by-side comparison of up to 4 trails
        4. **About** — ML metrics, feature importance, and contribution matrix
        """
    )

    # TODO (TM1): add hero image / banner of a Swiss alpine scene here.
    # TODO (TM1): surface the "last model retrained" timestamp.


def main() -> None:
    """Application entry point."""
    bootstrap()
    initialise_session_state()
    render_landing()


if __name__ == "__main__":
    main()
