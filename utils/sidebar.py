"""Shared sidebar widgets — reused across every page.

Provides:
    1. **Five filters** (canton, region, difficulty, length, max altitude)
       that narrow the candidate trails.
    2. The trail selector populated from the filter result.
    3. Date picker, risk-tolerance slider, refresh-weather button.

All values are written to ``st.session_state`` so any page can read them.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from data import db_manager, weather_fetcher
from utils.constants import (
    DEFAULT_RISK_TOLERANCE,
    RISK_SLIDER_MAX,
    RISK_SLIDER_MIN,
)


def _render_filters(meta: dict) -> dict:
    """Render the 5 filter widgets and return the chosen values."""
    with st.sidebar.expander("🔎 Filter trails", expanded=True):
        cantons = st.multiselect(
            "Canton",
            options=meta["cantons"],
            default=[],
            help="Select one or more cantons. Empty = all.",
            key="flt_cantons",
        )
        regions = st.multiselect(
            "Region",
            options=meta["regions"],
            default=[],
            help="Alps, Pre-Alps, Jura, Mittelland.",
            key="flt_regions",
        )
        difficulties = st.multiselect(
            "Difficulty (SAC)",
            options=meta["difficulties"],
            default=[],
            help="T1 = easy hike · T6 = alpine. Empty = all.",
            key="flt_difficulties",
        )
        length_lo, length_hi = st.slider(
            "Length (km)",
            min_value=float(int(meta["min_length_km"])),
            max_value=float(int(meta["max_length_km"]) + 1),
            value=(
                float(int(meta["min_length_km"])),
                float(int(meta["max_length_km"]) + 1),
            ),
            step=0.5,
            key="flt_length",
        )
        alt_lo, alt_hi = st.slider(
            "Max altitude (m)",
            min_value=int(meta["min_max_alt_m"]),
            max_value=int(meta["max_max_alt_m"]),
            value=(int(meta["min_max_alt_m"]), int(meta["max_max_alt_m"])),
            step=50,
            key="flt_alt",
        )

    return {
        "cantons": cantons or None,
        "regions": regions or None,
        "difficulties": difficulties or None,
        "min_length_km": length_lo,
        "max_length_km": length_hi,
        "min_alt_m": alt_lo,
        "max_alt_m": alt_hi,
    }


def render_shared_sidebar() -> None:
    """Render filters + trail / date / risk widgets."""
    meta = db_manager.get_trail_metadata()
    if not meta["cantons"]:
        st.sidebar.error("No trails seeded. Restart the app or run bootstrap.")
        return

    st.sidebar.header("Your hike")

    filters = _render_filters(meta)
    trails = db_manager.get_filtered_trails(**filters)
    st.sidebar.caption(f"**{len(trails)}** trail(s) match your filters.")

    if not trails:
        st.sidebar.warning("No trails match. Loosen the filters above.")
        st.session_state["selected_trail_id"] = None
        st.session_state["filtered_trail_ids"] = []
        return

    options = {f"{t['name']}  ·  {t['canton']}  ·  {t['difficulty']}": t["id"]
               for t in trails}
    labels = list(options.keys())

    current_id = st.session_state.get("selected_trail_id")
    default_idx = next(
        (i for i, lbl in enumerate(labels) if options[lbl] == current_id), 0
    )
    chosen = st.sidebar.selectbox(
        "Trail", labels, index=default_idx, key="trail_select"
    )
    st.session_state["selected_trail_id"] = options[chosen]
    st.session_state["filtered_trail_ids"] = [t["id"] for t in trails]

    today = date.today()
    chosen_date = st.sidebar.date_input(
        "Date",
        value=st.session_state.get("selected_date") or today,
        min_value=today - timedelta(days=2),
        max_value=today + timedelta(days=6),
        key="date_select",
    )
    st.session_state["selected_date"] = chosen_date

    risk = st.sidebar.slider(
        "Risk tolerance",
        min_value=RISK_SLIDER_MIN,
        max_value=RISK_SLIDER_MAX,
        value=st.session_state.get("risk_tolerance", DEFAULT_RISK_TOLERANCE),
        help="1 = very cautious · 5 = bold (raises BORDERLINE / AVOID thresholds).",
        key="risk_slider",
    )
    st.session_state["risk_tolerance"] = risk

    st.sidebar.divider()
    if st.sidebar.button("🔄 Refresh weather"):
        trail = db_manager.get_trail(st.session_state["selected_trail_id"])
        with st.spinner("Fetching forecast…"):
            try:
                n = weather_fetcher.refresh_cache(
                    trail["id"], trail["lat"], trail["lon"], force=True
                )
                st.session_state["last_weather_refresh"] = (
                    f"{n} rows · {date.today().isoformat()}"
                )
                st.sidebar.success(f"Updated {n} days.")
            except Exception as e:
                st.sidebar.error(f"Refresh failed: {e}")

    last = st.session_state.get("last_weather_refresh")
    if last:
        st.sidebar.caption(f"Last refresh: {last}")
