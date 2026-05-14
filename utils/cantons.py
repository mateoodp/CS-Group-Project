"""Canton helpers. Powers the Map page's overview view.

The Map page works as a drill-down. First it shows one bubble per Swiss
canton, where the bubble color is the average verdict of that canton's
trails for the chosen date. Then if the user clicks a canton, it zooms
into that canton's individual trails.

This file does two things:
    - Stores the human-readable canton names (BE -> "Bern", etc).
    - Aggregates per-trail verdicts into one verdict per canton.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from datetime import date

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

# We can't average text labels like "SAFE" directly, so we map each
# verdict to a number, average those, then map the average back to a
# label. SAFE = 1, BORDERLINE = 2, AVOID = 3.
_SCORE = {"SAFE": 1, "BORDERLINE": 2, "AVOID": 3}
_BAND_TO_VERDICT = {1: "SAFE", 2: "BORDERLINE", 3: "AVOID"}


def aggregate_by_canton(trails, target_date: date) -> dict[str, dict]:
    """Group all trails by their canton and return one summary per canton.

    For each canton we compute:
        - count: how many trails it has.
        - avg_score: average verdict score across its trails.
        - verdict: SAFE if avg_score is at most 1.5, BORDERLINE up to 2.5,
                   otherwise AVOID. Falls back to "no data" if we have no
                   weather cached for any of the canton's trails.
        - lat, lon: centroid (average position) used to place the bubble.
        - data_coverage_pct: what fraction of the canton's trails have data.
        - trails: the full list of trail rows (kept for the drill-down view).

    The predictions are fetched in a single batched call (and cached for
    1 hour), so this function makes very few database trips even with
    hundreds of trails.
    """
    # We pass a sorted tuple of trail IDs as the cache key. Sorting matters
    # because the cache function treats different orderings as different
    # keys, and we don't want to recompute when the order changes.
    trail_ids = tuple(sorted(t["id"] for t in trails))
    verdicts = predictions.get_verdicts_for_date(
        target_date.isoformat(), trail_ids
    )

    # First pass: walk through every trail and drop it in the right bucket
    # for its canton. We collect its coordinates (for the centroid) and
    # its verdict score (for the average).
    buckets: dict[str, dict] = {}
    for t in trails:
        b = buckets.setdefault(t["canton"], {
            "trails": [], "scores": [], "lats": [], "lons": [],
        })
        b["trails"].append(t)
        b["lats"].append(t["lat"])
        b["lons"].append(t["lon"])
        v = verdicts.get(t["id"], {}).get("verdict", "—")
        b["scores"].append(_SCORE.get(v))

    # Second pass: turn each bucket into one summary dictionary. The
    # average score gets rounded to the nearest band (1, 2 or 3) and
    # mapped back to a verdict label. If a canton has no usable scores
    # at all, we mark it as "no data".
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
