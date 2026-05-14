"""Verdict helper. Wraps the ML model and provides a rule-based fallback.

Pages should never call ``trail_classifier.predict`` directly. If the
model hasn't been trained yet, that would crash with FileNotFoundError.
Instead they should go through this module. If no trained model exists,
we automatically fall back to the simple rule-based ``label_engine``,
so the UI always has something to display.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st

from data import db_manager, label_engine, weather_fetcher
from ml import trail_classifier
from utils.constants import VERDICT_COLOURS


# We line up the three verdicts on a 0/1/2 scale. SAFE is the calmest end,
# AVOID is the most cautious end. Putting them on a number line means we
# can move "one step toward AVOID" simply by adding 1, which makes the
# risk tolerance math very simple.
VERDICT_ORDER = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}
# Risk tolerance is a 1-to-5 slider. We translate it into an offset.
# A positive offset makes the verdict harsher (closer to AVOID). A negative
# offset makes it softer (closer to SAFE). Settings 2, 3 and 4 in the
# middle leave the verdict unchanged.
RISK_THRESHOLD_SHIFT = {1: +1, 2: 0, 3: 0, 4: 0, 5: -1}

# These SAC difficulty grades are dangerous on their own, no matter how
# nice the weather is. We never let any of these trails display as SAFE.
# On the two highest grades (T5, T6) any real weather concern is enough
# to push the verdict all the way to AVOID.
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


# Take a weather snapshot (one row from the weather_snapshots table) and
# turn it into the seven numbers the Random Forest expects. Any missing
# value is replaced with 0.0, which is how we trained the model too.
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
    """Predict a verdict for one trail on one day.

    Returns a tuple of:
        - verdict label: SAFE, BORDERLINE or AVOID
        - confidence: a number from 0 to 1
        - top_features: the three features that mattered most
        - source: either "ml" (trained model) or "rules" (fallback)
    """
    # If a trained model exists, we try it first. If anything goes wrong
    # while loading it or running it (corrupted file, missing feature),
    # we quietly fall through to the rule engine. This way the UI is
    # always able to show something instead of crashing.
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
    """Lazy: refresh the 7-day cache for a trail if it's stale or incomplete."""
    weather_fetcher.refresh_cache(
        trail_row["id"], trail_row["lat"], trail_row["lon"]
    )


def apply_risk_tolerance(
    verdict: str, risk: int, difficulty: str | None = None
) -> str:
    """Take the model's verdict and adjust it for the user's risk tolerance.

    Risk = 1 (very cautious): make the verdict one step harsher
        (SAFE becomes BORDERLINE, BORDERLINE becomes AVOID).
    Risk = 5 (bold): make the verdict one step softer
        (AVOID becomes BORDERLINE, BORDERLINE becomes SAFE).
    Risk = 2, 3 or 4: no change.

    Note that we only change what gets DISPLAYED. The model itself is
    untouched. The slider is just about how the user wants to interpret
    the same prediction.

    Safety lock: if the trail is T4, T5 or T6, a bold user is never
    allowed to push the verdict to SAFE. The slider expresses your
    confidence in your own judgement, not the grade of the route, and
    these alpine grades are always serious terrain.
    """
    shift = RISK_THRESHOLD_SHIFT.get(risk, 0)
    code = VERDICT_ORDER[verdict] + shift
    # Clamp the result so we don't go below SAFE or above AVOID.
    code = max(0, min(2, code))
    new = {0: "SAFE", 1: "BORDERLINE", 2: "AVOID"}[code]
    # Hard safety rule: T4 to T6 routes can never display as SAFE even
    # if the user has set the slider to the boldest setting.
    if difficulty in HARD_GRADES and new == "SAFE":
        return "BORDERLINE"
    return new


