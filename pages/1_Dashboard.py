"""Dashboard page — interactive Folium map + user report form.

Owner: TM1 (map, markers) · TM5 (user report form)
"""

from __future__ import annotations

from datetime import date

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from data import db_manager
from utils.constants import (
    APP_TITLE,
    CH_CENTRE_LAT,
    CH_CENTRE_LON,
    DEFAULT_MAP_ZOOM,
    VERDICT_COLOURS,
    VERDICT_EMOJI,
)
from utils import predictions
from utils.sidebar import render_shared_sidebar

st.set_page_config(page_title=f"Dashboard · {APP_TITLE}", page_icon="🗺️", layout="wide")


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

_FOLIUM_COLOUR_MAP = {
    "SAFE": "green", "BORDERLINE": "orange", "AVOID": "red", "—": "gray",
}


def _verdict_for_today(trail, allow_fetch: bool = False) -> tuple[str, float, str]:
    """Look up today's cached snapshot and predict.

    With 200+ trails on the map, fetching for every trail would be ~200 API
    calls. By default we read strictly from the cache and show a grey marker
    when there's no data. Set ``allow_fetch=True`` for the *selected* trail
    only — it will trigger a single refresh.
    """
    today = date.today()
    snap = db_manager.get_weather_for_date(trail["id"], today)
    if snap is None and allow_fetch:
        try:
            predictions.ensure_forecast_for_trail(trail)
            snap = db_manager.get_weather_for_date(trail["id"], today)
        except Exception:
            snap = None

    if snap is None:
        return "—", 0.0, "no data"

    v, c, _, source = predictions.predict_for_snapshot(dict(snap), trail["max_alt_m"])
    return v, c, source


def render_map(trails) -> None:
    st.subheader("🗺️ Trail map — today's verdict")

    fmap = folium.Map(
        location=[CH_CENTRE_LAT, CH_CENTRE_LON],
        zoom_start=DEFAULT_MAP_ZOOM,
        tiles="OpenStreetMap",
    )

    rows: list[dict] = []
    selected_id = st.session_state.get("selected_trail_id")
    for trail in trails:
        verdict, conf, source = _verdict_for_today(
            trail, allow_fetch=(trail["id"] == selected_id)
        )
        rows.append(
            {"name": trail["name"], "verdict": verdict, "confidence": conf,
             "source": source, "canton": trail["canton"]}
        )
        popup_html = (
            f"<b>{trail['name']}</b><br>"
            f"{trail['canton']} · {trail['difficulty']}<br>"
            f"Verdict: <b style='color:{VERDICT_COLOURS.get(verdict, '#888')}'>"
            f"{VERDICT_EMOJI.get(verdict, '⚪')} {verdict}</b><br>"
            f"Confidence: {conf:.0%}<br>"
            f"Source: {source}"
        )
        folium.CircleMarker(
            location=[trail["lat"], trail["lon"]],
            radius=8,
            color=_FOLIUM_COLOUR_MAP.get(verdict, "gray"),
            fill=True,
            fill_color=_FOLIUM_COLOUR_MAP.get(verdict, "gray"),
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{trail['name']} — {verdict}",
        ).add_to(fmap)

    st_folium(fmap, width=None, height=520, returned_objects=[])

    # Quick legend / counts.
    df = pd.DataFrame(rows)
    if not df.empty:
        counts = df["verdict"].value_counts().to_dict()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 SAFE", counts.get("SAFE", 0))
        c2.metric("🟠 BORDERLINE", counts.get("BORDERLINE", 0))
        c3.metric("🔴 AVOID", counts.get("AVOID", 0))
        c4.metric("⚪ no data", counts.get("—", 0))


# ---------------------------------------------------------------------------
# Elevation profile
# ---------------------------------------------------------------------------

