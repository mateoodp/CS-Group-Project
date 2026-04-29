"""Compare page — side-by-side comparison of 2–4 trails.

Owner: TM4 (ML + charts) · Support: TM5 (form)
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import db_manager
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS, VERDICT_EMOJI
from utils.sidebar import render_shared_sidebar

st.set_page_config(page_title=f"Compare · {APP_TITLE}", page_icon="🔀", layout="wide")

MIN_TRAILS: int = 2
MAX_TRAILS: int = 4

VERDICT_SCORE = {"SAFE": 1, "BORDERLINE": 2, "AVOID": 3}
RADAR_FIELDS = [
    ("temp_c", "Temp", -10, 30),
    ("wind_kmh", "Wind", 0, 80),
    ("precip_mm", "Precip", 0, 30),
    ("cloud_pct", "Cloud", 0, 100),
    ("snowline_m", "Snowline", 1000, 4500),
]


def _today_snapshot(trail_id: int):
    """Today's snapshot, refreshing the cache if needed."""
    snap = db_manager.get_weather_for_date(trail_id, date.today())
    if snap is not None:
        return dict(snap)
    trail = db_manager.get_trail(trail_id)
    try:
        predictions.ensure_forecast_for_trail(trail)
    except Exception:
        return None
    snap = db_manager.get_weather_for_date(trail_id, date.today())
    return dict(snap) if snap else None


def render_selector(trails) -> list[int]:
    options = {f"{t['name']} · {t['canton']}": t["id"] for t in trails}
    chosen = st.multiselect(
        f"Pick {MIN_TRAILS}–{MAX_TRAILS} trails",
        list(options.keys()),
        default=list(options.keys())[:3],
        max_selections=MAX_TRAILS,
    )
    return [options[c] for c in chosen]


def render_bar_chart(rows: list[dict]) -> None:
    st.subheader("📊 Today's predicted risk")
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


def render_summary_table(rows: list[dict]) -> None:
    st.subheader("🔢 Numbers side-by-side")
    if not rows:
        return
    table = []
    for r in rows:
        snap = r["snapshot"] or {}
        table.append({
            "Trail": r["name"],
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
        if col.button(f"🏔️ {r['name']}", key=f"compare_open_{r['trail_id']}",
                      use_container_width=True):
            st.session_state["selected_trail_id"] = r["trail_id"]
            st.switch_page("pages/6_Trail_Detail.py")


def main() -> None:
    render_shared_sidebar()
    st.title("🔀 Compare trails")

    filtered_ids = st.session_state.get("filtered_trail_ids")
    all_trails = db_manager.get_all_trails()
    trails = (
        [t for t in all_trails if t["id"] in set(filtered_ids)]
        if filtered_ids else all_trails
    )
    if filtered_ids:
        st.caption(
            f"Picking from **{len(trails)}** filtered trail(s). Adjust filters "
            "in the sidebar to widen the pool."
        )
    trail_ids = render_selector(trails)
    if not (MIN_TRAILS <= len(trail_ids) <= MAX_TRAILS):
        st.info(f"Select between {MIN_TRAILS} and {MAX_TRAILS} trails to compare.")
        return

    risk = st.session_state.get("risk_tolerance", 3)
    rows = []
    for tid in trail_ids:
        trail = db_manager.get_trail(tid)
        snap = _today_snapshot(tid)
        if snap is None:
            verdict, conf = "—", 0.0
        else:
            verdict, conf, _, _ = predictions.predict_for_snapshot(
                snap, trail["max_alt_m"]
            )
            verdict = predictions.apply_risk_tolerance(verdict, risk)
        rows.append({
            "trail_id": tid,
            "name": trail["name"],
            "max_alt_m": trail["max_alt_m"],
            "verdict": verdict if verdict != "—" else "BORDERLINE",
            "confidence": conf,
            "risk_score": VERDICT_SCORE.get(verdict, 2),
            "snapshot": snap,
        })

    render_bar_chart(rows)
    render_radar_chart(rows)
    render_summary_table(rows)


main()
