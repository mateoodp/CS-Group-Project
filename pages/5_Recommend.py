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
from utils.trail_detail import difficulty_dots_html, naismith_time

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
            "caveats": [],
            "rank_key": (VERDICT_RANK["—"], 1.0, trail["name"].lower()),
        }

    snap_dict = dict(snap)
    verdict, conf, _, source = predictions.predict_for_snapshot(
        snap_dict, trail["max_alt_m"]
    )
    adjusted, caveats = predictions.adjust_verdict(verdict, trail, snap_dict, risk)
    return {
        "trail": trail,
        "snapshot": snap_dict,
        "verdict": verdict,
        "adjusted": adjusted,
        "confidence": float(conf),
        "source": source,
        "caveats": caveats,
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
    st.caption("Tap any card to open the full route, weather breakdown, "
               "tricky parts, and photos.")
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    top = results[:TOP_N]

    for r in top:
        _render_result_card(r, target_date)

    if len(results) > TOP_N:
        with st.expander(f"Show the other {len(results) - TOP_N} matches"):
            for r in results[TOP_N:]:
                _render_result_card(r, target_date, compact=True)


# ---------------------------------------------------------------------------
# Card design — inspired by Norgeskart-style route list (clean white cards
# on a soft background, 4-dot SAC indicator, 3-column metrics row).
# ---------------------------------------------------------------------------

_CARD_CSS: str = """
<style>
  .hike-card {
    background: #ffffff;
    border: 1px solid #e6e8eb;
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 12px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  }
  .hike-card-title {
    font-size: 1.08rem;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1.3;
    margin-bottom: 8px;
  }
  .hike-card-meta {
    font-size: 0.85rem;
    color: #6b7177;
    margin-bottom: 14px;
  }
  .hike-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
    border-top: 1px solid #f0f1f3;
    padding-top: 12px;
  }
  .hike-stat-value {
    font-size: 1.05rem;
    font-weight: 600;
    color: #1a1a1a;
  }
  .hike-stat-label {
    font-size: 0.78rem;
    color: #8b9197;
    margin-top: 2px;
  }
  .verdict-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    color: white;
    vertical-align: middle;
    margin-left: 8px;
  }
  .safety-note {
    margin-top: 12px;
    padding: 8px 12px;
    background: #fff7ed;
    border-left: 3px solid #C0392B;
    border-radius: 4px;
    font-size: 0.84rem;
    color: #5a3a1a;
  }
</style>
"""


def _render_result_card(r: dict, target_date, compact: bool = False) -> None:
    """Render one trail as a clean white card with a 'View details' button."""
    trail = r["trail"]
    verdict = r["adjusted"]
    colour = VERDICT_COLOURS.get(verdict, "#888888")
    emoji = VERDICT_EMOJI.get(verdict, "⚪")

    ascent = trail["max_alt_m"] - trail["min_alt_m"]
    time_est = naismith_time(trail["length_km"], ascent)

    pill = (
        f"<span class='verdict-pill' style='background:{colour};'>"
        f"{emoji} {verdict}"
        f"</span>"
    )

    caveat_html = ""
    if r.get("caveats"):
        caveat_html = (
            f"<div class='safety-note'>⚠️ <b>Safety note:</b> "
            f"{r['caveats'][0]}</div>"
        )

    snap = r.get("snapshot") or {}
    weather_chip = ""
    if snap.get("temp_c") is not None and snap.get("wind_kmh") is not None:
        weather_chip = (
            f"<span style='color:#6b7177; font-size:0.85rem; margin-left:auto;'>"
            f"🌡️ {snap['temp_c']:.0f}°C · 💨 {snap['wind_kmh']:.0f} km/h"
            f"</span>"
        )

    info_col, btn_col = st.columns([5, 1])
    with info_col:
        st.markdown(
            f"""
            <div class="hike-card">
              <div class="hike-card-title">
                {trail['name']} {pill}
              </div>
              <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                {difficulty_dots_html(trail['difficulty'])}
                <span style="color:#6b7177; font-size:0.85rem;">
                  · {trail['canton']} · {trail['region']}
                </span>
                {weather_chip}
              </div>
              <div class="hike-stats">
                <div>
                  <div class="hike-stat-value">{time_est}</div>
                  <div class="hike-stat-label">Estimated time</div>
                </div>
                <div>
                  <div class="hike-stat-value">{ascent} m</div>
                  <div class="hike-stat-label">Ascent</div>
                </div>
                <div>
                  <div class="hike-stat-value">{trail['length_km']} km</div>
                  <div class="hike-stat-label">Length</div>
                </div>
              </div>
              {caveat_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with btn_col:
        key = f"detail_{'tail_' if compact else ''}{trail['id']}"
        if st.button("View details", key=key, use_container_width=True):
            st.session_state["selected_trail_id"] = trail["id"]
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
