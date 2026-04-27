"""Forecast page — 7-day risk timeline + risk-tolerance slider.

Owner: TM2 (charts) · TM3 (forecast data) · Support: TM1 (slider logic)
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from data import db_manager
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS, VERDICT_EMOJI
from utils.sidebar import render_shared_sidebar

st.set_page_config(page_title=f"Forecast · {APP_TITLE}", page_icon="📈", layout="wide")


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def render_timeline_chart(df) -> None:
    st.subheader("📈 Next 7 days — weather")
    if df.empty:
        st.info("No forecast data yet. Click 🔄 Refresh weather in the sidebar.")
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=df["snapshot_date"], y=df["temp_c"],
            mode="lines+markers",
            name="Temp (°C)",
            line=dict(color="#C0392B", width=3),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df["snapshot_date"], y=df["wind_kmh"],
            mode="lines+markers",
            name="Wind (km/h)",
            line=dict(color="#3a7bd5", width=3, dash="dot"),
        ),
        secondary_y=True,
    )
    fig.add_trace(
        go.Bar(
            x=df["snapshot_date"], y=df["precip_mm"],
            name="Precip (mm)", opacity=0.55,
            marker_color="#1E7B3A",
        ),
        secondary_y=True,
    )
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=-0.2),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Temperature (°C)", secondary_y=False)
    fig.update_yaxes(title_text="Wind (km/h) · Precip (mm)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Verdict cards
# ---------------------------------------------------------------------------

def render_verdict_cards(df, trail, risk_tolerance: int) -> None:
    st.subheader("🚦 Daily verdicts")
    if df.empty:
        st.info("Refresh the cache to populate the forecast.")
        return

    cols = st.columns(len(df))
    for i, (col, row) in enumerate(zip(cols, df.itertuples(index=False))):
        snap = {
            "temp_c": row.temp_c,
            "wind_kmh": row.wind_kmh,
            "precip_mm": row.precip_mm,
            "snowline_m": row.snowline_m,
            "cloud_pct": row.cloud_pct,
        }
        verdict, conf, _, source = predictions.predict_for_snapshot(
            snap, trail["max_alt_m"]
        )
        adjusted = predictions.apply_risk_tolerance(verdict, risk_tolerance)
        colour = VERDICT_COLOURS[adjusted]
        with col:
            st.markdown(
                f"""
                <div style="background:{colour}; color:white; padding:14px;
                            border-radius:10px; text-align:center;">
                  <div style="font-size:0.85rem; opacity:0.9;">
                    {row.snapshot_date.strftime('%a %d %b')}
                  </div>
                  <div style="font-size:1.6rem;">
                    {VERDICT_EMOJI[adjusted]}
                  </div>
                  <div style="font-weight:700;">{adjusted}</div>
                  <div style="font-size:0.78rem; opacity:0.85;">
                    {conf:.0%} · {source}
                  </div>
                  <div style="font-size:0.75rem; margin-top:6px;">
                    {row.temp_c:.0f}°C · {row.wind_kmh:.0f} km/h
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Best-day banner
# ---------------------------------------------------------------------------

def render_best_day(df, trail, risk_tolerance: int) -> None:
    if df.empty:
        return
    scored = []
    for row in df.itertuples(index=False):
        snap = {
            "temp_c": row.temp_c, "wind_kmh": row.wind_kmh,
            "precip_mm": row.precip_mm, "snowline_m": row.snowline_m,
            "cloud_pct": row.cloud_pct,
        }
        v, c, _, _ = predictions.predict_for_snapshot(snap, trail["max_alt_m"])
        v = predictions.apply_risk_tolerance(v, risk_tolerance)
        score = (
            {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}[v] * 1.0
            - c * 0.1
        )
        scored.append((row.snapshot_date, v, c, score))
    scored.sort(key=lambda t: t[3])
    best_date, best_v, best_c, _ = scored[0]
    if best_v == "SAFE":
        st.success(
            f"**Best day to go:** {best_date.strftime('%A %d %B')} — "
            f"{best_v} ({best_c:.0%} confidence)."
        )
    elif best_v == "BORDERLINE":
        st.warning(
            f"**Best day this week:** {best_date.strftime('%A %d %B')} — "
            f"only {best_v}. Consider rescheduling."
        )
    else:
        st.error(
            f"No safe day in the next 7. Earliest watchable day: "
            f"{best_date.strftime('%A %d %B')} ({best_v})."
        )


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------

def main() -> None:
    render_shared_sidebar()
    st.title("📈 7-day forecast")

    trail_id = st.session_state.get("selected_trail_id")
    risk = st.session_state.get("risk_tolerance", 3)
    trail = db_manager.get_trail(trail_id) if trail_id else None
    if trail is None:
        st.warning("Pick a trail in the sidebar.")
        return

    try:
        predictions.ensure_forecast_for_trail(trail)
    except Exception as e:
        st.warning(f"Could not refresh forecast (offline?): {e}")

    df = predictions.get_seven_day_forecast(trail["id"])

    st.markdown(f"### {trail['name']}  ·  {trail['canton']}  ·  {trail['difficulty']}")
    render_best_day(df, trail, risk)
    render_timeline_chart(df)
    st.divider()
    render_verdict_cards(df, trail, risk)


main()
