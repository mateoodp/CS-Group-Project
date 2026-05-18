"""Trail Detail page. The deep dive for a single hike on a single date.

This page reads ``selected_trail_id`` (and sometimes ``selected_date``)
from ``st.session_state``. The user gets here by clicking on a trail
card from Find, Map or Compare. It is not in the top navigation on
purpose, so there's no way to reach it without first picking a trail.

Page layout from top to bottom:

    1. Hero card with the trail name, SAC difficulty dots, four key
       stats, and the colored verdict chip.
    2. A date picker plus a "Compare with another trail" button.
    3. Five tabs:
        * Overview: quick stats and the weather snapshot for the day.
        * Route map: topographic map with a blue loop and hazard diamonds.
        * Tricky parts: rule-based cards highlighting safety concerns.
        * Weather: detailed verdict explanation, top vs bottom of trail,
                   7-day forecast cards, best-day banner, and a timeline.
        * Photos: free-licence photos pulled from Wikimedia Commons.
    4. At the bottom, a form to submit a personal trail report.
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
from utils.i18n import fmt_date, t, verdict_label
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

# Custom CSS that styles the hero card at the top, the floating verdict
# chip, and the altitude cards used inside the weather tab. Streamlit
# lets us inject CSS as a string when we set unsafe_allow_html=True.
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


# Build the big card at the top of the page. It shows the trail name,
# the SAC difficulty dots, four key stats (time, climb, length, max
# altitude) and the colored verdict chip floating on the right.
def render_header(trail, verdict_data: dict, target_date) -> None:
    # Pick the color and emoji that match this verdict. If the verdict is
    # missing or unknown we fall back to grey and a white circle dot.
    colour = VERDICT_COLOURS.get(verdict_data["adjusted"], "#888888")
    emoji = VERDICT_EMOJI.get(verdict_data["adjusted"], "⚪")
    ascent = trail["max_alt_m"] - trail["min_alt_m"]
    # Naismith's rule is a classic hiker formula for walking time, based on
    # the distance and how much you climb. It's only a rough estimate.
    time_est = naismith_time(trail["length_km"], ascent)

    st.markdown(_DETAIL_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="trail-hero">
          <span class="verdict-chip" style="--c:{colour};">
            {emoji} {verdict_label(verdict_data['adjusted'])} · {verdict_data['conf']:.0%}
            <span class="verdict-chip-sub">
              {fmt_date(target_date, 'short')} · {t(verdict_data['source'])}
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
              <div class="stat-label">{t("Estimated time")}</div>
            </div>
            <div>
              <div class="stat-value">{ascent} m</div>
              <div class="stat-label">{t("Ascent")}</div>
            </div>
            <div>
              <div class="stat-value">{trail['length_km']} km</div>
              <div class="stat-label">{t("Length")}</div>
            </div>
            <div>
              <div class="stat-value">{trail['max_alt_m']} m</div>
              <div class="stat-label">{t("Max altitude")}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_action_bar(trail, target_date) -> date:
    """Show the row of controls right under the hero card.

    From left to right: a date picker, a "Compare with..." button, a
    "Find more hikes" link, and a "Back to map" link. Returns the date
    the user picked in the date input.
    """
    today = date.today()
    # Streamlit pattern - https://docs.streamlit.io
    # Four columns side by side, one widget per column.
    bar_cols = st.columns([1.5, 1.5, 1, 1])

    with bar_cols[0]:
        chosen = st.date_input(
            t("📅 Date to assess"),
            value=target_date,
            min_value=today,
            max_value=today + timedelta(days=FORECAST_HORIZON_DAYS),
            key="trail_detail_date",
            help=t("Forecasts cover today + the next {n} days.",
                   n=FORECAST_HORIZON_DAYS),
        )

    with bar_cols[1]:
        st.markdown("&nbsp;", unsafe_allow_html=True)  # vertical alignment shim
        if st.button(
            t("🔀 Compare with another trail"),
            width="stretch",
            help=t("Opens Compare with {name} preselected.",
                   name=trail["name"]),
        ):
            # Streamlit pattern - https://docs.streamlit.io
            # Save the current trail and date in session state so the
            # Compare page can pick them up after we switch over to it.
            st.session_state["compare_seed_trail_id"] = trail["id"]
            st.session_state["compare_date"] = chosen
            st.switch_page("pages/3_Compare.py")

    with bar_cols[2]:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.page_link(
            "pages/1_Find.py",
            label=t("Find more hikes"),
            icon="🧭",
            width="stretch",
        )
    with bar_cols[3]:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.page_link("pages/2_Map.py", label=t("Back to map"), icon="🗺️",
                     width="stretch")

    return chosen


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------


# Overview tab. Shows four basic route stats at the top, then the
# weather snapshot for the chosen date below.
def tab_overview(trail, snapshot, verdict, conf, source) -> None:
    st.markdown(
        section_heading(
            t("At a glance"),
            t("Core route facts and the cached forecast snapshot for the selected date."),
            t("Overview"),
        ),
        unsafe_allow_html=True,
    )
    # Streamlit pattern - https://docs.streamlit.io
    # st.metric is the built-in widget for showing a single big number with
    # a small label underneath. It's perfect for headline stats like this.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("Length"), f"{trail['length_km']} km")
    c2.metric(t("Max altitude"), f"{trail['max_alt_m']} m")
    c3.metric(
        t("Elevation range"),
        f"{trail['max_alt_m'] - trail['min_alt_m']} m",
        help=t("Difference between min and max altitude."),
    )
    c4.metric(t("Difficulty (SAC)"), trail["difficulty"])

    # If we don't have weather data for this date in the local database,
    # show a hint to refresh the cache instead of leaving the section blank.
    st.markdown(t("#### Snapshot for this date"))
    if snapshot is None:
        st.info(
            t("No cached weather snapshot for this date. "
              "Use **🔄 Refresh weather** in the sidebar to fetch one.")
        )
    else:
        # Four small stat cards in a row: temperature, wind, precipitation,
        # and where the snow line is (the altitude above which snow stays).
        a, b, c, d = st.columns(4)
        a.metric(
            t("🌡️ Temp"),
            (
                f"{snapshot['temp_c']:.0f} °C"
                if snapshot.get("temp_c") is not None
                else "—"
            ),
        )
        b.metric(
            t("💨 Wind"),
            (
                f"{snapshot['wind_kmh']:.0f} km/h"
                if snapshot.get("wind_kmh") is not None
                else "—"
            ),
        )
        c.metric(
            t("☔ Precip"),
            (
                f"{snapshot['precip_mm']:.1f} mm"
                if snapshot.get("precip_mm") is not None
                else "—"
            ),
        )
        d.metric(
            t("❄️ Snowline"),
            (
                f"{int(snapshot['snowline_m'])} m"
                if snapshot.get("snowline_m") is not None
                else "—"
            ),
        )

    st.caption(t("Verdict source: **{source}** · Confidence: **{conf}**",
                 source=t(source), conf=f"{conf:.0%}"))


# Route map tab. Shows a topographic map with a fake loop drawn on top
# (since we don't have real GPX traces), plus warning diamonds for any
# hazards. Below the map we draw an elevation profile chart.
def tab_route(trail, snapshot) -> None:
    st.markdown(
        section_heading(
            t("Route on the map"),
            t("Approximate loop geometry with route context and hazard markers."),
            t("Map"),
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        t("Note: detailed GPX traces aren't bundled with the seeded trails, "
          "so the loop drawn here is **approximate** — a circle centred on "
          "the official start point with the same total length. Use it for "
          "orientation, not navigation.")
    )

    # Build a fake circular loop centered on the trail's start point. We
    # don't have real GPS traces for our trails, so this is just a visual
    # placeholder. The total perimeter matches the trail's listed length.
    pts = synthetic_route(trail["lat"], trail["lon"], trail["length_km"])
    # Adapted from folium docs - https://python-visualization.github.io/folium/
    # OpenTopoMap is a free topographic map style with contour lines, so
    # the user can see elevation changes around the trail.
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
    # Draw the approximate trail loop as a blue line on top of the map.
    folium.PolyLine(
        pts,
        color="#1f7ae0",
        weight=5,
        opacity=0.95,
        tooltip=t("≈{km} km loop", km=trail["length_km"]),
    ).add_to(fmap)
    # Drop a green "play" pin at the trail's official start point.
    folium.Marker(
        [trail["lat"], trail["lon"]],
        tooltip=t("Start · {name}", name=trail["name"]),
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(fmap)

    # Put a "summit" flag pin at the halfway point of our fake loop. The
    # real summit could be anywhere, but this is good enough as a hint.
    half = pts[len(pts) // 2]
    folium.Marker(
        [half[0], half[1]],
        tooltip=t("Summit · approx. {alt} m", alt=trail["max_alt_m"]),
        icon=folium.Icon(color="darkblue", icon="flag", prefix="fa"),
    ).add_to(fmap)

    # The hazard list comes from looking at the trail's grade and the
    # weather snapshot. Each hazard gets drawn as a diamond shape on the
    # map. Yellow means "caution", red means "serious hazard".
    hazards = hazard_points(pts, trail, snapshot)
    for h in hazards:
        bg = "#E69F00" if h["severity"] == "warn" else "#C0392B"
        # Adapted from folium docs - https://python-visualization.github.io/folium/
        # DivIcon is a folium feature that lets us draw any HTML we want
        # as a map marker. We rotate a square 45 degrees to make a diamond.
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
            + t("🟡 = caution · 🔴 = serious hazard. Hover any diamond on "
                "the map for details.")
            + "</div>",
            unsafe_allow_html=True,
        )

    # Adapted from folium docs - https://python-visualization.github.io/folium/
    # st_folium plugs a folium map into Streamlit. We pass returned_objects=[]
    # so that panning or zooming the map doesn't trigger a Streamlit rerun
    # (which would be wasteful and feel laggy to the user).
    st_folium(fmap, width=None, height=480, returned_objects=[])

    # Build a simple elevation profile chart. Because we don't have real
    # elevation data along the route, we fake it: climb from min altitude
    # up to the trail's max altitude, then back down. 30 sample points is
    # smooth enough for a chart but cheap to compute.
    st.markdown(t("#### ⛰️ Elevation profile"))
    n = 30
    half_n = n // 2
    xs = list(range(n + 1))
    ys = [
        trail["min_alt_m"]
        + (trail["max_alt_m"] - trail["min_alt_m"])
        * (i / half_n if i <= half_n else (n - i) / half_n)
        for i in xs
    ]
    # If we have today's snowline saved, we draw it as a dashed horizontal
    # line across the elevation chart. This makes it easy to see whether
    # the trail crosses into snow territory near its summit.
    snap = db_manager.get_weather_for_date(trail["id"], date.today())
    snowline = snap["snowline_m"] if snap and snap["snowline_m"] else None

    # Adapted from Plotly Python docs - https://plotly.com/python/
    # A filled area chart looks like a small mountain silhouette, which is
    # exactly what we want for an elevation profile. The snowline (if any)
    # gets added on top as a horizontal dashed line.
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[trail["length_km"] * i / n for i in xs],
            y=ys,
            mode="lines",
            line=dict(color="#1E7B3A", width=3),
            fill="tozeroy",
            fillcolor="rgba(30, 123, 58, 0.15)",
            name=t("Elevation"),
        )
    )
    if snowline:
        fig.add_hline(
            y=snowline,
            line_dash="dash",
            line_color="#3a7bd5",
            annotation_text=t("Snowline · {alt} m", alt=int(snowline)),
            annotation_position="top right",
        )
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=t("Distance (km)"),
        yaxis_title=t("Altitude (m)"),
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")


# Tricky parts tab. We loop through the list of hazard notes that
# analyse_tricky_sections returns and draw a small bordered card for each.
def tab_tricky(trail, snapshot) -> None:
    st.markdown(
        section_heading(
            t("Tricky parts and what to pack"),
            t("Terrain, weather and logistics notes generated from route grade and forecast conditions."),
            t("Safety notes"),
        ),
        unsafe_allow_html=True,
    )
    # This helper looks at the trail's difficulty grade and the day's
    # weather, then returns a list of safety notes worth showing.
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
# Weather tab. This is the most detailed tab. We pulled what used to be a
# separate Forecast page into here.
# ---------------------------------------------------------------------------


# Build the HTML for one of the altitude cards (the "top" or "bottom" of
# the trail). If we don't have a forecast for that altitude, we still
# return a card but with a friendly "no data" message inside.
def _altitude_card(label: str, alt_m: int, projected: dict | None) -> str:
    if not projected:
        return (
            f"<div class='alt-card'>"
            f"<h5>{label} · {alt_m} m</h5>"
            f"<div class='alt-row'>{t('No forecast cached for this day.')}</div>"
            f"</div>"
        )
    temp = projected.get("temp_c")
    wind = projected.get("wind_kmh")
    precip = projected.get("precip_mm")
    snowline = projected.get("snowline_m")

    # We build a few summary lines and skip any indicator we don't have
    # data for (so a missing wind reading doesn't print "None km/h").
    rows = []
    if wind is not None:
        rows.append(t("💨 {wind} km/h wind", wind=f"{wind:.0f}"))
    if precip is not None:
        rows.append(t("☔ {precip} mm precip", precip=f"{precip:.1f}"))
    if snowline is not None:
        # Compare the snowline to this card's altitude. If the snowline is
        # higher than the hiker, snow is "above" them. If lower, snow is
        # already where they'll be walking, which is more risky.
        margin = int(snowline) - alt_m
        marker = t("above") if margin >= 0 else t("below")
        rows.append(t("❄️ snowline {margin} m {marker} you",
                      margin=abs(margin), marker=marker))

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
    """Return up to 7 cached forecast rows starting from today (oldest first).

    We grab a wider 14-day window from the database first, then pick the
    next 7 days starting today. The extra cushion means a few missing
    rows still let us return a useful list of upcoming days.
    """
    # Pull the wider window first; we narrow it down to today + next 7 below.
    rows = db_manager.get_weather_history(trail_id, days=14)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    # Drop any past dates, sort the remaining ones in ascending order,
    # and keep the first seven (today plus the next six days).
    today = date.today()
    df = df[df["snapshot_date"] >= today].sort_values("snapshot_date").head(7)
    return df.reset_index(drop=True)


# Look at the upcoming 7 days and find the single best day to hike. The
# winning day is the one with the safest verdict, and among days with the
# same verdict, the one with the highest confidence. Then we show a banner
# with appropriate wording: green for SAFE, orange for BORDERLINE, red
# when even the best upcoming day is AVOID.
def _render_best_day(df, trail, risk: int) -> None:
    if df.empty:
        return
    grade = trail["difficulty"]
    # T4, T5, T6 routes are never displayed as SAFE no matter how good the
    # weather is. We change the banner wording to reflect that rule.
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
        # Build a single score so we can sort. The verdict matters most
        # (a SAFE day always beats a BORDERLINE one), and within the same
        # verdict we use confidence as a tiebreaker. Lower score is better.
        score = ({"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}[v] * 1.0) - c * 0.1
        scored.append((row.snapshot_date, v, c, score))
    scored.sort(key=lambda t: t[3])
    best_date, best_v, best_c, _ = scored[0]
    if best_v == "SAFE":
        st.success(
            t("🌟 **Best day to go:** {d} — {verdict} ({conf} confidence).",
              d=fmt_date(best_date, "long"),
              verdict=verdict_label(best_v),
              conf=f"{best_c:.0%}")
        )
    elif best_v == "BORDERLINE":
        msg = (
            t(" Note: {grade} routes are never marked SAFE; this is the "
              "best *weather*, not a safety endorsement.", grade=grade)
            if is_hard
            else t(" Consider rescheduling if you can.")
        )
        st.warning(
            t("🌗 **Best window this week:** {d} — BORDERLINE.{msg}",
              d=fmt_date(best_date, "long"), msg=msg)
        )
    else:
        st.error(
            t("⛔ No safe day in the next 7. Earliest watchable day: {d} "
              "({verdict}).",
              d=fmt_date(best_date, "long"), verdict=verdict_label(best_v))
        )


# Draw a small colored card for each of the next 7 days. The card uses the
# verdict color as its background. The day currently shown in the date
# picker gets a blue outline so the user can locate it at a glance.
def _render_seven_day_cards(df, trail, risk: int, target_date) -> None:
    st.markdown(t("##### Daily verdicts (next 7 days)"))
    if df.empty:
        st.info(t("Refresh the cache to populate the 7-day forecast."))
        return
    # Streamlit pattern - https://docs.streamlit.io
    # Create one column per day and drop a colored HTML card into each.
    cols = st.columns(len(df))
    for col, row in zip(cols, df.itertuples(index=False)):
        snap = {
            "temp_c": row.temp_c,
            "wind_kmh": row.wind_kmh,
            "precip_mm": row.precip_mm,
            "snowline_m": row.snowline_m,
            "cloud_pct": row.cloud_pct,
        }
        # First get the raw verdict from the model, then adjust it for the
        # user's risk tolerance and the trail's difficulty grade.
        verdict, conf, _, source = predictions.predict_for_snapshot(
            snap, trail["max_alt_m"]
        )
        adjusted, _ = predictions.adjust_verdict(verdict, trail, snap, risk)
        colour = VERDICT_COLOURS[adjusted]
        # If this card corresponds to the date the user is currently
        # looking at, we add a blue outline so it stands out.
        is_today = row.snapshot_date == target_date
        ring = "outline:3px solid #1f7ae0;" if is_today else ""
        with col:
            st.markdown(
                f"""
                <div style="background:{colour}; color:white; padding:12px 8px;
                            border-radius:10px; text-align:center; {ring}">
                  <div style="font-size:0.78rem; opacity:0.9;">
                    {fmt_date(row.snapshot_date, 'short')}
                  </div>
                  <div style="font-size:1.4rem; line-height:1;">
                    {VERDICT_EMOJI[adjusted]}
                  </div>
                  <div style="font-weight:700; font-size:0.88rem;">{verdict_label(adjusted)}</div>
                  <div style="font-size:0.72rem; opacity:0.85;">
                    {row.temp_c:.0f}°C · {row.wind_kmh:.0f} km/h
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.caption(t("Day with a blue outline = the date you're currently viewing above."))


