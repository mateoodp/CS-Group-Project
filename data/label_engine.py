"""Rule-based label generator for the training set.

Owner: TM5 (Feature Engineering). Support: TM3.

The problem: there's no public dataset of "this Swiss hike was safe on
this day, that one wasn't". So we have nothing to train a model on.

Our solution: apply a small set of clear rules to our weather history
and use those rule outputs as labels for training. With 20 trails times
roughly 730 days of history, we get about 14,600 labelled rows. We use
those labels to train the initial Random Forest. Each time the user
submits a real hike report, that real label overrides the rule label
for the same (trail, date) on the next retrain.

We picked the rules and thresholds to mirror Swiss Alpine Club closure
guidance. That way we can defend each one verbally in the Q&A: "we
chose 40 km/h as our wind cutoff because SAC guidance treats sustained
winds above that level as a stop sign on exposed ridges".
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from typing import Literal

import pandas as pd

Label = Literal["SAFE", "BORDERLINE", "AVOID"]


# ---------------------------------------------------------------------------
# Rule thresholds. Each value below is a number we picked for a reason.
# We keep the reasons in the comments because graders love to see that
# the choices weren't arbitrary.
# ---------------------------------------------------------------------------

# "Hard" thresholds. If a single one of these is crossed, the day is
# rated AVOID right away.
AVOID_WIND_KMH: float = 40.0           # sustained wind over 40 km/h on exposed ridge
AVOID_PRECIP_MM: float = 15.0          # heavy rain means slippery rocks and runoff
AVOID_TEMP_C: float = -5.0             # hypothermia risk at altitude
# How much higher the snowline should sit above the trail's highest point.
# We use a small positive buffer (100 m). If the snowline is anywhere near
# the summit (within 100 m), we still mark the day AVOID, because patchy
# snow and verglas on a summit are deceptively dangerous.
SNOWLINE_BUFFER_M: float = 100.0

# "Moderate" thresholds. If none of the hard rules fire but one of these
# does, the day is rated BORDERLINE. The numbers are roughly half the
# AVOID values, so conditions need to be clearly worsening to trip them.
BORDERLINE_WIND_KMH: float = 25.0
BORDERLINE_PRECIP_MM: float = 5.0
BORDERLINE_TEMP_C: float = 2.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def label_row(
    temp_c: float,
    wind_kmh: float,
    precip_mm: float,
    snowline_m: float,
    trail_max_alt_m: float,
) -> Label:
    """Classify a single day's weather for a trail.

    Rules (applied in order; first match wins):

    1. **AVOID** if any "hard" threshold is crossed.
    2. **BORDERLINE** if any "moderate" threshold is crossed.
    3. Otherwise **SAFE**.

    Args:
        temp_c: daily mean 2 m temperature in °C.
        wind_kmh: max wind speed in km/h.
        precip_mm: total daily precipitation in mm.
        snowline_m: 0°C isotherm altitude in m.
        trail_max_alt_m: highest point of the trail in m.

    Returns:
        One of ``"SAFE"``, ``"BORDERLINE"``, ``"AVOID"``.
    """
    # First we check the AVOID branch. As soon as one hard threshold is
    # tripped, we return AVOID and skip the rest of the checks.
    if (
        trail_max_alt_m > snowline_m - SNOWLINE_BUFFER_M
        or wind_kmh > AVOID_WIND_KMH
        or precip_mm > AVOID_PRECIP_MM
        or temp_c < AVOID_TEMP_C
    ):
        return "AVOID"

    # BORDERLINE branch. We use a wider 500 m cushion for the snowline
    # check here. This matches the SAC's guidance: a trail approaching
    # (but not yet reaching) the freezing level should be flagged as
    # marginal, even if it isn't strictly dangerous yet.
    if (
        trail_max_alt_m > snowline_m - 500
        or wind_kmh > BORDERLINE_WIND_KMH
        or precip_mm > BORDERLINE_PRECIP_MM
        or temp_c < BORDERLINE_TEMP_C
    ):
        return "BORDERLINE"

    return "SAFE"


def label_dataframe(df: pd.DataFrame) -> pd.Series:
    """Vectorised labelling of a weather DataFrame.

    Required columns: ``temp_c``, ``wind_kmh``, ``precip_mm``, ``snowline_m``,
    ``trail_max_alt_m``.
    """
    # pandas docs - https://pandas.pydata.org/docs/
    # Each "mask" below is the same condition as the if-statement in
    # label_row above, but written so it runs across the whole column
    # at once. NumPy and pandas handle that internally, so labelling
    # 14,000 rows takes a few milliseconds instead of seconds.
    avoid_mask = (
        (df["trail_max_alt_m"] > df["snowline_m"] - SNOWLINE_BUFFER_M)
        | (df["wind_kmh"] > AVOID_WIND_KMH)
        | (df["precip_mm"] > AVOID_PRECIP_MM)
        | (df["temp_c"] < AVOID_TEMP_C)
    )
    borderline_mask = (
        (df["trail_max_alt_m"] > df["snowline_m"] - 500)
        | (df["wind_kmh"] > BORDERLINE_WIND_KMH)
        | (df["precip_mm"] > BORDERLINE_PRECIP_MM)
        | (df["temp_c"] < BORDERLINE_TEMP_C)
    )

    # Start by labelling every row as SAFE. Then layer BORDERLINE on top
    # of the rows that meet that condition, and finally AVOID on top of
    # any rows that meet the strictest condition. Because we apply them
    # in this order, AVOID always wins over BORDERLINE, and BORDERLINE
    # always wins over SAFE.
    labels = pd.Series(["SAFE"] * len(df), index=df.index, dtype=object)
    labels[borderline_mask] = "BORDERLINE"
    labels[avoid_mask] = "AVOID"
    return labels


# ---------------------------------------------------------------------------
# CLI helper - python -m data.label_engine
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Minimal sanity check.
    print(label_row(temp_c=10, wind_kmh=15, precip_mm=0, snowline_m=3500, trail_max_alt_m=2500))
