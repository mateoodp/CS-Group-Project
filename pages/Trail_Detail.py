"""Trail Detail — the deep page for a single hike on a single date.

Reads ``selected_trail_id`` (and optionally ``selected_date``) from
``st.session_state``. The page is reachable only by clicking a hike from
Find / Map / Compare — it doesn't appear in the top nav.

Layout:

    1. Hero card: trail name, SAC dots, 4-stat row, verdict chip.
    2. In-page date picker + "Compare with another trail" CTA.
    3. Five tabs:
        * Overview     — at-a-glance metrics and the day's snapshot.
        * Route map    — topo tiles, blue route, hazard diamonds.
        * Tricky parts — rule-based hazard cards.
        * Weather      — verdict explanation + Top/Bottom panel +
                         7-day cards + best-day banner + timeline.
        * Photos       — Wikimedia Commons.
    4. Bottom: the "submit a trail report" form (was on Map).
"""
# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from datetime import date, timedelta

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_folium import st_folium

from data import db_manager
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS, VERDICT_EMOJI
from utils.sidebar import render_shared_sidebar
from utils.theme import apply_app_theme, page_hero, section_heading
from utils.topnav import render_top_nav
from utils.route_images import trail_id_from_query_params
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

# Streamlit pattern - https://docs.streamlit.io
# Page metadata. Must be the first Streamlit call on the page.
st.set_page_config(
    page_title=f"Trail · {APP_TITLE}",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Open-Meteo's free forecast endpoint serves today + the next 6 days.
FORECAST_HORIZON_DAYS: int = 6


# ---------------------------------------------------------------------------
# Hero header
# ---------------------------------------------------------------------------

# Custom CSS for the hero card, verdict chip and altitude cards.
# Injected with unsafe_allow_html=True via the helper below.
_DETAIL_CSS: str = """
<style>
  .trail-hero {
    background: #ffffff;
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 30px;
    padding: 24px 26px;
    margin-bottom: 1rem;
    box-shadow: 0 24px 60px rgba(21, 39, 32, .1);
  }
  .trail-hero-title {
    font-size: clamp(2rem, 3.2vw, 3.6rem);
    font-weight: 850;
    line-height: 1;
    color: #14201c;
    margin-bottom: 10px;
    letter-spacing: 0;
  }
  .trail-hero-meta {
    color: #6b756f; font-size: 0.94rem; margin-bottom: 18px;
  }
  .trail-hero-stats {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 14px; padding-top: 18px;
    border-top: 1px solid #edf0ed;
  }
  .stat-value { font-size: 1.15rem; font-weight: 850; color: #14201c; }
  .stat-label {
    font-size: 0.76rem; color: #6b756f; margin-top: 3px;
    font-weight: 800; text-transform: uppercase;
  }
  .verdict-chip {
    float: right;
    background: var(--c, #888);
    color: white;
    padding: 8px 15px;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 850;
    box-shadow: 0 14px 28px rgba(21, 39, 32, .14);
  }
  .verdict-chip-sub { display: block; font-size: 0.72rem; opacity: 0.85; }
  .alt-card {
    background: #ffffff;
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 24px;
    padding: 16px 18px;
    box-shadow: 0 14px 34px rgba(21, 39, 32, .07);
  }
  .alt-card h5 { margin: 0 0 8px 0; font-size: 0.92rem; color: #4a4a4a; }
  .alt-card .alt-temp { font-size: 1.6rem; font-weight: 700; }
  .alt-card .alt-row { color: #6b7177; font-size: 0.88rem; margin-top: 4px; }
  @media (max-width: 900px) {
    .trail-hero-stats { grid-template-columns: repeat(2, 1fr); }
  }
</style>
"""


# Renders the big "hero" card at the top of the page: name, SAC dots,
# the four-stat grid (time, ascent, length, max altitude) and the verdict chip.
def render_header(trail, verdict_data: dict, target_date) -> None:
    # Look up colour + emoji for the verdict, defaulting to a neutral grey/dot.
    colour = VERDICT_COLOURS.get(verdict_data["adjusted"], "#888888")
    emoji = VERDICT_EMOJI.get(verdict_data["adjusted"], "⚪")
    ascent = trail["max_alt_m"] - trail["min_alt_m"]
    # Naismith's rule: rough walking time from distance and ascent.
    time_est = naismith_time(trail["length_km"], ascent)

    st.markdown(_DETAIL_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="trail-hero">
          <span class="verdict-chip" style="--c:{colour};">
            {emoji} {verdict_data['adjusted']} · {verdict_data['conf']:.0%}
            <span class="verdict-chip-sub">
              {target_date.strftime('%a %d %b')} · {verdict_data['source']}
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


def render_action_bar(trail, target_date) -> date:
    """Date picker + Compare-with + Back-to-Find. Returns chosen date."""
    today = date.today()
    # Streamlit pattern - https://docs.streamlit.io
    # Four columns: date picker, compare button, find-link, back-to-map link.
    bar_cols = st.columns([1.5, 1.5, 1, 1])

    with bar_cols[0]:
        chosen = st.date_input(
            "📅 Date to assess",
            value=target_date,
            min_value=today,
            max_value=today + timedelta(days=FORECAST_HORIZON_DAYS),
            key="trail_detail_date",
            help=f"Forecasts cover today + the next {FORECAST_HORIZON_DAYS} days.",
        )

    with bar_cols[1]:
        st.markdown("&nbsp;", unsafe_allow_html=True)  # vertical alignment shim
        if st.button(
            "🔀 Compare with another trail",
            width="stretch",
            help=f"Opens Compare with {trail['name']} preselected.",
        ):
            # Streamlit pattern - https://docs.streamlit.io
            # Hand off the current trail and date to the Compare page via session state.
            st.session_state["compare_seed_trail_id"] = trail["id"]
            st.session_state["compare_date"] = chosen
            st.switch_page("pages/3_Compare.py")

    with bar_cols[2]:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.page_link(
            "pages/1_Find.py",
            label="Find more hikes",
            icon="🧭",
            width="stretch",
        )
    with bar_cols[3]:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.page_link("pages/2_Map.py", label="Back to map", icon="🗺️", width="stretch")

    return chosen


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------


# Overview tab: four core route metrics on top, then the day's weather snapshot.
def tab_overview(trail, snapshot, verdict, conf, source) -> None:
    st.markdown(
        section_heading(
            "At a glance",
            "Core route facts and the cached forecast snapshot for the selected date.",
            "Overview",
        ),
        unsafe_allow_html=True,
    )
    # Streamlit pattern - https://docs.streamlit.io
    # Use st.metric for each headline number.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Length", f"{trail['length_km']} km")
    c2.metric("Max altitude", f"{trail['max_alt_m']} m")
    c3.metric(
        "Elevation range",
        f"{trail['max_alt_m'] - trail['min_alt_m']} m",
        help="Difference between min and max altitude.",
    )
    c4.metric("Difficulty (SAC)", trail["difficulty"])

    # If the cache has no row for the chosen date, prompt the user to refresh.
    st.markdown("#### Snapshot for this date")
    if snapshot is None:
        st.info(
            "No cached weather snapshot for this date. "
            "Use **🔄 Refresh weather** in the sidebar to fetch one."
        )
    else:
        # Four-up snapshot: temperature, wind, precipitation, snowline.
        a, b, c, d = st.columns(4)
        a.metric(
            "🌡️ Temp",
            (
                f"{snapshot['temp_c']:.0f} °C"
                if snapshot.get("temp_c") is not None
                else "—"
            ),
        )
        b.metric(
            "💨 Wind",
            (
                f"{snapshot['wind_kmh']:.0f} km/h"
                if snapshot.get("wind_kmh") is not None
                else "—"
            ),
        )
        c.metric(
            "☔ Precip",
            (
                f"{snapshot['precip_mm']:.1f} mm"
                if snapshot.get("precip_mm") is not None
                else "—"
            ),
        )
        d.metric(
            "❄️ Snowline",
            (
                f"{int(snapshot['snowline_m'])} m"
                if snapshot.get("snowline_m") is not None
                else "—"
            ),
        )

    st.caption(f"Verdict source: **{source}** · Confidence: **{conf:.0%}**")


# Route map tab: folium map with synthetic loop, hazard diamonds, plus elevation profile.
def tab_route(trail, snapshot) -> None:
    st.markdown(
        section_heading(
            "Route on the map",
            "Approximate loop geometry with route context and hazard markers.",
            "Map",
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        "Note: detailed GPX traces aren't bundled with the seeded trails, so "
        "the loop drawn here is **approximate** — a circle centred on the "
        "official start point with the same total length. Use it for "
        "orientation, not navigation."
    )

    # Build a synthetic circular route since real GPX traces aren't shipped.
    pts = synthetic_route(trail["lat"], trail["lon"], trail["length_km"])
    # Adapted from folium docs - https://python-visualization.github.io/folium/
    # OpenTopoMap tiles give a topographic context layer with contour lines.
    fmap = folium.Map(
        location=[trail["lat"], trail["lon"]],
        zoom_start=13,
        tiles="OpenTopoMap",
        attr=(
            "Map data: © <a href='https://www.openstreetmap.org/copyright'>"
            "OpenStreetMap</a> contributors, SRTM | Map style: © "
            "<a href='https://opentopomap.org'>OpenTopoMap</a> "
            "(CC-BY-SA)"
        ),
    )
    # Blue polyline = the (approximate) loop drawn on top of the topo tiles.
    folium.PolyLine(
        pts,
        color="#1f7ae0",
        weight=5,
        opacity=0.95,
        tooltip=f"≈{trail['length_km']} km loop",
    ).add_to(fmap)
    # Green play-button marker at the trail start.
    folium.Marker(
        [trail["lat"], trail["lon"]],
        tooltip=f"Start · {trail['name']}",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(fmap)

    # Drop a "summit" marker at the loop midpoint as a rough peak indicator.
    half = pts[len(pts) // 2]
    folium.Marker(
        [half[0], half[1]],
        tooltip=f"Summit · approx. {trail['max_alt_m']} m",
        icon=folium.Icon(color="darkblue", icon="flag", prefix="fa"),
    ).add_to(fmap)

    # Hazards are derived from the route shape, trail metadata and weather snapshot.
    # We render each as a rotated-square "diamond" with a yellow/red colour by severity.
    hazards = hazard_points(pts, trail, snapshot)
    for h in hazards:
        bg = "#E69F00" if h["severity"] == "warn" else "#C0392B"
        # Adapted from folium docs - https://python-visualization.github.io/folium/
        # DivIcon lets us inject raw HTML/CSS for a custom marker shape.
        diamond = folium.DivIcon(
            html=(
                f"<div style='width:30px; height:30px; transform:rotate(45deg);"
                f"background:{bg}; border:2px solid #000;"
                f"display:flex; align-items:center; justify-content:center;'>"
                f"<span style='transform:rotate(-45deg); font-weight:700;"
                f"color:#000; font-size:14px;'>!</span></div>"
            )
        )
        folium.Marker([h["lat"], h["lon"]], tooltip=h["label"], icon=diamond).add_to(
            fmap
        )

    if hazards:
        st.markdown(
            "<div style='font-size:0.85rem; color:#6b7177; margin:6px 0 8px;'>"
            "🟡 = caution · 🔴 = serious hazard. Hover any diamond on the map "
            "for details."
            "</div>",
            unsafe_allow_html=True,
        )

    # Adapted from folium docs - https://python-visualization.github.io/folium/
    # st_folium embeds the folium map in Streamlit; returned_objects=[] avoids reruns on pan/zoom.
    st_folium(fmap, width=None, height=480, returned_objects=[])

    # Synthetic elevation profile: triangle from min altitude up to max altitude and back.
    # n = 30 sample points keeps the chart smooth without being expensive.
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
    # Pull today's snowline (if cached) to draw a reference line on the profile.
    snap = db_manager.get_weather_for_date(trail["id"], date.today())
    snowline = snap["snowline_m"] if snap and snap["snowline_m"] else None

    # Adapted from Plotly Python docs - https://plotly.com/python/
    # Filled area chart for the elevation profile, with optional snowline overlay.
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
    st.plotly_chart(fig, width="stretch")


# Tricky parts tab: render a card per rule-based hazard/packing note.
def tab_tricky(trail, snapshot) -> None:
    st.markdown(
        section_heading(
            "Tricky parts and what to pack",
            "Terrain, weather and logistics notes generated from route grade and forecast conditions.",
            "Safety notes",
        ),
        unsafe_allow_html=True,
    )
    # Helper combines SAC grade thresholds with weather signals to surface notes.
    parts = analyse_tricky_sections(trail, snapshot)
    for p in parts:
        with st.container(border=True):
            st.markdown(
                f"**{p['icon']} {p['title']}**  "
                f"<span style='opacity:0.6; font-size:0.85rem;'> · {p['category']}</span>",
                unsafe_allow_html=True,
            )
            st.write(p["blurb"])


# ---------------------------------------------------------------------------
# Weather tab - merges the old Forecast page into Trail Detail
# ---------------------------------------------------------------------------


# Build the HTML for a single altitude card (top or bottom of trail).
# Returns an empty-state card when no forecast is available.
def _altitude_card(label: str, alt_m: int, projected: dict | None) -> str:
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

    # Build a small list of summary lines, skipping any indicator that is missing.
    rows = []
    if wind is not None:
        rows.append(f"💨 {wind:.0f} km/h wind")
    if precip is not None:
        rows.append(f"☔ {precip:.1f} mm precip")
    if snowline is not None:
        # Snowline relative to this card's altitude: positive = above hiker, negative = below.
        margin = int(snowline) - alt_m
        marker = "above" if margin >= 0 else "below"
        rows.append(f"❄️ snowline {abs(margin)} m {marker} you")

    rows_html = "".join(f"<div class='alt-row'>{r}</div>" for r in rows)
    temp_str = f"{temp:.0f}°C" if temp is not None else "—"
    return (
        f"<div class='alt-card'>"
        f"<h5>{label} · {alt_m} m</h5>"
        f"<div class='alt-temp'>{temp_str}</div>"
        f"{rows_html}"
        f"</div>"
    )


def _seven_day_dataframe(trail_id: int) -> pd.DataFrame:
    """Up to 7 cached forecast rows starting from today (oldest first)."""
    # Pull a 14-day window so we still get a useful 7-day slice even if a few rows are missing.
    rows = db_manager.get_weather_history(trail_id, days=14)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    # Keep today and forward only, then take the soonest seven days.
    today = date.today()
    df = df[df["snapshot_date"] >= today].sort_values("snapshot_date").head(7)
    return df.reset_index(drop=True)


# Scan the 7-day window, pick the day with the best (verdict, confidence) pair,
# and render an appropriate success/warning/error banner.
def _render_best_day(df, trail, risk: int) -> None:
    if df.empty:
        return
    grade = trail["difficulty"]
    # Hard alpine grades never get a SAFE call; we adjust the banner wording for them.
    is_hard = grade in {"T4", "T5", "T6"}
    scored = []
    for row in df.itertuples(index=False):
        snap = {
            "temp_c": row.temp_c,
            "wind_kmh": row.wind_kmh,
            "precip_mm": row.precip_mm,
            "snowline_m": row.snowline_m,
            "cloud_pct": row.cloud_pct,
        }
        v, c, _, _ = predictions.predict_for_snapshot(snap, trail["max_alt_m"])
        v, _ = predictions.adjust_verdict(v, trail, snap, risk)
        # Composite score: lower is better. Verdict dominates (0/1/2), confidence is a tiebreaker.
        score = ({"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}[v] * 1.0) - c * 0.1
        scored.append((row.snapshot_date, v, c, score))
    scored.sort(key=lambda t: t[3])
    best_date, best_v, best_c, _ = scored[0]
    if best_v == "SAFE":
        st.success(
            f"🌟 **Best day to go:** {best_date.strftime('%A %d %B')} — "
            f"{best_v} ({best_c:.0%} confidence)."
        )
    elif best_v == "BORDERLINE":
        msg = (
            (
                f" Note: {grade} routes are never marked SAFE; this is the best "
                "*weather*, not a safety endorsement."
            )
            if is_hard
            else " Consider rescheduling if you can."
        )
        st.warning(
            f"🌗 **Best window this week:** {best_date.strftime('%A %d %B')} — "
            f"BORDERLINE.{msg}"
        )
    else:
        st.error(
            f"⛔ No safe day in the next 7. Earliest watchable day: "
            f"{best_date.strftime('%A %d %B')} ({best_v})."
        )


# Render one coloured card per upcoming day. The currently-viewed date gets a blue outline.
def _render_seven_day_cards(df, trail, risk: int, target_date) -> None:
    st.markdown("##### Daily verdicts (next 7 days)")
    if df.empty:
        st.info("Refresh the cache to populate the 7-day forecast.")
        return
    # Streamlit pattern - https://docs.streamlit.io
    # One column per day; we splat a coloured HTML card into each.
    cols = st.columns(len(df))
    for col, row in zip(cols, df.itertuples(index=False)):
        snap = {
            "temp_c": row.temp_c,
            "wind_kmh": row.wind_kmh,
            "precip_mm": row.precip_mm,
            "snowline_m": row.snowline_m,
            "cloud_pct": row.cloud_pct,
        }
        # Predict raw verdict, then post-process for risk tolerance and SAC grade.
        verdict, conf, _, source = predictions.predict_for_snapshot(
            snap, trail["max_alt_m"]
        )
        adjusted, _ = predictions.adjust_verdict(verdict, trail, snap, risk)
        colour = VERDICT_COLOURS[adjusted]
        # Blue outline highlights the date currently selected in the action bar.
        is_today = row.snapshot_date == target_date
        ring = "outline:3px solid #1f7ae0;" if is_today else ""
        with col:
            st.markdown(
                f"""
                <div style="background:{colour}; color:white; padding:12px 8px;
                            border-radius:10px; text-align:center; {ring}">
                  <div style="font-size:0.78rem; opacity:0.9;">
                    {row.snapshot_date.strftime('%a %d %b')}
                  </div>
                  <div style="font-size:1.4rem; line-height:1;">
                    {VERDICT_EMOJI[adjusted]}
                  </div>
                  <div style="font-weight:700; font-size:0.88rem;">{adjusted}</div>
                  <div style="font-size:0.72rem; opacity:0.85;">
                    {row.temp_c:.0f}°C · {row.wind_kmh:.0f} km/h
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.caption("Day with a blue outline = the date you're currently viewing above.")


# Adapted from Plotly Python docs - https://plotly.com/python/
# Optional timeline (collapsed by default): temperature line, wind line on the
# secondary axis, and precipitation bars sharing the wind axis.
def _render_timeline_chart(df) -> None:
    if df.empty:
        return
    with st.expander("📈 7-day timeline (temperature · wind · precip)", expanded=False):
        # make_subplots with secondary_y lets us mix two y-scales on the same plot.
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=df["snapshot_date"],
                y=df["temp_c"],
                mode="lines+markers",
                name="Temp (°C)",
                line=dict(color="#C0392B", width=3),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=df["snapshot_date"],
                y=df["wind_kmh"],
                mode="lines+markers",
                name="Wind (km/h)",
                line=dict(color="#3a7bd5", width=3, dash="dot"),
            ),
            secondary_y=True,
        )
        fig.add_trace(
            go.Bar(
                x=df["snapshot_date"],
                y=df["precip_mm"],
                name="Precip (mm)",
                opacity=0.55,
                marker_color="#1E7B3A",
            ),
            secondary_y=True,
        )
        fig.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=-0.2),
            hovermode="x unified",
        )
        fig.update_yaxes(title_text="Temperature (°C)", secondary_y=False)
        fig.update_yaxes(title_text="Wind (km/h) · Precip (mm)", secondary_y=True)
        st.plotly_chart(fig, width="stretch")


# Weather tab: the deepest tab on the page. Stacks the verdict explanation,
# top/bottom altitude cards, per-indicator breakdown, 7-day cards and timeline.
def tab_weather(trail, snapshot, verdict, adjusted, target_date, risk) -> None:
    st.markdown(
        section_heading(
            f"Why is it considered {adjusted or '—'}?",
            "The same verdict logic is broken down into readable weather and terrain signals.",
            "Forecast explanation",
        ),
        unsafe_allow_html=True,
    )
    # interpret_weather translates the snapshot into headline + bullet points + per-indicator notes.
    interp = interpret_weather(snapshot, trail, adjusted or verdict)

    if interp["headline"]:
        st.info(interp["headline"])

    # Top vs Bottom weather (lapse-rate projection).
    # The reported forecast is one point. We project it to the trail's min/max altitudes
    # using a standard environmental lapse rate to give a feel for top-of-climb conditions.
    st.markdown("##### Top vs. bottom weather")
    st.caption(
        "Forecasts are reported at one point. We project them to the trail's "
        "min and max altitudes using the standard lapse rate "
        "(−6.5 °C / 1000 m of climb). Treat as a guide, not a guarantee."
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

    # Two-column grid of small cards: one per weather indicator with a written takeaway.
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

    st.divider()
    st.markdown(
        section_heading(
            "The whole week at a glance",
            "Use the seven-day outlook to find a better window if today looks mixed.",
            "Forecast window",
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        "Use this to find the best day to go — verdicts here use the same "
        "safety logic as the headline above."
    )
    # Build the 7-day forecast frame once, then drive three downstream renderers.
    df = _seven_day_dataframe(trail["id"])
    _render_best_day(df, trail, risk)
    _render_seven_day_cards(df, trail, risk, target_date)
    _render_timeline_chart(df)


# Photos tab: query Wikimedia Commons for free-licence pictures of the route.
def tab_photos(trail) -> None:
    st.markdown(
        section_heading(
            "Pictures of the route",
            "Free-licensed Wikimedia Commons images for visual context.",
            "Photos",
        ),
        unsafe_allow_html=True,
    )
    # First try a richer query with canton + hiking, then fall back to bare trail name.
    query = f"{trail['name']} {trail['canton']} hiking"
    with st.spinner("Searching Wikimedia Commons…"):
        images = fetch_trail_images(query, limit=4)
        if not images:
            images = fetch_trail_images(trail["name"], limit=4)

    if not images:
        st.info(
            f"No Commons photos found for *{trail['name']}*. "
            "Try clicking the trail name on Wikipedia for context, or "
            "submit your own via the report form below."
        )
        return

    st.caption(
        "Photos pulled from Wikimedia Commons — click any image to see "
        "the original, photographer, and licence terms."
    )
    # Two-column gallery. Fall back to a hyperlink if the image fails to load.
    cols = st.columns(2)
    for i, img in enumerate(images):
        with cols[i % 2]:
            try:
                st.image(img["url"], width="stretch", caption=img["title"])
            except Exception:
                st.write(f"[{img['title']}]({img['page']})")
            st.markdown(
                f"<div style='font-size:0.8rem; opacity:0.7;'>"
                f"<a href='{img['page']}' target='_blank'>source ↗</a>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Bottom-of-page user report form
# ---------------------------------------------------------------------------


# User report form. Submissions are written to the user_reports table and act
# as ground-truth labels next time the Random Forest is retrained.
def render_report_form(trail) -> None:
    st.divider()
    st.markdown(
        section_heading(
            f"Hiked {trail['name']}? Submit a report",
            "Your report becomes ground truth on the next model retrain and helps verdicts improve.",
            "Community signal",
        ),
        unsafe_allow_html=True,
    )
    # Streamlit pattern - https://docs.streamlit.io
    # st.form batches inputs until the user clicks submit, avoiding partial reruns.
    with st.form(f"user_report_form_{trail['id']}", clear_on_submit=True):
        c1, c2 = st.columns([1, 1])
        with c1:
            report_date = st.date_input("Date hiked", value=date.today())
            label = st.radio(
                "Conditions you found",
                ["SAFE", "BORDERLINE", "AVOID"],
                horizontal=True,
            )
        with c2:
            comment = st.text_area(
                "What was it like?",
                "",
                max_chars=300,
                placeholder="e.g. 'Section above 2300 m had verglas — needed crampons.'",
            )
        submitted = st.form_submit_button("Submit report", type="primary")
        if submitted:
            db_manager.insert_user_report(
                trail_id=trail["id"],
                report_date=report_date,
                user_label=label,
                comment=comment.strip(),
            )
            st.success(f"Report saved for {trail['name']}. Thank you 🙏")


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------


# Page entry point. Resolves which trail to show, loads weather, computes the
# verdict, and stitches together the header, action bar, tabs and report form.
def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    apply_app_theme()

    # Streamlit pattern - https://docs.streamlit.io
    # Support deep links: ?trail=<id> in the URL pre-populates session state.
    query_trail_id = trail_id_from_query_params(st.query_params)
    if query_trail_id is not None:
        st.session_state["selected_trail_id"] = query_trail_id

    trail_id = st.session_state.get("selected_trail_id")
    # No trail context: render an empty-state hero with shortcuts back into Find/Map.
    if trail_id is None:
        st.markdown(
            page_hero(
                "Trail detail",
                "Choose a route from Find or Map to see forecast interpretation, route context, hazards and photos.",
                "Route intelligence",
            ),
            unsafe_allow_html=True,
        )
        st.warning(
            "No trail selected yet. Open **🧭 Find a hike** for a quiz-based "
            "ranking, or **🗺️ Map** to browse all trails visually."
        )
        c1, c2 = st.columns(2)
        c1.page_link("pages/1_Find.py", label="Go to Find a hike", icon="🧭")
        c2.page_link("pages/2_Map.py", label="Browse the map", icon="🗺️")
        return

    trail = db_manager.get_trail(trail_id)
    if trail is None:
        st.error(f"Trail #{trail_id} not found in the database.")
        return

    # Date defaults to today unless the user came in with a specific date selected.
    target_date = st.session_state.get("selected_date") or date.today()

    # Lazily ensure we have a forecast row for this trail; swallow errors when offline.
    try:
        predictions.ensure_forecast_for_trail(trail)
    except Exception:
        pass  # offline-friendly: show "no data" downstream

    snap_row = db_manager.get_weather_for_date(trail["id"], target_date)
    snapshot = dict(snap_row) if snap_row else None

    # Run the classifier (or rule fallback) only when we actually have a snapshot.
    if snapshot:
        verdict, conf, _, source = predictions.predict_for_snapshot(
            snapshot, trail["max_alt_m"]
        )
    else:
        verdict, conf, source = "—", 0.0, "no data"

    # Post-process the raw verdict against risk tolerance and hard SAC grades.
    risk = st.session_state.get("risk_tolerance", 3)
    if verdict in {"SAFE", "BORDERLINE", "AVOID"}:
        adjusted, caveats = predictions.adjust_verdict(verdict, trail, snapshot, risk)
    else:
        adjusted, caveats = verdict, []

    render_header(
        trail,
        {"verdict": verdict, "adjusted": adjusted, "conf": conf, "source": source},
        target_date,
    )

    # Surface any "safety lock" notes raised by adjust_verdict (e.g. T6 routes never SAFE).
    for c in caveats:
        st.warning(f"⚠️ **Safety lock:** {c}")

    # If the user changed the date in the action bar, persist it and rerun.
    new_date = render_action_bar(trail, target_date)
    if new_date != target_date:
        st.session_state["selected_date"] = new_date
        st.rerun()

    # Streamlit pattern - https://docs.streamlit.io
    # Five tabs hold the deep content for this trail.
    overview, route, weather, tricky, photos = st.tabs(
        ["Overview", "Route map", "Weather", "Tricky parts", "Photos"]
    )
    with overview:
        tab_overview(trail, snapshot, verdict, conf, source)
    with route:
        tab_route(trail, snapshot)
    with weather:
        tab_weather(trail, snapshot, verdict, adjusted, target_date, risk)
    with tricky:
        tab_tricky(trail, snapshot)
    with photos:
        tab_photos(trail)

    render_report_form(trail)


main()
