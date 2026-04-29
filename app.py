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

from data import db_manager
from ml import trail_classifier
from utils.constants import APP_TAGLINE, APP_TITLE, DEFAULT_RISK_TOLERANCE
from utils.sidebar import render_shared_sidebar

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
    """Seed shared keys used across all pages."""
    defaults: dict = {
        "selected_trail_id": None,
        "selected_date": None,
        "risk_tolerance": DEFAULT_RISK_TOLERANCE,
        "last_weather_refresh": None,
        "last_metrics": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def bootstrap() -> None:
    """One-time setup: create SQLite tables and seed the trails table."""
    db_manager.setup_db()


def render_landing() -> None:
    st.title(f"🏔️ {APP_TITLE}")
    st.caption(APP_TAGLINE)

    n_trails = len(db_manager.get_all_trails())
    n_weather = len(db_manager.get_all_weather())
    has_model = trail_classifier.model_exists()

    c1, c2, c3 = st.columns(3)
    c1.metric("Trails", n_trails)
    c2.metric("Weather rows cached", f"{n_weather:,}")
    c3.metric("Model trained", "✅" if has_model else "❌ — see About tab")

    st.markdown(
        """
        ## Get started

        1. **Pick a trail** in the sidebar (date, risk tolerance).
        2. Open **🗺️ Dashboard** for the colour-coded map and elevation profile.
        3. Open **📈 Forecast** for a 7-day timeline and per-day verdicts.
        4. Open **🔀 Compare** to weigh up to 4 trails side by side.
        5. Open **🧭 Recommend** to answer a 5-question quiz and get the best
           hikes ranked for today or any day in the next week.
        6. Open **ℹ️ About** to see the ML pipeline, retrain the model, and
           inspect the contribution matrix.

        ---

        On a fresh install, the SQLite database has only trails — no weather
        and no model. Open the **About** tab → click **Seed historical weather**
        → click **Retrain model**. After that everything is cached.
        """
    )


def main() -> None:
    bootstrap()
    initialise_session_state()
    render_shared_sidebar()
    render_landing()


if __name__ == "__main__":
    main()