# Adapted from Plotly Python docs - https://plotly.com/python/
# A bonus 7-day timeline chart, hidden inside an expander so it doesn't
# clutter the page. Temperature gets a red line on the left axis. Wind
# (blue dashed line) and precipitation (green bars) share the right axis.
def _render_timeline_chart(df) -> None:
    if df.empty:
        return
    with st.expander(t("📈 7-day timeline (temperature · wind · precip)"),
                     expanded=False):
        # make_subplots with secondary_y=True is the Plotly trick to put
        # two different y-axes (left and right) on the same chart. We
        # need this because temperature uses degrees but wind uses km/h.
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=df["snapshot_date"],
                y=df["temp_c"],
                mode="lines+markers",
                name=t("Temp (°C)"),
                line=dict(color="#C0392B", width=3),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=df["snapshot_date"],
                y=df["wind_kmh"],
                mode="lines+markers",
                name=t("Wind (km/h)"),
                line=dict(color="#3a7bd5", width=3, dash="dot"),
            ),
            secondary_y=True,
        )
        fig.add_trace(
            go.Bar(
                x=df["snapshot_date"],
                y=df["precip_mm"],
                name=t("Precip (mm)"),
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
        fig.update_yaxes(title_text=t("Temperature (°C)"), secondary_y=False)
        fig.update_yaxes(title_text=t("Wind (km/h) · Precip (mm)"),
                         secondary_y=True)
        st.plotly_chart(fig, width="stretch")


# Weather tab. The biggest tab in the page. From top to bottom it shows
# the verdict explanation, top vs bottom altitude weather cards, a
# per-indicator breakdown (temp, wind, precip, cloud, snow), the 7-day
# verdict cards, and the optional timeline chart.
def tab_weather(trail, snapshot, verdict, adjusted, target_date, risk) -> None:
    st.markdown(
        section_heading(
            t("Why is it considered {verdict}?",
              verdict=verdict_label(adjusted or "—")),
            t("The same verdict logic is broken down into readable weather and terrain signals."),
            t("Forecast explanation"),
        ),
        unsafe_allow_html=True,
    )
    # interpret_weather takes the raw numbers and turns them into plain
    # English text: a one-line headline, a few bullet points, and a small
    # note for each weather indicator.
    interp = interpret_weather(snapshot, trail, adjusted or verdict)

    if interp["headline"]:
        st.info(interp["headline"])

    # Top vs Bottom weather. The forecast Open-Meteo gives us is for a
    # single point. To give the user a feel for what it's like at the
    # bottom and top of the climb, we estimate both using the standard
    # lapse rate (air gets 6.5 degrees cooler per 1000 m of climb).
    st.markdown(t("##### Top vs. bottom weather"))
    st.caption(
        t("Forecasts are reported at one point. We project them to the "
          "trail's min and max altitudes using the standard lapse rate "
          "(−6.5 °C / 1000 m of climb). Treat as a guide, not a guarantee.")
    )
    bottom_proj = weather_at_altitude(
        snapshot, trail["min_alt_m"], reference_alt_m=trail["min_alt_m"]
    )
    top_proj = weather_at_altitude(
        snapshot, trail["max_alt_m"], reference_alt_m=trail["min_alt_m"]
    )
    col_top, col_bot = st.columns(2)
    col_top.markdown(
        _altitude_card(t("⛰️ Top of the trail"), trail["max_alt_m"], top_proj),
        unsafe_allow_html=True,
    )
    col_bot.markdown(
        _altitude_card(t("🌲 Bottom of the trail"), trail["min_alt_m"],
                       bottom_proj),
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(t("##### Top reasons"))
        for b in interp["bullets"]:
            st.markdown(f"- {b}")

    # A two-column grid of small bordered cards. One card per weather
    # indicator (temperature, wind, precip, cloud, snowline). Each card
    # shows a number plus a written takeaway in plain English.
    st.markdown(t("##### Per-indicator breakdown"))
    grid = st.columns(2)
    items = [
        (t("🌡️ Temperature"), interp["temp"]),
        (t("💨 Wind"), interp["wind"]),
        (t("☔ Precipitation"), interp["precip"]),
        (t("☁️ Cloud cover"), interp["cloud"]),
        (t("❄️ Snowline vs. trail max"), interp["snow"]),
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
            t("The whole week at a glance"),
            t("Use the seven-day outlook to find a better window if today looks mixed."),
            t("Forecast window"),
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        t("Use this to find the best day to go — verdicts here use the same "
          "safety logic as the headline above.")
    )
    # We compute the 7-day forecast dataframe once and pass it to three
    # different renderers. This way we don't query the database three
    # times for the same data.
    df = _seven_day_dataframe(trail["id"])
    _render_best_day(df, trail, risk)
    _render_seven_day_cards(df, trail, risk, target_date)
    _render_timeline_chart(df)


# Photos tab. We search Wikimedia Commons (a free, openly-licensed image
# library) for pictures of the route. Photos there are safe to display
# since they're explicitly licensed for reuse.
def tab_photos(trail) -> None:
    st.markdown(
        section_heading(
            t("Pictures of the route"),
            t("Free-licensed Wikimedia Commons images for visual context."),
            t("Photos"),
        ),
        unsafe_allow_html=True,
    )
    # First we try a more specific search ("trail name canton hiking") so
    # we get photos of the actual area. If that returns nothing, we fall
    # back to just the trail name as a broader query. The query stays in
    # English because Wikimedia Commons indexes most photos that way.
    query = f"{trail['name']} {trail['canton']} hiking"
    with st.spinner(t("Searching Wikimedia Commons…")):
        images = fetch_trail_images(query, limit=4)
        if not images:
            images = fetch_trail_images(trail["name"], limit=4)

    if not images:
        st.info(
            t("No Commons photos found for *{name}*. Try clicking the trail "
              "name on Wikipedia for context, or submit your own via the "
              "report form below.", name=trail["name"])
        )
        return

    st.caption(
        t("Photos pulled from Wikimedia Commons — click any image to see "
          "the original, photographer, and licence terms.")
    )
    # Two-column photo gallery. If for some reason an image URL fails to
    # load, we still show a clickable link to its Wikimedia page so the
    # user can see the photo there.
    cols = st.columns(2)
    for i, img in enumerate(images):
        with cols[i % 2]:
            try:
                st.image(img["url"], width="stretch", caption=img["title"])
            except Exception:
                st.write(f"[{img['title']}]({img['page']})")
            st.markdown(
                f"<div style='font-size:0.8rem; opacity:0.7;'>"
                f"<a href='{img['page']}' target='_blank'>{t('source ↗')}</a>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Bottom-of-page user report form
# ---------------------------------------------------------------------------


# The form at the bottom of the page where the user can submit their own
# report after hiking. Submissions go into the user_reports table. The
# next time the model is retrained, these reports are used as real labels
# (overriding the rule-based labels for those specific trail/date pairs),
# so the model can learn from actual hiker experience.
def render_report_form(trail) -> None:
    st.divider()
    st.markdown(
        section_heading(
            t("Hiked {name}? Submit a report", name=trail["name"]),
            t("Your report becomes ground truth on the next model retrain and helps verdicts improve."),
            t("Community signal"),
        ),
        unsafe_allow_html=True,
    )
    # Streamlit pattern - https://docs.streamlit.io
    # Wrapping the inputs in st.form means Streamlit waits until the user
    # clicks Submit before rerunning the page. Without a form, the page
    # would rerun after every keystroke or click, which would be wasteful.
    with st.form(f"user_report_form_{trail['id']}", clear_on_submit=True):
        c1, c2 = st.columns([1, 1])
        with c1:
            report_date = st.date_input(t("Date hiked"), value=date.today())
            # The radio keeps English option values (the database stores
            # them) but shows localised labels via format_func.
            label = st.radio(
                t("Conditions you found"),
                ["SAFE", "BORDERLINE", "AVOID"],
                horizontal=True,
                format_func=verdict_label,
            )
        with c2:
            comment = st.text_area(
                t("What was it like?"),
                "",
                max_chars=300,
                placeholder=t("e.g. 'Section above 2300 m had verglas — "
                              "needed crampons.'"),
            )
        submitted = st.form_submit_button(t("Submit report"), type="primary")
        if submitted:
            db_manager.insert_user_report(
                trail_id=trail["id"],
                report_date=report_date,
                user_label=label,
                comment=comment.strip(),
            )
            st.success(t("Report saved for {name}. Thank you 🙏",
                          name=trail["name"]))


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------


# Main function for the Trail Detail page. It figures out which trail to
# display, loads the weather, computes the verdict, then renders the
# header, the action bar, the five tabs and the report form at the bottom.
def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    apply_app_theme()

    # Streamlit pattern - https://docs.streamlit.io
    # Allow direct URL links like "?trail_id=5" to open this page on a
    # specific trail. We read the URL parameter and write it into session
    # state, which is what the rest of the page reads from.
    query_trail_id = trail_id_from_query_params(st.query_params)
    if query_trail_id is not None:
        st.session_state["selected_trail_id"] = query_trail_id

    trail_id = st.session_state.get("selected_trail_id")
    # No trail was selected. We can't render anything trail-specific, so
    # instead we show a friendly empty state with shortcuts to Find and Map.
    if trail_id is None:
        st.markdown(
            page_hero(
                t("Trail detail"),
                t("Choose a route from Find or Map to see forecast interpretation, route context, hazards and photos."),
                t("Route intelligence"),
            ),
            unsafe_allow_html=True,
        )
        st.warning(
            t("No trail selected yet. Open **🧭 Find a hike** for a "
              "quiz-based ranking, or **🗺️ Map** to browse all trails "
              "visually.")
        )
        c1, c2 = st.columns(2)
        c1.page_link("pages/1_Find.py", label=t("Go to Find a hike"),
                     icon="🧭")
        c2.page_link("pages/2_Map.py", label=t("Browse the map"), icon="🗺️")
        return

    trail = db_manager.get_trail(trail_id)
    if trail is None:
        st.error(t("Trail #{id} not found in the database.", id=trail_id))
        return

    # If the user arrived from another page with a date selected, use that.
    # Otherwise default to today.
    target_date = st.session_state.get("selected_date") or date.today()

    # Make sure we have a fresh forecast for this trail. If the network
    # is down or the API is busy, we silently move on. The rest of the
    # page will just show "no data" wherever the weather is missing, which
    # is better than crashing.
    try:
        predictions.ensure_forecast_for_trail(trail)
    except Exception:
        pass

    snap_row = db_manager.get_weather_for_date(trail["id"], target_date)
    snapshot = dict(snap_row) if snap_row else None

    # Only run the classifier if we actually have weather data. Otherwise
    # we set the verdict to the placeholder so the UI shows "no data".
    if snapshot:
        verdict, conf, _, source = predictions.predict_for_snapshot(
            snapshot, trail["max_alt_m"]
        )
    else:
        verdict, conf, source = "—", 0.0, "no data"

    # Now take the raw verdict from the model and adjust it. The user's
    # risk tolerance can shift it up or down by one step, and the trail's
    # SAC grade enforces hard safety rules (T4+ can never be SAFE, etc.).
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

    # If the difficulty rules overrode the verdict (for instance, a sunny
    # T6 route gets bumped down because the terrain is intrinsically
    # dangerous), we show the reason as a yellow warning under the hero.
    for c in caveats:
        st.warning(t("⚠️ **Safety lock:** {caveat}", caveat=c))

    # If the user picked a different date in the action bar, save the new
    # date in session state and rerun the page so the whole layout updates
    # to match (verdict, weather snapshot, tabs all change with the date).
    new_date = render_action_bar(trail, target_date)
    if new_date != target_date:
        st.session_state["selected_date"] = new_date
        st.rerun()

    # Streamlit pattern - https://docs.streamlit.io
    # The five tabs hold all the deep content for this trail. The user
    # can click between them without reloading the page.
    overview, route, weather, tricky, photos = st.tabs(
        [t("Overview"), t("Route map"), t("Weather"), t("Tricky parts"),
         t("Photos")]
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
