"""Weather API client for the Hiking Forecaster.

Owner: TM3 (Data / API Lead)

Three free APIs, no keys required:

1. **Open-Meteo Forecast** — current + 7-day forecast.
   https://api.open-meteo.com/v1/forecast
2. **Open-Meteo Archive** — 2 years of historical daily weather.
   https://archive-api.open-meteo.com/v1/archive
3. **Swisstopo GeoAdmin** — trail GPS and elevation profile.
   https://api3.geo.admin.ch

Data fetched here is written through ``db_manager`` into the
``weather_snapshots`` table.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import requests

from data import db_manager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
GEOADMIN_URL: str = "https://api3.geo.admin.ch/rest/services/all/MapServer/identify"

CACHE_TTL_HOURS: int = 1              # how old live data can be before refetch
HISTORY_YEARS: int = 2                 # 2 years of archive → ~730 rows/trail
REQUEST_TIMEOUT_S: int = 15            # seconds before giving up on an API call


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_forecast(lat: float, lon: float) -> dict:
    """Fetch current + 7-day daily forecast for a coordinate.

    Returns the raw JSON ``daily`` block from Open-Meteo. Caller is
    responsible for mapping it to DB rows via ``upsert_weather_snapshot``.

    Variables requested (matches ML feature set):
        * temperature_2m_max / _min
        * wind_speed_10m_max
        * wind_gusts_10m_max
        * precipitation_sum
        * snowfall_sum
        * cloud_cover_mean
        * freezing_level_height  (the 0°C isotherm = snowline)

    TODO (TM3): build the params dict, call requests.get, handle errors.
    """
    raise NotImplementedError


def fetch_archive(
    lat: float, lon: float, start: date, end: date
) -> dict:
    """Fetch historical daily weather between ``start`` and ``end``.

    Used once per trail at setup to seed the ML training data (~730 rows).

    TODO (TM3): implement. Same variables as ``fetch_forecast``.
    """
    raise NotImplementedError


def fetch_trail_elevation(lat: float, lon: float) -> list[dict]:
    """Return an elevation profile for a point via GeoAdmin (optional).

    TODO (TM3 or TM1): implement. Used by the Dashboard elevation chart.
    If GeoAdmin proves unreliable, fall back to Open-Meteo's elevation.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Cache logic
# ---------------------------------------------------------------------------

def refresh_cache(trail_id: int, lat: float, lon: float) -> None:
    """Refresh the cache for a trail if older than ``CACHE_TTL_HOURS``.

    Workflow:
        1. Check the most-recent ``weather_snapshots`` row for this trail.
        2. If older than TTL, call ``fetch_forecast`` and upsert 7 rows.
        3. Update ``st.session_state['last_weather_refresh']`` in the UI.

    TODO (TM3): implement.
    """
    raise NotImplementedError


def seed_historical_weather(trail_id: int, lat: float, lon: float) -> None:
    """One-shot: download 2 years of archive weather for a trail.

    Called by the ML setup script. Safe to re-run — upsert will dedupe.

    TODO (TM3): implement. Show a progress message in Streamlit so the
    user knows it's working (archive calls take ~2–5s per trail).
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get(url: str, params: dict) -> dict:
    """Thin wrapper around ``requests.get`` with timeout and error handling.

    TODO (TM3): implement. Raise a clear error message on non-200, rather
    than letting requests raise the raw HTTPError.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# CLI helper — python -m data.weather_fetcher
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick smoke test: fetch 3 days of forecast for Säntis.
    print("Fetching forecast for Säntis (47.2493, 9.3432)…")
    data = fetch_forecast(47.2493, 9.3432)
    print(data)
