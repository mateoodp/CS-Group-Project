"""Shared constants for the Swiss Alpine Hiking Condition Forecaster.

Owner: shared. Anyone on the team can edit this file. Whenever a new
constant is added, please update the docstring so it's clear what it
means. Keeping this file as the single source of truth is one of our
graded points (Criterion 6).
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

# Traffic light colors mapped to our three verdict labels. We use the same
# three colors everywhere (map bubbles, card pills, table cells) so the
# user only has to learn the meaning once.
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

# Approximate center of Switzerland in latitude / longitude. We use these
# to center the Folium map when the user hasn't picked a canton yet. The
# coordinates were checked against Swisstopo references.
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


