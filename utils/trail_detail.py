"""Helper functions for the trail-detail page.

This module groups together a bunch of small utility functions used by
the Trail Detail page:

    * synthetic_route: draws a fake circular polyline because we don't
                       have real GPX data for our trails.
    * interpret_weather: turns a forecast snapshot into plain English
                         text the user can actually read.
    * analyse_tricky_sections: returns a list of rule-based hazard cards.
    * fetch_trail_images: searches Wikimedia Commons for trail photos
                          (results are cached).
    * difficulty_dots_html: renders a SAC difficulty as 4 colored dots.
    * naismith_time: estimated walking time from distance and ascent.
    * weather_at_altitude: projects a forecast up or down a few hundred
                           meters using the standard lapse rate.

All these functions are pure (no side effects) except for the photo
fetcher, which calls Wikimedia's free public API. Its results are cached
for 24 hours via st.cache_data so we don't spam the API.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

import math
from typing import Optional

import requests
import streamlit as st

from utils.i18n import t


# ---------------------------------------------------------------------------
# Synthetic route
# ---------------------------------------------------------------------------

def synthetic_route(
    lat: float, lon: float, length_km: float, n_points: int = 48
) -> list[tuple[float, float]]:
    """Build a fake circular trail loop centered on the given coordinate.

    Our seeded trails don't ship with real GPS traces, so we can't draw
    the actual route on the map. Instead we draw a circle. The circle's
    perimeter matches the trail's listed length, so visually it's
    roughly the right size. The UI always labels this as approximate.
    """
    # Standard circle math: if the perimeter is length_km then the
    # radius is length_km / (2 * pi). We then convert kilometers to
    # latitude/longitude degrees. One degree of latitude is about 111 km
    # everywhere. One degree of longitude shrinks as you go away from
    # the equator (because meridians get closer together near the poles),
    # so we multiply by cos(latitude) to compensate.
    radius_km = max(length_km, 0.5) / (2 * math.pi)
    radius_lat = radius_km / 111.0
    radius_lon = radius_km / max(111.0 * math.cos(math.radians(lat)), 1e-3)

    pts: list[tuple[float, float]] = []
    # Walk around the circle in n_points + 1 evenly spaced steps. We add
    # the extra step so the polyline ends exactly where it started, which
    # makes folium draw a fully closed loop.
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

# The little helpers below ("banders") take a continuous weather reading
# like "12 degrees" or "27 km/h wind" and return a short label plus a
# practical hint. The cutoff numbers come from typical Swiss hiking
# guidance (DAV / SAC advice for alpine routes).
def _temp_band(temp: float) -> tuple[str, str]:
    if temp < -5:
        return t("very cold"), t("winter gear and avalanche awareness essential")
    if temp < 2:
        return t("cold"), t("expect ice on shaded sections")
    if temp < 10:
        return t("cool"), t("comfortable for uphill effort")
    if temp < 20:
        return t("mild"), t("ideal hiking temperature")
    if temp < 28:
        return t("warm"), t("carry extra water")
    return t("hot"), t("start early, watch for heat exhaustion")


def _wind_band(w: float) -> tuple[str, str]:
    if w < 15:
        return t("light"), t("negligible on the trail")
    if w < 30:
        return t("moderate"), t("noticeable on ridges")
    if w < 50:
        return t("strong"), t("exposed traverses can feel unsafe")
    return (t("very strong"),
            t("consider postponing — gusts threaten balance on ridges"))


def _precip_band(p: float) -> tuple[str, str]:
    if p < 0.5:
        return t("dry"), t("no precipitation expected")
    if p < 3:
        return t("light showers"), t("a shell jacket is enough")
    if p < 10:
        return t("rainy"), t("wet rocks and slippery descents")
    return t("heavy rain"), t("rivers in spate, lightning risk on ridges")


def _cloud_band(c: float) -> str:
    if c < 25:
        return t("mostly sunny — strong UV at altitude")
    if c < 60:
        return t("partly cloudy — pleasant light")
    if c < 85:
        return t("overcast — limited views")
    return t("fully clouded — visibility may drop in fog")


def interpret_weather(snapshot: Optional[dict], trail: dict, verdict: str) -> dict:
    """Turn a weather snapshot into plain-English text the user can read.

    Returns a dictionary with these keys: headline, temp, wind, precip,
    cloud, snow, and bullets. The ``bullets`` value is a list of short
    reasons that explain why we landed on the verdict we did. Any
    indicator we don't have data for gets set to None and is skipped
    by the UI.
    """
    # If we have no forecast at all, return an empty payload with a
    # friendly headline. The UI will render it as a hint instead of
    # crashing or showing zeros everywhere.
    if not snapshot:
        return {
            "headline": t("No cached forecast for this day yet — refresh the "
                           "weather from the sidebar to see an "
                           "interpretation."),
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
        out["temp"] = t("**{temp} °C** — {band}; {note}.",
                        temp=f"{temp:.0f}", band=band, note=note)
    else:
        out["temp"] = None

    band, note = _wind_band(wind)
    out["wind"] = t("**{wind} km/h** — {band}; {note}.",
                    wind=f"{wind:.0f}", band=band, note=note)

    band, note = _precip_band(precip)
    out["precip"] = t("**{precip} mm** — {band}; {note}.",
                      precip=f"{precip:.1f}", band=band, note=note)

    if cloud is not None:
        out["cloud"] = t("**{cloud}%** — {note}.",
                         cloud=f"{cloud:.0f}", note=_cloud_band(cloud))
    else:
        out["cloud"] = None

    # The snowline tells us the altitude above which the air is below
    # freezing. We compare it to the trail's highest point. If the
    # snowline is above the summit, the trail is snow-free. If it sits
    # below the summit, expect snow on the upper section.
    if snow is not None:
        margin = snow - max_alt
        if margin >= 300:
            out["snow"] = t(
                "Snowline at **{snow} m** sits {margin} m above the trail's "
                "max altitude ({max} m) — route is snow-free.",
                snow=int(snow), margin=int(margin), max=max_alt)
        elif margin >= 0:
            out["snow"] = t(
                "Snowline at **{snow} m** is only {margin} m above the "
                "summit ({max} m) — patchy snow possible near the top.",
                snow=int(snow), margin=int(margin), max=max_alt)
        else:
            out["snow"] = t(
                "Snowline at **{snow} m** is {margin} m **below** the "
                "summit ({max} m) — expect snow on the upper section.",
                snow=int(snow), margin=abs(int(margin)), max=max_alt)
    else:
        out["snow"] = None

    # Build a list of short bullet point reasons that explain why we
    # arrived at this verdict. These show up under the headline in the
    # Weather tab so the user can quickly understand the call.
    bullets: list[str] = []
    if temp is not None:
        if -2 <= temp <= 22 and verdict == "SAFE":
            bullets.append(t("Comfortable temperature ({temp} °C).",
                             temp=f"{temp:.0f}"))
        if temp < -2:
            bullets.append(t("Cold enough ({temp} °C) to need full winter "
                             "gear.", temp=f"{temp:.0f}"))
        if temp > 28:
            bullets.append(t("Heat ({temp} °C) raises dehydration risk.",
                             temp=f"{temp:.0f}"))

    if wind < 30:
        if verdict == "SAFE":
            bullets.append(t("Wind is light ({wind} km/h).",
                             wind=f"{wind:.0f}"))
    elif wind >= 50:
        bullets.append(t("Strong gusts ({wind} km/h) on exposed sections.",
                         wind=f"{wind:.0f}"))

    if precip < 1 and verdict == "SAFE":
        bullets.append(t("Dry conditions — no rain forecast."))
    elif precip >= 5:
        bullets.append(t("Rain ({precip} mm) — wet rock + slippery descents.",
                         precip=f"{precip:.1f}"))

    if snow is not None and snow < max_alt:
        bullets.append(
            t("Snow on the upper section (snowline {snow} m < trail max "
              "{max} m).", snow=int(snow), max=max_alt)
        )

    if not bullets:
        bullets.append(
            t("A mix of indicators — see the per-feature breakdown above "
              "for the full picture.")
        )

    # Pick the right tone of headline depending on the SAC difficulty
    # grade. On harder routes we use stricter language, even when the
    # weather is great, to remind the user that the terrain itself is
    # the bigger risk.
    grade = trail["difficulty"]
    is_hard = grade in {"T4", "T5", "T6"}
    is_demanding = grade in {"T3", "T4", "T5", "T6"}

    if is_hard:
        headline_map = {
            "SAFE": t(
                "✅ The *weather* is favourable — but this is a {grade} "
                "route and we never call T4–T6 hikes SAFE. Treat the "
                "conditions as a green light for the sky, not for the "
                "route. Read the **Tricky parts** tab.", grade=grade),
            "BORDERLINE": t(
                "⚠️ Mixed signals on a {grade} route — that combination "
                "calls for a hard look at your experience and your "
                "turn-back plan before you set off.", grade=grade),
            "AVOID": t(
                "⛔ On a {grade} route, today's weather pushes the day "
                "past safe. Postpone — the mountain isn't going anywhere.",
                grade=grade),
        }
    elif is_demanding:
        headline_map = {
            "SAFE": t(
                "✅ Weather looks good. **T3 is still demanding terrain** "
                "— pack poles and proper boots, and turn back if you feel "
                "unsteady."),
            "BORDERLINE": t(
                "⚠️ Mixed conditions on a T3 route. Be ready to call it "
                "short."),
            "AVOID": t(
                "⛔ Today's weather plus T3 terrain is a postpone. Try a "
                "lower alternative or wait for clearer conditions."),
        }
    else:
        headline_map = {
            "SAFE": t("✅ Conditions look favourable. Pack the basics and "
                      "enjoy."),
            "BORDERLINE": t("⚠️ Conditions are mixed — bring extra layers "
                            "and reassess at the trailhead."),
            "AVOID": t("⛔ Conditions point to a postpone. The trail is "
                       "safer on a different day."),
        }

    out["headline"] = headline_map.get(
        verdict, t("Forecast cached — see the breakdown below.")
    )

    # On the alpine grades, we slip a terrain warning to the very top of
    # the bullet list. We want the user to see the danger note before
    # they read any positive weather indicators below it.
    if is_hard and verdict in {"SAFE", "BORDERLINE"}:
        bullets.insert(0, t(
            "⚠️ **Terrain caveat:** {grade} routes carry inherent risk — "
            "exposure, scrambling, or alpine commitment. Good weather is "
            "necessary but not sufficient.", grade=grade))

    out["bullets"] = bullets
    return out


# ---------------------------------------------------------------------------
# Tricky-parts analyser
# ---------------------------------------------------------------------------

# For each SAC grade we have a fixed safety description. Each entry has
# an icon, a title and a longer blurb. The Trail Detail page renders one
# of these as a card on the "Tricky parts" tab based on the trail's grade.
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
    """Build the list of hazard cards shown on the Tricky Parts tab.

    Each dictionary in the returned list becomes one card on the page.
    We add them in a deliberate order:

        1. Safety preface (only on T3 and above).
        2. Terrain card based on the SAC grade.
        3. Emergency / logistics info (only on T4-T6).
        4. Effort cards (long climbs, long distance, high altitude).
        5. Conditions cards driven by the weather snapshot.
    """
    parts: list[dict] = []
    grade = trail["difficulty"]

    # On T3 and the alpine grades, the very first card reminds the user
    # that nice weather alone is not enough to make these routes safe.
    # We surface this warning before anything else so it's hard to miss.
    if grade in {"T3", "T4", "T5", "T6"}:
        parts.append({
            "icon": "🛑",
            "title": t("Good weather is not enough on this grade"),
            "blurb": t(
                "This is a **{grade}** route. The verdict above reflects "
                "sky and air conditions only — it doesn't account for your "
                "fitness, your route-finding skill, what to do if you twist "
                "an ankle two hours from the nearest road, or how the "
                "terrain reacts to fading light. **If you are in any doubt, "
                "turn back.** Better an aborted hike than a rescue call (or "
                "worse).", grade=grade),
            "category": t("Safety"),
        })

    diff_note = _DIFFICULTY_NOTES.get(grade)
    if diff_note:
        # _DIFFICULTY_NOTES stores English source text; translate the
        # title and blurb here so the card follows the language switch.
        parts.append({
            "icon": diff_note["icon"],
            "title": t(diff_note["title"]),
            "blurb": t(diff_note["blurb"]),
            "category": t("Terrain"),
        })

    if grade in {"T4", "T5", "T6"}:
        parts.append({
            "icon": "📞",
            "title": t("Have an emergency plan"),
            "blurb": t(
                "Tell someone your route and expected return time. Carry a "
                "charged phone, a head torch, and a basic first-aid kit. "
                "Switzerland: Rega air-rescue **1414**, mountain rescue "
                "**117**. Mobile coverage in alpine valleys can be patchy "
                "— don't rely on it."),
            "category": t("Safety"),
        })

    # Cards about how hard the effort will be. We bucket by elevation
    # gain (how much vertical climbing) and by total distance.
    elev_gain = trail["max_alt_m"] - trail["min_alt_m"]
    if elev_gain >= 1200:
        parts.append({
            "icon": "📈",
            "title": t("Big climb — {n} m of elevation gain", n=elev_gain),
            "blurb": t("Pace yourself: roughly 4–6 hours of sustained "
                       "ascent. Eat early, refill often."),
            "category": t("Effort"),
        })
    elif elev_gain >= 700:
        parts.append({
            "icon": "↗️",
            "title": t("Moderate climb — {n} m of gain", n=elev_gain),
            "blurb": t("Plan for ~2–3 hours uphill. Steady pace beats "
                       "stop-start bursts."),
            "category": t("Effort"),
        })

    if trail["length_km"] >= 18:
        parts.append({
            "icon": "🛣️",
            "title": t("Long day — {km} km", km=trail["length_km"]),
            "blurb": t("Start at first light. Bring two litres of water "
                       "and a real lunch."),
            "category": t("Logistics"),
        })

    if trail["max_alt_m"] >= 3000:
        parts.append({
            "icon": "🫁",
            "title": t("High altitude — peaks at {n} m",
                       n=trail["max_alt_m"]),
            "blurb": t("Thinner air; expect a 10–20% slower pace. Mild "
                       "altitude headache is common."),
            "category": t("Physiology"),
        })
    elif trail["max_alt_m"] >= 2500:
        parts.append({
            "icon": "🌄",
            "title": t("Subalpine peak — {n} m", n=trail["max_alt_m"]),
            "blurb": t("Sun is intense above 2000 m. Cap, sunglasses, "
                       "factor 50 sunscreen."),
            "category": t("Physiology"),
        })

    if snapshot:
        snowline = snapshot.get("snowline_m")
        if snowline is not None and snowline < trail["max_alt_m"]:
            margin = trail["max_alt_m"] - int(snowline)
            severity = (
                t("**serious**: ")
                if margin > 200 or grade in {"T4", "T5", "T6"}
                else ""
            )
            parts.append({
                "icon": "❄️",
                "title": t("Snow on the upper {n} m of the route", n=margin),
                "blurb": t(
                    "{severity}The snowline ({snowline} m) sits below the "
                    "summit ({max} m). Expect verglas (clear ice on rock) "
                    "on north-facing sections — this is invisible and "
                    "deadly. Microspikes minimum; crampons + ice axe if "
                    "you're venturing onto snowfields. Turn back if you "
                    "don't have them.",
                    severity=severity, snowline=int(snowline),
                    max=trail["max_alt_m"]),
                "category": t("Conditions"),
            })

        wind = snapshot.get("wind_kmh") or 0.0
        if wind >= 50:
            parts.append({
                "icon": "💨",
                "title": t("Dangerous winds — {n} km/h", n=f"{wind:.0f}"),
                "blurb": t(
                    "Gusts at this strength routinely knock hikers off "
                    "ridges. Stay below tree line; postpone any exposed "
                    "traverse, summit or aiguille. This is **postpone "
                    "weather**, not push-on weather."),
                "category": t("Conditions"),
            })
        elif wind >= 30:
            parts.append({
                "icon": "💨",
                "title": t("Notable wind — {n} km/h", n=f"{wind:.0f}"),
                "blurb": t(
                    "Manageable on flat ground but treacherous on exposed "
                    "ridges and cornices. If your route includes either, "
                    "reconsider."),
                "category": t("Conditions"),
            })

        precip = snapshot.get("precip_mm") or 0.0
        if precip >= 10:
            parts.append({
                "icon": "⛈️",
                "title": t("Heavy precipitation — {n} mm",
                           n=f"{precip:.1f}"),
                "blurb": t(
                    "Rivers swell quickly; previously easy crossings "
                    "become impassable. **Lightning is the leading cause "
                    "of death** on exposed Swiss summits in summer — get "
                    "off ridges before storms develop and stay off until "
                    "they pass."),
                "category": t("Conditions"),
            })
        elif precip >= 3:
            parts.append({
                "icon": "☔",
                "title": t("Wet rock — {n} mm forecast", n=f"{precip:.1f}"),
                "blurb": t(
                    "Limestone and slabs lose much of their friction when "
                    "wet. Descents become the crux. Allow extra time and "
                    "consider an easier alternative."),
                "category": t("Conditions"),
            })

        temp = snapshot.get("temp_c")
        if temp is not None and temp < -5:
            parts.append({
                "icon": "🥶",
                "title": t("Hypothermia conditions ({n} °C)",
                           n=f"{temp:.0f}"),
                "blurb": t(
                    "Below −5 °C with any wind, hypothermia is a real "
                    "risk. Full winter layering, spare gloves, hot drink, "
                    "and a buddy. Solo winter hiking at this temperature "
                    "is not sensible."),
                "category": t("Conditions"),
            })
        elif temp is not None and temp < 2:
            parts.append({
                "icon": "🥶",
                "title": t("Cold forecast ({n} °C)", n=f"{temp:.0f}"),
                "blurb": t(
                    "Expect ice on shaded sections of trail before noon. "
                    "Insulating layers, gloves, and watch fingers/toes "
                    "during stops."),
                "category": t("Conditions"),
            })

    if grade in {"T1", "T2"} and len(parts) <= 1:
        parts.append({
            "icon": "✅",
            "title": t("Nothing technical flagged"),
            "blurb": t(
                "On this grade, standard hiking kit and the usual "
                "mountain common sense (water, layers, a map) are enough. "
                "Still check the weather an hour before you leave — alpine "
                "forecasts move."),
            "category": t("Terrain"),
        })
    return parts


# ---------------------------------------------------------------------------
# Wikimedia Commons photo search
# ---------------------------------------------------------------------------

# Wikimedia Commons API - https://commons.wikimedia.org/w/api.php
# Public API for searching Creative-Commons-licensed photos. Free, and
# does not require an API key.
_COMMONS_API: str = "https://commons.wikimedia.org/w/api.php"
# Wikimedia request etiquette - https://meta.wikimedia.org/wiki/User-Agent_policy
# Wikimedia asks any tool that uses their API to identify itself with a
# User-Agent header. So we set ours to a short string that describes the
# project. This way they can contact us if our app is misbehaving.
_USER_AGENT: str = "SwissHikingForecaster/1.0 (educational project)"
_IMAGE_EXTS: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp")


# Streamlit caching pattern - https://docs.streamlit.io
# Cache search results for 24 hours. The same trail name will get the
# same answer for at least a day, which keeps us polite toward the
# Commons API and makes the page feel instant on repeat visits.
@st.cache_data(ttl=86400, show_spinner=False)
def fetch_trail_images(query: str, limit: int = 4) -> list[dict]:
    """Search Wikimedia Commons for free-licensed photos matching the query.

    Returns up to ``limit`` results. Each result is a dictionary with
    keys ``url``, ``page`` and ``title``. The ``url`` is already sized to
    800 pixels wide, so the page does not need to do its own resizing.
    Results are cached for 24 hours. If the network is down or the API
    fails, we return an empty list and the UI shows a fallback image.
    """
    if not query:
        return []
    # MediaWiki search action - https://www.mediawiki.org/wiki/API:Search
    # We use action=query with list=search to get the best matching files.
    # We ask for more results than needed because the API has no way to
    # say "only image files", so we filter client-side based on file
    # extension. The srnamespace=6 parameter restricts results to the
    # File: namespace, which is where Wikimedia stores image files.
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
        # Any network or parsing problem returns an empty list. The caller
        # can show a fallback image instead of the page crashing.
        return []

    # Filter the search results to actual image files, then build a tidy
    # dictionary for each one. The ``url`` is a Special:FilePath link,
    # which Wikimedia auto-resizes for us. We also keep a link back to
    # the Commons file page so the user can check the photo licence.
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
# Visual helpers used across the discovery cards and the trail headers.
# ---------------------------------------------------------------------------

# For each SAC grade we store a (color, number-of-filled-dots-out-of-four)
# pair. This produces the four-dot difficulty badge you see on cards and
# in the trail hero. The color escalates from green (easy) to black (T6),
# and more dots get filled in as the grade goes up.
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
    """Return the HTML for the four-dot difficulty badge for a SAC grade."""
    colour, filled = _DIFFICULTY_DOTS.get(grade, ("#888", 0))
    dots: list[str] = []
    # We always draw exactly 4 dots. The first few are filled with color
    # based on the grade. The remaining ones stay as empty outlines.
    # That way the user can see "this grade is X out of 4" at a glance.
    for i in range(4):
        bg = colour if i < filled else "transparent"
        border = colour if i < filled else "#cfd2d6"
        dots.append(
            f"<span style='display:inline-block; width:{dot_size_px}px; "
            f"height:{dot_size_px}px; border-radius:50%; "
            f"background:{bg}; border:1.5px solid {border};'></span>"
        )
    label = t(_GRADE_LABEL.get(grade, grade))
    return (
        "<span style='display:inline-flex; align-items:center; gap:6px;'>"
        + "".join(dots)
        + f"<span style='margin-left:6px; font-size:0.88rem; "
        + f"color:#4a4a4a;'>{label}</span></span>"
    )


def naismith_time(length_km: float, ascent_m: float) -> str:
    """Estimate how long a hike will take using Naismith's rule.

    Naismith's rule is a classic walking time formula: 12 minutes per
    kilometer on flat ground, plus another 10 minutes for every 100 m
    of climbing. We treat the catalogue's length_km as the round-trip
    distance and only count ascent once (assuming one main climb).
    The result is good enough for a quick estimate; it is not a guarantee.
    """
    # Naismith's rule - https://en.wikipedia.org/wiki/Naismith%27s_rule
    # 12 minutes per km flat plus 10 minutes per 100 m of ascent. The
    # divmod call splits the total minutes into hours and remainder
    # minutes so we can format it nicely.
    minutes = max(1, length_km * 12 + (ascent_m / 100.0) * 10)
    h, m = divmod(int(round(minutes)), 60)
    if h == 0:
        return t("{m} min", m=m)
    if m == 0:
        return t("{h} h", h=h)
    return t("{h} h {m} min", h=h, m=m)


# ---------------------------------------------------------------------------
# Top vs Bottom weather (lapse-rate projection)
# ---------------------------------------------------------------------------

# Atmospheric lapse rate - https://en.wikipedia.org/wiki/Lapse_rate
# Air gets 6.5 degrees Celsius colder for every 1000 m you climb. This
# is the standard meteorological average and the same number Open-Meteo
# uses internally when adjusting forecasts for altitude.
_LAPSE_RATE: float = 0.0065
# Wind speeds up at altitude because there's less friction from trees
# and buildings. We use a simple linear ramp: 1.0x at the trail bottom
# and up to 1.4x at the top. This is just a rough rule of thumb that
# matches what we see in typical Swiss alpine weather data.
_WIND_TOP_MULT: float = 1.4


def weather_at_altitude(
    snapshot: Optional[dict],
    target_alt_m: float,
    reference_alt_m: float,
) -> Optional[dict]:
    """Estimate what the weather looks like at a different altitude.

    The forecast we get from Open-Meteo is for a single point. We use
    ``reference_alt_m`` (usually the trail's lowest altitude) as that
    measurement point and project the values up or down to
    ``target_alt_m`` using simple rules:

    * Temperature: gets 6.5 degrees colder per 1000 m of climb.
    * Wind: scales up linearly from 1.0x at the bottom to about 1.4x.
    * Precipitation, cloud cover and snowline: left alone, because we
      don't have a sensible way to project these for a single trail.

    Returns ``None`` if there's no snapshot to project from.
    """
    if snapshot is None:
        return None

    # delta_m is the height difference we're projecting across. It is
    # positive when going up (bottom to top), negative when going down.
    # We call dict() on the snapshot to make a copy so changes here don't
    # accidentally affect the row sitting in the cache.
    delta_m = target_alt_m - reference_alt_m
    out: dict = dict(snapshot)

    # Temperature: subtract lapse_rate times delta_m. Climbing higher
    # gives a positive delta_m, which subtracts a bigger number, so the
    # temperature ends up cooler. That matches reality.
    if snapshot.get("temp_c") is not None:
        out["temp_c"] = snapshot["temp_c"] - _LAPSE_RATE * delta_m

    if snapshot.get("wind_kmh") is not None and delta_m > 0:
        # Use 1500 m of climb as the reference for the full multiplier.
        # Shorter climbs get a proportionally smaller boost. Climbs of
        # more than 1500 m simply cap at the full _WIND_TOP_MULT, since
        # we don't want a runaway multiplier for very tall mountains.
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
    """Pick a few points along the loop to flag with hazard diamonds.

    Returns a list of dictionaries with keys ``lat``, ``lon``, ``label``
    and ``severity``. Severity is either ``"warn"`` (rendered yellow)
    or ``"avoid"`` (rendered red). These get used by the Trail Detail
    route map to drop diamond-shaped markers on top of the map.

    Severity grows with the SAC grade (harder routes get red markers)
    and with the weather (snow on the summit, strong wind, heavy rain
    all push markers toward red).
    """
    if not pts:
        return []

    # We treat the midpoint of our fake loop as the "summit" and the
    # quarter and three-quarter points as ridge / descent sections.
    # These three locations are where we'll attach hazard markers.
    summit = pts[len(pts) // 2]
    quarter = pts[len(pts) // 4]
    three_q = pts[3 * len(pts) // 4]

    grade = trail["difficulty"]
    out: list[dict] = []

    # Markers based on SAC difficulty grade. Alpine routes get a red
    # marker at the summit warning about exposure. T3 gets a yellow
    # marker at the same spot reminding the user to be surefooted.
    if grade in {"T4", "T5", "T6"}:
        out.append({
            "lat": summit[0], "lon": summit[1],
            "label": t("Exposed alpine section ({grade}) — falling rock + "
                       "scrambling", grade=grade),
            "severity": "avoid",
        })
    elif grade == "T3":
        out.append({
            "lat": summit[0], "lon": summit[1],
            "label": t("Steep, partly exposed terrain — surefootedness "
                       "required"),
            "severity": "warn",
        })

    # Markers based on the weather snapshot. We add one for snow at the
    # summit, one for strong wind on the exposed three-quarter ridge,
    # and one for slippery wet rock on the descent (the quarter point).
    if snapshot:
        snowline = snapshot.get("snowline_m")
        if snowline is not None and snowline < trail["max_alt_m"]:
            out.append({
                "lat": summit[0], "lon": summit[1],
                "label": t("Snowline ({snowline} m) below summit ({max} m) "
                           "— verglas possible",
                           snowline=int(snowline), max=trail["max_alt_m"]),
                "severity": "avoid",
            })

        wind = snapshot.get("wind_kmh") or 0.0
        if wind >= 40:
            out.append({
                "lat": three_q[0], "lon": three_q[1],
                "label": t("Exposed ridge — {n} km/h wind", n=f"{wind:.0f}"),
                "severity": "warn",
            })

        precip = snapshot.get("precip_mm") or 0.0
        if precip >= 5:
            out.append({
                "lat": quarter[0], "lon": quarter[1],
                "label": t("Wet rock on descent — {n} mm precipitation",
                           n=f"{precip:.1f}"),
                "severity": "warn",
            })

    return out
