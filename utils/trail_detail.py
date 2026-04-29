"""Helpers for the trail-detail sub-page.

Provides:
    * ``synthetic_route``       — fake polyline (we have no GPX data).
    * ``interpret_weather``     — plain-English explanation of a verdict.
    * ``analyse_tricky_sections`` — rule-based list of route hazards.
    * ``fetch_trail_images``    — Wikimedia Commons image search (cached).

The first three are pure functions; the last calls a free public API
(no key needed) and is wrapped in ``st.cache_data`` to avoid repeat hits.
"""

from __future__ import annotations

import math
from typing import Optional

import requests
import streamlit as st


# ---------------------------------------------------------------------------
# Synthetic route
# ---------------------------------------------------------------------------

def synthetic_route(
    lat: float, lon: float, length_km: float, n_points: int = 48
) -> list[tuple[float, float]]:
    """Build an approximate circular loop centred on ``(lat, lon)``.

    We don't have GPX traces for the seeded trails, so the route shown on
    the map is a circle whose perimeter equals ``length_km``. Always shown
    with an "approximate" caveat in the UI.
    """
    radius_km = max(length_km, 0.5) / (2 * math.pi)
    radius_lat = radius_km / 111.0
    radius_lon = radius_km / max(111.0 * math.cos(math.radians(lat)), 1e-3)

    pts: list[tuple[float, float]] = []
    for i in range(n_points + 1):
        angle = 2 * math.pi * i / n_points
        pts.append(
            (lat + radius_lat * math.sin(angle),
             lon + radius_lon * math.cos(angle))
        )
    return pts


# ---------------------------------------------------------------------------
# Weather interpretation
# ---------------------------------------------------------------------------

def _temp_band(t: float) -> tuple[str, str]:
    if t < -5:
        return "very cold", "winter gear and avalanche awareness essential"
    if t < 2:
        return "cold", "expect ice on shaded sections"
    if t < 10:
        return "cool", "comfortable for uphill effort"
    if t < 20:
        return "mild", "ideal hiking temperature"
    if t < 28:
        return "warm", "carry extra water"
    return "hot", "start early, watch for heat exhaustion"


def _wind_band(w: float) -> tuple[str, str]:
    if w < 15:
        return "light", "negligible on the trail"
    if w < 30:
        return "moderate", "noticeable on ridges"
    if w < 50:
        return "strong", "exposed traverses can feel unsafe"
    return "very strong", "consider postponing — gusts threaten balance on ridges"


def _precip_band(p: float) -> tuple[str, str]:
    if p < 0.5:
        return "dry", "no precipitation expected"
    if p < 3:
        return "light showers", "a shell jacket is enough"
    if p < 10:
        return "rainy", "wet rocks and slippery descents"
    return "heavy rain", "rivers in spate, lightning risk on ridges"


def _cloud_band(c: float) -> str:
    if c < 25:
        return "mostly sunny — strong UV at altitude"
    if c < 60:
        return "partly cloudy — pleasant light"
    if c < 85:
        return "overcast — limited views"
    return "fully clouded — visibility may drop in fog"


