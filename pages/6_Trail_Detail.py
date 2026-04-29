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
    difficulty_dots_html,
    fetch_trail_images,
    hazard_points,
    interpret_weather,
    naismith_time,
    synthetic_route,
    weather_at_altitude,
)

st.set_page_config(
    page_title=f"Trail · {APP_TITLE}", page_icon="🏔️", layout="wide"
)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

_DETAIL_CSS: str = """
<style>
  .trail-hero {
    background: #ffffff;
    border: 1px solid #e6e8eb;
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  }
  .trail-hero-title {
    font-size: 1.6rem; font-weight: 700; line-height: 1.2;
    color: #1a1a1a; margin-bottom: 4px;
  }
  .trail-hero-meta {
    color: #6b7177; font-size: 0.92rem; margin-bottom: 14px;
  }
  .trail-hero-stats {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 18px; padding-top: 14px;
    border-top: 1px solid #f0f1f3;
  }
  .stat-value { font-size: 1.1rem; font-weight: 600; color: #1a1a1a; }
  .stat-label { font-size: 0.78rem; color: #8b9197; margin-top: 2px; }
  .verdict-chip {
    float: right; background: var(--c, #888); color: white;
    padding: 6px 14px; border-radius: 999px;
    font-size: 0.85rem; font-weight: 600;
  }
  .verdict-chip-sub { display: block; font-size: 0.72rem; opacity: 0.85; }
  .alt-card {
    background: #ffffff; border: 1px solid #e6e8eb;
    border-radius: 12px; padding: 14px 16px;
  }
  .alt-card h5 { margin: 0 0 8px 0; font-size: 0.92rem; color: #4a4a4a; }
  .alt-card .alt-temp { font-size: 1.6rem; font-weight: 700; }
  .alt-card .alt-row { color: #6b7177; font-size: 0.88rem; margin-top: 4px; }
</style>
"""


