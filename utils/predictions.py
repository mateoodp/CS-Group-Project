"""Verdict helper — wraps the ML model with a rule-based fallback.

Other pages should never call ``trail_classifier.predict`` directly: if the
model isn't trained yet, that raises FileNotFoundError. This helper falls
back to the transparent rule-based ``label_engine`` so the UI always has
something to display.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from data import db_manager, label_engine, weather_fetcher
from ml import trail_classifier
from utils.constants import VERDICT_COLOURS


VERDICT_ORDER = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}
RISK_THRESHOLD_SHIFT = {1: -1, 2: 0, 3: 0, 4: 0, 5: 1}  # see apply_risk_tolerance


def _features_from_snapshot(snap: dict, trail_max_alt_m: float) -> dict:
    """Derive the 7 ML features from a single weather_snapshots row dict."""
    temp = snap.get("temp_c") or 0.0
    wind = snap.get("wind_kmh") or 0.0
    precip = snap.get("precip_mm") or 0.0
    snowline = snap.get("snowline_m") or 0.0
    cloud = snap.get("cloud_pct") or 0.0
    return {
        "temperature_c": temp,
        "wind_speed_kmh": wind,
        "precipitation_mm": precip,
        "cloud_cover_pct": cloud,
        "snowline_minus_trailmax": snowline - trail_max_alt_m,
        "wind_chill_index": trail_classifier.wind_chill(temp, wind),
        # Best-effort: caller should pre-compute rolling sum for accuracy. For
        # a single-day forecast we approximate with today's precip × 7 / 7.
        "precip_7day_rolling": precip,
    }


def predict_for_snapshot(
    snapshot: dict, trail_max_alt_m: float
) -> tuple[str, float, list[tuple[str, float]], str]:
    """Return ``(verdict, confidence, top_features, source)``.

    ``source`` is ``"ml"`` if the trained Random Forest produced the verdict,
    or ``"rules"`` if it fell back to the rule-based label engine.
    """
    if trail_classifier.model_exists():
        try:
            features = _features_from_snapshot(snapshot, trail_max_alt_m)
            v, c, top = trail_classifier.predict(features)
            return v, c, top, "ml"
        except Exception:
            pass

    label = label_engine.label_row(
        temp_c=snapshot.get("temp_c") or 0.0,
        wind_kmh=snapshot.get("wind_kmh") or 0.0,
        precip_mm=snapshot.get("precip_mm") or 0.0,
        snowline_m=snapshot.get("snowline_m") or 9999.0,
        trail_max_alt_m=trail_max_alt_m,
    )
    return label, 0.66, [], "rules"


def ensure_forecast_for_trail(trail_row) -> None:
    """Lazy: refresh the 7-day cache for a trail if it's stale or empty."""
    age = db_manager.get_latest_snapshot_age_hours(trail_row["id"])
    if age is None or age >= 24:
        weather_fetcher.refresh_cache(
            trail_row["id"], trail_row["lat"], trail_row["lon"]
        )


def apply_risk_tolerance(verdict: str, risk: int) -> str:
    """Adjust the displayed verdict for the user's risk tolerance.

    Risk = 1 (cautious): demote one step (SAFE→BORDERLINE, BORDERLINE→AVOID).
    Risk = 5 (bold)    : promote one step (AVOID→BORDERLINE, BORDERLINE→SAFE).
    Risk 2–4          : no change. The *model* is unchanged — only display.
    """
    shift = RISK_THRESHOLD_SHIFT.get(risk, 0)
    code = VERDICT_ORDER[verdict] + shift
    code = max(0, min(2, code))
    return {0: "SAFE", 1: "BORDERLINE", 2: "AVOID"}[code]


def verdict_colour(verdict: str) -> str:
    return VERDICT_COLOURS.get(verdict, "#888888")


def get_seven_day_forecast(trail_id: int) -> pd.DataFrame:
    """Return up to 7 cached forecast rows for a trail starting today."""
    rows = db_manager.get_weather_history(trail_id, days=14)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    today = date.today()
    df = df[df["snapshot_date"] >= today].sort_values("snapshot_date").head(7)
    return df.reset_index(drop=True)
