"""Map page. Lets the user explore Switzerland by canton, then by trail.

The page has two views. Which one shows up depends on whether a canton
has been chosen, which we track using ``st.session_state["map_selected_canton"]``:

    * Overview view: one bubble per canton on the Swiss map. The color
      shows the average verdict for that canton on the chosen date, and
      the size shows how many trails it has. A grid of buttons under the
      map does the same thing in case the map clicks are not responsive.

    * Drill-down view: once a canton is selected, the map zooms in and
      shows that canton's individual trails as markers. The user can go
      back to the overview with the back button.
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
from utils.i18n import fmt_date, t, verdict_label
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

# Folium's marker palette only accepts specific color names, so we translate
# our verdict labels into the closest matching folium color.
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
    """Show a date picker just for this page. Returns the date the user picked."""
    # The Open-Meteo free forecast only covers today and the next 6 days, so
    # we restrict the date picker to that window. Anything outside would have
    # no weather data for us to use.
    today = date.today()
    chosen = st.date_input(
        t("📅 Date to assess"),
        value=st.session_state.get("map_date") or today,
        min_value=today,
        max_value=today + timedelta(days=FORECAST_HORIZON_DAYS),
        key="map_date_input",
        help=t("Forecasts cover today + the next {n} days.",
               n=FORECAST_HORIZON_DAYS),
    )
    st.session_state["map_date"] = chosen
    return chosen


# ---------------------------------------------------------------------------
# Overview view (cantons)
# ---------------------------------------------------------------------------


def render_canton_overview_map(canton_data: dict[str, dict]) -> str | None:
    """Draw the Switzerland map with one bubble per canton.

    Returns the code of the canton the user clicked, or None if they
    didn't click on anything.
    """
    # Adapted from folium docs - https://python-visualization.github.io/folium/
    # We start the map centered on Switzerland. OpenStreetMap is the free
    # default tile provider, no API key needed.
    fmap = folium.Map(
        location=[CH_CENTRE_LAT, CH_CENTRE_LON],
        zoom_start=DEFAULT_MAP_ZOOM,
        tiles="OpenStreetMap",
    )

    for code, d in sorted(canton_data.items()):
        colour = _FOLIUM_COLOUR_MAP.get(d["verdict"], "gray")
        # The bubble grows when the canton has more trails. We cap it at 35
        # trails so big cantons don't draw a huge bubble that covers others.
        radius = 12 + min(d["count"], 35) * 0.6
        coverage = (
            f"<br>{t('Data coverage')}: {d['data_coverage_pct']:.0f}%"
            if d["data_coverage_pct"] < 100
            else ""
        )
        popup_html = (
            f"<b>{canton_label(code)}</b><br>"
            f"{t('{count} trails', count=d['count'])}<br>"
            f"{t('Average verdict')}: <b style='color:{VERDICT_COLOURS.get(d['verdict'], '#888')}'>"
            f"{VERDICT_EMOJI.get(d['verdict'], '⚪')} {verdict_label(d['verdict'])}</b>"
            f"{coverage}<br>"
            f"<i>{t('Click marker again or use the button below to drill in.')}</i>"
        )
        # We use CircleMarker (not the default Marker pin) because we want
        # to control the size of the bubble based on trail count.
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

    # st_folium is the helper that connects folium maps with Streamlit. It
    # sends click events from the browser back to Python. We only ask for
    # the tooltip of the last thing the user clicked, to keep things fast.
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
            t("Drill into a canton"),
            t("Click any canton on the map or use these quick buttons to zoom into individual trails."),
            t("Browse by region"),
        ),
        unsafe_allow_html=True,
    )
    # Sort cantons so the ones with the most trails come first. If two
    # cantons have the same count, we sort them alphabetically. This way
    # the most useful buttons are always on the first row of the grid.
    cantons_sorted = sorted(
        canton_data.items(),
        key=lambda kv: (-(kv[1]["count"]), kv[0]),  # most trails first, then by code
    )
    cols_per_row = 6
    # Work out how many rows of buttons we need. We use integer math to
    # round up instead of importing math.ceil just for one calculation.
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
                (t("safe cantons"), counts["SAFE"]),
                (t("borderline cantons"), counts["BORDERLINE"]),
                (t("avoid cantons"), counts["AVOID"]),
                (t("no data"), counts["—"]),
            ]
        ),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Drill-down view (trails of a single canton)
# ---------------------------------------------------------------------------


def _verdict_for_trail(trail, target_date: date) -> tuple[str, float]:
    """Look up the verdict and confidence for one trail on one date."""
    # We import predictions here (inside the function) instead of at the top
    # of the file. This way pandas only gets loaded if the user actually
    # opens the map drill-down view, which makes the cold start faster.
    from utils import predictions

    # This function only reads from the cache, it never fetches new weather
    # from the API. If there's no saved weather for this date, we show
    # "no data" instead of making the user wait for a download.
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
    """Draw a zoomed-in map of one canton's trails.

    Returns the name of the trail the user clicked, or None if nothing
    was clicked.
    """
    if not trails:
        st.info(t("No trails recorded for {canton}.",
                  canton=canton_label(canton_code)))
        return None

    # We center the map on the middle point of the canton's trails. The
    # "centroid" is just the average latitude and average longitude.
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
    # Tell folium to zoom in so that all the trail markers fit on screen.
    # We add a small bit of padding so nothing sits right on the edge.
    fmap.fit_bounds(
        [
            [min(lats) - 0.05, min(lons) - 0.05],
            [max(lats) + 0.05, max(lons) + 0.05],
        ]
    )

    # Draw one circle marker for each trail and color it based on the verdict
    # we predicted for the chosen date.
    for trail in trails:
        verdict, conf = _verdict_for_trail(trail, target_date)
        colour = _FOLIUM_COLOUR_MAP.get(verdict, "gray")
        popup_html = (
            f"<b>{trail['name']}</b><br>"
            f"{trail['canton']} · {trail['difficulty']} · {trail['length_km']} km<br>"
            f"{t('Verdict')}: <b style='color:{VERDICT_COLOURS.get(verdict, '#888')}'>"
            f"{VERDICT_EMOJI.get(verdict, '⚪')} {verdict_label(verdict)}</b>"
            f"{f' · {conf:.0%}' if conf else ''}<br>"
            f"<i>{t('Pick from the dropdown below to open the full trail page.')}</i>"
        )
        folium.CircleMarker(
            location=[trail["lat"], trail["lon"]],
            radius=8,
            color=colour,
            weight=1.5,
            fill=True,
            fill_color=colour,
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=trail["name"],
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
            t("Open a trail detail page"),
            t("Pick a trail to see route notes, forecast interpretation, photos and reports."),
            t("Trail selector"),
        ),
        unsafe_allow_html=True,
    )
    options = {
        f"{tr['name']}  ·  {tr['difficulty']}  ·  {tr['length_km']} km": tr["id"]
        for tr in trails
    }
    if not options:
        return
    chosen = st.selectbox(
        t("Trail"), list(options.keys()), index=0, key="drilldown_trail_select"
    )
    # Same trick as the Find page: we save the trail ID and date into
    # session state, then switch to the Trail Detail page. Session state
    # is how Streamlit pages share information with each other.
    if st.button(t("→ Open trail detail"), type="primary", width="stretch"):
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
            t("Trail map"),
            t("Browse Switzerland by canton, then zoom into individual trails with condition-aware colors for the date you choose."),
            t("Map discovery"),
        ),
        unsafe_allow_html=True,
    )

    # ---- Date picker (drives every colour on the page) ----
    chosen_date = render_date_picker()

    all_trails = db_manager.get_all_trails()

    # If any trails have no cached weather for this date, fetch them in
    # the background. This only runs once per session (so users don't
    # wait every time they come back to the page).
    # Open-Meteo Forecast API - https://open-meteo.com/en/docs
    _, n_failed = ensure_weather_cached(
        all_trails, page_key="map", target_date=chosen_date
    )
    if n_failed:
        st.caption(
            t("⚠️ {n} trail(s) couldn't be fetched (network blip or "
              "Open-Meteo rate-limit). Refresh the page to retry.", n=n_failed)
        )

    # We use one session state value to decide which view to show. If a
    # canton code is stored there, we render the drill-down view. If not,
    # we render the overview of all of Switzerland.
    selected = st.session_state.get("map_selected_canton")

    # ============================================================
    # Drill-down view
    # ============================================================
    if selected and selected in {t["canton"] for t in all_trails}:
        st.markdown(
            section_heading(
                t("Trails in {canton}", canton=canton_label(selected)),
                t("Showing every trail in {canton} for {d}. Click a marker "
                  "or use the selector below.",
                  canton=CANTON_NAMES.get(selected, selected),
                  d=fmt_date(chosen_date, "full")),
                t("Canton detail"),
            ),
            unsafe_allow_html=True,
        )
        cols = st.columns([1, 4])
        if cols[0].button(t("← All cantons"), width="stretch"):
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
            t("Canton overview"),
            t("Each bubble is a Swiss canton, colored by the average trail "
              "verdict for {d}. Bigger bubble means more trails.",
              d=fmt_date(chosen_date, "full")),
            t("At a glance"),
        ),
        unsafe_allow_html=True,
    )

    # Group the trails by canton ahead of time. For each canton we compute
    # the average verdict and the number of trails, so the map can use them
    # right away to size and color the bubbles.
    canton_data = aggregate_by_canton(all_trails, chosen_date)
    render_summary_metrics(canton_data)

    # If the user clicked on a canton bubble, save that canton code in
    # session state and rerun the page. Next time around the drill-down
    # view will run instead of the overview.
    clicked_canton = render_canton_overview_map(canton_data)
    if clicked_canton and clicked_canton in canton_data:
        st.session_state["map_selected_canton"] = clicked_canton
        st.rerun()

    render_canton_button_grid(canton_data)


main()
