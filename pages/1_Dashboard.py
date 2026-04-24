"""Dashboard page — interactive Folium map + user report form.

Owner: TM1 (map, markers) · TM5 (user report form)

Layout (top → bottom):
    1. Sidebar: trail selector, date picker, risk-tolerance slider.
    2. Folium map with colour-coded markers (green/orange/red) per today's
       ML verdict. Click a marker → popup with verdict, confidence, mini-weather.
    3. Plotly elevation profile of the selected trail, with a dashed line at
       today's snowline. Area above the snowline is shaded blue.
    4. User-submitted condition-report form.
    5. Live feed of the most recent user reports.
"""

from __future__ import annotations

import streamlit as st

from data import db_manager, weather_fetcher
from ml import trail_classifier
from utils.constants import (
    APP_TITLE,
    VERDICT_COLOURS,
    RISK_SLIDER_MIN,
    RISK_SLIDER_MAX,
)

st.set_page_config(page_title=f"Dashboard · {APP_TITLE}", page_icon="🗺️", layout="wide")


# ---------------------------------------------------------------------------
# Sidebar — shared widgets
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    """Trail selector, date picker, risk-tolerance slider.

    Values are written to ``st.session_state`` so other pages read them.

    TODO (TM1): implement. Use ``db_manager.get_all_trails()`` for options.
    """
    st.sidebar.header("Your hike")
    # TODO: trail selectbox
    # TODO: date picker (today..today+7)
    # TODO: risk slider (1..5)


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

def render_map() -> None:
    """Render the Folium leaflet map with colour-coded trail markers.

    Steps:
        1. ``trails = db_manager.get_all_trails()``
        2. For each trail, call ``trail_classifier.predict`` on today's weather.
        3. Build a Folium map centred on Switzerland.
        4. Drop a marker per trail — colour from VERDICT_COLOURS.
        5. Popup: verdict · confidence · top 3 features.
        6. ``st_folium(m, width=900, height=500)``.

    TODO (TM1): implement.
    """
    st.subheader("🗺️ Trail map")
    st.info("Map renders here. See TODOs in pages/1_Dashboard.py.")


# ---------------------------------------------------------------------------
# Elevation profile
# ---------------------------------------------------------------------------

def render_elevation_profile() -> None:
    """Plotly line chart: altitude vs. distance, with snowline overlay.

    TODO (TM1): implement.
    """
    st.subheader("⛰️ Elevation profile")
    st.info("Elevation profile renders here.")


# ---------------------------------------------------------------------------
# User report form
# ---------------------------------------------------------------------------

def render_report_form() -> None:
    """Form to submit a real-world trail condition report.

    Uses ``st.form`` so the whole submission is atomic. On submit:
        ``db_manager.insert_user_report(...)``
    then re-run to show the new report in the feed below.

    TODO (TM5): implement.
    """
    st.subheader("📝 Submit a trail report")
    st.info("User report form renders here.")


def render_recent_reports() -> None:
    """Live feed of the last N user reports.

    TODO (TM5): implement.
    """
    st.subheader("🗣️ Recent reports from hikers")
    st.info("Recent reports feed renders here.")


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("🗺️ Dashboard")
    render_sidebar()
    render_map()
    st.divider()
    render_elevation_profile()
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        render_report_form()
    with col2:
        render_recent_reports()


main()
