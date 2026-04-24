"""Compare page — side-by-side comparison of 2–4 trails.

Owner: TM4 (ML + charts) · Support: TM5 (form)

Widgets:
    * ``st.multiselect`` — pick 2 to 4 trails.
    * Grouped Plotly bar chart — today's predicted risk score per trail.
    * Radar / spider chart — 7 weather features normalised per trail.
    * Summary table — side-by-side numeric values.
"""

from __future__ import annotations

import streamlit as st

from data import db_manager
from ml import trail_classifier
from utils.constants import APP_TITLE

st.set_page_config(page_title=f"Compare · {APP_TITLE}", page_icon="🔀", layout="wide")

MAX_TRAILS: int = 4
MIN_TRAILS: int = 2


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

def render_selector() -> list[int]:
    """Multiselect for 2–4 trails. Returns selected trail_ids.

    TODO (TM4): implement using ``db_manager.get_all_trails()``.
    """
    st.subheader("Pick 2–4 trails")
    return []


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def render_bar_chart(trail_ids: list[int]) -> None:
    """Grouped bar chart — today's predicted risk per trail.

    TODO (TM4): implement.
    """
    st.subheader("📊 Predicted risk")
    st.info("Grouped bar chart renders here.")


def render_radar_chart(trail_ids: list[int]) -> None:
    """Radar / spider chart — normalised weather features per trail.

    Use ``plotly.graph_objects.Scatterpolar`` — one trace per trail.

    TODO (TM4): implement.
    """
    st.subheader("🕸️ Weather profile")
    st.info("Radar chart renders here.")


def render_summary_table(trail_ids: list[int]) -> None:
    """Side-by-side numeric values for each trail.

    TODO (TM5): implement.
    """
    st.subheader("🔢 Numbers side-by-side")
    st.info("Summary table renders here.")


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("🔀 Compare trails")

    trail_ids = render_selector()
    if not (MIN_TRAILS <= len(trail_ids) <= MAX_TRAILS):
        st.info(f"Select between {MIN_TRAILS} and {MAX_TRAILS} trails to compare.")
        return

    render_bar_chart(trail_ids)
    render_radar_chart(trail_ids)
    render_summary_table(trail_ids)


main()
