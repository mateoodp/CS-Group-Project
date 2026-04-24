"""Rule-based bootstrap labeller for the ML training set.

Owner: TM5 (Feature Engineering) · Support: TM3

Problem: there are no publicly labelled datasets for Swiss trail safety.

Solution: apply a small set of transparent, domain-defensible rules to the
historical weather data in ``weather_snapshots`` to produce ~14,600 labelled
rows (20 trails × 730 days). These bootstrap labels train the initial Random
Forest. User-submitted reports (``user_reports`` table) enrich the labels on
every retrain.

The rules deliberately mirror Swiss Alpine Club (SAC) closure guidance so
that they can be justified verbally in the graded Q&A.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

Label = Literal["SAFE", "BORDERLINE", "AVOID"]


# ---------------------------------------------------------------------------
# Rule thresholds — document every one of these. Graders love transparency.
# ---------------------------------------------------------------------------

AVOID_WIND_KMH: float = 40.0           # sustained wind > 40 km/h on exposed ridge
AVOID_PRECIP_MM: float = 15.0          # heavy rain → slippery rocks, runoff
AVOID_TEMP_C: float = -5.0             # hypothermia threshold at altitude
SNOWLINE_BUFFER_M: float = 100.0       # trail max should be this far BELOW snowline

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

    1. **AVOID** if
        - trail max is above (snowline - buffer), i.e. snow on upper section, OR
        - sustained wind > ``AVOID_WIND_KMH``, OR
        - daily precipitation > ``AVOID_PRECIP_MM``, OR
        - temperature < ``AVOID_TEMP_C``.

    2. **BORDERLINE** if any moderate threshold is crossed.

    3. Otherwise **SAFE**.

    Args:
        temp_c: daily mean 2 m temperature in °C.
        wind_kmh: max wind speed in km/h.
        precip_mm: total daily precipitation in mm.
        snowline_m: 0°C isotherm altitude in m.
        trail_max_alt_m: highest point of the trail in m.

    Returns:
        One of ``"SAFE"``, ``"BORDERLINE"``, ``"AVOID"``.

    TODO (TM5): implement the rule cascade.
    """
    raise NotImplementedError


def label_dataframe(df: pd.DataFrame) -> pd.Series:
    """Vectorised labelling of a weather DataFrame.

    Expected columns: ``temp_c``, ``wind_kmh``, ``precip_mm``, ``snowline_m``,
    and either ``trail_max_alt_m`` or a trail_id that can be joined.

    TODO (TM5): implement using boolean masks for speed, then fall back to
    ``df.apply(label_row, axis=1)`` if readability matters more than speed.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# CLI helper — python -m data.label_engine
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Minimal sanity check.
    print(label_row(temp_c=10, wind_kmh=15, precip_mm=0, snowline_m=3500, trail_max_alt_m=2500))
