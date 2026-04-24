"""Forecast page — 7-day risk timeline + risk-tolerance slider.

Owner: TM2 (charts) · TM3 (forecast data) · Support: TM1 (slider logic)

Layout:
    1. Re-use the sidebar from Dashboard (trail, date, risk slider).
    2. Plotly multi-line chart: temperature, precipitation, wind — next 7 days.
    3. Seven colour-coded cards (green/orange/red) — one per day — showing
       the ML verdict + confidence.
    4. Sunset-warning widget: if user estimated walking time pushes past
       civil sunset, flag the trail portion where they'll be caught out.
"""

from __future__ import annotations

import streamlit as st

from data import db_manager, weather_fetcher
from ml import trail_classifier
from utils.constants import APP_TITLE, VERDICT_COLOURS

st.set_page_config(page_title=f"Forecast · {APP_TITLE}", page_icon="📈", layout="wide")


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def render_timeline_chart(trail_id: int) -> None:
    """Plotly multi-line chart for the next 7 days.

    x-axis: date. Three y-traces: temperature (°C), precipitation (mm),
    wind speed (km/h). Use ``plotly.graph_objects`` with secondary y-axes.

    TODO (TM2): implement.
    """
    st.subheader("📈 Next 7 days — weather")
    st.info("7-day weather chart renders here.")


# ---------------------------------------------------------------------------
# Verdict cards
# ---------------------------------------------------------------------------

def render_verdict_cards(trail_id: int, risk_tolerance: int) -> None:
    """Render 7 colour-coded cards, one per day.

    The risk tolerance (1–5) adjusts the thresholds for displaying
    BORDERLINE vs AVOID — the *model output* is never changed, only how it
    is thresholded for display.

    TODO (TM2 + TM1): implement.
    """
    st.subheader("🚦 Daily verdicts")
    cols = st.columns(7)
    for i, col in enumerate(cols):
        with col:
            st.markdown(f"**Day +{i}**")
            st.info("TODO")


# ---------------------------------------------------------------------------
# Sunset warning (Feature 7)
# ---------------------------------------------------------------------------

def render_sunset_warning(trail_id: int) -> None:
    """Estimate walking time and warn if the hiker may still be out at sunset.

    Inputs:
        * trail length + difficulty → estimate duration (DIN 33466 formula).
        * sunset time for trail coordinates (from Open-Meteo daily).
        * user-chosen start time.

    Output:
        * warning card if duration_after_sunset > 0.
        * (optional) map pin of "where you'll be at sunset".

    TODO (TM5 or TM1): implement.
    """
    st.subheader("🌅 Sunset warning")
    st.info("Sunset warning renders here.")


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("📈 7-day forecast")

    trail_id = st.session_state.get("selected_trail_id")
    risk = st.session_state.get("risk_tolerance", 3)

    if trail_id is None:
        st.warning("Pick a trail on the Dashboard page first.")
        return

    render_timeline_chart(trail_id)
    st.divider()
    render_verdict_cards(trail_id, risk)
    st.divider()
    render_sunset_warning(trail_id)


main()
