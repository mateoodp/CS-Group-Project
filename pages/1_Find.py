"""Find a hike - front door of the app.

User answers a 5-question quiz (canton, region, difficulty, length, max
altitude) and picks a date within the 7-day forecast horizon. The page:

    1. Filters trails by the quiz answers.
    2. Refreshes each candidate's forecast cache (no-op if fresh).
    3. Predicts the verdict for the chosen date.
    4. Ranks by verdict ascending (SAFE first), then by confidence.
    5. Renders the top results as cards. Click a card -> Trail Detail.
"""

from __future__ import annotations

from html import escape
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import streamlit as st

from data import db_manager, weather_fetcher
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_EMOJI
from utils.sidebar import render_shared_sidebar
from utils.theme import (
    apply_app_theme,
    page_hero,
    section_heading,
    stat_pills_html,
    status_class,
)
from utils.route_images import route_image_info, trail_detail_url
from utils.topnav import render_top_nav
from utils.trail_detail import difficulty_dots_html, naismith_time

st.set_page_config(
    page_title=f"Find - {APP_TITLE}",
    page_icon="compass",
    layout="wide",
    initial_sidebar_state="collapsed",
)

VERDICT_RANK = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2, "UNKNOWN": 3}
TOP_N: int = 10
FORECAST_HORIZON_DAYS: int = 6