def apply_difficulty_floor(
    verdict: str, trail, snapshot: Optional[dict]
) -> tuple[str, list[str]]:
    """Cap the verdict based on how technical the trail is.

    Even if the weather is perfect, some trails are inherently dangerous
    because of the terrain. This function enforces that.

    Returns a tuple of (final_verdict, caveats). The caveats list holds
    plain-English reasons for any adjustment. We pass those up so the
    UI can explain to the user why a sunny T5 isn't being marked SAFE.

    Rules:

    * T4, T5 or T6 (alpine grades): can never be SAFE. If the model
      said SAFE we bump it to BORDERLINE.
    * T5 or T6: any real weather concern bumps the verdict straight to
      AVOID. "Real concern" means wind at least 30 km/h, precipitation
      at least 2 mm, or the snowline is within 200 m of the trail's
      summit. On exposed alpine terrain there's no margin for error.
    * T3: we leave the verdict alone, but if it's SAFE we attach a
      caveat reminding the user that T3 still requires surefootedness.
    """
    difficulty = trail["difficulty"]
    caveats: list[str] = []
    final = verdict

    # Rule 1: T4 to T6 routes can never be SAFE, no matter the weather.
    if difficulty in HARD_GRADES and final == "SAFE":
        final = "BORDERLINE"
        caveats.append(
            f"This is a {difficulty} ({DIFFICULTY_NAMES[difficulty]}). "
            "Even with perfect weather, the terrain itself carries serious "
            "risk — a slip on exposed ground can be lethal. We never mark "
            "T4–T6 routes as SAFE; treat the conditions as a green light "
            "for the *weather*, not for the *route*."
        )

    # Rule 2: on T5 and T6, any meaningful weather concern pushes the
    # verdict all the way to AVOID. The thresholds below are deliberately
    # strict because on alpine terrain there's no room to be wrong.
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
    """Run the full verdict adjustment pipeline.

    Pages should call this single function (not the individual rules
    below) to turn a raw model verdict into the verdict shown to the
    user. We apply the difficulty floor first (terrain wins over weather)
    and then the user's risk tolerance.

    Returns (final_verdict, caveats). The caveats list contains
    plain-English warning messages the UI should show.
    """
    floored, caveats = apply_difficulty_floor(weather_verdict, trail, snapshot)
    final = apply_risk_tolerance(floored, risk, difficulty=trail["difficulty"])
    return final, caveats


def verdict_colour(verdict: str) -> str:
    return VERDICT_COLOURS.get(verdict, "#888888")


# Streamlit caching pattern - https://docs.streamlit.io/library/advanced-features/caching
# We cache this function's results for one hour. The cache key is the
# (date, list-of-trail-ids) pair. This way, if the user opens the same
# page again or filters in a way that hits the same trails, we return
# the cached verdicts instantly instead of re-running the model.
@st.cache_data(ttl=3600)
def get_verdicts_for_date(
    snapshot_date_iso: str, trail_ids: tuple[int, ...]
) -> dict[int, dict]:
    """Compute verdicts for many trails on one date in a single batch.

    This is the fast path used by pages that need verdicts for lots of
    trails at once (the Map overview, for example). Doing it in one batch
    instead of one trail at a time is much quicker because:

      - one JOIN query gets all the weather snapshots
      - one query gets all the trail metadata
      - we load the trained model only once
      - we call predict_batch once on the whole dataframe

    Results are cached for an hour, keyed by date and the sorted tuple
    of trail IDs. Any filter change inside that hour hits the cache and
    the page renders instantly.

    Returns a dictionary mapping trail_id to a dict with keys
    "verdict", "confidence", "snapshot" and "trail". Trails with no
    cached weather get the placeholder verdict and a snapshot of None.
    Callers use that to render the grey "no data" markers.
    """
    snapshot_date = date.fromisoformat(snapshot_date_iso)
    # Two database queries up front: one for all the day's snapshots, one
    # for the trail metadata. Everything below works in memory after that.
    snapshots = db_manager.get_all_snapshots_for_date(snapshot_date)
    trail_meta = {t["id"]: dict(t) for t in db_manager.get_all_trails()}

    out: dict[int, dict] = {}
    feature_rows: list[dict] = []
    feature_tids: list[int] = []
    for tid in trail_ids:
        trail = trail_meta.get(tid)
        if trail is None:
            continue
        snap = snapshots.get(tid)
        if snap is None:
            out[tid] = {
                "verdict": "—",
                "confidence": 0.0,
                "snapshot": None,
                "trail": trail,
            }
            continue
        feats = _features_from_snapshot(snap, trail["max_alt_m"])
        feats["trail_id"] = tid
        feature_rows.append(feats)
        feature_tids.append(tid)

    # Fast path: send every trail through predict_batch in one go. The
    # model only gets loaded once, which is the slow part. Looping
    # trail-by-trail would reload it every time.
    if feature_rows and trail_classifier.model_exists():
        try:
            df = pd.DataFrame(feature_rows)
            scored = trail_classifier.predict_batch(df)
            for tid, row in zip(feature_tids, scored.itertuples(index=False)):
                trail = trail_meta[tid]
                snap = snapshots[tid]
                floored, _ = apply_difficulty_floor(row.verdict, trail, snap)
                out[tid] = {
                    "verdict": floored,
                    "confidence": float(row.confidence),
                    "snapshot": snap,
                    "trail": trail,
                }
            return out
        except Exception:
            pass  # fall through to per-row rules path

    for tid in feature_tids:
        trail = trail_meta[tid]
        snap = snapshots[tid]
        v, c, _, _ = predict_for_snapshot(snap, trail["max_alt_m"])
        floored, _ = apply_difficulty_floor(v, trail, snap)
        out[tid] = {
            "verdict": floored,
            "confidence": float(c),
            "snapshot": snap,
            "trail": trail,
        }
    return out


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
