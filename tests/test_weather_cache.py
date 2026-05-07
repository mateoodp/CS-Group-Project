from __future__ import annotations

from datetime import date, timedelta


def _fake_forecast(start: date, days: int = 7) -> dict:
    dates = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    return {
        "elevation": 1200,
        "daily": {
            "time": dates,
            "temperature_2m_max": [10.0] * days,
            "temperature_2m_min": [4.0] * days,
            "wind_speed_10m_max": [12.0] * days,
            "precipitation_sum": [0.0] * days,
            "snowfall_sum": [0.0] * days,
            "cloud_cover_mean": [35.0] * days,
        },
        "hourly": {},
    }


def test_refresh_cache_fetches_when_today_exists_but_future_days_are_missing(
    tmp_path, monkeypatch
) -> None:
    from data import db_manager, weather_fetcher

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_manager, "DB_PATH", test_db)
    db_manager.setup_db()

    trail = db_manager.get_all_trails()[0]
    today = date.today()
    db_manager.upsert_weather_snapshot(
        trail_id=trail["id"],
        snapshot_date=today,
        temp_c=8.0,
        wind_kmh=10.0,
        precip_mm=0.0,
        snowline_m=2500.0,
        cloud_pct=30.0,
    )
    assert (
        db_manager.get_weather_for_date(trail["id"], today + timedelta(days=2)) is None
    )

    monkeypatch.setattr(
        weather_fetcher,
        "fetch_forecast",
        lambda lat, lon: _fake_forecast(today),
    )

    rows = weather_fetcher.refresh_cache(trail["id"], trail["lat"], trail["lon"])

    assert rows == 7
    assert (
        db_manager.get_weather_for_date(trail["id"], today + timedelta(days=2))
        is not None
    )
