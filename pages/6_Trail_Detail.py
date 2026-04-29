"""Trail Detail — sub-page rendered when the user clicks on a hike.

Reads ``selected_trail_id`` (and optionally ``selected_date``) from
``st.session_state``. Renders five tabs:

    * Overview     — key metrics + a snapshot card.
    * Route        — interactive folium map + elevation profile.
    * Tricky parts — rule-based hazards keyed off difficulty + weather.
    * Weather      — plain-English explanation of today's verdict.
    * Photos       — free-licensed images from Wikimedia Commons.
"""

from __future__ import annotations

from datetime import date

import folium
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from data import db_manager
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS, VERDICT_EMOJI
from utils.trail_detail import (
    analyse_tricky_sections,
    fetch_trail_images,
    interpret_weather,
    synthetic_route,
)

st.set_page_config(
    page_title=f"Trail · {APP_TITLE}", page_icon="🏔️", layout="wide"
)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def render_header(trail, snapshot, verdict: str, conf: float, source: str,
                  adjusted: str, target_date) -> None:
    colour = VERDICT_COLOURS.get(adjusted, "#888888")
    emoji = VERDICT_EMOJI.get(adjusted, "⚪")

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between;
                    align-items:center; gap:14px; flex-wrap:wrap;
                    border-left:8px solid {colour}; background:#fafafa;
                    padding:14px 18px; border-radius:8px;">
          <div>
            <div style="font-size:1.6rem; font-weight:700;">
              {trail['name']}
            </div>
            <div style="opacity:0.75;">
              {trail['canton']} · {trail['region']} ·
              {trail['difficulty']} ·
              {trail['length_km']} km · {trail['min_alt_m']}–{trail['max_alt_m']} m
            </div>
          </div>
          <div style="background:{colour}; color:white; padding:8px 16px;
                      border-radius:18px; font-weight:700; white-space:nowrap;">
            {emoji} {adjusted} · {conf:.0%}
            <div style="font-size:0.72rem; opacity:0.9;">
              {target_date.strftime('%a %d %b')} · {source}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

def tab_overview(trail, snapshot, verdict, conf, source) -> None:
    st.subheader("📍 At a glance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Length", f"{trail['length_km']} km")
    c2.metric("Max altitude", f"{trail['max_alt_m']} m")
    c3.metric("Elevation range",
              f"{trail['max_alt_m'] - trail['min_alt_m']} m",
              help="Difference between min and max altitude.")
    c4.metric("Difficulty (SAC)", trail["difficulty"])

    st.markdown("#### Today's snapshot")
    if snapshot is None:
        st.info("No cached weather snapshot for today. "
                "Refresh the weather from the sidebar of any other page.")
    else:
        a, b, c, d = st.columns(4)
        a.metric("🌡️ Temp",
                 f"{snapshot['temp_c']:.0f} °C" if snapshot.get("temp_c") is not None else "—")
        b.metric("💨 Wind",
                 f"{snapshot['wind_kmh']:.0f} km/h" if snapshot.get("wind_kmh") is not None else "—")
        c.metric("☔ Precip",
                 f"{snapshot['precip_mm']:.1f} mm" if snapshot.get("precip_mm") is not None else "—")
        d.metric("❄️ Snowline",
                 f"{int(snapshot['snowline_m'])} m" if snapshot.get("snowline_m") is not None else "—")

    st.caption(f"Verdict source: **{source}** · Confidence: **{conf:.0%}**")


