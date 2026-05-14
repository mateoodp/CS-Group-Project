"""Automatic background weather caching. No "refresh" button needed.

The user should never have to think about whether the weather cache is
up to date. So at the top of each page's ``main()`` we call
``ensure_weather_cached(...)``. This module quietly fetches any missing
forecasts for today's date in the background. It only shows a spinner
on the first run, and only briefly.

A few tuning choices worth knowing:

* 4 parallel workers. We tested with 8, but Open-Meteo started rate
  limiting us around 10 concurrent requests. 4 is comfortably under
  the limit and still gives a good speedup.
* One retry. If the first attempt fails, we try one more time with
  ``force=True`` (which clears any stale partial cache). After that
  we give up and the page treats the trail as having no data.
* We memoise in ``st.session_state`` so this only runs once per
  Streamlit session for the same group of trails.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import streamlit as st

from data import db_manager, weather_fetcher

PARALLEL_WORKERS: int = 4
MAX_RETRIES: int = 1


def _fetch_one(trail) -> bool:
    """Refresh one trail's weather cache. Returns True on success."""
    # We try at most twice. The first attempt respects the existing cache.
    # If it fails (typically a network error), the second attempt sets
    # force=True so any partly-written cache gets overwritten cleanly.
    for attempt in range(MAX_RETRIES + 1):
        try:
            weather_fetcher.refresh_cache(
                trail["id"],
                trail["lat"],
                trail["lon"],
                force=(attempt > 0),
            )
            return True
        except Exception:
            if attempt == MAX_RETRIES:
                return False
    return False


def trails_missing_for_date(trails, target_date: date) -> list[dict]:
    return [
        t
        for t in trails
        if db_manager.get_weather_for_date(t["id"], target_date) is None
    ]


def trails_missing_today(trails) -> list[dict]:
    return trails_missing_for_date(trails, date.today())


def ensure_weather_cached(
    trails,
    *,
    page_key: str,
    target_date: date | None = None,
    quiet: bool = False,
) -> tuple[int, int]:
    """Make sure each trail has a cached forecast for the target date.

    Safe to call as many times as you want during a Streamlit session.
    The function remembers what it's already tried and won't redo the
    work. ``page_key`` lets each page keep its own memo (so "map" and
    "compare" can both run without stepping on each other).

    Returns a tuple of ``(succeeded_count, failed_count)``. If you set
    ``quiet=True`` we skip the spinner UI on the first run too, which
    is nice for very small trail lists where the fetch is fast anyway.
    """
    target_date = target_date or date.today()
    missing = trails_missing_for_date(trails, target_date)
    if not missing:
        return 0, 0

    # Streamlit session state pattern - https://docs.streamlit.io/library/api-reference/session-state
    # Build a memo key combining the page name and the target date. If this
    # key already exists in session state, we've tried this combination
    # before and we don't need to try again.
    memo_key = f"_data_health_done__{page_key}__{target_date.isoformat()}"
    if st.session_state.get(memo_key):
        # We already attempted the fetch in this session. We still report
        # the count of trails that are missing data, so the page can show
        # the user a small warning if needed.
        return 0, len(missing)

    if not quiet:
        spinner_msg = (
            f"⏳ Pulling weather for {len(missing)} trail(s)… "
            "this only happens once per session."
        )
        spinner = st.spinner(spinner_msg)
    else:
        spinner = None

    succeeded = failed = 0
    if spinner:
        with spinner:
            succeeded, failed = _do_fetch(missing)
    else:
        succeeded, failed = _do_fetch(missing)

    st.session_state[memo_key] = True
    return succeeded, failed


def _do_fetch(trails) -> tuple[int, int]:
    """Fetch all the trails in parallel. Returns (ok_count, failed_count)."""
    succeeded = failed = 0
    # ThreadPoolExecutor pattern - https://docs.python.org/3/library/concurrent.futures.html
    # We limit ourselves to PARALLEL_WORKERS workers at a time. This keeps
    # the total request rate well under Open-Meteo's limit and is fast
    # enough that the page feels responsive.
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futures = [ex.submit(_fetch_one, t) for t in trails]
        for fut in as_completed(futures):
            if fut.result():
                succeeded += 1
            else:
                failed += 1
    return succeeded, failed
