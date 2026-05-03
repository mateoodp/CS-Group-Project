"""Automatic background weather caching — no user button required.

The user shouldn't have to think about whether the cache is warm. Pages
call :func:`ensure_weather_cached` near the top of their ``main()`` and
this module silently fetches anything missing for *today's* date,
showing a brief spinner only on the first run of the day.

Tuning notes:

* **4 parallel workers** — friendlier to Open-Meteo than 8. Burst
  requests above ~10 concurrent get rate-limited (we observed this
  during validation runs).
* **One retry** with ``force=True`` if the first request times out.
* Always cached in ``st.session_state`` — never re-runs more than once
  per Streamlit session for the same trail set.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import streamlit as st

from data import db_manager, weather_fetcher

PARALLEL_WORKERS: int = 4
MAX_RETRIES: int = 1


def _fetch_one(trail) -> bool:
    """Refresh one trail's cache. Retry once on failure."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            weather_fetcher.refresh_cache(
                trail["id"], trail["lat"], trail["lon"],
                force=(attempt > 0),
            )
            return True
        except Exception:
            if attempt == MAX_RETRIES:
                return False
    return False


def trails_missing_today(trails) -> list[dict]:
    today = date.today()
    return [
        t for t in trails
        if db_manager.get_weather_for_date(t["id"], today) is None
    ]


def ensure_weather_cached(
    trails,
    *,
    page_key: str,
    quiet: bool = False,
) -> tuple[int, int]:
    """Fetch missing forecasts for the given trails, in the background.

    Idempotent within a Streamlit session: if we've already attempted to
    cover the same trail set, we don't re-run. ``page_key`` namespaces
    the once-per-session memo (e.g. ``"map"``, ``"compare"``).

    Returns ``(succeeded, failed)``. When ``quiet=True`` no UI is shown
    even on first run — useful for very small trail sets where the
    fetch is essentially instant.
    """
    today = date.today()
    missing = trails_missing_today(trails)
    if not missing:
        return 0, 0

    memo_key = f"_data_health_done__{page_key}__{today.isoformat()}"
    if st.session_state.get(memo_key):
        # Already attempted in this session; surface failures count only.
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
    """Run the parallel fetch. Returns (ok, failed)."""
    succeeded = failed = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futures = [ex.submit(_fetch_one, t) for t in trails]
        for fut in as_completed(futures):
            if fut.result():
                succeeded += 1
            else:
                failed += 1
    return succeeded, failed
