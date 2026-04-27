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

CACHE_TTL_HOURS: int = 1               # how old live data can be before refetch
HISTORY_YEARS: int = 2                 # 2 years of archive → ~730 rows/trail
REQUEST_TIMEOUT_S: int = 15            # seconds before giving up on an API call

# Daily variables shared by forecast and archive endpoints.
_DAILY_VARS: list[str] = [
    "temperature_2m_max",
    "temperature_2m_min",
    "wind_speed_10m_max",
    "precipitation_sum",
    "snowfall_sum",
    "cloud_cover_mean",
]

# Hourly variable used to derive a daily snowline (0°C isotherm).
_HOURLY_VARS: list[str] = ["freezing_level_height"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get(url: str, params: dict) -> dict:
    """Thin wrapper around ``requests.get`` with timeout and clear errors."""
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as e:
        raise RuntimeError(f"Network error calling {url}: {e}") from e
    if resp.status_code != 200:
        raise RuntimeError(
            f"API call to {url} failed: HTTP {resp.status_code} — {resp.text[:200]}"
        )
    return resp.json()


def _hourly_to_daily_snowline(hourly: dict) -> dict[str, float]:
    """Collapse hourly freezing_level_height into a per-day mean (metres)."""
    times = hourly.get("time", [])
    levels = hourly.get("freezing_level_height", [])
    buckets: dict[str, list[float]] = {}
    for t, lvl in zip(times, levels):
        if lvl is None:
            continue
        day = t[:10]
        buckets.setdefault(day, []).append(float(lvl))
    return {d: sum(v) / len(v) for d, v in buckets.items() if v}


LAPSE_RATE_C_PER_M: float = 0.0065   # standard environmental lapse rate


def _estimated_snowline(temp_c: float, point_elevation_m: float) -> float:
    """Estimate the 0°C isotherm from surface temperature + elevation.

    Used as a fallback when the API's ``freezing_level_height`` is missing
    (the archive endpoint returns null for it). Standard meteorology: temp
    drops ~6.5°C per 1000 m of altitude, so the 0°C line sits at::

        snowline = elevation + temp_c / 0.0065

    Clamped to [0, 6000] to keep the model from seeing absurd values.
    """
    if temp_c is None:
        return 0.0
    snow = point_elevation_m + (temp_c / LAPSE_RATE_C_PER_M)
    return max(0.0, min(snow, 6000.0))


def _daily_block_to_rows(
    trail_id: int,
    daily: dict,
    snowline_by_day: dict[str, float],
    point_elevation_m: float,
) -> list[dict]:
    """Convert an Open-Meteo ``daily`` block into upsert-ready dict rows."""
    times = daily.get("time", [])
    rows: list[dict] = []
    for i, day in enumerate(times):
        tmax = daily["temperature_2m_max"][i]
        tmin = daily["temperature_2m_min"][i]
        temp_mean = (
            (tmax + tmin) / 2.0
            if tmax is not None and tmin is not None
            else (tmax if tmax is not None else tmin)
        )
        snowline = snowline_by_day.get(day)
        if snowline is None and temp_mean is not None:
            snowline = _estimated_snowline(temp_mean, point_elevation_m)
        rows.append(
            {
                "trail_id": trail_id,
                "snapshot_date": day,
                "temp_c": temp_mean,
                "wind_kmh": daily["wind_speed_10m_max"][i],
                "precip_mm": (daily["precipitation_sum"][i] or 0.0)
                + (daily["snowfall_sum"][i] or 0.0),
                "snowline_m": snowline,
                "cloud_pct": daily["cloud_cover_mean"][i],
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Public API — forecast / archive
# ---------------------------------------------------------------------------

def fetch_forecast(lat: float, lon: float) -> dict:
    """Fetch current + 7-day daily forecast for a coordinate.

    Returns the raw JSON dict from Open-Meteo (top-level, not just ``daily``).
    Hourly freezing_level_height is included so callers can derive the snowline.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(_DAILY_VARS),
        "hourly": ",".join(_HOURLY_VARS),
        "timezone": "Europe/Zurich",
        "forecast_days": 7,
    }
    return _get(FORECAST_URL, params)


def fetch_archive(
    lat: float, lon: float, start: date, end: date
) -> dict:
    """Fetch historical daily weather between ``start`` and ``end``."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(_DAILY_VARS),
        "hourly": ",".join(_HOURLY_VARS),
        "timezone": "Europe/Zurich",
    }
    return _get(ARCHIVE_URL, params)


def fetch_trail_elevation(lat: float, lon: float) -> Optional[float]:
    """Single-point elevation in metres via Open-Meteo (GeoAdmin fallback).

    Open-Meteo returns the requested point's elevation in every forecast call,
    so this is essentially free. Returns ``None`` on failure.
    """
    try:
        data = _get(
            FORECAST_URL,
            {"latitude": lat, "longitude": lon, "timezone": "Europe/Zurich"},
        )
        return data.get("elevation")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cache logic
# ---------------------------------------------------------------------------

def refresh_cache(trail_id: int, lat: float, lon: float, force: bool = False) -> int:
    """Refresh the 7-day forecast cache for a trail.

    Returns the number of rows upserted. If the cache is fresh
    (``< CACHE_TTL_HOURS`` since the most recent ``snapshot_date``), this is
    a no-op unless ``force=True``.
    """
    if not force:
        age_h = db_manager.get_latest_snapshot_age_hours(trail_id)
        if age_h is not None and age_h < CACHE_TTL_HOURS:
            return 0

    data = fetch_forecast(lat, lon)
    snowline = _hourly_to_daily_snowline(data.get("hourly", {}))
    elev = data.get("elevation") or 0.0
    rows = _daily_block_to_rows(trail_id, data.get("daily", {}), snowline, elev)
    db_manager.upsert_weather_snapshots_bulk(rows)
    return len(rows)


def seed_historical_weather(
    trail_id: int, lat: float, lon: float, years: int = HISTORY_YEARS
) -> int:
    """Download historical archive weather for a trail.

    Idempotent — upsert deduplicates by (trail_id, snapshot_date). Returns
    the number of rows upserted.
    """
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=int(365 * years))
    data = fetch_archive(lat, lon, start, end)
    snowline = _hourly_to_daily_snowline(data.get("hourly", {}))
    elev = data.get("elevation") or 0.0
    rows = _daily_block_to_rows(trail_id, data.get("daily", {}), snowline, elev)
    db_manager.upsert_weather_snapshots_bulk(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# CLI helper — python -m data.weather_fetcher
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Fetching forecast for Säntis (47.2493, 9.3432)…")
    data = fetch_forecast(47.2493, 9.3432)
    print({k: v for k, v in data.items() if k in ("latitude", "longitude", "elevation")})
    print("Daily keys:", list(data.get("daily", {}).keys()))
