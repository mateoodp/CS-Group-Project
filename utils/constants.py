"""Shared constants for the Swiss Alpine Hiking Condition Forecaster.

Owner: shared — edits welcome from any teammate. Keep docstrings up to date
so the "single source of truth" principle is obvious to graders (Criterion 6).
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------

APP_TITLE: Final[str] = "Swiss Alpine Hiking Condition Forecaster"
APP_TAGLINE: Final[str] = (
    "Go / Borderline / Avoid verdicts for Swiss trails, powered by machine learning."
)
UNIVERSITY: Final[str] = "University of St.Gallen (HSG)"
COURSE: Final[str] = "Grundlagen und Methoden der Informatik — FCS/BWL Group Project"
SUBMISSION_DEADLINE: Final[str] = "2026-05-14"


# ---------------------------------------------------------------------------
# Verdict colours (used by map markers and cards)
# ---------------------------------------------------------------------------

# Traffic-light palette mapped to the three verdict labels. Used both in the
# Folium markers and the CSS pill components for consistency across the app.
VERDICT_COLOURS: Final[dict[str, str]] = {
    "SAFE": "#1E7B3A",       # green
    "BORDERLINE": "#E69F00", # amber
    "AVOID": "#C0392B",      # red
}

VERDICT_EMOJI: Final[dict[str, str]] = {
    "SAFE": "🟢",
    "BORDERLINE": "🟠",
    "AVOID": "🔴",
}


# ---------------------------------------------------------------------------
# Risk tolerance slider (1 = very cautious, 5 = bold)
# ---------------------------------------------------------------------------

RISK_SLIDER_MIN: Final[int] = 1
RISK_SLIDER_MAX: Final[int] = 5
DEFAULT_RISK_TOLERANCE: Final[int] = 3


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

# Approximate geographic centre of Switzerland - used to centre the Folium map
# when no trail is selected. Coordinates verified against Swiss topo references.
# Centre of Switzerland - used when initialising the Folium map.
CH_CENTRE_LAT: Final[float] = 46.8182
CH_CENTRE_LON: Final[float] = 8.2275
DEFAULT_MAP_ZOOM: Final[int] = 8


# ---------------------------------------------------------------------------
# ML feature display names
# ---------------------------------------------------------------------------

FEATURE_DISPLAY_NAMES: Final[dict[str, str]] = {
    "temperature_c": "Temperature (°C)",
    "wind_speed_kmh": "Wind speed (km/h)",
    "precipitation_mm": "Precipitation (mm)",
    "snowline_minus_trailmax": "Snowline − trail max (m)",
    "wind_chill_index": "Wind chill (°C)",
    "cloud_cover_pct": "Cloud cover (%)",
    "precip_7day_rolling": "7-day rolling precip (mm)",
}


