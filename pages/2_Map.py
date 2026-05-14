"""Map — drill-down view of Switzerland by canton then by trail.

Two states, gated by ``st.session_state["map_selected_canton"]``:

    * **Overview** — one bubble per canton, coloured by the average
      verdict of its trails for the chosen date, sized by trail count.
      A button grid below the map mirrors the action so users with
      flaky map clicks can still drill in.

    * **Drill-down** — when a canton is selected, the map zooms to that
      canton's bounding box and shows individual trails as markers. A
      "← Back to all cantons" button returns to the overview.
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
from utils.cantons import aggregate_by_canton, canton_label, CANTON_NAMES
from utils.data_health import ensure_weather_cached
from utils.sidebar import render_shared_sidebar
from utils.theme import apply_app_theme, page_hero, section_heading, stat_pills_html
from utils.topnav import render_top_nav

# Streamlit pattern - https://docs.streamlit.io
st.set_page_config(
    page_title=f"Map · {APP_TITLE}",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

FORECAST_HORIZON_DAYS: int = 6

# Map verdict labels to colour strings that folium's built-in palette understands.
# Adapted from folium docs - https://python-visualization.github.io/folium/
_FOLIUM_COLOUR_MAP = {
    "SAFE": "green",
    "BORDERLINE": "orange",
    "AVOID": "red",
    "—": "gray",
}


# ---------------------------------------------------------------------------
# Date control
# ---------------------------------------------------------------------------


def render_date_picker() -> date:
    """Page-local date picker for the map. Returns the chosen date."""
    # Open-Meteo only covers today + 6 days so we clamp the date range to match.
    today = date.today()
    chosen = st.date_input(
        "📅 Date to assess",
        value=st.session_state.get("map_date") or today,
        min_value=today,
        max_value=today + timedelta(days=FORECAST_HORIZON_DAYS),
        key="map_date_input",
        help=f"Forecasts cover today + the next {FORECAST_HORIZON_DAYS} days.",
    )
    st.session_state["map_date"] = chosen
    return chosen


# ---------------------------------------------------------------------------
# Overview view (cantons)
# ---------------------------------------------------------------------------


def render_canton_overview_map(canton_data: dict[str, dict]) -> str | None:
    """Folium map: one bubble per canton. Returns clicked-canton code or None."""
    # Adapted from folium docs - https://python-visualization.github.io/folium/
    # Map is centred on Switzerland; tile source is OpenStreetMap (free).
    fmap = folium.Map(
        location=[CH_CENTRE_LAT, CH_CENTRE_LON],
        zoom_start=DEFAULT_MAP_ZOOM,
        tiles="OpenStreetMap",
    )

    for code, d in sorted(canton_data.items()):
        colour = _FOLIUM_COLOUR_MAP.get(d["verdict"], "gray")
        # Radius scales with trail count (bigger canton = bigger bubble).
        radius = 12 + min(d["count"], 35) * 0.6
        coverage = (
            f"<br>Data coverage: {d['data_coverage_pct']:.0f}%"
            if d["data_coverage_pct"] < 100
            else ""
        )
        popup_html = (
            f"<b>{canton_label(code)}</b><br>"
            f"{d['count']} trails<br>"
            f"Average verdict: <b style='color:{VERDICT_COLOURS.get(d['verdict'], '#888')}'>"
            f"{VERDICT_EMOJI.get(d['verdict'], '⚪')} {d['verdict']}</b>"
            f"{coverage}<br>"
            f"<i>Click marker again or use the button below to drill in.</i>"
        )
        # CircleMarker is used (not Marker) so we can size it with trail count.
        folium.CircleMarker(
            location=[d["lat"], d["lon"]],
            radius=radius,
            color="#222",
            weight=1.5,
            fill=True,
            fill_color=colour,
            fill_opacity=0.78,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=code,  # used to capture click → drill-down
        ).add_to(fmap)

    # st_folium bridges click events from the browser back into Streamlit.
    # We only ask for the tooltip of the last-clicked object to keep payload small.
    out = st_folium(
        fmap,
        width=None,
        height=560,
        returned_objects=["last_object_clicked_tooltip"],
        key="canton_overview_map",
    )
    return (out or {}).get("last_object_clicked_tooltip")


def render_canton_button_grid(canton_data: dict[str, dict]) -> None:
    """Below-map fallback: buttons for every canton, coloured by verdict."""
    st.markdown(
        section_heading(
            "Drill into a canton",
            "Click any canton on the map or use these quick buttons to zoom into individual trails.",
            "Browse by region",
        ),
        unsafe_allow_html=True,
    )
    # Sort by trail count descending, then code alphabetically so the busiest
    # cantons land in the first row of the grid.
    cantons_sorted = sorted(
        canton_data.items(),
        key=lambda kv: (-(kv[1]["count"]), kv[0]),  # bigger first, then alpha
    )
    cols_per_row = 6
    # Compute the number of rows with ceiling division (no math.ceil dependency).
    rows_needed = (len(cantons_sorted) + cols_per_row - 1) // cols_per_row
    idx = 0
    for _ in range(rows_needed):
        cols = st.columns(cols_per_row)
        for c in cols:
            if idx >= len(cantons_sorted):
                continue
            code, d = cantons_sorted[idx]
            idx += 1
            emoji = VERDICT_EMOJI.get(d["verdict"], "⚪")
            label = f"{emoji} **{code}**  ·  {d['count']}"
            if c.button(label, key=f"canton_btn_{code}", width="stretch"):
                st.session_state["map_selected_canton"] = code
                st.rerun()


def render_summary_metrics(canton_data: dict[str, dict]) -> None:
    """Top-of-page tally of cantons by verdict."""
    counts = {"SAFE": 0, "BORDERLINE": 0, "AVOID": 0, "—": 0}
    for d in canton_data.values():
        counts[d["verdict"]] = counts.get(d["verdict"], 0) + 1
    st.markdown(
        stat_pills_html(
            [
                ("safe cantons", counts["SAFE"]),
                ("borderline cantons", counts["BORDERLINE"]),
                ("avoid cantons", counts["AVOID"]),
                ("no data", counts["—"]),
            ]
        ),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Drill-down view (trails of a single canton)
# ---------------------------------------------------------------------------


def _verdict_for_trail(trail, target_date: date) -> tuple[str, float]:
    """Cache lookup → (verdict, confidence)."""
    from utils import predictions  # local to avoid pandas import on cold load

    # Read-only: this map view never triggers fetches itself, so an empty
    # snapshot means we surface "no data" instead of stalling.
    snap = db_manager.get_weather_for_date(trail["id"], target_date)
    if snap is None:
        return "—", 0.0
    snap_dict = dict(snap)
    v, c, _, _ = predictions.predict_for_snapshot(snap_dict, trail["max_alt_m"])
    floored, _ = predictions.apply_difficulty_floor(v, trail, snap_dict)
    return floored, float(c)


def render_canton_drilldown_map(
    trails, canton_code: str, target_date: date
) -> str | None:
    """Folium map of one canton's trails. Returns clicked-trail name or None."""
    if not trails:
        st.info(f"No trails recorded for {canton_label(canton_code)}.")
        return None

    # Centre the map on the average position of the canton's trails.
    lats = [t["lat"] for t in trails]
    lons = [t["lon"] for t in trails]
    centre_lat = sum(lats) / len(lats)
    centre_lon = sum(lons) / len(lons)

    # Adapted from folium docs - https://python-visualization.github.io/folium/
    fmap = folium.Map(
        location=[centre_lat, centre_lon],
        zoom_start=10,
        tiles="OpenStreetMap",
    )
    # Auto-zoom to a bounding box that contains every marker (+ a small pad).
    fmap.fit_bounds(
        [
            [min(lats) - 0.05, min(lons) - 0.05],
            [max(lats) + 0.05, max(lons) + 0.05],
        ]
    )

    # One CircleMarker per trail, coloured by its predicted verdict.
    for t in trails:
        verdict, conf = _verdict_for_trail(t, target_date)
        colour = _FOLIUM_COLOUR_MAP.get(verdict, "gray")
        popup_html = (
            f"<b>{t['name']}</b><br>"
            f"{t['canton']} · {t['difficulty']} · {t['length_km']} km<br>"
            f"Verdict: <b style='color:{VERDICT_COLOURS.get(verdict, '#888')}'>"
            f"{VERDICT_EMOJI.get(verdict, '⚪')} {verdict}</b>"
            f"{f' · {conf:.0%}' if conf else ''}<br>"
            f"<i>Pick from the dropdown below to open the full trail page.</i>"
        )
        folium.CircleMarker(
            location=[t["lat"], t["lon"]],
            radius=8,
            color=colour,
            weight=1.5,
            fill=True,
            fill_color=colour,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=t["name"],
        ).add_to(fmap)

    out = st_folium(
        fmap,
        width=None,
        height=560,
        returned_objects=["last_object_clicked_tooltip"],
        key=f"drilldown_map_{canton_code}",
    )
    return (out or {}).get("last_object_clicked_tooltip")


