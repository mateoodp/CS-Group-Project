"""Planner page. Helps the user find the best trail for a specific day.

The user picks a difficulty, optionally a region, and a date. The page
returns a sorted list of trails that the model predicts as SAFE on that
day, with the most confident ones at the top.
"""
# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data import db_manager, weather_fetcher
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS
from utils.i18n import fmt_date, t, verdict_label
from utils.sidebar import render_shared_sidebar
from utils.topnav import render_top_nav

# Streamlit pattern - https://docs.streamlit.io
# Configure the browser tab and page layout. Must run before other Streamlit calls.
st.set_page_config(
    page_title=f"Planner · {APP_TITLE}",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# Main function for this page. It shows the input controls (difficulty,
# region, date) and runs the planner search when the user clicks the button.
def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    st.title(t("🗓️ Trail planner"))
    st.markdown(
        t("Tell us what kind of hike you want and when. We will find the "
          "best trails predicted SAFE on that day.")
    )
    st.divider()

    # Read the available difficulties and regions straight from the database.
    # This way the dropdowns always match what's actually in the catalogue,
    # instead of being hard-coded lists that could go out of sync.
    meta = db_manager.get_trail_metadata()

    # Streamlit pattern - https://docs.streamlit.io
    # Three columns sitting side by side. Each one holds a single input:
    # difficulty filter, region filter, and the date picker.
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        difficulties = st.multiselect(
            t("Difficulty (SAC scale)"),
            options=meta["difficulties"],
            default=["T1", "T2", "T3"],
            help=t("T1 = easy hiking path · T6 = difficult alpine route."),
        )
    with col_b:
        regions = st.multiselect(
            t("Region (optional)"),
            options=meta["regions"],
            default=[],
            help=t("Leave empty to search all regions."),
        )
    with col_c:
        today = date.today()
        # The free Open-Meteo forecast only covers today plus the next 6
        # days, so we restrict the date picker to that window.
        target_date = st.date_input(
            t("Target date"),
            value=today + timedelta(days=1),
            min_value=today,
            max_value=today + timedelta(days=6),
        )

    # Only run the planner when the user actually clicks the button.
    # Without this, Streamlit would re-run the whole search every time
    # the user touched any widget on the page.
    if st.button(t("Find trails"), type="primary"):
        with st.spinner(t("Querying forecast data…")):
            _run_planner(difficulties or None, regions or None, target_date)


# The actual planner. Steps:
# 1. Get the trails that match the user's filters from the database.
# 2. For each one, look up (or fetch) the weather for the chosen date.
# 3. Run the model to get a verdict and confidence.
# 4. Sort the results and show them as a styled table.
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
            t("No trails match those filters. Try widening the difficulty "
              "or region.")
        )
        return

    results = []
    # Streamlit pattern - https://docs.streamlit.io
    # Show a progress bar so the user knows the app is working. We update
    # it after each trail finishes so the bar moves smoothly.
    progress = st.progress(0.0, text=t("Checking forecasts…"))
    for i, t in enumerate(trails):
        # Try the local database first. If we don't have weather saved for
        # this date yet, we ask Open-Meteo for it. We swallow API failures
        # so one broken trail doesn't kill the whole search.
        snap = db_manager.get_weather_for_date(t["id"], target_date)
        if snap is None:
            try:
                # Open-Meteo Forecast API - https://open-meteo.com/en/docs
                weather_fetcher.refresh_cache(
                    t["id"], t["lat"], t["lon"], force=False
                )
                snap = db_manager.get_weather_for_date(t["id"], target_date)
            except Exception:
                snap = None
        if snap:
            # Ask the model to predict a verdict for this trail on this date.
            # If the model isn't trained yet, the rule-based engine takes over.
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
        st.error(t("No forecast data found for any matching trail on that date."))
        return

    df = pd.DataFrame(results)
    # Sort the table in two passes. First by verdict, so SAFE rows are at
    # the top, then BORDERLINE, then AVOID. Within each verdict bucket we
    # sort by confidence (highest first), so the strongest recommendations
    # come ahead of the weaker ones.
    order = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}
    df["_sort"] = df["Verdict"].map(order)
    df = df.sort_values(
        ["_sort", "Confidence"], ascending=[True, False]
    ).drop(columns=["_sort"])

    safe_count = (df["Verdict"] == "SAFE").sum()
    st.markdown(
        t("**{safe} of {total} trails** predicted SAFE on {d}.",
          safe=safe_count, total=len(df), d=fmt_date(target_date, "long"))
    )

    # Small helper that returns the CSS color we want for a single cell in
    # the Verdict column. Pandas Styler runs this function on every cell.
    # It keys on the internal English verdict, so it runs before the
    # display formatting below translates the label.
    def colour_verdict(val: str) -> str:
        c = VERDICT_COLOURS.get(val, "#888")
        return f"background-color:{c}; color:white; font-weight:bold;"

    styled = df.style.map(colour_verdict, subset=["Verdict"])
    # format() swaps each verdict for its localised label at display time;
    # relabel_index() translates the column headers. The DataFrame itself
    # keeps English keys so the sorting and colour logic above stays valid.
    styled = styled.format({"Verdict": verdict_label, "Confidence": "{:.0%}"})
    styled = styled.relabel_index(
        [t(col) for col in df.columns], axis="columns"
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


main()
