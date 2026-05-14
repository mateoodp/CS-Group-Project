"""Weather API client for the Hiking Forecaster.

Owner: TM3 (Data / API Lead)

We use three free public APIs, none of which require an API key:

1. Open-Meteo Forecast: gives us current and 7-day forecast.
   https://api.open-meteo.com/v1/forecast
2. Open-Meteo Archive: gives us up to two years of past daily weather.
   We use this to seed the training data.
   https://archive-api.open-meteo.com/v1/archive
3. Swisstopo GeoAdmin: gives us trail GPS and elevation lookups.
   https://api3.geo.admin.ch

Everything this module fetches is saved into the weather_snapshots
table through the db_manager helpers.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import requests

from data import db_manager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Open-Meteo Forecast API - https://open-meteo.com/en/docs
FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
# Open-Meteo Historical Archive API - https://open-meteo.com/en/docs/historical-weather-api
ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
# Swisstopo GeoAdmin API - https://docs.geo.admin.ch/access-data/identify-features.html
GEOADMIN_URL: str = "https://api3.geo.admin.ch/rest/services/all/MapServer/identify"

CACHE_TTL_HOURS: int = 1  # cached weather older than this is considered stale
HISTORY_YEARS: int = 2  # 2 years of archive gives us roughly 730 rows per trail
REQUEST_TIMEOUT_S: int = 15  # how long we wait for an API response before giving up
FORECAST_DAYS: int = 7  # how many days ahead we ask Open-Meteo to forecast

# Daily weather variables we ask Open-Meteo for. Both the forecast and
# the archive endpoints accept the same field names. These names have
# to match Open-Meteo's docs exactly or the request fails.
_DAILY_VARS: list[str] = [
    "temperature_2m_max",
    "temperature_2m_min",
    "wind_speed_10m_max",
    "precipitation_sum",
    "snowfall_sum",
    "cloud_cover_mean",
]

# We also ask for one hourly variable: freezing_level_height. This is the
# altitude where the air temperature crosses 0 degrees. From the 24 hourly
# samples we average a daily snowline value to use in the model.
_HOURLY_VARS: list[str] = ["freezing_level_height"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get(url: str, params: dict) -> dict:
    """A small wrapper around requests.get with a timeout and clear errors."""
    # We don't hard-code the URL because the same function calls both
    # the forecast and the archive endpoints.
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as e:
        # We catch any requests-library exception and re-raise it as a
        # plain RuntimeError. That way the rest of the app only has to
        # worry about one kind of error, regardless of what went wrong.
        raise RuntimeError(f"Network error calling {url}: {e}") from e
    if resp.status_code != 200:
        # We trim the error body to the first 200 characters so the
        # message stays readable when shown in the UI or logged.
        raise RuntimeError(
            f"API call to {url} failed: HTTP {resp.status_code} — {resp.text[:200]}"
        )
    return resp.json()


def _hourly_to_daily_snowline(hourly: dict) -> dict[str, float]:
    """Turn 24 hourly snowline readings into one daily average per day."""
    times = hourly.get("time", [])
    levels = hourly.get("freezing_level_height", [])
    # Group all the hourly readings by their date. Each timestamp from
    # the API looks like "2024-06-15T08:00", so the first 10 characters
    # are the date and we use that as a bucket key.
    buckets: dict[str, list[float]] = {}
    for t, lvl in zip(times, levels):
        if lvl is None:
            continue
        day = t[:10]
        buckets.setdefault(day, []).append(float(lvl))
    # The daily snowline value is the average of all the hourly readings
    # we collected for that day.
    return {d: sum(v) / len(v) for d, v in buckets.items() if v}


LAPSE_RATE_C_PER_M: float = 0.0065  # standard environmental lapse rate


def _estimated_snowline(temp_c: float, point_elevation_m: float) -> float:
    """Estimate the snowline altitude from a temperature and an elevation.

    We use this as a fallback when the API doesn't give us a freezing
    level value (the archive endpoint often returns nulls for it).
    The math comes from the standard lapse rate: air gets about
    6.5 degrees colder per 1000 m of climb. So if we measure the
    temperature at a known elevation, we can work out how much higher
    we'd need to climb before reaching 0 degrees:

        snowline = elevation + temp_c / 0.0065

    We clamp the result to a sensible range so a stray bad reading
    doesn't feed an extreme number into the model.
    """
    if temp_c is None:
        return 0.0
    # The math here is the lapse rate equation rearranged. We start at
    # the measurement elevation and add how far above it the freezing
    # level sits, given our current temperature.
    snow = point_elevation_m + (temp_c / LAPSE_RATE_C_PER_M)
    # Cap the value between 0 m and 6000 m. The troposphere essentially
    # never has a freezing level higher than that in the real world.
    return max(0.0, min(snow, 6000.0))


def _daily_block_to_rows(
    trail_id: int,
    daily: dict,
    snowline_by_day: dict[str, float],
    point_elevation_m: float,
) -> list[dict]:
    """Convert Open-Meteo's daily block into rows ready to insert into our DB."""
    times = daily.get("time", [])
    rows: list[dict] = []
    for i, day in enumerate(times):
        # Open-Meteo gives us a daily min and max temperature. We turn
        # those into one daily mean for the database. If only one of
        # them is present, we still use that single value rather than
        # losing the whole day.
        tmax = daily["temperature_2m_max"][i]
        tmin = daily["temperature_2m_min"][i]
        temp_mean = (
            (tmax + tmin) / 2.0
            if tmax is not None and tmin is not None
            else (tmax if tmax is not None else tmin)
        )
        # If we got a real freezing level reading from the API, use it.
        # Otherwise estimate one from temperature and elevation. The
        # archive endpoint returns null for this variable a lot of the
        # time, so the fallback is important.
        snowline = snowline_by_day.get(day)
        if snowline is None and temp_mean is not None:
            snowline = _estimated_snowline(temp_mean, point_elevation_m)
        rows.append(
            {
                "trail_id": trail_id,
                "snapshot_date": day,
                "temp_c": temp_mean,
                "wind_kmh": daily["wind_speed_10m_max"][i],
                # Add rain (mm of water) and snowfall (mm of water
                # equivalent) into one single precipitation number.
                # Our model only cares about total moisture, not the
                # split between rain and snow.
                "precip_mm": (daily["precipitation_sum"][i] or 0.0)
                + (daily["snowfall_sum"][i] or 0.0),
                "snowline_m": snowline,
                "cloud_pct": daily["cloud_cover_mean"][i],
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Public API - forecast / archive
# ---------------------------------------------------------------------------


def fetch_forecast(lat: float, lon: float) -> dict:
    """Get the current weather and 7-day forecast for a given location.

    Returns the raw JSON response from Open-Meteo. We include the
    hourly freezing level alongside the daily values so the caller
    can compute a snowline from it.
    """
    # Open-Meteo Forecast API - https://open-meteo.com/en/docs
    # We ask for 7 days of forecast and we explicitly set the timezone
    # to Europe/Zurich. That way the date labels line up with what
    # users in Switzerland would expect.
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join(_DAILY_VARS),
        "hourly": ",".join(_HOURLY_VARS),
        "timezone": "Europe/Zurich",
        "forecast_days": 7,
    }
    return _get(FORECAST_URL, params)


def fetch_archive(lat: float, lon: float, start: date, end: date) -> dict:
    """Get historical daily weather for a location between two dates."""
    # Open-Meteo Historical Archive API - https://open-meteo.com/en/docs/historical-weather-api
    # We call this once per trail when seeding the training data.
    # Two years of history per trail gives us a good base for the model.
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
    """Look up the elevation at a single point, using Open-Meteo.

    Open-Meteo already includes the elevation of the requested point in
    every forecast response, so we get this for free. We make a minimal
    request (no weather variables) just to read the elevation field.
    Returns None if anything goes wrong.
    """
    # Open-Meteo Forecast API - https://open-meteo.com/en/docs
    # Minimal request: we just need the elevation, no daily/hourly data.
    try:
        data = _get(
            FORECAST_URL,
            {"latitude": lat, "longitude": lon, "timezone": "Europe/Zurich"},
        )
        return data.get("elevation")
    except Exception:
        # Any failure (network down, JSON parse error, missing field)
        # gives a clean None. The caller treats that as "unknown".
        return None


# ---------------------------------------------------------------------------
# Cache logic
# ---------------------------------------------------------------------------


def refresh_cache(trail_id: int, lat: float, lon: float, force: bool = False) -> int:
    """Refresh the 7-day forecast cache for one trail.

    Returns the number of rows we wrote into the database. If the cache
    is already fresh (the newest snapshot is less than CACHE_TTL_HOURS
    old), we skip the API call and return 0. Passing ``force=True``
    overrides that check and refetches anyway.
    """
    # Fast path: if every day in the next 7 is already cached AND the
    # newest cached row is still within the TTL, we don't need to call
    # Open-Meteo at all. We just return 0.
    if not force and _forecast_cache_complete(trail_id):
        age_h = db_manager.get_latest_snapshot_age_hours(trail_id)
        if age_h is not None and age_h < CACHE_TTL_HOURS:
            return 0

    # Otherwise call the API for fresh data, compute the daily snowline
    # from the hourly readings, build database rows, and bulk-insert
    # them all in one go.
    data = fetch_forecast(lat, lon)
    snowline = _hourly_to_daily_snowline(data.get("hourly", {}))
    elev = data.get("elevation") or 0.0
    rows = _daily_block_to_rows(trail_id, data.get("daily", {}), snowline, elev)
    db_manager.upsert_weather_snapshots_bulk(rows)
    return len(rows)


def _forecast_cache_complete(trail_id: int) -> bool:
    """Check if every forecast day for a trail is already in the cache."""
    today = date.today()
    # We check today and each of the next FORECAST_DAYS - 1 dates. As
    # soon as a single one is missing, we return False so the caller
    # knows we need to fetch fresh data.
    return all(
        db_manager.get_weather_for_date(trail_id, today + timedelta(days=i)) is not None
        for i in range(FORECAST_DAYS)
    )


def seed_historical_weather(
    trail_id: int, lat: float, lon: float, years: int = HISTORY_YEARS
) -> int:
    """Download a few years of historical weather for one trail.

    Safe to run multiple times: our database upsert pattern handles
    duplicates based on (trail_id, snapshot_date), so we never end up
    with two copies of the same day. Returns the number of rows we
    wrote.
    """
    # The archive endpoint only goes up to yesterday, so we use
    # yesterday as our end date. We go back ``years`` years from there
    # for the start date.
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=int(365 * years))
    data = fetch_archive(lat, lon, start, end)
    # Same helper as the forecast path uses to turn hourly readings
    # into one daily snowline value.
    snowline = _hourly_to_daily_snowline(data.get("hourly", {}))
    elev = data.get("elevation") or 0.0
    rows = _daily_block_to_rows(trail_id, data.get("daily", {}), snowline, elev)
    db_manager.upsert_weather_snapshots_bulk(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# CLI helper - python -m data.weather_fetcher
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Fetching forecast for Säntis (47.2493, 9.3432)…")
    data = fetch_forecast(47.2493, 9.3432)
    print(
        {k: v for k, v in data.items() if k in ("latitude", "longitude", "elevation")}
    )
    print("Daily keys:", list(data.get("daily", {}).keys()))