def render_drilldown_picker(trails, target_date: date) -> None:
    """Below-map: dropdown to open a trail's detail page."""
    st.markdown(
        section_heading(
            "Open a trail detail page",
            "Pick a trail to see route notes, forecast interpretation, photos and reports.",
            "Trail selector",
        ),
        unsafe_allow_html=True,
    )
    options = {
        f"{t['name']}  ·  {t['difficulty']}  ·  {t['length_km']} km": t["id"]
        for t in trails
    }
    if not options:
        return
    chosen = st.selectbox(
        "Trail", list(options.keys()), index=0, key="drilldown_trail_select"
    )
    # Same pattern as the Find page: stash IDs in session_state then navigate.
    if st.button("→ Open trail detail", type="primary", width="stretch"):
        st.session_state["selected_trail_id"] = options[chosen]
        st.session_state["selected_date"] = target_date
        st.switch_page("pages/Trail_Detail.py")


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------


# Page entry: render nav, choose date, then either show the overview or drill-down.
def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    apply_app_theme()

    st.markdown(
        page_hero(
            "Trail map",
            "Browse Switzerland by canton, then zoom into individual trails with condition-aware colors for the date you choose.",
            "Map discovery",
        ),
        unsafe_allow_html=True,
    )

    # ---- Date picker (drives every colour on the page) ----
    chosen_date = render_date_picker()

    all_trails = db_manager.get_all_trails()

    # Auto-fetch any missing forecasts (4-worker pool, once per session).
    # Open-Meteo Forecast API - https://open-meteo.com/en/docs
    _, n_failed = ensure_weather_cached(
        all_trails, page_key="map", target_date=chosen_date
    )
    if n_failed:
        st.caption(
            f"⚠️ {n_failed} trail(s) couldn't be fetched (network blip or "
            "Open-Meteo rate-limit). Refresh the page to retry."
        )

    # Drill-down vs overview is driven by a single session_state key.
    selected = st.session_state.get("map_selected_canton")

    # ============================================================
    # Drill-down view
    # ============================================================
    if selected and selected in {t["canton"] for t in all_trails}:
        st.markdown(
            section_heading(
                f"Trails in {canton_label(selected)}",
                f"Showing every trail in {CANTON_NAMES.get(selected, selected)} for {chosen_date.strftime('%A %d %B %Y')}. Click a marker or use the selector below.",
                "Canton detail",
            ),
            unsafe_allow_html=True,
        )
        cols = st.columns([1, 4])
        if cols[0].button("← All cantons", width="stretch"):
            st.session_state["map_selected_canton"] = None
            st.rerun()

        canton_trails = [t for t in all_trails if t["canton"] == selected]
        clicked_trail_name = render_canton_drilldown_map(
            canton_trails, selected, chosen_date
        )
        if clicked_trail_name:
            match = next(
                (t for t in canton_trails if t["name"] == clicked_trail_name),
                None,
            )
            if match:
                st.session_state["selected_trail_id"] = match["id"]
                st.session_state["selected_date"] = chosen_date
                st.switch_page("pages/Trail_Detail.py")

        render_drilldown_picker(canton_trails, chosen_date)
        return

    # ============================================================
    # Canton overview view
    # ============================================================
    st.markdown(
        section_heading(
            "Canton overview",
            f"Each bubble is a Swiss canton, colored by the average trail verdict for {chosen_date.strftime('%A %d %B %Y')}. Bigger bubble means more trails.",
            "At a glance",
        ),
        unsafe_allow_html=True,
    )

    # Pre-aggregate trail counts and per-canton verdict for the chosen date.
    canton_data = aggregate_by_canton(all_trails, chosen_date)
    render_summary_metrics(canton_data)

    # If the user clicked a bubble, store the canton code and rerun in drill-down mode.
    clicked_canton = render_canton_overview_map(canton_data)
    if clicked_canton and clicked_canton in canton_data:
        st.session_state["map_selected_canton"] = clicked_canton
        st.rerun()

    render_canton_button_grid(canton_data)


main()
