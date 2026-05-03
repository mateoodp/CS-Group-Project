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
# Positive shift = harsher verdict (toward AVOID). Cautious users (risk=1)
# pull the verdict one step toward AVOID; bold users (risk=5) pull it one
# step toward SAFE. Risks 2–4 leave the verdict alone.
RISK_THRESHOLD_SHIFT = {1: +1, 2: 0, 3: 0, 4: 0, 5: -1}

# SAC grades that carry inherent terrain risk regardless of weather. We
# never let these be displayed as SAFE, and on T5/T6 any non-trivial
# weather concern bumps the verdict to AVOID.
HARD_GRADES: frozenset[str] = frozenset({"T4", "T5", "T6"})
EXTREME_GRADES: frozenset[str] = frozenset({"T5", "T6"})

DIFFICULTY_NAMES: dict[str, str] = {
    "T1": "easy hike",
    "T2": "mountain hike",
    "T3": "demanding mountain hike",
    "T4": "alpine hike",
    "T5": "demanding alpine hike",
    "T6": "difficult alpine hike",
}


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


def apply_risk_tolerance(
    verdict: str, risk: int, difficulty: str | None = None
) -> str:
    """Adjust the displayed verdict for the user's risk tolerance.

    Risk = 1 (cautious): demote one step (SAFE→BORDERLINE, BORDERLINE→AVOID).
    Risk = 5 (bold)    : promote one step (AVOID→BORDERLINE, BORDERLINE→SAFE).
    Risk 2–4          : no change. The *model* is unchanged — only display.

    Safety lock: if ``difficulty`` is in :data:`HARD_GRADES` (T4–T6), a bold
    user is **never** allowed to push the verdict to SAFE. The slider
    expresses confidence in your judgement, not the inherent grade of the
    route — and a T4+ hike is always serious terrain.
    """
    shift = RISK_THRESHOLD_SHIFT.get(risk, 0)
    code = VERDICT_ORDER[verdict] + shift
    code = max(0, min(2, code))
    new = {0: "SAFE", 1: "BORDERLINE", 2: "AVOID"}[code]
    if difficulty in HARD_GRADES and new == "SAFE":
        return "BORDERLINE"
    return new


def apply_difficulty_floor(
    verdict: str, trail, snapshot: Optional[dict]
) -> tuple[str, list[str]]:
    """Cap the verdict by the trail's intrinsic difficulty.

    Returns ``(verdict, caveats)``. ``caveats`` is a list of plain-text
    reasons explaining each adjustment — surface these in the UI so users
    understand *why* a sunny T5 isn't being marked SAFE.

    Rules:

    * **T4+** (alpine hike or harder): can never be SAFE. SAFE is bumped
      to BORDERLINE.
    * **T5/T6** (alpine grades): any meaningful weather concern (wind ≥ 30
      km/h, precipitation ≥ 2 mm, or snowline within 200 m of the summit)
      bumps the verdict all the way to AVOID. Sustained exposure with
      anything less than perfect conditions is a stop sign.
    * **T3**: stays as the weather suggests, but a SAFE verdict carries
      a caveat that surefootedness is required.
    """
    difficulty = trail["difficulty"]
    caveats: list[str] = []
    final = verdict

    if difficulty in HARD_GRADES and final == "SAFE":
        final = "BORDERLINE"
        caveats.append(
            f"This is a {difficulty} ({DIFFICULTY_NAMES[difficulty]}). "
            "Even with perfect weather, the terrain itself carries serious "
            "risk — a slip on exposed ground can be lethal. We never mark "
            "T4–T6 routes as SAFE; treat the conditions as a green light "
            "for the *weather*, not for the *route*."
        )

    if difficulty in EXTREME_GRADES and snapshot:
        wind = snapshot.get("wind_kmh") or 0.0
        precip = snapshot.get("precip_mm") or 0.0
        snowline = snapshot.get("snowline_m")
        max_alt = trail["max_alt_m"]
        concerns: list[str] = []
        if wind >= 30:
            concerns.append(f"wind {wind:.0f} km/h on exposed climbing terrain")
        if precip >= 2:
            concerns.append(
                f"precipitation {precip:.1f} mm — wet rock above 2500 m turns "
                "scrambling deadly"
            )
        if snowline is not None and snowline < max_alt + 200:
            concerns.append(
                f"snowline {int(snowline)} m within 200 m of the summit "
                f"({max_alt} m) — verglas and hidden ice likely"
            )
        if concerns and final != "AVOID":
            final = "AVOID"
            caveats.append(
                f"On a {difficulty} route, any of these is a stop sign: "
                + "; ".join(concerns) + "."
            )

    if difficulty == "T3" and final == "SAFE":
        caveats.append(
            "T3 demands surefootedness on steep, partly exposed terrain. "
            "A fall here can mean a serious injury. Hiking poles and proper "
            "boots are non-negotiable; turn back if you feel unsteady."
        )

    return final, caveats


def adjust_verdict(
    weather_verdict: str,
    trail,
    snapshot: Optional[dict],
    risk: int,
) -> tuple[str, list[str]]:
    """Apply the difficulty floor, then the user's risk tolerance.

    This is the single entry point pages should use to convert a raw
    weather verdict into a displayed verdict. Returns the final verdict
    plus a list of safety caveats to surface in the UI.
    """
    floored, caveats = apply_difficulty_floor(weather_verdict, trail, snapshot)
    final = apply_risk_tolerance(floored, risk, difficulty=trail["difficulty"])
    return final, caveats


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
