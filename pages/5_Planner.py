"""Planner page — find the best trail for a given day.

Takes user input (difficulty, region, date) and returns a ranked list of
trails predicted SAFE on that day, ordered by confidence.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data import db_manager, weather_fetcher
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS
from utils.sidebar import render_shared_sidebar
from utils.topnav import render_top_nav

st.set_page_config(
    page_title=f"Planner · {APP_TITLE}",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    st.title("🗓️ Trail planner")
    st.markdown(
        "Tell us what kind of hike you want and when. "
        "We will find the best trails predicted SAFE on that day."
    )
    st.divider()

    meta = db_manager.get_trail_metadata()

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        difficulties = st.multiselect(
            "Difficulty (SAC scale)",
            options=meta["difficulties"],
            default=["T1", "T2", "T3"],
            help="T1 = easy hiking path · T6 = difficult alpine route.",
        )
    with col_b:
        regions = st.multiselect(
            "Region (optional)",
            options=meta["regions"],
            default=[],
            help="Leave empty to search all regions.",
        )
    with col_c:
        today = date.today()
        target_date = st.date_input(
            "Target date",
            value=today + timedelta(days=1),
            min_value=today,
            max_value=today + timedelta(days=6),
        )

    if st.button("Find trails", type="primary"):
        with st.spinner("Querying forecast data…"):
            _run_planner(difficulties or None, regions or None, target_date)


def _run_planner(
    difficulties: list[str] | None,
    regions: list[str] | None,
    target_date: date,
) -> None:
    trails = db_manager.get_filtered_trails(
        difficulties=difficulties,
        regions=regions,
    )
    if not trails:
        st.warning(
            "No trails match those filters. "
            "Try widening the difficulty or region."
        )
        return

    results = []
    progress = st.progress(0.0, text="Checking forecasts…")
    for i, t in enumerate(trails):
        snap = db_manager.get_weather_for_date(t["id"], target_date)
        if snap is None:
            try:
                weather_fetcher.refresh_cache(
                    t["id"], t["lat"], t["lon"], force=False
                )
                snap = db_manager.get_weather_for_date(t["id"], target_date)
            except Exception:
                snap = None
        if snap:
            v, conf, _, source = predictions.predict_for_snapshot(
                dict(snap), t["max_alt_m"]
            )
            results.append({
                "Trail": t["name"],
                "Canton": t["canton"],
                "Difficulty": t["difficulty"],
                "Verdict": v,
                "Confidence": conf,
                "Temp °C": (
                    round(snap["temp_c"], 1)
                    if snap["temp_c"] is not None else None
                ),
                "Wind km/h": (
                    round(snap["wind_kmh"])
                    if snap["wind_kmh"] is not None else None
                ),
                "Precip mm": (
                    round(snap["precip_mm"], 1)
                    if snap["precip_mm"] is not None else None
                ),
                "Max alt m": t["max_alt_m"],
                "Source": source,
            })
        progress.progress((i + 1) / len(trails))
    progress.empty()

    if not results:
        st.error("No forecast data found for any matching trail on that date.")
        return

    df = pd.DataFrame(results)
    order = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}
    df["_sort"] = df["Verdict"].map(order)
    df = df.sort_values(
        ["_sort", "Confidence"], ascending=[True, False]
    ).drop(columns=["_sort"])

    safe_count = (df["Verdict"] == "SAFE").sum()
    st.markdown(
        f"**{safe_count} of {len(df)} trails** predicted SAFE on "
        f"{target_date.strftime('%A %d %B')}."
    )

    def colour_verdict(val: str) -> str:
        c = VERDICT_COLOURS.get(val, "#888")
        return f"background-color:{c}; color:white; font-weight:bold;"

    styled = df.style.map(colour_verdict, subset=["Verdict"])
    styled = styled.format({"Confidence": "{:.0%}"})
    st.dataframe(styled, use_container_width=True, hide_index=True)


main()
