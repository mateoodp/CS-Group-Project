"""Map — visual overview of every trail with today's verdict.

Single job: show all 234 Swiss trails on a map, colour-coded by today's
forecast verdict, and route the user to the Trail Detail page when they
pick one. Filtering is collapsible and lives on the page (not the sidebar)
so it doesn't fight with the Find quiz.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from data import db_manager, weather_fetcher
from utils import predictions
from utils.constants import (
    APP_TITLE,
    CH_CENTRE_LAT,
    CH_CENTRE_LON,
    DEFAULT_MAP_ZOOM,
    VERDICT_COLOURS,
    VERDICT_EMOJI,
)
from utils.sidebar import render_shared_sidebar
from utils.topnav import render_top_nav

PARALLEL_WORKERS: int = 8

st.set_page_config(
    page_title=f"Map · {APP_TITLE}", page_icon="🗺️", layout="wide",
    initial_sidebar_state="collapsed",
)


_FOLIUM_COLOUR_MAP = {
    "SAFE": "green", "BORDERLINE": "orange", "AVOID": "red", "—": "gray",
}


def _verdict_for_today(trail) -> tuple[str, float, str, list[str]]:
    """Cache-only lookup. With 234 trails, fetching per marker would be too slow."""
    snap = db_manager.get_weather_for_date(trail["id"], date.today())
    if snap is None:
        return "—", 0.0, "no data", []
    snap_dict = dict(snap)
    v, c, _, source = predictions.predict_for_snapshot(
        snap_dict, trail["max_alt_m"]
    )
    floored, caveats = predictions.apply_difficulty_floor(v, trail, snap_dict)
    return floored, c, source, caveats


def _trails_missing_today(trails) -> list[dict]:
    """Return trails with no cached snapshot for today."""
    today = date.today()
    missing = []
    for t in trails:
        snap = db_manager.get_weather_for_date(t["id"], today)
        if snap is None:
            missing.append(t)
    return missing


def bulk_fetch_weather(trails) -> tuple[int, int]:
    """Fetch the 7-day forecast for every trail in parallel.

    Returns ``(succeeded, failed)``. Skips any trail whose cache is already
    fresh — so re-running this within the hour is essentially free.
    """
    progress = st.progress(0.0, text=f"Fetching weather for {len(trails)} trails…")
    succeeded = failed = 0
    done = 0

    def fetch_one(t):
        try:
            weather_fetcher.refresh_cache(t["id"], t["lat"], t["lon"])
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futures = {ex.submit(fetch_one, t): t for t in trails}
        for fut in as_completed(futures):
            ok = fut.result()
            succeeded += int(ok)
            failed += int(not ok)
            done += 1
            progress.progress(
                done / len(trails),
                text=f"Fetched {done}/{len(trails)} ({failed} failed so far)",
            )
    progress.empty()
    return succeeded, failed


def render_data_health_banner(trails) -> None:
    """Show how many trails lack today's data and offer a one-click fix."""
    missing = _trails_missing_today(trails)
    if not missing:
        st.success(
            f"✅ All {len(trails)} visible trail(s) have today's forecast cached."
        )
        return

    pct = 100 * len(missing) / max(1, len(trails))
    msg_col, btn_col = st.columns([4, 1])
    with msg_col:
        st.warning(
            f"⚠️ **{len(missing)} of {len(trails)}** trail(s) "
            f"({pct:.0f}%) have no weather cached for today — they show as "
            f"grey markers and won't appear with a verdict. Fetch them now "
            f"to fix it."
        )
    with btn_col:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button(
            f"🔄 Fetch {len(missing)} trail(s)",
            use_container_width=True,
            type="primary",
        ):
            ok, ko = bulk_fetch_weather(missing)
            if ko == 0:
                st.success(f"✅ Fetched all {ok} trail(s) — refresh the map.")
            else:
                st.warning(
                    f"Fetched {ok} trail(s); {ko} still failed (likely an "
                    f"Open-Meteo hiccup — try the button again in a minute)."
                )
            st.rerun()


