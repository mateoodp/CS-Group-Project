"""Shared constants for the Swiss Alpine Hiking Condition Forecaster.

Owner: shared — edits welcome from any teammate. Keep docstrings up to date
so the "single source of truth" principle is obvious to graders (Criterion 6).
"""

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

# Centre of Switzerland — used when initialising the Folium map.
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


# ---------------------------------------------------------------------------
# Contribution matrix (Criterion 7)
#
# Fill in real names before submission. Values: "L" (Lead), "M" (Major),
# "S" (Support), "—" (None).
# ---------------------------------------------------------------------------

CONTRIBUTION_MATRIX: Final[list[dict[str, str]]] = [
    {"Task / Feature": "Project Management",                 "TM1": "L", "TM2": "S", "TM3": "—", "TM4": "—", "TM5": "—"},
    {"Task / Feature": "Product Concept",                    "TM1": "M", "TM2": "M", "TM3": "—", "TM4": "—", "TM5": "S"},
    {"Task / Feature": "API Integration (weather_fetcher)",  "TM1": "—", "TM2": "—", "TM3": "L", "TM4": "—", "TM5": "S"},
    {"Task / Feature": "Database Design (db_manager)",       "TM1": "—", "TM2": "L", "TM3": "—", "TM4": "—", "TM5": "—"},
    {"Task / Feature": "Bootstrap Label Engine",             "TM1": "—", "TM2": "—", "TM3": "M", "TM4": "—", "TM5": "L"},
    {"Task / Feature": "ML Model (trail_classifier)",        "TM1": "—", "TM2": "—", "TM3": "—", "TM4": "L", "TM5": "M"},
    {"Task / Feature": "Feature Engineering",                "TM1": "—", "TM2": "—", "TM3": "—", "TM4": "M", "TM5": "L"},
    {"Task / Feature": "Folium Map (Dashboard)",             "TM1": "L", "TM2": "—", "TM3": "—", "TM4": "—", "TM5": "S"},
    {"Task / Feature": "Forecast Tab (charts + slider)",     "TM1": "S", "TM2": "L", "TM3": "M", "TM4": "—", "TM5": "—"},
    {"Task / Feature": "Compare Tab (radar chart)",          "TM1": "—", "TM2": "—", "TM3": "—", "TM4": "L", "TM5": "S"},
    {"Task / Feature": "User Report Form",                   "TM1": "—", "TM2": "—", "TM3": "—", "TM4": "—", "TM5": "L"},
    {"Task / Feature": "About Tab + Metrics",                "TM1": "L", "TM2": "S", "TM3": "—", "TM4": "S", "TM5": "—"},
    {"Task / Feature": "Code Documentation",                 "TM1": "M", "TM2": "M", "TM3": "M", "TM4": "M", "TM5": "M"},
    {"Task / Feature": "Testing & Bug Fixes",                "TM1": "—", "TM2": "L", "TM3": "S", "TM4": "S", "TM5": "—"},
    {"Task / Feature": "Video Recording",                    "TM1": "—", "TM2": "—", "TM3": "L", "TM4": "—", "TM5": "M"},
    {"Task / Feature": "Streamlit Cloud Deployment",         "TM1": "—", "TM2": "—", "TM3": "—", "TM4": "—", "TM5": "L"},
]