def render_quiz(meta: dict) -> dict | None:
    """Render the 5-question quiz + date picker. Return answers on submit."""
    st.markdown(
        section_heading(
            "Tune your trail day",
            "Filter by region, grade, distance and altitude. The ranking still uses the same forecast and model logic underneath.",
            "Personalized search",
        ),
        unsafe_allow_html=True,
    )

    today = date.today()
    with st.form("recommend_quiz"):
        c1, c2 = st.columns(2)
        with c1:
            cantons = st.multiselect(
                "Cantons",
                options=meta["cantons"],
                placeholder="Any canton",
                help="Leave empty to search all Swiss cantons.",
            )
            regions = st.multiselect(
                "Regions",
                options=meta["regions"],
                placeholder="Any region",
                help="Alps - Pre-Alps - Jura - Mittelland. Empty = all.",
            )
            difficulties = st.multiselect(
                "SAC grade",
                options=meta["difficulties"],
                placeholder="Any grade",
                help="T1 = strolling - T6 = serious alpine. Empty = all.",
            )
        with c2:
            length_lo, length_hi = st.slider(
                "Distance",
                min_value=float(int(meta["min_length_km"])),
                max_value=float(int(meta["max_length_km"]) + 1),
                value=(
                    float(int(meta["min_length_km"])),
                    float(int(meta["max_length_km"]) + 1),
                ),
                step=0.5,
                help="Route length in kilometres.",
            )
            alt_lo, alt_hi = st.slider(
                "Highest point",
                min_value=int(meta["min_max_alt_m"]),
                max_value=int(meta["max_max_alt_m"]),
                value=(int(meta["min_max_alt_m"]), int(meta["max_max_alt_m"])),
                step=50,
                help="Maximum altitude reached by the trail.",
            )
            mode = st.radio(
                "Date window",
                ["Today", "Pick a date"],
                horizontal=True,
                help=f"Forecasts cover today + the next {FORECAST_HORIZON_DAYS} days.",
            )
            if mode == "Today":
                chosen_date = today
                st.caption(f"Using today: {today.strftime('%A %d %B %Y')}")
            else:
                chosen_date = st.date_input(
                    "Date",
                    value=today,
                    min_value=today,
                    max_value=today + timedelta(days=FORECAST_HORIZON_DAYS),
                )

        submitted = st.form_submit_button(
            "Find matching hikes", type="primary", width="stretch"
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


PARALLEL_WORKERS: int = 8  # how many trails we fetch in parallel
MAX_FETCH_RETRIES: int = 1  # retry once on failure (so total: 2 attempts)


def _ensure_snapshot(trail, target_date: date) -> tuple[dict | None, str | None]:
    """Try hard to get a cached snapshot for ``(trail, target_date)``.

    Returns ``(snapshot_dict_or_none, error_message_or_none)``. Tries the
    cache first, then a fetch, then a forced refetch as a fallback. We
    surface the *last* error so the UI can show users why a trail is
    missing 闂?never silently degrade to "no data".
    """
    snap = db_manager.get_weather_for_date(trail["id"], target_date)
    if snap is not None:
        return dict(snap), None

    last_err: Exception | None = None
    for attempt in range(MAX_FETCH_RETRIES + 1):
        try:
            weather_fetcher.refresh_cache(
                trail["id"],
                trail["lat"],
                trail["lon"],
                force=(attempt > 0),
            )
            snap = db_manager.get_weather_for_date(trail["id"], target_date)
            if snap is not None:
                return dict(snap), None
        except Exception as e:
            last_err = e

    err = (
        f"{last_err.__class__.__name__}: {last_err}"
        if last_err
        else (f"forecast covers today + 6 days; date {target_date} is out of range")
    )
    return None, err


def _score_trail(trail, target_date: date, risk: int) -> dict:
    """Score one trail. Always returns a complete row (even on failure)."""
    snap, err = _ensure_snapshot(trail, target_date)

    if snap is None:
        return {
            "trail": trail,
            "snapshot": None,
            "verdict": "UNKNOWN",
            "adjusted": "UNKNOWN",
            "confidence": 0.0,
            "source": "no data",
            "error": err,
            "caveats": [],
            "rank_key": (VERDICT_RANK["UNKNOWN"], 1.0, trail["name"].lower()),
        }

    verdict, conf, _, source = predictions.predict_for_snapshot(
        snap, trail["max_alt_m"]
    )
    adjusted, caveats = predictions.adjust_verdict(verdict, trail, snap, risk)
    return {
        "trail": trail,
        "snapshot": snap,
        "verdict": verdict,
        "adjusted": adjusted,
        "confidence": float(conf),
        "source": source,
        "error": None,
        "caveats": caveats,
        # Lower is better: SAFE first, then high confidence, then name.
        "rank_key": (
            VERDICT_RANK.get(adjusted, 3),
            -float(conf),
            trail["name"].lower(),
        ),
    }


def _score_all_parallel(candidates, target_date: date, risk: int) -> list[dict]:
    """Score every candidate in parallel with a small thread pool + progress."""
    results: list[dict] = []
    progress = st.progress(
        0.0, text=f"Checking the forecast for {len(candidates)} trail(s)..."
    )
    done = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futures = {ex.submit(_score_trail, t, target_date, risk): t for t in candidates}
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            progress.progress(
                done / len(candidates),
                text=f"Scored {done}/{len(candidates)} trails...",
            )
    progress.empty()
    return results


def render_results(results: list[dict], target_date: date) -> None:
    if not results:
        st.warning(
            "No trails matched your quiz answers. Loosen the filters and try again."
        )
        return

    summary = {"SAFE": 0, "BORDERLINE": 0, "AVOID": 0, "UNKNOWN": 0}
    for r in results:
        summary[r["adjusted"]] = summary.get(r["adjusted"], 0) + 1

    st.success(
        f"Ranked **{len(results)}** matching trail(s) for "
        f"**{target_date.strftime('%A %d %B %Y')}**. "
        f"SAFE {summary['SAFE']} | BORDERLINE {summary['BORDERLINE']} | "
        f"AVOID {summary['AVOID']} | UNKNOWN {summary['UNKNOWN']}"
    )
    st.markdown(
        stat_pills_html(
            [
                ("safe", summary["SAFE"]),
                ("borderline", summary["BORDERLINE"]),
                ("avoid", summary["AVOID"]),
                ("no data", summary["UNKNOWN"]),
            ]
        ),
        unsafe_allow_html=True,
    )

    # Surface failed fetches loudly - never silently degrade to "no data".
    failed = [r for r in results if r.get("error")]
    if failed:
        sample_errors = sorted({r["error"] for r in failed})[:3]
        with st.expander(
            f"{len(failed)} trail(s) could not be scored - show details",
            expanded=False,
        ):
            st.markdown(
                "These trails appear in the list with **no data**. The most "
                "common cause is a transient Open-Meteo API hiccup - usually "
                "fixes itself; click **Re-run search** above to retry."
            )
            st.markdown("**Sample error message(s):**")
            for e in sample_errors:
                st.code(e)
            st.markdown("**Affected trails:**")
            st.write(
                ", ".join(r["trail"]["name"] for r in failed[:30])
                + ("..." if len(failed) > 30 else "")
            )

    st.markdown(
        section_heading(
            f"Top {min(TOP_N, len(results))} hikes",
            "Open any recommendation for the route map, weather breakdown, tricky parts, photos and reports.",
            "Ranked recommendations",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    top = results[:TOP_N]

    cols = st.columns(3, gap="large")
    for i, r in enumerate(top):
        with cols[i % 3]:
            _render_result_card(r, target_date, image_index=i)

    if len(results) > TOP_N:
        with st.expander(f"Show the other {len(results) - TOP_N} matches"):
            tail_cols = st.columns(3, gap="large")
            for i, r in enumerate(results[TOP_N:]):
                with tail_cols[i % 3]:
                    _render_result_card(r, target_date, compact=True, image_index=i)


# ---------------------------------------------------------------------------
# Card design 闂?inspired by Norgeskart-style route list (clean white cards
# on a soft background, 4-dot SAC indicator, 3-column metrics row).
# ---------------------------------------------------------------------------

_CARD_CSS: str = """
<style>
  .hike-card {
    background: #ffffff;
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 28px;
    padding: .72rem;
    margin-bottom: .65rem;
    position: relative;
    box-shadow: 0 18px 42px rgba(21, 39, 32, .08);
  }
  .hike-card-link {
    display: block;
    color: #14201c;
    cursor: pointer;
    text-decoration: none;
    margin-bottom: .65rem;
  }
  .hike-card-link:visited,
  .hike-card-link:hover,
  .hike-card-link:active {
    color: #14201c;
    text-decoration: none;
  }
  .hike-card-link * {
    text-decoration: none;
  }
  .hike-card-link:hover .hike-card {
    transform: translateY(-3px);
    box-shadow: 0 24px 52px rgba(21, 39, 32, .12);
  }
  .hike-card-link .hike-card {
    transition: transform .18s ease, box-shadow .18s ease;
  }
  .hike-card-hitbox {
    position: absolute;
    inset: 0;
    z-index: 5;
    border-radius: 28px;
    text-decoration: none;
  }
  .hike-card-image {
    height: 210px;
    border-radius: 22px;
    background-size: cover;
    background-position: center;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
  }
  .hike-card-image::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,.04), rgba(0,0,0,.38));
  }
  .hike-card-image .verdict-pill {
    position: absolute;
    left: .85rem;
    bottom: .85rem;
    z-index: 1;
    margin-left: 0;
  }
  .image-notice {
    position: absolute;
    right: .85rem;
    top: .85rem;
    z-index: 1;
    border-radius: 999px;
    background: rgba(20, 32, 28, .74);
    color: #fff;
    padding: .42rem .68rem;
    font-size: .72rem;
    font-weight: 850;
    backdrop-filter: blur(10px);
  }
  .hike-card-body {
    padding: 0 .35rem .4rem;
  }
  .hike-card-title {
    font-size: 1.18rem;
    font-weight: 850;
    color: #14201c;
    line-height: 1.3;
    margin-bottom: 10px;
  }
  .hike-card-meta {
    font-size: 0.85rem;
    color: #6b7177;
    margin-bottom: .75rem;
    min-height: 2.4rem;
  }
  .hike-card-link .hike-card-meta,
  .hike-card-link .hike-card-meta * {
    color: #6b7177;
  }
  .hike-card-link .hike-card-title,
  .hike-card-link .hike-stat-value {
    color: #14201c;
  }
  .hike-card-link .hike-stat-label {
    color: #6b756f;
  }
  .hike-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    border-top: 1px solid #edf0ed;
    padding-top: 12px;
  }
  .hike-stat-value {
    font-size: .98rem;
    font-weight: 850;
    color: #14201c;
  }
  .hike-stat-label {
    font-size: 0.72rem;
    color: #6b756f;
    margin-top: 2px;
    font-weight: 800;
    text-transform: uppercase;
  }
  .verdict-pill {
    display: inline-block;
    padding: 5px 11px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 850;
    color: white;
    vertical-align: middle;
    margin-left: 8px;
  }
  .verdict-pill.safe { background:#5f9f45; }
  .verdict-pill.borderline { background:#c9851e; }
  .verdict-pill.avoid { background:#b7473f; }
  .verdict-pill.unknown { background:#7c8580; }
  .safety-note {
    margin-top: 12px;
    padding: 8px 12px;
    background: #fff7ed;
    border-left: 3px solid #C0392B;
    border-radius: 12px;
    font-size: 0.84rem;
    color: #5a3a1a;
  }
</style>
"""


def _render_result_card(
    r: dict,
    target_date,
    compact: bool = False,
    image_index: int = 0,
) -> None:
    """Render one trail as a discovery image card with a detail button."""
    trail = r["trail"]
    verdict = r["adjusted"]
    emoji = VERDICT_EMOJI.get(verdict, "")

    ascent = trail["max_alt_m"] - trail["min_alt_m"]
    time_est = naismith_time(trail["length_km"], ascent)

    pill = (
        f"<span class='verdict-pill {status_class(verdict)}'>"
        f"{escape(emoji)} {escape(verdict)}"
        f"</span>"
    )

    caveat_html = ""
    if r.get("caveats"):
        caveat_html = (
            f"<div class='safety-note'><b>Safety note:</b> "
            f"{escape(r['caveats'][0])}</div>"
        )

    snap = r.get("snapshot") or {}
    weather_chip = ""
    if snap.get("temp_c") is not None and snap.get("wind_kmh") is not None:
        weather_chip = (
            f"<span style='color:#6b7177;'>"
            f"{snap['temp_c']:.0f} C {chr(183)} wind {snap['wind_kmh']:.0f} km/h"
            f"</span>"
        )
    image_info = route_image_info(trail)
    image_notice_html = (
        f'<span class="image-notice">{escape(str(image_info["notice"]))}</span>'
        if image_info.get("notice")
        else ""
    )

    detail_url = escape(trail_detail_url(trail))
    html = (
        '<div class="hike-card-link">'
        '<div class="hike-card">'
        f'<a class="hike-card-hitbox" href="{detail_url}" aria-label="Open {escape(trail["name"])}"></a>'
        f'<div class="hike-card-image" style="background-image:url(\'{escape(str(image_info["url"]))}\');">'
        f"{image_notice_html}{pill}"
        "</div>"
        '<div class="hike-card-body">'
        f'<div class="hike-card-title">{escape(trail["name"])}</div>'
        '<div class="hike-card-meta">'
        f"{difficulty_dots_html(trail['difficulty'])}"
        '<div style="margin-top:.45rem;">'
        f"{escape(trail['canton'])} {chr(183)} {escape(trail['region'])} {chr(183)} {weather_chip}"
        "</div>"
        "</div>"
        '<div class="hike-stats">'
        "<div>"
        f'<div class="hike-stat-value">{escape(time_est)}</div>'
        '<div class="hike-stat-label">Time</div>'
        "</div>"
        "<div>"
        f'<div class="hike-stat-value">{ascent} m</div>'
        '<div class="hike-stat-label">Ascent</div>'
        "</div>"
        "<div>"
        f'<div class="hike-stat-value">{trail["length_km"]} km</div>'
        '<div class="hike-stat-label">Length</div>'
        "</div>"
        "</div>"
        f"{caveat_html}"
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)

def render_recent_community_feed() -> None:
    """Bottom-of-page community section: most recent hiker reports."""
    st.divider()
    st.markdown(
        section_heading(
            "Recent reports from hikers",
            "Community reports become training signal the next time the model is retrained.",
            "Trail notes",
        ),
        unsafe_allow_html=True,
    )
    rows = db_manager.get_recent_user_reports(limit=6)
    if not rows:
        st.caption(
            "No reports yet. Open any trail's detail page and submit one "
            "after your hike - they go straight into the model on the next retrain."
        )
        return
    cols = st.columns(min(3, len(rows)))
    for col, r in zip(cols, rows):
        emoji = VERDICT_EMOJI.get(r["user_label"], "")
        comment = (r["comment"] or "").strip() or "_no comment_"
        with col:
            with st.container(border=True):
                st.markdown(
                    f"{emoji} **{r['trail_name']}** - {r['user_label']}  \n"
                    f"_{r['report_date']}_  \n{comment}"
                )


def _answers_signature(answers: dict) -> str:
    """Stable hash of quiz answers 闂?used to invalidate cached results."""
    serialisable = {
        k: (v.isoformat() if isinstance(v, date) else v) for k, v in answers.items()
    }
    return json.dumps(serialisable, sort_keys=True, default=str)


def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    apply_app_theme()

    st.markdown(
        page_hero(
            "Find my best hike",
            "Tell us what kind of day you want and when. We cross-reference your preferences with the live weather forecast and rank matching hikes safest first.",
            "AI trail finder",
        ),
        unsafe_allow_html=True,
    )

    meta = db_manager.get_trail_metadata()
    if not meta["cantons"]:
        st.error("No trails seeded. Restart the app or run bootstrap.")
        return

    # 1) Render the quiz. ``submitted_answers`` is non-None *only on the
    #    rerun immediately after Submit*. Persist into session state so the
    #    results survive subsequent reruns without re-submitting the form.
    submitted_answers = render_quiz(meta)
    if submitted_answers is not None:
        st.session_state["find_answers"] = submitted_answers
        # Quiz changed 闂?invalidate any cached results.
        st.session_state.pop("find_results", None)
        st.session_state.pop("find_answers_sig", None)

    answers = st.session_state.get("find_answers")
    if answers is None:
        st.info(
            "Fill in the filters and hit **Find matching hikes** to see your "
            "ranked recommendations."
        )
        render_recent_community_feed()
        return

    # 2) "Re-run" / "Reset" controls so the user can refresh or start over.
    bar = st.columns([1, 1, 4])
    with bar[0]:
        rerun_clicked = st.button("Re-run search", width="stretch")
    with bar[1]:
        if st.button("Clear & restart", width="stretch"):
            st.session_state.pop("find_answers", None)
            st.session_state.pop("find_results", None)
            st.session_state.pop("find_answers_sig", None)
            st.rerun()

    # 3) Compute (or reuse) results. We cache by a hash of the answers, so
    #    flipping pages / clicking buttons doesn't re-fetch all 234 trails.
    sig = _answers_signature(answers)
    cache_hit = (
        not rerun_clicked
        and st.session_state.get("find_answers_sig") == sig
        and st.session_state.get("find_results") is not None
    )

    if cache_hit:
        results = st.session_state["find_results"]
    else:
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

        risk = st.session_state.get("risk_tolerance", 3)
        results = _score_all_parallel(candidates, answers["date"], risk)
        results.sort(key=lambda r: r["rank_key"])
        st.session_state["find_results"] = results
        st.session_state["find_answers_sig"] = sig

    render_results(results, answers["date"])
    render_recent_community_feed()


main()