def render_filters(meta: dict) -> dict:
    """Collapsible page-local filter strip (no sidebar entanglement)."""
    with st.expander("🔎 Filter what's on the map", expanded=False):
        c1, c2, c3 = st.columns(3)
        cantons = c1.multiselect("Canton", options=meta["cantons"], default=[])
        regions = c2.multiselect("Region", options=meta["regions"], default=[])
        difficulties = c3.multiselect(
            "Difficulty (SAC)", options=meta["difficulties"], default=[]
        )
    return {
        "cantons": cantons or None,
        "regions": regions or None,
        "difficulties": difficulties or None,
    }


def render_map(trails) -> list[dict]:
    """Render the Folium map; return per-trail rows for the legend tally."""
    fmap = folium.Map(
        location=[CH_CENTRE_LAT, CH_CENTRE_LON],
        zoom_start=DEFAULT_MAP_ZOOM,
        tiles="OpenStreetMap",
    )

    rows: list[dict] = []
    for trail in trails:
        verdict, conf, source, caveats = _verdict_for_today(trail)
        rows.append({"verdict": verdict})
        caveat_html = (
            f"<br><span style='font-size:0.85em; color:#C0392B;'>"
            f"⚠️ {caveats[0][:120]}…</span>" if caveats else ""
        )
        popup_html = (
            f"<b>{trail['name']}</b><br>"
            f"{trail['canton']} · {trail['difficulty']}<br>"
            f"Verdict: <b style='color:{VERDICT_COLOURS.get(verdict, '#888')}'>"
            f"{VERDICT_EMOJI.get(verdict, '⚪')} {verdict}</b>"
            f"{f' · {conf:.0%}' if conf else ''}<br>"
            f"<i>Click a marker, then 'Open trail' below for the full page.</i>"
            f"{caveat_html}"
        )
        folium.CircleMarker(
            location=[trail["lat"], trail["lon"]],
            radius=7,
            color=_FOLIUM_COLOUR_MAP.get(verdict, "gray"),
            fill=True,
            fill_color=_FOLIUM_COLOUR_MAP.get(verdict, "gray"),
            fill_opacity=0.85,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{trail['name']} — {verdict}",
        ).add_to(fmap)

    st_folium(fmap, width=None, height=560, returned_objects=[])
    return rows


def render_legend_and_picker(rows: list[dict], trails) -> None:
    """Verdict tally + a fast trail-picker dropdown that opens Trail Detail."""
    df = pd.DataFrame(rows)
    if not df.empty:
        counts = df["verdict"].value_counts().to_dict()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🟢 SAFE",       counts.get("SAFE", 0))
        c2.metric("🟠 BORDERLINE", counts.get("BORDERLINE", 0))
        c3.metric("🔴 AVOID",      counts.get("AVOID", 0))
        c4.metric("⚪ no data",    counts.get("—", 0))

    st.divider()
    st.subheader("🏔️ Open a trail's detail page")
    st.caption(
        "Pick from the dropdown below — it lists the same trails you see on "
        "the map. For a personalised ranking instead, head to **🧭 Find a hike**."
    )

    options = {f"{t['name']}  ·  {t['canton']}  ·  {t['difficulty']}": t["id"]
               for t in trails}
    if not options:
        return
    labels = list(options.keys())
    chosen = st.selectbox("Trail", labels, index=0, key="map_trail_select")
    if st.button("→ Open trail detail", type="primary", use_container_width=True):
        st.session_state["selected_trail_id"] = options[chosen]
        st.session_state["selected_date"] = date.today()
        st.switch_page("pages/Trail_Detail.py")


def main() -> None:
    render_top_nav()
    render_shared_sidebar()

    st.title("🗺️ Trail map")
    st.caption(
        f"Every Swiss trail in our catalogue, colour-coded by today's "
        f"forecast verdict ({date.today().strftime('%A %d %B')}). Tap a "
        f"marker for the popup, or use the picker below to open the full "
        f"trail page."
    )

    meta = db_manager.get_trail_metadata()
    filters = render_filters(meta)

    all_trails = db_manager.get_all_trails()
    if any(filters.values()):
        trails = db_manager.get_filtered_trails(**filters)
    else:
        trails = all_trails

    st.caption(
        f"Showing **{len(trails)}** of {len(all_trails)} trails."
        if any(filters.values())
        else f"Showing all **{len(all_trails)}** trails."
    )

    render_data_health_banner(trails)

    rows = render_map(trails)
    render_legend_and_picker(rows, trails)


main()