def render_header(trail, snapshot, verdict: str, conf: float, source: str,
                  adjusted: str, target_date) -> None:
    colour = VERDICT_COLOURS.get(adjusted, "#888888")
    emoji = VERDICT_EMOJI.get(adjusted, "⚪")
    ascent = trail["max_alt_m"] - trail["min_alt_m"]
    time_est = naismith_time(trail["length_km"], ascent)

    st.markdown(_DETAIL_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="trail-hero">
          <span class="verdict-chip" style="--c:{colour};">
            {emoji} {adjusted} · {conf:.0%}
            <span class="verdict-chip-sub">
              {target_date.strftime('%a %d %b')} · {source}
            </span>
          </span>
          <div class="trail-hero-title">{trail['name']}</div>
          <div class="trail-hero-meta">
            {difficulty_dots_html(trail['difficulty'])}
            <span style="margin-left:10px;">
              · {trail['canton']} · {trail['region']}
            </span>
          </div>
          <div class="trail-hero-stats">
            <div>
              <div class="stat-value">{time_est}</div>
              <div class="stat-label">Estimated time</div>
            </div>
            <div>
              <div class="stat-value">{ascent} m</div>
              <div class="stat-label">Ascent</div>
            </div>
            <div>
              <div class="stat-value">{trail['length_km']} km</div>
              <div class="stat-label">Length</div>
            </div>
            <div>
              <div class="stat-value">{trail['max_alt_m']} m</div>
              <div class="stat-label">Max altitude</div>
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


def tab_route(trail, snapshot) -> None:
    st.subheader("🗺️ Route on the map")
    st.caption(
        "Note: detailed GPX traces aren't bundled with the seeded trails, so "
        "the loop drawn here is **approximate** — a circle centred on the "
        "official start point with the same total length. Use it for "
        "orientation, not navigation."
    )

    pts = synthetic_route(trail["lat"], trail["lon"], trail["length_km"])
    # OpenTopoMap gives us the same beige topographic look as the reference
    # design — contour lines, shaded relief, distinct trail routing.
    fmap = folium.Map(
        location=[trail["lat"], trail["lon"]],
        zoom_start=13,
        tiles="OpenTopoMap",
        attr=("Map data: © <a href='https://www.openstreetmap.org/copyright'>"
              "OpenStreetMap</a> contributors, SRTM | Map style: © "
              "<a href='https://opentopomap.org'>OpenTopoMap</a> "
              "(CC-BY-SA)"),
    )

    folium.PolyLine(
        pts,
        color="#1f7ae0",   # vivid blue, matching the reference route line
        weight=5,
        opacity=0.95,
        tooltip=f"≈{trail['length_km']} km loop",
    ).add_to(fmap)
    folium.Marker(
        [trail["lat"], trail["lon"]],
        tooltip=f"Start · {trail['name']}",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(fmap)

    half = pts[len(pts) // 2]
    folium.Marker(
        [half[0], half[1]],
        tooltip=f"Summit · approx. {trail['max_alt_m']} m",
        icon=folium.Icon(color="darkblue", icon="flag", prefix="fa"),
    ).add_to(fmap)

    # Yellow / red hazard diamonds keyed off difficulty + today's weather.
    hazards = hazard_points(pts, trail, snapshot)
    for i, h in enumerate(hazards, start=1):
        bg = "#E69F00" if h["severity"] == "warn" else "#C0392B"
        diamond = folium.DivIcon(html=(
            f"<div style='width:30px; height:30px; transform:rotate(45deg);"
            f"background:{bg}; border:2px solid #000;"
            f"display:flex; align-items:center; justify-content:center;'>"
            f"<span style='transform:rotate(-45deg); font-weight:700;"
            f"color:#000; font-size:14px;'>!</span></div>"
        ))
        folium.Marker(
            [h["lat"], h["lon"]],
            tooltip=h["label"],
            icon=diamond,
        ).add_to(fmap)

    if hazards:
        st.markdown(
            "<div style='font-size:0.85rem; color:#6b7177; margin:6px 0 8px;'>"
            "🟡 = caution · 🔴 = serious hazard. Hover any diamond on the map "
            "for details."
            "</div>",
            unsafe_allow_html=True,
        )

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


def _altitude_card(label: str, alt_m: int, projected: dict | None) -> str:
    """Build the HTML for one of the two altitude cards (top vs bottom)."""
    if not projected:
        return (
            f"<div class='alt-card'>"
            f"<h5>{label} · {alt_m} m</h5>"
            f"<div class='alt-row'>No forecast cached for this day.</div>"
            f"</div>"
        )
    temp = projected.get("temp_c")
    wind = projected.get("wind_kmh")
    precip = projected.get("precip_mm")
    snowline = projected.get("snowline_m")

    bottom_rows = []
    if wind is not None:
        bottom_rows.append(f"💨 {wind:.0f} km/h wind")
    if precip is not None:
        bottom_rows.append(f"☔ {precip:.1f} mm precip")
    if snowline is not None:
        margin = int(snowline) - alt_m
        marker = "above" if margin >= 0 else "below"
        bottom_rows.append(
            f"❄️ snowline {abs(margin)} m {marker} you"
        )

    rows_html = "".join(
        f"<div class='alt-row'>{r}</div>" for r in bottom_rows
    )
    temp_str = f"{temp:.0f}°C" if temp is not None else "—"
    return (
        f"<div class='alt-card'>"
        f"<h5>{label} · {alt_m} m</h5>"
        f"<div class='alt-temp'>{temp_str}</div>"
        f"{rows_html}"
        f"</div>"
    )


def tab_weather(trail, snapshot, verdict, adjusted) -> None:
    st.subheader("🌦️ Why is it considered " + (adjusted or "—") + "?")
    interp = interpret_weather(snapshot, trail, adjusted or verdict)

    if interp["headline"]:
        st.info(interp["headline"])

    # Top vs Bottom weather (lapse-rate projection).
    st.markdown("##### Top vs. bottom weather")
    st.caption(
        "Forecasts are reported at one point. We project them to the trail's "
        "minimum and maximum altitudes using the standard atmospheric lapse "
        "rate (−6.5 °C / 1000 m of climb). Treat as a guide, not a guarantee."
    )
    bottom_proj = weather_at_altitude(
        snapshot, trail["min_alt_m"], reference_alt_m=trail["min_alt_m"]
    )
    top_proj = weather_at_altitude(
        snapshot, trail["max_alt_m"], reference_alt_m=trail["min_alt_m"]
    )
    col_top, col_bot = st.columns(2)
    col_top.markdown(
        _altitude_card("⛰️ Top of the trail", trail["max_alt_m"], top_proj),
        unsafe_allow_html=True,
    )
    col_bot.markdown(
        _altitude_card("🌲 Bottom of the trail", trail["min_alt_m"], bottom_proj),
        unsafe_allow_html=True,
    )

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
    if verdict in {"SAFE", "BORDERLINE", "AVOID"}:
        adjusted, caveats = predictions.adjust_verdict(
            verdict, trail, snapshot, risk
        )
    else:
        adjusted, caveats = verdict, []

    render_header(trail, snapshot, verdict, conf, source, adjusted, target_date)

    for c in caveats:
        st.warning(f"⚠️ **Safety lock:** {c}")

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
        tab_route(trail, snapshot)
    with tricky:
        tab_tricky(trail, snapshot)
    with weather:
        tab_weather(trail, snapshot, verdict, adjusted)
    with photos:
        tab_photos(trail)


main()