def tab_route(trail) -> None:
    st.subheader("🗺️ Route on the map")
    st.caption(
        "Note: detailed GPX traces aren't bundled with the seeded trails, so "
        "the loop drawn here is **approximate** — a circle centred on the "
        "official start point with the same total length. Use it for "
        "orientation, not navigation."
    )

    pts = synthetic_route(trail["lat"], trail["lon"], trail["length_km"])
    fmap = folium.Map(
        location=[trail["lat"], trail["lon"]],
        zoom_start=13,
        tiles="OpenStreetMap",
    )
    folium.PolyLine(
        pts, color="#1E7B3A", weight=4, opacity=0.85,
        tooltip=f"≈{trail['length_km']} km loop",
    ).add_to(fmap)
    folium.Marker(
        [trail["lat"], trail["lon"]],
        tooltip=f"Start · {trail['name']}",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(fmap)

    # Highlight the conceptual "halfway" / summit point on the loop.
    half = pts[len(pts) // 2]
    folium.Marker(
        [half[0], half[1]],
        tooltip=f"Approx. summit · {trail['max_alt_m']} m",
        icon=folium.Icon(color="red", icon="flag", prefix="fa"),
    ).add_to(fmap)

    st_folium(fmap, width=None, height=480, returned_objects=[])

    st.markdown("#### ⛰️ Elevation profile")
    n = 30
    half_n = n // 2
    xs = list(range(n + 1))
    ys = [
        trail["min_alt_m"]
        + (trail["max_alt_m"] - trail["min_alt_m"])
        * (i / half_n if i <= half_n else (n - i) / half_n)
        for i in xs
    ]
    snap = db_manager.get_weather_for_date(trail["id"], date.today())
    snowline = snap["snowline_m"] if snap and snap["snowline_m"] else None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[trail["length_km"] * i / n for i in xs],
        y=ys,
        mode="lines",
        line=dict(color="#1E7B3A", width=3),
        fill="tozeroy",
        fillcolor="rgba(30, 123, 58, 0.15)",
        name="Elevation",
    ))
    if snowline:
        fig.add_hline(
            y=snowline, line_dash="dash", line_color="#3a7bd5",
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


def tab_tricky(trail, snapshot) -> None:
    st.subheader("⚠️ Tricky parts & what to pack")
    parts = analyse_tricky_sections(trail, snapshot)
    for p in parts:
        with st.container(border=True):
            st.markdown(
                f"**{p['icon']} {p['title']}**  "
                f"<span style='opacity:0.6; font-size:0.85rem;'> · {p['category']}</span>",
                unsafe_allow_html=True,
            )
            st.write(p["blurb"])


def tab_weather(trail, snapshot, verdict, adjusted) -> None:
    st.subheader("🌦️ Why is it considered " + (adjusted or "—") + "?")
    interp = interpret_weather(snapshot, trail, adjusted or verdict)

    if interp["headline"]:
        st.info(interp["headline"])

    with st.container(border=True):
        st.markdown("##### Top reasons")
        for b in interp["bullets"]:
            st.markdown(f"- {b}")

    st.markdown("##### Per-indicator breakdown")
    grid = st.columns(2)
    items = [
        ("🌡️ Temperature", interp["temp"]),
        ("💨 Wind", interp["wind"]),
        ("☔ Precipitation", interp["precip"]),
        ("☁️ Cloud cover", interp["cloud"]),
        ("❄️ Snowline vs. trail max", interp["snow"]),
    ]
    for i, (label, body) in enumerate(items):
        if not body:
            continue
        with grid[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.markdown(body)


def tab_photos(trail) -> None:
    st.subheader("📷 Pictures of the route")
    query = f"{trail['name']} {trail['canton']} hiking"
    with st.spinner("Searching Wikimedia Commons…"):
        images = fetch_trail_images(query, limit=4)
        if not images:
            # Fall back to just the trail name.
            images = fetch_trail_images(trail["name"], limit=4)

    if not images:
        st.info(
            f"No Commons photos found for *{trail['name']}*. "
            "Try clicking the trail name on Wikipedia for context, or "
            "submit your own via the user-report form."
        )
        return

    st.caption(
        "Photos pulled from Wikimedia Commons — click any image to see "
        "the original, photographer, and licence terms."
    )
    cols = st.columns(2)
    for i, img in enumerate(images):
        with cols[i % 2]:
            try:
                st.image(img["url"], use_container_width=True, caption=img["title"])
            except Exception:
                st.write(f"[{img['title']}]({img['page']})")
            st.markdown(
                f"<div style='font-size:0.8rem; opacity:0.7;'>"
                f"<a href='{img['page']}' target='_blank'>source ↗</a>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------

def main() -> None:
    trail_id = st.session_state.get("selected_trail_id")
    if trail_id is None:
        st.title("🏔️ Trail detail")
        st.warning(
            "No trail selected. Open the **🧭 Recommend**, **🔀 Compare**, or "
            "**🗺️ Dashboard** tab and click *View details* on any hike."
        )
        st.page_link("pages/5_Recommend.py", label="→ Go to Recommend", icon="🧭")
        return

    trail = db_manager.get_trail(trail_id)
    if trail is None:
        st.error(f"Trail #{trail_id} not found in the database.")
        return

    target_date = st.session_state.get("selected_date") or date.today()

    # Lazy-refresh the cache so we have something to interpret.
    try:
        predictions.ensure_forecast_for_trail(trail)
    except Exception:
        pass  # offline-friendly: we'll show a "no data" notice

    snap_row = db_manager.get_weather_for_date(trail["id"], target_date)
    snapshot = dict(snap_row) if snap_row else None

    if snapshot:
        verdict, conf, _, source = predictions.predict_for_snapshot(
            snapshot, trail["max_alt_m"]
        )
    else:
        verdict, conf, source = "—", 0.0, "no data"

    risk = st.session_state.get("risk_tolerance", 3)
    adjusted = (predictions.apply_risk_tolerance(verdict, risk)
                if verdict in {"SAFE", "BORDERLINE", "AVOID"} else verdict)

    render_header(trail, snapshot, verdict, conf, source, adjusted, target_date)

    nav_cols = st.columns(3)
    nav_cols[0].page_link("pages/5_Recommend.py", label="← Back to Recommend", icon="🧭")
    nav_cols[1].page_link("pages/2_Forecast.py", label="7-day forecast →", icon="📈")
    nav_cols[2].page_link("pages/3_Compare.py", label="Compare trails →", icon="🔀")

    overview, route, tricky, weather, photos = st.tabs(
        ["Overview", "Route map", "Tricky parts", "Weather", "Photos"]
    )
    with overview:
        tab_overview(trail, snapshot, verdict, conf, source)
    with route:
        tab_route(trail)
    with tricky:
        tab_tricky(trail, snapshot)
    with weather:
        tab_weather(trail, snapshot, verdict, adjusted)
    with photos:
        tab_photos(trail)


main()
