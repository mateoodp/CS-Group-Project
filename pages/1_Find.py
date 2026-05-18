"""Find a hike page. This is the main entry point for users.

The user fills in a short quiz (canton, region, difficulty, length, max
altitude) and picks a date within the 7-day forecast window. Then the page:

    1. Filters trails by the quiz answers.
    2. Refreshes each candidate's forecast cache (does nothing if fresh).
    3. Predicts the verdict for the chosen date.
    4. Sorts so the safest trails appear first, then by confidence.
    5. Shows the top results as cards. Clicking a card opens Trail Detail.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from html import escape
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import streamlit as st

from data import db_manager, weather_fetcher
from utils import predictions
from utils.constants import APP_TITLE, VERDICT_EMOJI
from utils.i18n import fmt_date, t, verdict_label
from utils.sidebar import render_shared_sidebar
from utils.theme import (
    apply_app_theme,
    image_for_index,
    page_hero,
    section_heading,
    stat_pills_html,
    status_class,
)
from utils.topnav import render_top_nav
from utils.trail_detail import difficulty_dots_html, naismith_time

# Streamlit pattern - https://docs.streamlit.io
st.set_page_config(
    page_title=f"Find · {APP_TITLE}",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# We assign a number to each verdict so we can sort the list. Lower numbers
# come first, which means SAFE trails always end up at the top of the results.
VERDICT_RANK = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2, "—": 3}
TOP_N: int = 10
FORECAST_HORIZON_DAYS: int = 6


def render_quiz(meta: dict) -> dict | None:
    """Render the 5-question quiz + date picker. Return answers on submit."""
    st.markdown(
        section_heading(
            t("Tune your trail day"),
            t("Filter by region, grade, distance and altitude. The ranking still uses the same forecast and model logic underneath."),
            t("Personalized search"),
        ),
        unsafe_allow_html=True,
    )

    today = date.today()
    # When this counter goes up, all the widget keys below change too.
    # Streamlit then treats them as brand-new widgets and resets them
    # back to their default values. We use this to power the "Clear" button.
    v = st.session_state.get("quiz_reset_counter", 0)

    # Two-column layout: filters on the left, distance/altitude/date on the right.
    # Streamlit pattern - https://docs.streamlit.io
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            cantons = st.multiselect(
                t("Cantons"),
                options=meta["cantons"],
                placeholder=t("Any canton"),
                help=t("Leave empty to search all Swiss cantons."),
                key=f"quiz_cantons_{v}",
            )
            regions = st.multiselect(
                t("Regions"),
                options=meta["regions"],
                placeholder=t("Any region"),
                help=t("Alps · Pre-Alps · Jura · Mittelland. Empty = all."),
                key=f"quiz_regions_{v}",
            )
            difficulties = st.multiselect(
                t("SAC grade"),
                options=meta["difficulties"],
                placeholder=t("Any grade"),
                help=t("T1 = strolling · T6 = serious alpine. Empty = all."),
                key=f"quiz_difficulties_{v}",
            )
        with c2:
            length_lo, length_hi = st.slider(
                t("Distance"),
                min_value=float(int(meta["min_length_km"])),
                max_value=float(int(meta["max_length_km"]) + 1),
                value=(
                    float(int(meta["min_length_km"])),
                    float(int(meta["max_length_km"]) + 1),
                ),
                step=0.5,
                key=f"quiz_length_{v}",
                help=t("Route length in kilometres."),
            )
            alt_lo, alt_hi = st.slider(
                t("Highest point"),
                min_value=int(meta["min_max_alt_m"]),
                max_value=int(meta["max_max_alt_m"]),
                value=(int(meta["min_max_alt_m"]), int(meta["max_max_alt_m"])),
                step=50,
                key=f"quiz_alt_{v}",
                help=t("Maximum altitude reached by the trail."),
            )
            # The radio shows translated labels but we keep the English
            # option values so the comparison below ("== Today") still works.
            mode = st.radio(
                t("Date window"),
                ["Today", "Pick a date"],
                horizontal=True,
                format_func=t,
                help=t("Forecasts cover today + the next {n} days.",
                       n=FORECAST_HORIZON_DAYS),
                key=f"quiz_mode_{v}",
            )
            if mode == "Today":
                chosen_date = today
                st.caption(f"📅 {fmt_date(today, 'full')}")
            else:
                chosen_date = st.date_input(
                    t("Date"),
                    value=today,
                    min_value=today,
                    max_value=today + timedelta(days=FORECAST_HORIZON_DAYS),
                    key=f"quiz_date_{v}",
                )

        submitted = st.button(
            t("🧭 Find my best hikes"), type="primary", use_container_width=True
        )

    if not submitted:
        return None

    # Empty multiselects collapse to None so the DB filter treats them as "any".
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


# How many trails we fetch weather for at the same time. More workers is
# faster but Open-Meteo will start blocking us if we go too high.
PARALLEL_WORKERS: int = 8
# If the first try fails, we attempt one more time before giving up.
MAX_FETCH_RETRIES: int = 1


def _ensure_snapshot(trail, target_date: date) -> tuple[dict | None, str | None]:
    """Try hard to get a cached snapshot for ``(trail, target_date)``.

    Returns ``(snapshot_dict_or_none, error_message_or_none)``. We try the
    cache first, then a fetch, then a forced re-fetch as a last resort. The
    last error message is kept so the UI can explain why a trail is
    missing, instead of just silently showing "no data".
    """
    # If we already have a saved forecast for this trail and date, just use it.
    snap = db_manager.get_weather_for_date(trail["id"], target_date)
    if snap is not None:
        return dict(snap), None

    # Otherwise call the Open-Meteo API to fetch fresh weather. If the first
    # attempt fails, we try one more time with force=True (which ignores any
    # stale data in the cache).
    # Open-Meteo Forecast API - https://open-meteo.com/en/docs
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
    """Score one trail. Always returns a complete row (even on failure).

    If the weather fetch fails we still return a result row, just with the
    placeholder verdict. That way the user can see the trail appears in the
    catalogue, instead of it silently disappearing.
    """
    snap, err = _ensure_snapshot(trail, target_date)

    # No weather data, so we return a placeholder. The rank_key is set high
    # so this trail ends up at the bottom of the list.
    if snap is None:
        return {
            "trail": trail,
            "snapshot": None,
            "verdict": "—",
            "adjusted": "—",
            "confidence": 0.0,
            "source": "no data",
            "error": err,
            "caveats": [],
            "rank_key": (VERDICT_RANK["—"], 1.0, trail["name"].lower()),
        }

    # Ask the ML model (or the simple rule engine if the model is not trained)
    # for a verdict. Then adjust it based on trail difficulty and the user's
    # risk tolerance to get the final verdict we show on the card.
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
    """Score every trail at the same time using a small group of workers.

    Without parallel workers, scoring 234 trails one at a time would take
    too long. ThreadPoolExecutor sends multiple requests at once so the
    page feels responsive. A progress bar shows the user it's working.
    """
    # ThreadPoolExecutor works well here because the slow part is waiting for
    # the Open-Meteo API to respond (not heavy Python work).
    results: list[dict] = []
    progress = st.progress(
        0.0,
        text=t("Checking the forecast for {n} trail(s)…", n=len(candidates)),
    )
    done = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futures = {
            ex.submit(_score_trail, trail, target_date, risk): trail
            for trail in candidates
        }
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            progress.progress(
                done / len(candidates),
                text=t("Scored {done}/{total} trails…",
                       done=done, total=len(candidates)),
            )
    progress.empty()
    return results


# Top-level results renderer: success banner, stat pills, error expander,
# and a 3-column grid of cards (with a "show more" expander beyond TOP_N).
def render_results(results: list[dict], target_date: date) -> None:
    if not results:
        st.warning(
            t("No trails matched your quiz answers. Loosen the filters and try again.")
        )
        return

    # Count how many trails fell into each verdict bucket. We use this for
    # the small summary line and the colored pills below the search results.
    summary = {"SAFE": 0, "BORDERLINE": 0, "AVOID": 0, "—": 0}
    for r in results:
        summary[r["adjusted"]] = summary.get(r["adjusted"], 0) + 1

    st.success(
        t(
            "Ranked **{n}** matching trail(s) for **{d}**. 🟢 {safe} · 🟠 "
            "{borderline} · 🔴 {avoid} · ⚪ {nodata}",
            n=len(results),
            d=fmt_date(target_date, "full"),
            safe=summary["SAFE"],
            borderline=summary["BORDERLINE"],
            avoid=summary["AVOID"],
            nodata=summary["—"],
        )
    )
    st.markdown(
        stat_pills_html(
            [
                (t("safe"), summary["SAFE"]),
                (t("borderline"), summary["BORDERLINE"]),
                (t("avoid"), summary["AVOID"]),
                (t("no data"), summary["—"]),
            ]
        ),
        unsafe_allow_html=True,
    )

    # Show failed fetches clearly so the user knows what is missing and why.
    # We never want to hide errors behind a generic "no data" label.
    failed = [r for r in results if r.get("error")]
    if failed:
        sample_errors = sorted({r["error"] for r in failed})[:3]
        with st.expander(
            t("⚠️ {n} trail(s) couldn't be scored — show details",
              n=len(failed)),
            expanded=False,
        ):
            st.markdown(
                t("These trails appear in the list with **no data**. The most "
                  "common cause is a transient Open-Meteo API hiccup — usually "
                  "fixes itself; click **🔁 Re-run search** above to retry.")
            )
            st.markdown(t("**Sample error message(s):**"))
            for e in sample_errors:
                st.code(e)
            st.markdown(t("**Affected trails:**"))
            st.write(
                ", ".join(r["trail"]["name"] for r in failed[:30])
                + ("…" if len(failed) > 30 else "")
            )

    st.markdown(
        section_heading(
            t("Top {n} hikes", n=min(TOP_N, len(results))),
            t("Open any recommendation for the route map, weather breakdown, tricky parts, photos and reports."),
            t("Ranked recommendations"),
        ),
        unsafe_allow_html=True,
    )
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    top = results[:TOP_N]

    # Top-N grid. Wraps every 3 cards using a modulo on the column index.
    # Streamlit pattern - https://docs.streamlit.io
    cols = st.columns(3, gap="large")
    for i, r in enumerate(top):
        with cols[i % 3]:
            _render_result_card(r, target_date, image_index=i)

    if len(results) > TOP_N:
        with st.expander(t("Show the other {n} matches", n=len(results) - TOP_N)):
            tail_cols = st.columns(3, gap="large")
            for i, r in enumerate(results[TOP_N:]):
                with tail_cols[i % 3]:
                    _render_result_card(r, target_date, compact=True, image_index=i)


# ---------------------------------------------------------------------------
# Card design - inspired by Norgeskart-style route list (clean white cards
# on a soft background, 4-dot SAC indicator, 3-column metrics row).
# ---------------------------------------------------------------------------

# Inline CSS for the result cards (white card, image hero, 3-stat row,
# coloured verdict pill, optional amber safety note).
_CARD_CSS: str = """
<style>
  .hike-card {
    background: #ffffff;
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 28px;
    padding: .72rem;
    margin-bottom: .65rem;
    box-shadow: 0 18px 42px rgba(21, 39, 32, .08);
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
    emoji = VERDICT_EMOJI.get(verdict, "⚪")

    # Naismith's rule is a simple walking-time formula used by hikers:
    # 12 minutes per kilometer plus 10 minutes for every 100 meters of climb.
    ascent = trail["max_alt_m"] - trail["min_alt_m"]
    time_est = naismith_time(trail["length_km"], ascent)

    pill = (
        f"<span class='verdict-pill {status_class(verdict)}'>"
        f"{escape(emoji)} {escape(verdict_label(verdict))}"
        f"</span>"
    )

    caveat_html = ""
    if r.get("caveats"):
        caveat_html = (
            f"<div class='safety-note'>⚠️ <b>{escape(t('Safety note'))}:</b> "
            f"{escape(r['caveats'][0])}</div>"
        )

    snap = r.get("snapshot") or {}
    weather_chip = ""
    if snap.get("temp_c") is not None and snap.get("wind_kmh") is not None:
        weather_chip = (
            f"<span style='color:#6b7177;'>"
            f"🌡️ {snap['temp_c']:.0f}°C · 💨 {snap['wind_kmh']:.0f} km/h"
            f"</span>"
        )

    st.markdown(
        f"""
        <div class="hike-card">
          <div class="hike-card-image" style="background-image:url('{escape(image_for_index(image_index))}');">
            {pill}
          </div>
          <div class="hike-card-body">
            <div class="hike-card-title">{escape(trail['name'])}</div>
            <div class="hike-card-meta">
              {difficulty_dots_html(trail['difficulty'])}
              <div style="margin-top:.45rem;">
                {escape(trail['canton'])} · {escape(trail['region'])} · {weather_chip}
              </div>
            </div>
            <div class="hike-stats">
              <div>
                <div class="hike-stat-value">{escape(time_est)}</div>
                <div class="hike-stat-label">{escape(t("Time"))}</div>
              </div>
              <div>
                <div class="hike-stat-value">{ascent} m</div>
                <div class="hike-stat-label">{escape(t("Ascent"))}</div>
              </div>
              <div>
                <div class="hike-stat-value">{trail['length_km']} km</div>
                <div class="hike-stat-label">{escape(t("Length"))}</div>
              </div>
            </div>
            {caveat_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # When the user clicks "View details" we save the trail and date in
    # session state, then jump to the Trail Detail page. Streamlit pages
    # share data through session state so we don't lose this when we switch.
    key = f"detail_{'tail_' if compact else ''}{trail['id']}"
    if st.button(t("View details"), key=key, width="stretch"):
        st.session_state["selected_trail_id"] = trail["id"]
        st.session_state["selected_date"] = target_date
        st.switch_page("pages/Trail_Detail.py")


def render_recent_community_feed() -> None:
    """Bottom-of-page community section: most recent hiker reports."""
    st.divider()
    st.markdown(
        section_heading(
            t("Recent reports from hikers"),
            t("Community reports become training signal the next time the model is retrained."),
            t("Trail notes"),
        ),
        unsafe_allow_html=True,
    )
    # Pull the most recent user-submitted hike reports. Used as light social
    # proof and as a hint that submitted reports feed the next retrain.
    rows = db_manager.get_recent_user_reports(limit=6)
    if not rows:
        st.caption(
            t("No reports yet. Open any trail's detail page and submit one "
              "after your hike — they go straight into the model on the next retrain.")
        )
        return
    cols = st.columns(min(3, len(rows)))
    for col, r in zip(cols, rows):
        emoji = VERDICT_EMOJI.get(r["user_label"], "⚪")
        comment = (r["comment"] or "").strip() or t("_no comment_")
        with col:
            with st.container(border=True):
                st.markdown(
                    f"{emoji} **{r['trail_name']}** — "
                    f"{verdict_label(r['user_label'])}  \n"
                    f"_{r['report_date']}_  \n{comment}"
                )


def _answers_signature(answers: dict) -> str:
    """Build a stable text fingerprint of the quiz answers.

    We use this to decide if we can reuse the previous result list. If the
    fingerprint changes, the cached results are thrown away and we run a
    fresh search.
    """
    serialisable = {
        k: (v.isoformat() if isinstance(v, date) else v) for k, v in answers.items()
    }
    return json.dumps(serialisable, sort_keys=True, default=str)


# Page entry point: nav + sidebar + theme, then quiz/results flow.
def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    apply_app_theme()

    st.markdown(
        page_hero(
            t("Find my best hike"),
            t("Tell us what kind of day you want and when. We cross-reference your preferences with the live weather forecast and rank matching hikes safest first."),
            t("AI trail finder"),
        ),
        unsafe_allow_html=True,
    )

    # Quiz options (canton list, min/max length, etc.) come from a single
    # SQL roll-up so the widgets always match what's actually in the DB.
    meta = db_manager.get_trail_metadata()
    if not meta["cantons"]:
        st.error(t("No trails seeded. Restart the app or run bootstrap."))
        return

    # 1) Show the quiz. ``submitted_answers`` is only set on the run right
    #    after the user clicks Submit. We save it in session state so the
    #    results stay visible when Streamlit reruns the page later (for
    #    example when the user clicks a "View details" button on a card).
    submitted_answers = render_quiz(meta)
    if submitted_answers is not None:
        st.session_state["find_answers"] = submitted_answers
        # The user just submitted new answers, so any old cached results
        # are out of date. We delete them so a fresh search will run below.
        st.session_state.pop("find_results", None)
        st.session_state.pop("find_answers_sig", None)

    answers = st.session_state.get("find_answers")
    if answers is None:
        st.info(
            t("👆 Fill in the filters and hit **Find matching hikes** to see your "
              "ranked recommendations.")
        )
        render_recent_community_feed()
        return

    # 2) "Reset" control so the user can start over.
    bar = st.columns([1, 5])
    with bar[0]:
        if st.button(t("✖ Clear & restart"), use_container_width=True):
            st.session_state.pop("find_answers", None)
            st.session_state.pop("find_results", None)
            st.session_state.pop("find_answers_sig", None)
            st.session_state["quiz_reset_counter"] = (
                st.session_state.get("quiz_reset_counter", 0) + 1
            )
            st.rerun()

    # 3) Either compute new results, or reuse the ones we already have. We
    #    compare a fingerprint of the answers. If it matches what we saved
    #    before, we skip the slow fetch and reuse the cached results.
    sig = _answers_signature(answers)
    cache_hit = (
        st.session_state.get("find_answers_sig") == sig
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
                t("No trails match your quiz answers. Try widening the canton, "
                  "difficulty, or length filters.")
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
