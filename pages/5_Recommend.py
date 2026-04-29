"""Recommend page — quiz + date picker → ranked best hikes.

The user answers a short quiz (canton, region, difficulty, length, max
altitude) and picks a date within the 7-day forecast horizon. We then:

    1. Filter trails by the quiz answers.
    2. Refresh each candidate's forecast cache (no-op if fresh).
    3. Predict the verdict for the chosen date.
    4. Rank by verdict ascending (SAFE first), then by confidence.
    5. Render the top results as cards.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from data import db_manager, weather_fetcher
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_COLOURS, VERDICT_EMOJI

st.set_page_config(
    page_title=f"Recommend · {APP_TITLE}", page_icon="🧭", layout="wide"
)

VERDICT_RANK = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2, "—": 3}
TOP_N: int = 10
FORECAST_HORIZON_DAYS: int = 6


def render_quiz(meta: dict) -> dict | None:
    """Render the 5-question quiz + date picker. Return answers on submit."""
    st.markdown(
        "Answer a few questions and we'll rank the best Swiss hikes for your "
        "chosen day, blending **your preferences** with the **weather forecast**."
    )

    today = date.today()
    with st.form("recommend_quiz"):
        c1, c2 = st.columns(2)
        with c1:
            cantons = st.multiselect(
                "1) Which cantons are OK?",
                options=meta["cantons"],
                help="Leave empty to allow any canton.",
            )
            regions = st.multiselect(
                "2) Which regions?",
                options=meta["regions"],
                help="Alps · Pre-Alps · Jura · Mittelland. Empty = all.",
            )
            difficulties = st.multiselect(
                "3) Difficulty (SAC scale)",
                options=meta["difficulties"],
                help="T1 = strolling · T6 = serious alpine. Empty = all.",
            )
        with c2:
            length_lo, length_hi = st.slider(
                "4) Length range (km)",
                min_value=float(int(meta["min_length_km"])),
                max_value=float(int(meta["max_length_km"]) + 1),
                value=(
                    float(int(meta["min_length_km"])),
                    float(int(meta["max_length_km"]) + 1),
                ),
                step=0.5,
            )
            alt_lo, alt_hi = st.slider(
                "5) Max altitude range (m)",
                min_value=int(meta["min_max_alt_m"]),
                max_value=int(meta["max_max_alt_m"]),
                value=(int(meta["min_max_alt_m"]), int(meta["max_max_alt_m"])),
                step=50,
            )
            mode = st.radio(
                "When?",
                ["Today", "Pick a date"],
                horizontal=True,
                help=f"Forecasts cover today + the next {FORECAST_HORIZON_DAYS} days.",
            )
            if mode == "Today":
                chosen_date = today
                st.caption(f"📅 {today.strftime('%A %d %B %Y')}")
            else:
                chosen_date = st.date_input(
                    "Date",
                    value=today,
                    min_value=today,
                    max_value=today + timedelta(days=FORECAST_HORIZON_DAYS),
                )

        submitted = st.form_submit_button(
            "🧭 Find my best hikes", type="primary", use_container_width=True
        )

    if not submitted:
        return None

    return {
        "cantons": cantons or None,
        "regions": regions or None,
        "difficulties": difficulties or None,
        "min_length_km": length_lo,
        "max_length_km": length_hi,
        "min_alt_m": alt_lo,
        "max_alt_m": alt_hi,
        "date": chosen_date,
    }


def _score_trail(trail, target_date: date, risk: int) -> dict:
    """Refresh forecast (cached) and score a trail for the target date."""
    snap = db_manager.get_weather_for_date(trail["id"], target_date)
    if snap is None:
        try:
            weather_fetcher.refresh_cache(trail["id"], trail["lat"], trail["lon"])
            snap = db_manager.get_weather_for_date(trail["id"], target_date)
        except Exception:
            snap = None

    if snap is None:
        return {
            "trail": trail,
            "snapshot": None,
            "verdict": "—",
            "adjusted": "—",
            "confidence": 0.0,
            "source": "no data",
            "rank_key": (VERDICT_RANK["—"], 1.0, trail["name"].lower()),
        }

    snap_dict = dict(snap)
    verdict, conf, _, source = predictions.predict_for_snapshot(
        snap_dict, trail["max_alt_m"]
    )
    adjusted = predictions.apply_risk_tolerance(verdict, risk)
    return {
        "trail": trail,
        "snapshot": snap_dict,
        "verdict": verdict,
        "adjusted": adjusted,
        "confidence": float(conf),
        "source": source,
        # Lower is better: SAFE first, then high confidence, then name.
        "rank_key": (
            VERDICT_RANK.get(adjusted, 3),
            -float(conf),
            trail["name"].lower(),
        ),
    }


def render_results(results: list[dict], target_date: date) -> None:
    if not results:
        st.warning(
            "No trails matched your quiz answers. Loosen the filters and try again."
        )
        return

    summary = {"SAFE": 0, "BORDERLINE": 0, "AVOID": 0, "—": 0}
    for r in results:
        summary[r["adjusted"]] = summary.get(r["adjusted"], 0) + 1

    st.success(
        f"Ranked **{len(results)}** matching trail(s) for "
        f"**{target_date.strftime('%A %d %B %Y')}**. "
        f"🟢 {summary['SAFE']} · 🟠 {summary['BORDERLINE']} · "
        f"🔴 {summary['AVOID']} · ⚪ {summary['—']}"
    )

    st.subheader(f"🏆 Top {min(TOP_N, len(results))} hikes")
    st.caption("Click **View details** on any card for the route map, weather "
               "explanation, tricky parts, and photos.")
    top = results[:TOP_N]

    for idx, r in enumerate(top, start=1):
        trail = r["trail"]
        snap = r["snapshot"] or {}
        verdict = r["adjusted"]
        colour = VERDICT_COLOURS.get(verdict, "#888888")
        emoji = VERDICT_EMOJI.get(verdict, "⚪")

        weather_bits = []
        if snap.get("temp_c") is not None:
            weather_bits.append(f"🌡️ {snap['temp_c']:.0f}°C")
        if snap.get("wind_kmh") is not None:
            weather_bits.append(f"💨 {snap['wind_kmh']:.0f} km/h")
        if snap.get("precip_mm") is not None:
            weather_bits.append(f"☔ {snap['precip_mm']:.1f} mm")
        if snap.get("snowline_m") is not None:
            weather_bits.append(f"❄️ snowline {int(snap['snowline_m'])} m")
        weather_line = "  ·  ".join(weather_bits) or "_no weather data cached_"

        with st.container(border=True):
            info_col, btn_col = st.columns([5, 1])
            with info_col:
                st.markdown(
                    f"""
                    <div style="border-left:6px solid {colour};
                                padding-left:12px;">
                      <div style="font-size:1.05rem; font-weight:700;">
                        #{idx} · {trail['name']}
                        <span style="background:{colour}; color:white;
                                     padding:2px 10px; border-radius:12px;
                                     font-size:0.8rem; margin-left:8px;">
                          {emoji} {verdict} · {r['confidence']:.0%}
                        </span>
                      </div>
                      <div style="opacity:0.7; font-size:0.92rem;">
                        {trail['canton']} · {trail['region']} ·
                        {trail['difficulty']} ·
                        {trail['length_km']} km · max {trail['max_alt_m']} m
                      </div>
                      <div style="margin-top:6px; font-size:0.9rem; opacity:0.85;">
                        {weather_line}
                        <span style="float:right; opacity:0.6;">
                          source: {r['source']}
                        </span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with btn_col:
                if st.button(
                    "View details",
                    key=f"detail_btn_{trail['id']}",
                    use_container_width=True,
                ):
                    st.session_state["selected_trail_id"] = trail["id"]
                    st.session_state["selected_date"] = target_date
                    st.switch_page("pages/6_Trail_Detail.py")

    if len(results) > TOP_N:
        with st.expander(f"Show the other {len(results) - TOP_N} matches"):
            for r in results[TOP_N:]:
                t = r["trail"]
                row_l, row_r = st.columns([5, 1])
                row_l.write(
                    f"{VERDICT_EMOJI.get(r['adjusted'], '⚪')} "
                    f"**{t['name']}** · {t['canton']} · {t['difficulty']} · "
                    f"{t['length_km']} km — {r['adjusted']} ({r['confidence']:.0%})"
                )
                if row_r.button(
                    "Open", key=f"detail_btn_tail_{t['id']}",
                    use_container_width=True,
                ):
                    st.session_state["selected_trail_id"] = t["id"]
                    st.session_state["selected_date"] = target_date
                    st.switch_page("pages/6_Trail_Detail.py")