def interpret_weather(snapshot: Optional[dict], trail: dict, verdict: str) -> dict:
    """Return per-indicator commentary + an overall reason for the verdict.

    Always returns the keys: ``headline``, ``temp``, ``wind``, ``precip``,
    ``cloud``, ``snow`` and ``bullets`` (list of plain-text reasons that
    drove the verdict). Empty/None values are gracefully skipped.
    """
    if not snapshot:
        return {
            "headline": "No cached forecast for this day yet — refresh the weather "
                        "from the sidebar to see an interpretation.",
            "temp": None, "wind": None, "precip": None,
            "cloud": None, "snow": None, "bullets": [],
        }

    temp = snapshot.get("temp_c")
    wind = snapshot.get("wind_kmh") or 0.0
    precip = snapshot.get("precip_mm") or 0.0
    cloud = snapshot.get("cloud_pct")
    snow = snapshot.get("snowline_m")
    max_alt = trail["max_alt_m"]

    out: dict = {"bullets": []}

    if temp is not None:
        band, note = _temp_band(temp)
        out["temp"] = f"**{temp:.0f} °C** — {band}; {note}."
    else:
        out["temp"] = None

    band, note = _wind_band(wind)
    out["wind"] = f"**{wind:.0f} km/h** — {band}; {note}."

    band, note = _precip_band(precip)
    out["precip"] = f"**{precip:.1f} mm** — {band}; {note}."

    if cloud is not None:
        out["cloud"] = f"**{cloud:.0f}%** — {_cloud_band(cloud)}."
    else:
        out["cloud"] = None

    if snow is not None:
        margin = snow - max_alt
        if margin >= 300:
            out["snow"] = (
                f"Snowline at **{int(snow)} m** sits {int(margin)} m above the trail's "
                f"max altitude ({max_alt} m) — route is snow-free."
            )
        elif margin >= 0:
            out["snow"] = (
                f"Snowline at **{int(snow)} m** is only {int(margin)} m above the "
                f"summit ({max_alt} m) — patchy snow possible near the top."
            )
        else:
            out["snow"] = (
                f"Snowline at **{int(snow)} m** is {abs(int(margin))} m **below** the "
                f"summit ({max_alt} m) — expect snow on the upper section."
            )
    else:
        out["snow"] = None

    bullets: list[str] = []
    if temp is not None:
        if -2 <= temp <= 22 and verdict == "SAFE":
            bullets.append(f"Comfortable temperature ({temp:.0f} °C).")
        if temp < -2:
            bullets.append(f"Cold enough ({temp:.0f} °C) to need full winter gear.")
        if temp > 28:
            bullets.append(f"Heat ({temp:.0f} °C) raises dehydration risk.")

    if wind < 30:
        if verdict == "SAFE":
            bullets.append(f"Wind is light ({wind:.0f} km/h).")
    elif wind >= 50:
        bullets.append(f"Strong gusts ({wind:.0f} km/h) on exposed sections.")

    if precip < 1 and verdict == "SAFE":
        bullets.append("Dry conditions — no rain forecast.")
    elif precip >= 5:
        bullets.append(f"Rain ({precip:.1f} mm) — wet rock + slippery descents.")

    if snow is not None and snow < max_alt:
        bullets.append(
            f"Snow on the upper section (snowline {int(snow)} m < trail max {max_alt} m)."
        )

    if not bullets:
        bullets.append(
            "A mix of indicators — see the per-feature breakdown above for the full picture."
        )

    headline_map = {
        "SAFE": "✅ Conditions look favourable. Pack the basics and enjoy.",
        "BORDERLINE": "⚠️ Conditions are mixed — bring extra layers and reassess at the trailhead.",
        "AVOID": "⛔ Conditions point to a postpone. The trail is safer on a different day.",
    }
    out["headline"] = headline_map.get(
        verdict, "Forecast cached — see the breakdown below."
    )
    out["bullets"] = bullets
    return out


# ---------------------------------------------------------------------------
# Tricky-parts analyser
# ---------------------------------------------------------------------------

_DIFFICULTY_NOTES: dict[str, dict] = {
    "T1": {"icon": "🚶",
           "title": "Easy hiking path",
           "blurb": "Wide, well-graded path. No exposure. Trainers are fine."},
    "T2": {"icon": "🥾",
           "title": "Mountain hiking trail",
           "blurb": "Mostly maintained, occasional uneven terrain. Hiking shoes recommended."},
    "T3": {"icon": "🪨",
           "title": "Demanding mountain hike",
           "blurb": "Steep sections, partly exposed. Surefootedness required; hiking poles help."},
    "T4": {"icon": "⛰️",
           "title": "Alpine hike",
           "blurb": "Occasional use of hands. Some exposure. Stiff boots strongly advised."},
    "T5": {"icon": "🧗",
           "title": "Demanding alpine hike",
           "blurb": "Easy climbing passages, exposure. Alpine experience and helmet recommended."},
    "T6": {"icon": "🪢",
           "title": "Difficult alpine hike",
           "blurb": "Sustained climbing, glacier travel possible. Rope, crampons, and partner needed."},
}


