"""Canton helpers — names, colour-coding aggregation for the Map page.

The Map page now drills down: first you see one bubble per canton coloured
by the average verdict of its trails, then you click into a canton and
see the individual trails. These helpers do the aggregation and provide
human-readable canton names.
"""

from __future__ import annotations

from datetime import date

from data import db_manager
from utils import predictions

# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------

CANTON_NAMES: dict[str, str] = {
    "AG": "Aargau",            "AI": "Appenzell Innerrhoden",
    "AR": "Appenzell Ausserrhoden",
    "BE": "Bern",              "BL": "Basel-Landschaft",
    "BS": "Basel-Stadt",       "FR": "Fribourg",
    "GE": "Geneva",            "GL": "Glarus",
    "GR": "Graubünden",        "JU": "Jura",
    "LU": "Lucerne",           "NE": "Neuchâtel",
    "NW": "Nidwalden",         "OW": "Obwalden",
    "SG": "St. Gallen",        "SH": "Schaffhausen",
    "SO": "Solothurn",         "SZ": "Schwyz",
    "TG": "Thurgau",           "TI": "Ticino",
    "UR": "Uri",               "VD": "Vaud",
    "VS": "Valais",             "ZG": "Zug",
    "ZH": "Zurich",            "AR/AI": "Appenzell (joint)",
}


def canton_label(code: str) -> str:
    """Return ``"BE · Bern"`` style label, falling back to the code alone."""
    name = CANTON_NAMES.get(code)
    return f"{code} · {name}" if name else code


# ---------------------------------------------------------------------------
# Verdict aggregation
# ---------------------------------------------------------------------------

_SCORE = {"SAFE": 1, "BORDERLINE": 2, "AVOID": 3}
_BAND_TO_VERDICT = {1: "SAFE", 2: "BORDERLINE", 3: "AVOID"}


def _trail_verdict_score(trail, target_date: date) -> int | None:
    """Predicted (difficulty-floored) verdict score for one trail."""
    snap_row = db_manager.get_weather_for_date(trail["id"], target_date)
    if snap_row is None:
        return None
    snap = dict(snap_row)
    v, _, _, _ = predictions.predict_for_snapshot(snap, trail["max_alt_m"])
    floored, _ = predictions.apply_difficulty_floor(v, trail, snap)
    return _SCORE[floored]


def aggregate_by_canton(trails, target_date: date) -> dict[str, dict]:
    """Group trails by canton, compute average verdict + centroid + count.

    Returns a dict: ``{canton_code: {code, count, avg_score, verdict,
    lat, lon, data_coverage_pct, trails}}``. ``verdict`` is a banded
    SAFE/BORDERLINE/AVOID derived from ``avg_score`` (≤1.5 → SAFE,
    ≤2.5 → BORDERLINE, else AVOID), or ``"—"`` if no data was cached
    for any of the canton's trails.
    """
    buckets: dict[str, dict] = {}
    for t in trails:
        b = buckets.setdefault(t["canton"], {
            "trails": [], "scores": [], "lats": [], "lons": [],
        })
        b["trails"].append(t)
        b["lats"].append(t["lat"])
        b["lons"].append(t["lon"])
        b["scores"].append(_trail_verdict_score(t, target_date))

    out: dict[str, dict] = {}
    for code, b in buckets.items():
        valid_scores = [s for s in b["scores"] if s is not None]
        if valid_scores:
            avg = sum(valid_scores) / len(valid_scores)
            band = round(avg)
            verdict = _BAND_TO_VERDICT.get(band, "BORDERLINE")
        else:
            avg = None
            verdict = "—"
        out[code] = {
            "code": code,
            "count": len(b["trails"]),
            "avg_score": avg,
            "verdict": verdict,
            "lat": sum(b["lats"]) / len(b["lats"]),
            "lon": sum(b["lons"]) / len(b["lons"]),
            "data_coverage_pct": (
                100 * len(valid_scores) / len(b["scores"])
                if b["scores"] else 0
            ),
            "trails": b["trails"],
        }
    return out
