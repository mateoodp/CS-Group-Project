"""Swiss Alpine Hiking Condition Forecaster — Streamlit entry point.

Owner: TM1 (Project Lead)
Supporting: TM2, TM3

This file is the landing screen and one-time bootstrap. Real work happens
on the four pages under ``pages/``:

    1. Find a hike (front door — quiz + date)
    2. Map         (visual overview)
    3. Compare     (side-by-side for one date)
    4. About       (ML pipeline + retrain)

Plus a hidden Trail Detail sub-page reachable by clicking any hike from
the four pages above. The horizontal nav at the top of every page comes
from :mod:`utils.topnav` — Streamlit's auto sidebar nav is hidden via CSS.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from data import db_manager
from ml import trail_classifier
from utils.constants import APP_TAGLINE, APP_TITLE, DEFAULT_RISK_TOLERANCE
from utils.sidebar import render_shared_sidebar
from utils.topnav import render_top_nav

# ---------------------------------------------------------------------------
# Page config — MUST be the first Streamlit command in the script.
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def initialise_session_state() -> None:
    """Seed shared keys used across all pages."""
    defaults: dict = {
        "selected_trail_id": None,
        "selected_date": None,
        "risk_tolerance": DEFAULT_RISK_TOLERANCE,
        "last_weather_refresh": None,
        "last_metrics": None,
        "compare_seed_trail_id": None,
        "compare_date": None,
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
    c1.metric("Trails in catalogue", n_trails)
    c2.metric("Weather rows cached", f"{n_weather:,}")
    c3.metric("Model trained",
              "✅ ready" if has_model else "❌ open About → Retrain")

    st.divider()
    st.markdown("## How the app is laid out")

    cards = [
        ("🧭 Find a hike", "pages/1_Find.py",
         "**Start here.** Answer 5 questions (canton, region, difficulty, "
         "length, max altitude) and pick a date. We rank every Swiss trail "
         "that matches — safest first."),
        ("🗺️ Map", "pages/2_Map.py",
         "Browse all 234 trails on a map, colour-coded by today's verdict. "
         "Use this when you want to explore, not when you have a question."),
        ("🔀 Compare", "pages/3_Compare.py",
         "Pit 2–4 trails against each other for one date. Bar chart, radar "
         "chart, and the numbers side-by-side."),
        ("ℹ️ About", "pages/4_About.py",
         "How the ML model works, current accuracy metrics, and the button "
         "to retrain after seeding historical weather."),
    ]
    cols = st.columns(2)
    for i, (title, path, blurb) in enumerate(cards):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.markdown(blurb)
                st.page_link(path, label=f"Open {title.split(' ', 1)[1]} →")

    st.divider()
    st.markdown(
        """
        ##### How it flows

        Click a hike anywhere — Find's ranked list, the Map, or Compare's
        table — and you land on a **Trail Detail** page with the route on a
        topographic map, hazard markers, weather interpretation (with a
        Top vs. Bottom split), tricky-parts breakdown, and photos. From
        there you can change the date, hop into Compare with that trail
        preselected, or submit a hiker report.

        On a fresh install the database has only trails — no weather, no
        model. Open **ℹ️ About** → click **Seed historical weather** → click
        **Retrain model**. After that everything is cached.
        """
    )


def main() -> None:
    bootstrap()
    initialise_session_state()
    render_top_nav()
    render_shared_sidebar()
    render_landing()


if __name__ == "__main__":
    main()
