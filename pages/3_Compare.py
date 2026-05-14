"""Compare page. Lets the user put 2 to 4 trails side by side for one date.

The full workflow on this page:

    1. Pick a date (the picker lives on this page, not in the sidebar).
    2. Pick between 2 and 4 trails from a single dropdown.
    3. See a bar chart, a radar chart and a summary table side by side.
    4. Open any of those trails in the Trail Detail page.

If the user got here by clicking "Compare with..." on a Trail Detail page,
that trail is automatically added to the dropdown so they don't have to
pick it again.
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
import plotly.graph_objects as go
import streamlit as st

from data import db_manager, weather_fetcher
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS, VERDICT_EMOJI
from utils.sidebar import render_shared_sidebar
from utils.theme import apply_app_theme, page_hero, section_heading, stat_pills_html
from utils.topnav import render_top_nav

# Streamlit pattern - https://docs.streamlit.io
# Page metadata. Must be the first Streamlit call on the page.
st.set_page_config(
    page_title=f"Compare · {APP_TITLE}",
    page_icon="🔀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# A comparison only really makes sense with at least 2 trails. We cap it at 4
# so the bar and radar charts stay readable (more than that looks cluttered).
MIN_TRAILS: int = 2
MAX_TRAILS: int = 4
FORECAST_HORIZON_DAYS: int = 6

# To plot verdicts on a bar chart we turn each label into a number from 1 to 3.
# SAFE = 1 (best), AVOID = 3 (worst), BORDERLINE sits in the middle.
VERDICT_SCORE = {"SAFE": 1, "BORDERLINE": 2, "AVOID": 3}
# Settings for each axis of the radar chart. Each entry is:
# (key in the weather snapshot, label shown on the chart, min value, max value).
# The min and max values are used to scale every reading onto a 0-100 scale
# so wind in km/h and temperature in degrees stay visually comparable.
RADAR_FIELDS = [
    ("temp_c", "Temp", -10, 30),
    ("wind_kmh", "Wind", 0, 80),
    ("precip_mm", "Precip", 0, 30),
    ("cloud_pct", "Cloud", 0, 100),
    ("snowline_m", "Snowline", 1000, 4500),
]


def _snapshot_for(trail, target_date):
    """Return the weather snapshot for a trail on a date.

    First we check the local cache. If nothing is there for that date, we
    force a refresh from the Open-Meteo API and try the cache again. If
    that also fails (no internet, API down), we return None.
    """
    snap = db_manager.get_weather_for_date(trail["id"], target_date)
    if snap is not None:
        return dict(snap)
    # The cache had nothing for this date. We force a re-fetch even if
    # other days are still fresh, because we specifically need this date.
    try:
        # Open-Meteo Forecast API - https://open-meteo.com/en/docs
        weather_fetcher.refresh_cache(
            trail["id"], trail["lat"], trail["lon"], force=True
        )
    except Exception:
        return None
    snap = db_manager.get_weather_for_date(trail["id"], target_date)
    return dict(snap) if snap else None


def render_inputs(all_trails) -> tuple[date, list[int]]:
    """Render the date picker + trail multiselect. Returns (date, [trail_id])."""
    today = date.today()

    # Streamlit pattern - https://docs.streamlit.io
    # If the user just clicked "Compare with..." on a Trail Detail page,
    # the trail ID was saved in session state. We use it to pre-fill the
    # dropdown so the user doesn't have to re-pick their starting trail.
    st.markdown(
        section_heading(
            "Build your shortlist",
            "Choose a date and compare two to four candidate hikes under the same forecast window.",
            "Side-by-side planning",
        ),
        unsafe_allow_html=True,
    )

    # The multiselect dropdown needs nice text labels, but later we need the
    # trail IDs to fetch data. So we build two dictionaries: one mapping
    # label to ID, and a reverse one from ID back to label (used to figure
    # out which label to pre-select if we arrived from Trail Detail).
    options = {
        f"{t['name']}  ·  {t['canton']}  ·  {t['difficulty']}": t["id"]
        for t in all_trails
    }
    label_for_id = {tid: lbl for lbl, tid in options.items()}

    # If a trail was preselected via the "Compare with..." button, find its
    # display label so we can plug it into the multiselect's default value.
    preselected_label = None
    seed_id = st.session_state.pop("compare_seed_trail_id", None)
    if seed_id and seed_id in label_for_id:
        preselected_label = label_for_id[seed_id]

    # Streamlit pattern - https://docs.streamlit.io
    # Two columns side by side: a narrow date picker on the left, then a
    # wider multiselect for the trails on the right.
    c1, c2 = st.columns([1, 3])
    with c1:
        max_date = today + timedelta(days=FORECAST_HORIZON_DAYS)
        # If the user picked a date last time and that date is still in the
        # 7-day window, we keep it. Otherwise we default back to today.
        _stored = st.session_state.get("compare_date")
        if isinstance(_stored, str):
            from datetime import datetime as _dt
            _stored = _dt.fromisoformat(_stored).date()
        default_date = _stored if isinstance(_stored, date) and today <= _stored <= max_date else today
        chosen_date = st.date_input(
            "Date to compare",
            value=default_date,
            min_value=today,
            max_value=max_date,
        )
        st.session_state["compare_date"] = chosen_date
    with c2:
        defaults = []
        if preselected_label:
            defaults.append(preselected_label)
        chosen = st.multiselect(
            f"Pick {MIN_TRAILS}–{MAX_TRAILS} trails",
            list(options.keys()),
            default=defaults,
            max_selections=MAX_TRAILS,
            help="Use the search box to filter — start typing a trail name.",
        )

    return chosen_date, [options[c] for c in chosen]


# Adapted from Plotly Python docs - https://plotly.com/python/
# Draw a bar chart showing the risk score for each trail. The bars use 1
# for SAFE up to 3 for AVOID. The bar color matches the verdict color too,
# so you can read it without checking the axis.
def render_bar_chart(rows: list[dict]) -> None:
    st.markdown(
        section_heading(
            "Predicted risk",
            "Lower is better: SAFE sits at the calmer end of the scale, AVOID at the stop-sign end.",
            "Model verdict",
        ),
        unsafe_allow_html=True,
    )
    if not rows:
        return
    df = pd.DataFrame(rows)
    fig = go.Figure(
        go.Bar(
            x=df["name"],
            y=df["risk_score"],
            marker_color=[VERDICT_COLOURS[v] for v in df["verdict"]],
            text=[
                f"{VERDICT_EMOJI[v]} {v}<br>{c:.0%}"
                for v, c in zip(df["verdict"], df["confidence"])
            ],
            textposition="outside",
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(
            title="Risk score (1=SAFE, 3=AVOID)",
            tickvals=[1, 2, 3],
            ticktext=["SAFE", "BORDERLINE", "AVOID"],
            range=[0, 3.5],
        ),
        xaxis_title="",
    )
    st.plotly_chart(fig, width="stretch")


# Adapted from Plotly Python docs - https://plotly.com/python/
# Draw a radar (polar) chart. Each trail becomes a colored shape with one
# corner per weather variable (temp, wind, precip, cloud, snowline). We
# normalise each value to a 0-100 scale so the shapes are comparable even
# though the original units are very different.
def render_radar_chart(rows: list[dict]) -> None:
    st.markdown(
        section_heading(
            "Weather profile",
            "Normalized indicators show why routes with similar grades can diverge on the same day.",
            "Forecast shape",
        ),
        unsafe_allow_html=True,
    )
    if not rows:
        return
    fig = go.Figure()
    categories = [label for _, label, *_ in RADAR_FIELDS]
    for r in rows:
        snap = r["snapshot"] or {}
        # Convert each weather number to a 0-100 score using the min and
        # max values we defined in RADAR_FIELDS. This way temperature in
        # degrees and wind in km/h can sit on the same chart together.
        normed = []
        for key, _, lo, hi in RADAR_FIELDS:
            val = snap.get(key)
            if val is None:
                normed.append(0)
            else:
                normed.append(max(0, min(1, (val - lo) / (hi - lo))) * 100)
        # A radar chart has to come back to its starting point to draw a
        # closed shape, so we add the first value to the end of the list.
        fig.add_trace(
            go.Scatterpolar(
                r=normed + [normed[0]],
                theta=categories + [categories[0]],
                fill="toself",
                name=r["name"],
            )
        )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        paper_bgcolor="rgba(0,0,0,0)",
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=-0.15),
    )
    st.plotly_chart(fig, width="stretch")


# Side-by-side comparison table and per-trail "open detail page" buttons.
def render_summary_table(rows: list[dict], target_date) -> None:
    st.markdown(
        section_heading(
            "Numbers side by side",
            "The raw weather and route attributes behind the visual comparison.",
            "Decision table",
        ),
        unsafe_allow_html=True,
    )
    if not rows:
        return
    # We build a plain list of dictionaries first. Pandas will then turn
    # that list straight into a table with one row per dictionary, which
    # is the easiest way to feed data into st.dataframe.
    table = []
    for r in rows:
        snap = r["snapshot"] or {}
        table.append(
            {
                "Trail": r["name"],
                "Grade": r["difficulty"],
                "Verdict": f"{VERDICT_EMOJI[r['verdict']]} {r['verdict']}",
                "Confidence": f"{r['confidence']:.0%}",
                "Temp °C": (
                    f"{snap.get('temp_c', 0):.1f}"
                    if snap.get("temp_c") is not None
                    else "—"
                ),
                "Wind km/h": (
                    f"{snap.get('wind_kmh', 0):.0f}"
                    if snap.get("wind_kmh") is not None
                    else "—"
                ),
                "Precip mm": (
                    f"{snap.get('precip_mm', 0):.1f}"
                    if snap.get("precip_mm") is not None
                    else "—"
                ),
                "Snowline m": (
                    f"{snap.get('snowline_m', 0):.0f}"
                    if snap.get("snowline_m") is not None
                    else "—"
                ),
                "Trail max m": r["max_alt_m"],
            }
        )
    st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)

    st.markdown(
        section_heading(
            "Open a trail detail page",
            "Jump from comparison into the full route page for maps, hazards and photos.",
        ),
        unsafe_allow_html=True,
    )
    # One "Open" button per trail. When clicked, we save the trail ID and
    # date into session state and switch over to the Trail Detail page.
    cols = st.columns(len(rows))
    for col, r in zip(cols, rows):
        if col.button(
            f"🏔️ {r['name']}",
            key=f"compare_open_{r['trail_id']}",
            width="stretch",
        ):
            # Streamlit pattern - https://docs.streamlit.io
            # Pass the trail and date to the Trail Detail page through
            # session state, then jump to it with switch_page.
            st.session_state["selected_trail_id"] = r["trail_id"]
            st.session_state["selected_date"] = target_date
            st.switch_page("pages/Trail_Detail.py")


# Page entry point. Composes the layout: hero, inputs, summary pills, charts, table.
def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    apply_app_theme()

    st.markdown(
        page_hero(
            "Compare trails",
            "Pit two to four routes against each other for the same day, then open the strongest candidate for full route detail.",
            "Route comparison",
        ),
        unsafe_allow_html=True,
    )

    all_trails = db_manager.get_all_trails()
    target_date, trail_ids = render_inputs(all_trails)

    # If the user picked fewer than 2 or more than 4 trails, we stop here
    # and show a friendly message instead of drawing an empty chart.
    if not (MIN_TRAILS <= len(trail_ids) <= MAX_TRAILS):
        st.info(
            f"Select between **{MIN_TRAILS}** and **{MAX_TRAILS}** trails to "
            "compare. Tip: use the search box to filter the dropdown."
        )
        return

    # The risk tolerance slider lives in the shared sidebar. It goes from
    # 1 (very cautious) to 5 (bold). If the user hasn't moved it yet, we
    # use 3 as a neutral default.
    risk = st.session_state.get("risk_tolerance", 3)
    rows = []
    aggregated_caveats: list[tuple[str, str]] = []
    # For each selected trail, we fetch the weather, predict a verdict, and
    # collect any safety caveats so we can show them as warnings later.
    for tid in trail_ids:
        trail = db_manager.get_trail(tid)
        snap = _snapshot_for(trail, target_date)
        caveats: list[str] = []
        if snap is None:
            verdict, conf = "—", 0.0
        else:
            verdict, conf, _, _ = predictions.predict_for_snapshot(
                snap, trail["max_alt_m"]
            )
            verdict, caveats = predictions.adjust_verdict(verdict, trail, snap, risk)
        for c in caveats:
            aggregated_caveats.append((trail["name"], c))
        rows.append(
            {
                "trail_id": tid,
                "name": trail["name"],
                "difficulty": trail["difficulty"],
                "max_alt_m": trail["max_alt_m"],
                "verdict": verdict if verdict != "—" else "BORDERLINE",
                "confidence": conf,
                "risk_score": VERDICT_SCORE.get(verdict, 2),
                "snapshot": snap,
            }
        )

    # Count how many trails fall into each verdict bucket so we can show
    # the small summary pills above the charts.
    verdict_counts = {}
    for row in rows:
        verdict_counts[row["verdict"]] = verdict_counts.get(row["verdict"], 0) + 1
    st.markdown(
        stat_pills_html(
            [
                ("selected routes", len(rows)),
                ("safe", verdict_counts.get("SAFE", 0)),
                ("borderline", verdict_counts.get("BORDERLINE", 0)),
                ("avoid", verdict_counts.get("AVOID", 0)),
            ]
        ),
        unsafe_allow_html=True,
    )

    for trail_name, caveat in aggregated_caveats:
        st.warning(f"⚠️ **{trail_name}** — {caveat}")

    render_bar_chart(rows)
    render_radar_chart(rows)
    render_summary_table(rows, target_date)


main()