def analyse_tricky_sections(trail: dict, snapshot: Optional[dict]) -> list[dict]:
    """Return a list of rule-based hazard cards for this trail."""
    parts: list[dict] = []

    diff_note = _DIFFICULTY_NOTES.get(trail["difficulty"])
    if diff_note:
        parts.append({**diff_note, "category": "Terrain"})

    elev_gain = trail["max_alt_m"] - trail["min_alt_m"]
    if elev_gain >= 1200:
        parts.append({
            "icon": "📈",
            "title": f"Big climb — {elev_gain} m of elevation gain",
            "blurb": "Pace yourself: roughly 4–6 hours of sustained ascent. Eat early, refill often.",
            "category": "Effort",
        })
    elif elev_gain >= 700:
        parts.append({
            "icon": "↗️",
            "title": f"Moderate climb — {elev_gain} m of gain",
            "blurb": "Plan for ~2–3 hours uphill. Steady pace beats stop-start bursts.",
            "category": "Effort",
        })

    if trail["length_km"] >= 18:
        parts.append({
            "icon": "🛣️",
            "title": f"Long day — {trail['length_km']} km",
            "blurb": "Start at first light. Bring two litres of water and a real lunch.",
            "category": "Logistics",
        })

    if trail["max_alt_m"] >= 3000:
        parts.append({
            "icon": "🫁",
            "title": f"High altitude — peaks at {trail['max_alt_m']} m",
            "blurb": "Thinner air; expect a 10–20% slower pace. Mild altitude headache is common.",
            "category": "Physiology",
        })
    elif trail["max_alt_m"] >= 2500:
        parts.append({
            "icon": "🌄",
            "title": f"Subalpine peak — {trail['max_alt_m']} m",
            "blurb": "Sun is intense above 2000 m. Cap, sunglasses, factor 50 sunscreen.",
            "category": "Physiology",
        })

    if snapshot:
        snowline = snapshot.get("snowline_m")
        if snowline is not None and snowline < trail["max_alt_m"]:
            parts.append({
                "icon": "❄️",
                "title": "Snow on the upper section",
                "blurb": (
                    f"The snowline ({int(snowline)} m) sits below the summit "
                    f"({trail['max_alt_m']} m). Microspikes and waterproof boots "
                    "make the difference."
                ),
                "category": "Conditions",
            })

        wind = snapshot.get("wind_kmh") or 0.0
        if wind >= 50:
            parts.append({
                "icon": "💨",
                "title": f"Strong gusts — {wind:.0f} km/h",
                "blurb": "Avoid exposed ridges; the wind can knock you off balance.",
                "category": "Conditions",
            })

        precip = snapshot.get("precip_mm") or 0.0
        if precip >= 5:
            parts.append({
                "icon": "☔",
                "title": f"Wet day — {precip:.1f} mm of precipitation",
                "blurb": "Slippery rock descents; lightning risk on exposed peaks during summer storms.",
                "category": "Conditions",
            })

        temp = snapshot.get("temp_c")
        if temp is not None and temp < -2:
            parts.append({
                "icon": "🥶",
                "title": f"Sub-zero forecast ({temp:.0f} °C)",
                "blurb": "Layered insulation; watch fingers/toes during stops.",
                "category": "Conditions",
            })

    if not parts:
        parts.append({
            "icon": "✅",
            "title": "Nothing technical flagged",
            "blurb": "Standard hiking kit and the usual mountain common sense.",
            "category": "Terrain",
        })
    return parts


# ---------------------------------------------------------------------------
# Wikimedia Commons photo search
# ---------------------------------------------------------------------------

_COMMONS_API: str = "https://commons.wikimedia.org/w/api.php"
_USER_AGENT: str = "SwissHikingForecaster/1.0 (educational project)"
_IMAGE_EXTS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_trail_images(query: str, limit: int = 4) -> list[dict]:
    """Search Wikimedia Commons for free-licensed photos matching ``query``.

    Returns up to ``limit`` dicts: ``{url, page, title}``. ``url`` is a
    pre-sized thumbnail (800 px wide). Cached for 24 h. Returns ``[]`` on
    any network or parse failure — the UI shows a fallback in that case.
    """
    if not query:
        return []
    try:
        resp = requests.get(
            _COMMONS_API,
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srnamespace": 6,        # File: namespace only
                "srlimit": limit * 4,    # over-fetch then filter to image extensions
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=8,
        )
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
    except Exception:
        return []

    out: list[dict] = []
    for hit in hits:
        title = hit.get("title", "")
        if not title.lower().endswith(_IMAGE_EXTS):
            continue
        filename = title.replace("File:", "")
        safe = filename.replace(" ", "_")
        out.append({
            "title": filename,
            "url": f"https://commons.wikimedia.org/wiki/Special:FilePath/{safe}?width=800",
            "page": f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
        })
        if len(out) >= limit:
            break
    return out