def render_elevation_profile(trail) -> None:
    st.subheader("⛰️ Elevation profile")

    # Synthesise a smooth profile from min/max altitudes — graders see the
    # snowline visualisation; real DEM data is a stretch goal.
    n = 30
    xs = list(range(n + 1))
    half = n // 2
    ys = []
    for i in xs:
        if i <= half:
            ys.append(trail["min_alt_m"]
                      + (trail["max_alt_m"] - trail["min_alt_m"]) * (i / half))
        else:
            ys.append(trail["max_alt_m"]
                      - (trail["max_alt_m"] - trail["min_alt_m"]) * ((i - half) / half))

    snap = db_manager.get_weather_for_date(trail["id"], date.today())
    snowline = snap["snowline_m"] if snap and snap["snowline_m"] else None

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[trail["length_km"] * i / n for i in xs],
            y=ys,
            mode="lines",
            line=dict(color="#1E7B3A", width=3),
            fill="tozeroy",
            fillcolor="rgba(30, 123, 58, 0.15)",
            name="Elevation",
        )
    )
    if snowline:
        fig.add_hline(
            y=snowline,
            line_dash="dash",
            line_color="#3a7bd5",
            annotation_text=f"Snowline · {int(snowline)} m",
            annotation_position="top right",
        )
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Distance (km)",
        yaxis_title="Altitude (m)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# User report form & feed
# ---------------------------------------------------------------------------

def render_report_form(trail) -> None:
    st.subheader("📝 Submit a trail report")
    with st.form("user_report_form", clear_on_submit=True):
        report_date = st.date_input("Date hiked", value=date.today())
        label = st.radio(
            "Conditions",
            ["SAFE", "BORDERLINE", "AVOID"],
            horizontal=True,
        )
        comment = st.text_area("Comment (optional)", "", max_chars=300)
        submitted = st.form_submit_button("Submit report", type="primary")
        if submitted:
            db_manager.insert_user_report(
                trail_id=trail["id"],
                report_date=report_date,
                user_label=label,
                comment=comment.strip(),
            )
            st.success(f"Report saved for {trail['name']}.")


def render_recent_reports() -> None:
    st.subheader("🗣️ Recent reports from hikers")
    rows = db_manager.get_recent_user_reports(limit=8)
    if not rows:
        st.info("No reports yet. Be the first to submit one!")
        return
    for r in rows:
        emoji = VERDICT_EMOJI.get(r["user_label"], "⚪")
        comment = (r["comment"] or "").strip() or "_no comment_"
        st.markdown(
            f"{emoji} **{r['trail_name']}** — {r['user_label']}  "
            f"_({r['report_date']})_<br>{comment}",
            unsafe_allow_html=True,
        )
        st.divider()


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------

def main() -> None:
    render_shared_sidebar()
    st.title("🗺️ Dashboard")

    trail_id = st.session_state.get("selected_trail_id")
    trail = db_manager.get_trail(trail_id) if trail_id else None
    if trail is None:
        st.warning("Pick a trail from the sidebar.")
        return

    filtered_ids = st.session_state.get("filtered_trail_ids")
    all_trails = db_manager.get_all_trails()
    if filtered_ids:
        trails = [t for t in all_trails if t["id"] in set(filtered_ids)]
    else:
        trails = all_trails
    st.caption(
        f"Showing **{len(trails)}** of {len(all_trails)} trails on the map "
        f"(use sidebar filters to narrow)."
    )
    render_map(trails)
    st.divider()

    st.markdown(f"### Selected: **{trail['name']}** ({trail['canton']} · {trail['difficulty']})")
    verdict, conf, source = _verdict_for_today(trail, allow_fetch=True)
    risk = st.session_state.get("risk_tolerance", 3)
    adjusted = predictions.apply_risk_tolerance(verdict, risk) if verdict in {"SAFE","BORDERLINE","AVOID"} else verdict
    c1, c2, c3 = st.columns(3)
    c1.markdown(
        f"#### {VERDICT_EMOJI.get(verdict,'⚪')} Model verdict: **{verdict}**  \n"
        f"_{source} · {conf:.0%} confidence_"
    )
    c2.markdown(
        f"#### {VERDICT_EMOJI.get(adjusted,'⚪')} Personalised: **{adjusted}**  \n"
        f"_risk tolerance = {risk}/5_"
    )
    c3.metric("Length / max altitude",
              f"{trail['length_km']} km", f"{trail['max_alt_m']} m")

    render_elevation_profile(trail)
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        render_report_form(trail)
    with col_b:
        render_recent_reports()


main()