def main() -> None:
    st.title("🧭 Find my best hike")

    meta = db_manager.get_trail_metadata()
    if not meta["cantons"]:
        st.error("No trails seeded. Restart the app or run bootstrap.")
        return

    answers = render_quiz(meta)
    if answers is None:
        st.info(
            "Fill in the quiz above and hit **Find my best hikes** to see your "
            "ranked recommendations."
        )
        return

    candidates = db_manager.get_filtered_trails(
        cantons=answers["cantons"],
        regions=answers["regions"],
        difficulties=answers["difficulties"],
        min_length_km=answers["min_length_km"],
        max_length_km=answers["max_length_km"],
        min_alt_m=answers["min_alt_m"],
        max_alt_m=answers["max_alt_m"],
    )

    if not candidates:
        st.warning(
            "No trails match your quiz answers. Try widening the canton, "
            "difficulty, or length filters."
        )
        return

    target_date = answers["date"]
    risk = st.session_state.get("risk_tolerance", 3)

    progress = st.progress(0.0, text=f"Checking the forecast for {len(candidates)} trail(s)…")
    results: list[dict] = []
    for i, trail in enumerate(candidates, start=1):
        results.append(_score_trail(trail, target_date, risk))
        progress.progress(i / len(candidates), text=f"Scored {i}/{len(candidates)}")
    progress.empty()

    results.sort(key=lambda r: r["rank_key"])
    render_results(results, target_date)


main()
