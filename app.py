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

import json

import streamlit as st

from data import db_manager
from ml import trail_classifier
from utils.constants import APP_TITLE, DEFAULT_RISK_TOLERANCE
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


def _load_persisted_metrics() -> None:
    """Populate ``last_metrics`` from disk so About is hydrated on cold start.

    Read-only — never trains. Retraining takes 10–60 s and would freeze
    every app launch. If the JSON is missing or corrupt we fall through;
    the About page shows its placeholder until the user clicks Retrain.
    """
    if st.session_state.get("last_metrics") is not None:
        return
    if not (trail_classifier.model_exists()
            and trail_classifier.METRICS_PATH.exists()):
        return
    try:
        st.session_state["last_metrics"] = json.loads(
            trail_classifier.METRICS_PATH.read_text()
        )
    except Exception:
        pass


def render_landing() -> None:
    from datetime import date

    import plotly.graph_objects as go

    from utils import predictions
    from utils.constants import CH_CENTRE_LAT, CH_CENTRE_LON

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown(f"## {APP_TITLE}")
        st.markdown(
            "Around 20 hikers die in the Swiss Alps each year due to "
            "underestimated conditions. Weather apps show raw data. This tool "
            "gives a single **SAFE / BORDERLINE / AVOID** verdict per trail — "
            "powered by a Random Forest trained on two years of "
            "meteorological history."
        )
        st.markdown("---")

        n_trails = len(db_manager.get_all_trails())
        n_weather = len(db_manager.get_all_weather())
        has_model = trail_classifier.model_exists()

        m1, m2, m3 = st.columns(3)
        m1.metric("Trails", n_trails)
        m2.metric("Weather records", f"{n_weather:,}")
        m3.metric("Model", "Ready" if has_model else "Not trained")

        st.markdown("")
        if st.button("Find my best hike →", type="primary"):
            st.switch_page("pages/1_Find.py")

    with col_right:
        today = date.today()
        trails = db_manager.get_all_trails()
        trail_ids = tuple(sorted(t["id"] for t in trails))
        verdicts = predictions.get_verdicts_for_date(
            today.isoformat(), trail_ids
        )

        colour_map = {
            "SAFE": "#1E7B3A", "BORDERLINE": "#E69F00",
            "AVOID": "#C0392B", "—": "#AAAAAA",
        }
        lats: list[float] = []
        lons: list[float] = []
        colours: list[str] = []
        texts: list[str] = []
        for t in trails:
            d = verdicts.get(t["id"], {})
            v = d.get("verdict", "—")
            conf = d.get("confidence", 0.0)
            lats.append(t["lat"])
            lons.append(t["lon"])
            colours.append(colour_map.get(v, "#AAAAAA"))
            texts.append(f"{t['name']}<br>{v} · {conf:.0%}")

        fig = go.Figure(go.Scattergeo(
            lat=lats, lon=lons, mode="markers",
            marker=dict(size=7, color=colours, opacity=0.85),
            text=texts, hoverinfo="text",
        ))
        fig.update_geos(
            visible=False, resolution=50, scope="europe",
            center=dict(lat=CH_CENTRE_LAT, lon=CH_CENTRE_LON),
            projection_scale=8,
        )
        fig.update_layout(
            height=420, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Green = SAFE · Orange = BORDERLINE · "
            "Red = AVOID · Grey = no data"
        )


def main() -> None:
    bootstrap()
    initialise_session_state()
    _load_persisted_metrics()
    render_top_nav()
    render_shared_sidebar()
    render_landing()


if __name__ == "__main__":
    main()
