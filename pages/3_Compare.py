"""Compare — pit 2-4 trails against each other for a chosen date.

Single, self-contained workflow:

    1. Pick the date (page-local — no sidebar entanglement).
    2. Pick 2-4 trails from a single multiselect.
    3. See bar chart, radar chart, summary table side-by-side.
    4. Open any of them in Trail Detail.

When the user lands here from a Trail Detail "Compare with…" button,
their preselected trail is added to the multiselect automatically.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import db_manager
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS, VERDICT_EMOJI
from utils.sidebar import render_shared_sidebar
from utils.topnav import render_top_nav
from utils.trail_detail import difficulty_dots_html

st.set_page_config(
    page_title=f"Compare · {APP_TITLE}", page_icon="🔀", layout="wide",
    initial_sidebar_state="collapsed",
)

MIN_TRAILS: int = 2
MAX_TRAILS: int = 4
FORECAST_HORIZON_DAYS: int = 6

VERDICT_SCORE = {"SAFE": 1, "BORDERLINE": 2, "AVOID": 3}
RADAR_FIELDS = [
    ("temp_c", "Temp", -10, 30),
    ("wind_kmh", "Wind", 0, 80),
    ("precip_mm", "Precip", 0, 30),
    ("cloud_pct", "Cloud", 0, 100),
    ("snowline_m", "Snowline", 1000, 4500),
]


def _snapshot_for(trail, target_date):
    """Cached snapshot for ``(trail, date)``; refresh once if missing."""
    snap = db_manager.get_weather_for_date(trail["id"], target_date)
    if snap is not None:
        return dict(snap)
    try:
        predictions.ensure_forecast_for_trail(trail)
    except Exception:
        return None
    snap = db_manager.get_weather_for_date(trail["id"], target_date)
    return dict(snap) if snap else None


def render_inputs(all_trails) -> tuple[date, list[int]]:
    """Render the date picker + trail multiselect. Returns (date, [trail_id])."""
    today = date.today()

    # Pre-seed the multiselect from session state (e.g. when arriving via
    # a "Compare with…" button from the Trail Detail page).
    options = {f"{t['name']}  ·  {t['canton']}  ·  {t['difficulty']}": t["id"]
               for t in all_trails}
    label_for_id = {tid: lbl for lbl, tid in options.items()}

    preselected_label = None
    seed_id = st.session_state.pop("compare_seed_trail_id", None)
    if seed_id and seed_id in label_for_id:
        preselected_label = label_for_id[seed_id]

    c1, c2 = st.columns([1, 3])
    with c1:
        chosen_date = st.date_input(
            "Date to compare",
            value=st.session_state.get("compare_date") or today,
            min_value=today,
            max_value=today + timedelta(days=FORECAST_HORIZON_DAYS),
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


def render_bar_chart(rows: list[dict]) -> None:
    st.subheader("📊 Predicted risk for the chosen date")
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
    st.plotly_chart(fig, use_container_width=True)


def render_radar_chart(rows: list[dict]) -> None:
    st.subheader("🕸️ Weather profile")
    if not rows:
        return
    fig = go.Figure()
    categories = [label for _, label, *_ in RADAR_FIELDS]
    for r in rows:
        snap = r["snapshot"] or {}
        normed = []
        for key, _, lo, hi in RADAR_FIELDS:
            val = snap.get(key)
            if val is None:
                normed.append(0)
            else:
                normed.append(max(0, min(1, (val - lo) / (hi - lo))) * 100)
        fig.add_trace(go.Scatterpolar(
            r=normed + [normed[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name=r["name"],
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=-0.15),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_summary_table(rows: list[dict], target_date) -> None:
    st.subheader("🔢 Numbers side-by-side")
    if not rows:
        return
    table = []
    for r in rows:
        snap = r["snapshot"] or {}
        table.append({
            "Trail": r["name"],
            "Grade": r["difficulty"],
            "Verdict": f"{VERDICT_EMOJI[r['verdict']]} {r['verdict']}",
            "Confidence": f"{r['confidence']:.0%}",
            "Temp °C": f"{snap.get('temp_c', 0):.1f}" if snap.get("temp_c") is not None else "—",
            "Wind km/h": f"{snap.get('wind_kmh', 0):.0f}" if snap.get("wind_kmh") is not None else "—",
            "Precip mm": f"{snap.get('precip_mm', 0):.1f}" if snap.get("precip_mm") is not None else "—",
            "Snowline m": f"{snap.get('snowline_m', 0):.0f}" if snap.get("snowline_m") is not None else "—",
            "Trail max m": r["max_alt_m"],
        })
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    st.markdown("##### Open a trail's detail page")
    cols = st.columns(len(rows))
    for col, r in zip(cols, rows):
        if col.button(
            f"🏔️ {r['name']}",
            key=f"compare_open_{r['trail_id']}",
            use_container_width=True,
        ):
            st.session_state["selected_trail_id"] = r["trail_id"]
            st.session_state["selected_date"] = target_date
            st.switch_page("pages/Trail_Detail.py")


def main() -> None:
    render_top_nav()
    render_shared_sidebar()

    st.title("🔀 Compare trails")
    st.caption(
        "Pit two to four trails against each other for the same day. "
        "Switch the date to see how the same hikes look later in the week."
    )

    all_trails = db_manager.get_all_trails()
    target_date, trail_ids = render_inputs(all_trails)

    if not (MIN_TRAILS <= len(trail_ids) <= MAX_TRAILS):
        st.info(
            f"Select between **{MIN_TRAILS}** and **{MAX_TRAILS}** trails to "
            "compare. Tip: use the search box to filter the dropdown."
        )
        return

    risk = st.session_state.get("risk_tolerance", 3)
    rows = []
    aggregated_caveats: list[tuple[str, str]] = []
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
            verdict, caveats = predictions.adjust_verdict(
                verdict, trail, snap, risk
            )
        for c in caveats:
            aggregated_caveats.append((trail["name"], c))
        rows.append({
            "trail_id": tid,
            "name": trail["name"],
            "difficulty": trail["difficulty"],
            "max_alt_m": trail["max_alt_m"],
            "verdict": verdict if verdict != "—" else "BORDERLINE",
            "confidence": conf,
            "risk_score": VERDICT_SCORE.get(verdict, 2),
            "snapshot": snap,
        })

    for trail_name, caveat in aggregated_caveats:
        st.warning(f"⚠️ **{trail_name}** — {caveat}")

    render_bar_chart(rows)
    render_radar_chart(rows)
    render_summary_table(rows, target_date)


main()
