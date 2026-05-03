"""Helpers for the trail-detail sub-page.

Provides:
    * ``synthetic_route``       — fake polyline (we have no GPX data).
    * ``interpret_weather``     — plain-English explanation of a verdict.
    * ``analyse_tricky_sections`` — rule-based list of route hazards.
    * ``fetch_trail_images``    — Wikimedia Commons image search (cached).
    * ``difficulty_dots_html``  — 4-dot SAC-grade indicator (HTML span).
    * ``naismith_time``         — estimated walking time from length+ascent.
    * ``weather_at_altitude``   — lapse-rate adjustment for top vs bottom.

The pure functions have no side effects; the photo fetcher calls a free
public API (no key) and is wrapped in ``st.cache_data``.
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

    grade = trail["difficulty"]
    is_hard = grade in {"T4", "T5", "T6"}
    is_demanding = grade in {"T3", "T4", "T5", "T6"}

    if is_hard:
        headline_map = {
            "SAFE": (
                f"✅ The *weather* is favourable — but this is a {grade} route and "
                "we never call T4–T6 hikes SAFE. Treat the conditions as a green "
                "light for the sky, not for the route. Read the **Tricky parts** tab."
            ),
            "BORDERLINE": (
                f"⚠️ Mixed signals on a {grade} route — that combination calls for "
                "a hard look at your experience and your turn-back plan before you set off."
            ),
            "AVOID": (
                f"⛔ On a {grade} route, today's weather pushes the day past safe. "
                "Postpone — the mountain isn't going anywhere."
            ),
        }
    elif is_demanding:
        headline_map = {
            "SAFE": (
                "✅ Weather looks good. **T3 is still demanding terrain** — pack "
                "poles and proper boots, and turn back if you feel unsteady."
            ),
            "BORDERLINE": (
                "⚠️ Mixed conditions on a T3 route. Be ready to call it short."
            ),
            "AVOID": (
                "⛔ Today's weather plus T3 terrain is a postpone. Try a lower "
                "alternative or wait for clearer conditions."
            ),
        }
    else:
        headline_map = {
            "SAFE": "✅ Conditions look favourable. Pack the basics and enjoy.",
            "BORDERLINE": "⚠️ Conditions are mixed — bring extra layers and reassess at the trailhead.",
            "AVOID": "⛔ Conditions point to a postpone. The trail is safer on a different day.",
        }

    out["headline"] = headline_map.get(
        verdict, "Forecast cached — see the breakdown below."
    )

    if is_hard and verdict in {"SAFE", "BORDERLINE"}:
        bullets.insert(0, (
            f"⚠️ **Terrain caveat:** {grade} routes carry inherent risk — exposure, "
            "scrambling, or alpine commitment. Good weather is necessary but not "
            "sufficient."
        ))

    out["bullets"] = bullets
    return out


# ---------------------------------------------------------------------------
# Tricky-parts analyser
# ---------------------------------------------------------------------------

_DIFFICULTY_NOTES: dict[str, dict] = {
    "T1": {"icon": "🚶",
           "title": "Easy hiking path (T1)",
           "blurb": "Wide, well-graded path with no exposure. Trainers are fine. "
                    "Suitable for families and absolute beginners."},
    "T2": {"icon": "🥾",
           "title": "Mountain hiking trail (T2)",
           "blurb": "Mostly maintained, occasional uneven terrain. Hiking shoes "
                    "recommended; basic mountain awareness needed. Watch your footing "
                    "on wet sections."},
    "T3": {"icon": "🪨",
           "title": "Demanding mountain hike (T3) — read this first",
           "blurb": "Steep sections, partly exposed terrain, scree and unstable footing. "
                    "**Surefootedness is mandatory** — a slip can mean a long fall and "
                    "serious injury. Hiking poles and stiff-soled boots are essential. "
                    "Reconsider if you are tired, hiking alone, or unfamiliar with "
                    "mountain terrain."},
    "T4": {"icon": "⛰️",
           "title": "Alpine hike (T4) — this is not a regular hike",
           "blurb": "Trail is intermittent; route-finding is required. Use of hands "
                    "needed in places. **Exposure can be lethal in the event of a slip.** "
                    "Stiff boots, a helmet for falling rock, and prior alpine experience "
                    "are required. Solo hiking is strongly discouraged. Even in perfect "
                    "weather this terrain demands constant attention; a single moment of "
                    "inattention can be fatal."},
    "T5": {"icon": "🧗",
           "title": "Demanding alpine route (T5) — alpine skills required",
           "blurb": "Climbing passages up to UIAA grade II, sustained exposure for long "
                    "stretches. Helmet, harness and rope may be needed; glacier travel is "
                    "possible — carry crampons + ice axe and **know how to use them**. "
                    "Going alone is not appropriate for this grade. If you have any doubt "
                    "about your skills, hire a certified mountain guide."},
    "T6": {"icon": "🪢",
           "title": "Difficult alpine route (T6) — for experts only",
           "blurb": "Sustained climbing (UIAA II–III), glacier travel, severe exposure "
                    "for hours at a time. Mountaineering kit and a competent partner are "
                    "essential. **This is mountaineering, not hiking.** Without prior "
                    "alpine experience and a partner you trust with your life, do NOT "
                    "attempt — hire a guide or pick a different objective."},
}


def analyse_tricky_sections(trail: dict, snapshot: Optional[dict]) -> list[dict]:
    """Return a list of rule-based hazard cards for this trail."""
    parts: list[dict] = []
    grade = trail["difficulty"]

    # T3+: lead with the hard truth that good weather alone isn't enough.
    if grade in {"T3", "T4", "T5", "T6"}:
        parts.append({
            "icon": "🛑",
            "title": "Good weather is not enough on this grade",
            "blurb": (
                f"This is a **{grade}** route. The verdict above reflects sky and "
                "air conditions only — it doesn't account for your fitness, "
                "your route-finding skill, what to do if you twist an ankle two "
                "hours from the nearest road, or how the terrain reacts to fading "
                "light. **If you are in any doubt, turn back.** Better an aborted "
                "hike than a rescue call (or worse)."
            ),
            "category": "Safety",
        })

    diff_note = _DIFFICULTY_NOTES.get(grade)
    if diff_note:
        parts.append({**diff_note, "category": "Terrain"})

    if grade in {"T4", "T5", "T6"}:
        parts.append({
            "icon": "📞",
            "title": "Have an emergency plan",
            "blurb": (
                "Tell someone your route and expected return time. Carry a "
                "charged phone, a head torch, and a basic first-aid kit. "
                "Switzerland: Rega air-rescue **1414**, mountain rescue **117**. "
                "Mobile coverage in alpine valleys can be patchy — don't rely on it."
            ),
            "category": "Safety",
        })

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
            margin = trail["max_alt_m"] - int(snowline)
            severity = "**serious**: " if margin > 200 or grade in {"T4", "T5", "T6"} else ""
            parts.append({
                "icon": "❄️",
                "title": f"Snow on the upper {margin} m of the route",
                "blurb": (
                    f"{severity}The snowline ({int(snowline)} m) sits below the "
                    f"summit ({trail['max_alt_m']} m). Expect verglas (clear ice "
                    "on rock) on north-facing sections — this is invisible and "
                    "deadly. Microspikes minimum; crampons + ice axe if you're "
                    "venturing onto snowfields. Turn back if you don't have them."
                ),
                "category": "Conditions",
            })

        wind = snapshot.get("wind_kmh") or 0.0
        if wind >= 50:
            parts.append({
                "icon": "💨",
                "title": f"Dangerous winds — {wind:.0f} km/h",
                "blurb": (
                    "Gusts at this strength routinely knock hikers off ridges. "
                    "Stay below tree line; postpone any exposed traverse, summit "
                    "or aiguille. This is **postpone weather**, not push-on weather."
                ),
                "category": "Conditions",
            })
        elif wind >= 30:
            parts.append({
                "icon": "💨",
                "title": f"Notable wind — {wind:.0f} km/h",
                "blurb": (
                    "Manageable on flat ground but treacherous on exposed ridges "
                    "and cornices. If your route includes either, reconsider."
                ),
                "category": "Conditions",
            })

        precip = snapshot.get("precip_mm") or 0.0
        if precip >= 10:
            parts.append({
                "icon": "⛈️",
                "title": f"Heavy precipitation — {precip:.1f} mm",
                "blurb": (
                    "Rivers swell quickly; previously easy crossings become "
                    "impassable. **Lightning is the leading cause of death** on "
                    "exposed Swiss summits in summer — get off ridges before "
                    "storms develop and stay off until they pass."
                ),
                "category": "Conditions",
            })
        elif precip >= 3:
            parts.append({
                "icon": "☔",
                "title": f"Wet rock — {precip:.1f} mm forecast",
                "blurb": (
                    "Limestone and slabs lose much of their friction when wet. "
                    "Descents become the crux. Allow extra time and consider an "
                    "easier alternative."
                ),
                "category": "Conditions",
            })

        temp = snapshot.get("temp_c")
        if temp is not None and temp < -5:
            parts.append({
                "icon": "🥶",
                "title": f"Hypothermia conditions ({temp:.0f} °C)",
                "blurb": (
                    "Below −5 °C with any wind, hypothermia is a real risk. "
                    "Full winter layering, spare gloves, hot drink, and a buddy. "
                    "Solo winter hiking at this temperature is not sensible."
                ),
                "category": "Conditions",
            })
        elif temp is not None and temp < 2:
            parts.append({
                "icon": "🥶",
                "title": f"Cold forecast ({temp:.0f} °C)",
                "blurb": (
                    "Expect ice on shaded sections of trail before noon. "
                    "Insulating layers, gloves, and watch fingers/toes during stops."
                ),
                "category": "Conditions",
            })

    if grade in {"T1", "T2"} and len(parts) <= 1:
        parts.append({
            "icon": "✅",
            "title": "Nothing technical flagged",
            "blurb": (
                "On this grade, standard hiking kit and the usual mountain "
                "common sense (water, layers, a map) are enough. Still check "
                "the weather an hour before you leave — alpine forecasts move."
            ),
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


# ---------------------------------------------------------------------------
# Visual helpers — used by the redesigned cards/headers
# ---------------------------------------------------------------------------

# (colour, filled-out-of-4) per SAC grade. Mirrors the four-dot escalation
# in the reference design (green → blue → orange → red → black).
_DIFFICULTY_DOTS: dict[str, tuple[str, int]] = {
    "T1": ("#1E7B3A", 1),  # one green dot
    "T2": ("#1E7B3A", 2),  # two green dots
    "T3": ("#3a7bd5", 2),  # two blue dots
    "T4": ("#E69F00", 3),  # three orange dots
    "T5": ("#C0392B", 3),  # three red dots
    "T6": ("#222222", 4),  # four black dots
}

_GRADE_LABEL: dict[str, str] = {
    "T1": "T1 · Easy hike",
    "T2": "T2 · Mountain hike",
    "T3": "T3 · Demanding mountain hike",
    "T4": "T4 · Alpine hike",
    "T5": "T5 · Demanding alpine route",
    "T6": "T6 · Difficult alpine route",
}


def difficulty_dots_html(grade: str, dot_size_px: int = 11) -> str:
    """Return an inline-flex HTML span showing the SAC grade as 4 dots."""
    colour, filled = _DIFFICULTY_DOTS.get(grade, ("#888", 0))
    dots: list[str] = []
    for i in range(4):
        bg = colour if i < filled else "transparent"
        border = colour if i < filled else "#cfd2d6"
        dots.append(
            f"<span style='display:inline-block; width:{dot_size_px}px; "
            f"height:{dot_size_px}px; border-radius:50%; "
            f"background:{bg}; border:1.5px solid {border};'></span>"
        )
    label = _GRADE_LABEL.get(grade, grade)
    return (
        "<span style='display:inline-flex; align-items:center; gap:6px;'>"
        + "".join(dots)
        + f"<span style='margin-left:6px; font-size:0.88rem; "
        + f"color:#4a4a4a;'>{label}</span></span>"
    )


def naismith_time(length_km: float, ascent_m: float) -> str:
    """Estimated round-trip walking time using Naismith's rule.

    Naismith: 12 minutes per km on the flat + 10 minutes per 100 m of ascent.
    The seed catalogue stores ``length_km`` as the trail length; we treat it
    as the round-trip distance and apply ascent only once (single-summit
    out-and-back). Good enough for an at-a-glance figure — never quote it as
    a guarantee.
    """
    minutes = max(1, length_km * 12 + (ascent_m / 100.0) * 10)
    h, m = divmod(int(round(minutes)), 60)
    if h == 0:
        return f"{m} min"
    if m == 0:
        return f"{h} h"
    return f"{h} h {m} min"


# ---------------------------------------------------------------------------
# Top vs Bottom weather (lapse-rate projection)
# ---------------------------------------------------------------------------

# Standard environmental lapse rate (°C per metre).
_LAPSE_RATE: float = 0.0065
# Rough wind amplification at altitude (less surface friction). Linear
# interpolation between 1.0× at the trail bottom and ``_WIND_TOP_MULT`` at
# the top — purely heuristic, calibrated against typical Alpine ratios.
_WIND_TOP_MULT: float = 1.4


def weather_at_altitude(
    snapshot: Optional[dict],
    target_alt_m: float,
    reference_alt_m: float,
) -> Optional[dict]:
    """Project a forecast snapshot from one altitude to another.

    Open-Meteo gives us a single value per day at the trail's lat/lon; we
    treat ``reference_alt_m`` (typically the trail's min altitude) as the
    measurement point and project to ``target_alt_m`` using:

    * Temperature: standard lapse rate −6.5 °C / 1000 m of climb.
    * Wind: linear ramp from 1.0× at the bottom to ~1.4× at the top.
    * Precipitation, cloud cover, snowline: passed through unchanged
      (no defensible single-trail model for these).

    Returns ``None`` if the snapshot itself is ``None``.
    """
    if snapshot is None:
        return None

    delta_m = target_alt_m - reference_alt_m
    out: dict = dict(snapshot)

    if snapshot.get("temp_c") is not None:
        out["temp_c"] = snapshot["temp_c"] - _LAPSE_RATE * delta_m

    if snapshot.get("wind_kmh") is not None and delta_m > 0:
        # Scale to a fraction of the bottom-to-top ramp (assume ~1500 m total
        # climb produces the full multiplier — bigger climbs cap at the multiplier).
        ramp = min(1.0, delta_m / 1500.0)
        out["wind_kmh"] = snapshot["wind_kmh"] * (1.0 + (_WIND_TOP_MULT - 1.0) * ramp)

    return out


# ---------------------------------------------------------------------------
# Hazard markers for the route map
# ---------------------------------------------------------------------------

def hazard_points(
    pts: list[tuple[float, float]],
    trail: dict,
    snapshot: Optional[dict],
) -> list[dict]:
    """Choose 0–3 points on the synthetic loop to flag as hazards.

    Returns a list of dicts: ``{lat, lon, label, severity}`` where severity
    is ``"warn"`` (yellow) or ``"avoid"`` (red). Used to drop FontAwesome
    diamond markers on the topo map. Severity escalates with SAC grade and
    with weather concerns (snow on summit, strong wind, heavy precip).
    """
    if not pts:
        return []

    # Conceptual midpoint = the synthetic "summit" of the loop.
    summit = pts[len(pts) // 2]
    quarter = pts[len(pts) // 4]
    three_q = pts[3 * len(pts) // 4]

    grade = trail["difficulty"]
    out: list[dict] = []

    if grade in {"T4", "T5", "T6"}:
        out.append({
            "lat": summit[0], "lon": summit[1],
            "label": f"Exposed alpine section ({grade}) — falling rock + scrambling",
            "severity": "avoid",
        })
    elif grade == "T3":
        out.append({
            "lat": summit[0], "lon": summit[1],
            "label": "Steep, partly exposed terrain — surefootedness required",
            "severity": "warn",
        })

    if snapshot:
        snowline = snapshot.get("snowline_m")
        if snowline is not None and snowline < trail["max_alt_m"]:
            out.append({
                "lat": summit[0], "lon": summit[1],
                "label": (f"Snowline ({int(snowline)} m) below summit "
                          f"({trail['max_alt_m']} m) — verglas possible"),
                "severity": "avoid",
            })

        wind = snapshot.get("wind_kmh") or 0.0
        if wind >= 40:
            out.append({
                "lat": three_q[0], "lon": three_q[1],
                "label": f"Exposed ridge — {wind:.0f} km/h wind",
                "severity": "warn",
            })

        precip = snapshot.get("precip_mm") or 0.0
        if precip >= 5:
            out.append({
                "lat": quarter[0], "lon": quarter[1],
                "label": f"Wet rock on descent — {precip:.1f} mm precipitation",
                "severity": "warn",
            })

    return out
