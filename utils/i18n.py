"""Internationalisation (i18n) for the whole app — English and German.

This single module powers the language switch shown at the top-right of
every page. The design is intentionally simple so any team member can
extend it:

    1. ``t(text, **kwargs)`` is the only function pages need. You pass it
       the English string. If the current language is German it returns
       the German translation; otherwise it returns the English text
       unchanged. Optional keyword arguments are substituted with
       ``str.format`` (e.g. ``t("Found {n} trails", n=5)``).

    2. The chosen language lives in ``st.session_state["lang"]`` as a
       two-letter code (``"en"`` or ``"de"``). It survives page switches
       because Streamlit keeps session_state shared across pages.

    3. ``render_language_toggle()`` draws the EN/DE switch. ``topnav.py``
       calls it once, so the switch appears on every page automatically.

To translate a new string: wrap it in ``t(...)`` at the call site and add
one ``"English": "German"`` entry to the ``_DE`` dictionary below. Any
string that is missing from ``_DE`` simply falls back to English, so the
app never breaks on an untranslated phrase.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from datetime import date

import streamlit as st

# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

# Maps the internal two-letter code to the label shown on the toggle.
LANGUAGES: dict[str, str] = {
    "en": "🇬🇧 EN",
    "de": "🇩🇪 DE",
}

DEFAULT_LANG: str = "en"


# The chosen language is kept in this plain (non-widget) session_state
# key. Streamlit keeps plain keys alive across page navigation, whereas a
# value stored directly under a *widget* key is reset when you move to a
# page that hasn't drawn that widget yet. Routing the choice through this
# key is what makes the language preference stick across every page.
_LANG_STATE_KEY: str = "app_lang"
# The segmented-control widget uses its own separate key.
_LANG_WIDGET_KEY: str = "lang_toggle"


def get_lang() -> str:
    """Return the active language code (``"en"`` or ``"de"``)."""
    # ``or DEFAULT_LANG`` guards against the toggle being deselected,
    # which would otherwise leave a ``None`` in session_state.
    return st.session_state.get(_LANG_STATE_KEY) or DEFAULT_LANG


def _sync_language() -> None:
    """Copy the toggle's value into the persistent key (on_change callback)."""
    st.session_state[_LANG_STATE_KEY] = (
        st.session_state.get(_LANG_WIDGET_KEY) or DEFAULT_LANG
    )


def render_language_toggle() -> None:
    """Draw the EN/DE language switch. Called once by the top navigation.

    Every page rerun re-seeds the widget from the persistent
    ``app_lang`` key (via ``default``), and the ``on_change`` callback
    writes any new selection back to it. Because ``app_lang`` is a plain
    session_state key, the choice survives moving between pages.
    """
    # Make sure the persistent key exists before the widget reads it, so
    # the toggle starts on English the very first time the app is opened.
    st.session_state.setdefault(_LANG_STATE_KEY, DEFAULT_LANG)
    # Streamlit pattern - https://docs.streamlit.io
    # st.segmented_control gives a clean two-pill switch. label_visibility
    # is "collapsed" because the flag emojis already make the purpose obvious.
    st.segmented_control(
        "Language",
        options=list(LANGUAGES.keys()),
        format_func=lambda code: LANGUAGES[code],
        default=get_lang(),
        key=_LANG_WIDGET_KEY,
        on_change=_sync_language,
        label_visibility="collapsed",
    )


# ---------------------------------------------------------------------------
# Translation lookup
# ---------------------------------------------------------------------------


def t(text: str, **kwargs) -> str:
    """Translate ``text`` into the active language.

    ``text`` is always the English string. When the language is German we
    look it up in ``_DE``; a missing entry falls back to the English text.
    Any keyword arguments are substituted with ``str.format`` so callers
    can write ``t("Ranked {n} trails", n=count)``.
    """
    translated = text if get_lang() == "en" else _DE.get(text, text)
    if kwargs:
        translated = translated.format(**kwargs)
    return translated


# Verdict labels are stored internally as the English keys SAFE /
# BORDERLINE / AVOID (the database, the model and the colour maps all use
# them). We only ever translate them for display, through this helper.
_VERDICT_LABELS: dict[str, dict[str, str]] = {
    "SAFE": {"en": "SAFE", "de": "SICHER"},
    "BORDERLINE": {"en": "BORDERLINE", "de": "GRENZWERTIG"},
    "AVOID": {"en": "AVOID", "de": "MEIDEN"},
    "—": {"en": "—", "de": "—"},
}


def verdict_label(verdict: str) -> str:
    """Return the display label for a verdict in the active language."""
    return _VERDICT_LABELS.get(verdict, {}).get(get_lang(), verdict)


# ---------------------------------------------------------------------------
# Localised dates
# ---------------------------------------------------------------------------

# Python's strftime would give English month/weekday names regardless of
# the chosen language, so we keep our own small name tables and format
# dates by hand. This keeps the app free of system-locale dependencies.
_WEEKDAYS: dict[str, list[str]] = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
           "Saturday", "Sunday"],
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
           "Samstag", "Sonntag"],
}
_WEEKDAYS_SHORT: dict[str, list[str]] = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
}
_MONTHS: dict[str, list[str]] = {
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember"],
}
_MONTHS_SHORT: dict[str, list[str]] = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec"],
    "de": ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep",
           "Okt", "Nov", "Dez"],
}


def fmt_date(d: date, style: str = "full") -> str:
    """Format a date with localised weekday and month names.

    ``style`` picks the layout:
        * ``"full"``  -> "Monday 05 May 2026" / "Montag 05 Mai 2026"
        * ``"long"``  -> "Monday 05 May"      / "Montag 05 Mai"
        * ``"short"`` -> "Mon 05 May"         / "Mo 05 Mai"
    """
    lang = get_lang()
    if style == "short":
        weekday = _WEEKDAYS_SHORT[lang][d.weekday()]
        month = _MONTHS_SHORT[lang][d.month - 1]
        return f"{weekday} {d.day:02d} {month}"
    weekday = _WEEKDAYS[lang][d.weekday()]
    month = _MONTHS[lang][d.month - 1]
    if style == "long":
        return f"{weekday} {d.day:02d} {month}"
    return f"{weekday} {d.day:02d} {month} {d.year}"


# ---------------------------------------------------------------------------
# Long prose blocks
# ---------------------------------------------------------------------------
# Multi-paragraph text (the About page) is awkward to key by its English
# content, so these blocks are stored explicitly per language and fetched
# with block(). Streamlit dedents markdown, so the indentation here is
# only for source readability.

_BLOCKS: dict[str, dict[str, str]] = {
    "about_problem_body": {
        "en": """
Hiking in the Swiss Alps is one of the best things you can do in summer,
but it can also be dangerous. Around **20 people die every year** on Swiss
alpine trails, and many more get injured. Most of these accidents happen
because hikers did not realise how risky the conditions on a specific
trail would actually be on that day.

The weather apps people normally use (like MeteoSwiss or SRF Meteo) show
numbers such as temperature, wind speed, or chance of rain. That
information is useful, but it does not directly answer the question every
hiker is really asking: "is this trail a good idea today?" The Swiss
Alpine Club publishes avalanche warnings, but again not at the level of an
individual hike.

Our app tries to close that gap. You pick a trail and a date, and you get
one clear answer: **SAFE**, **BORDERLINE**, or **AVOID**. The answer comes
with a short explanation of the main reasons (for example "wind is too
strong" or "the trail is above the snow line that day"), so you can decide
for yourself whether to go, change your plans, or wait for better weather.
""",
        "de": """
Wandern in den Schweizer Alpen ist eines der schönsten Dinge im Sommer,
kann aber auch gefährlich sein. Jedes Jahr sterben rund **20 Menschen** auf
Schweizer Alpenwegen, und viele weitere verletzen sich. Die meisten dieser
Unfälle passieren, weil Wandernde nicht erkannten, wie riskant die
Bedingungen auf einem bestimmten Weg an jenem Tag tatsächlich waren.

Die Wetter-Apps, die die Leute normalerweise nutzen (wie MeteoSchweiz oder
SRF Meteo), zeigen Zahlen wie Temperatur, Windgeschwindigkeit oder
Regenwahrscheinlichkeit. Diese Informationen sind nützlich, beantworten
aber nicht direkt die Frage, die sich jede:r Wandernde wirklich stellt:
„Ist dieser Weg heute eine gute Idee?“ Der Schweizer Alpen-Club
veröffentlicht Lawinenwarnungen, aber wiederum nicht auf der Ebene einer
einzelnen Wanderung.

Unsere App versucht, diese Lücke zu schliessen. Du wählst einen Weg und ein
Datum und erhältst eine klare Antwort: **SICHER**, **GRENZWERTIG** oder
**MEIDEN**. Die Antwort kommt mit einer kurzen Erklärung der Hauptgründe
(zum Beispiel „der Wind ist zu stark“ oder „der Weg liegt an diesem Tag
über der Schneegrenze“), sodass du selbst entscheiden kannst, ob du gehst,
deine Pläne änderst oder auf besseres Wetter wartest.
""",
    },
    "about_attribution_body": {
        "en": """
- **[Open-Meteo Forecast](https://open-meteo.com/en/docs)**: current and 7-day forecast, free, no key.
- **[Open-Meteo Historical Archive](https://open-meteo.com/en/docs/historical-weather-api)**: up to two years of past weather, free, no key.
- **[Swisstopo GeoAdmin](https://docs.geo.admin.ch/access-data/identify-features.html)**: Swiss federal geodata for trail elevation lookups, free, no key.
""",
        "de": """
- **[Open-Meteo Forecast](https://open-meteo.com/en/docs)**: aktuelle und 7-Tage-Prognose, kostenlos, ohne Schlüssel.
- **[Open-Meteo Historisches Archiv](https://open-meteo.com/en/docs/historical-weather-api)**: bis zu zwei Jahre vergangenes Wetter, kostenlos, ohne Schlüssel.
- **[Swisstopo GeoAdmin](https://docs.geo.admin.ch/access-data/identify-features.html)**: eidgenössische Geodaten für Höhenabfragen der Wege, kostenlos, ohne Schlüssel.
""",
    },
}


def block(name: str) -> str:
    """Return a long prose block in the active language (see ``_BLOCKS``)."""
    entry = _BLOCKS.get(name, {})
    return entry.get(get_lang()) or entry.get("en", "")


# ---------------------------------------------------------------------------
# English -> German dictionary
# ---------------------------------------------------------------------------
# One entry per user-facing English string in the app. Strings with
# ``{placeholder}`` markers are substituted by ``t()`` via str.format, so
# the German value must keep the same placeholder names.

_DE: dict[str, str] = {
    # --- Navigation & shared --------------------------------------------
    "Find a hike": "Wanderung finden",
    "Map": "Karte",
    "Compare": "Vergleichen",
    "About": "Über",
    "no data": "keine Daten",
    "safe": "sicher",
    "borderline": "grenzwertig",
    "avoid": "meiden",

    # --- Sidebar --------------------------------------------------------
    "⚙️ Settings": "⚙️ Einstellungen",
    "Risk tolerance": "Risikobereitschaft",
    "1 = very cautious (verdict shifts toward AVOID). 5 = bold (toward "
    "SAFE). T4+ trails are still never marked SAFE, even at risk = 5.":
        "1 = sehr vorsichtig (Einschätzung tendiert zu MEIDEN). 5 = mutig "
        "(tendiert zu SICHER). T4+-Wege werden auch bei Risiko = 5 nie als "
        "SICHER markiert.",
    "ℹ️ Open **🧭 Find a hike** or **🗺️ Map** to choose a trail.":
        "ℹ️ Öffne **🧭 Wanderung finden** oder **🗺️ Karte**, um einen Weg "
        "auszuwählen.",
    "📍 Selected: **{name}**": "📍 Ausgewählt: **{name}**",
    "Weather is fetched automatically — no refresh needed.":
        "Das Wetter wird automatisch abgerufen — kein Aktualisieren nötig.",

    # --- Landing page (app.py) ------------------------------------------
    "Swiss Alpine Hiking Condition Forecaster":
        "Prognose für Wanderbedingungen in den Schweizer Alpen",
    "Discover Swiss Alpine Trails": "Entdecke Schweizer Alpenwege",
    "AI-powered hiking condition forecasts for safer alpine decisions":
        "KI-gestützte Prognosen für Wanderbedingungen — für sicherere "
        "Entscheidungen in den Alpen",
    "trail catalogue": "Wege im Katalog",
    "weather rows cached": "Wetterdatensätze gespeichert",
    "model status": "Modellstatus",
    "Ready": "Bereit",
    "Retrain": "Neu trainieren",
    "Explore map": "Karte erkunden",
    "Recommended routes": "Empfohlene Routen",
    "Top destinations": "Top-Ziele",
    "Large alpine views, practical trail stats, and condition cues at a "
    "glance.":
        "Weite Alpenpanoramen, praktische Wegdaten und Hinweise zu den "
        "Bedingungen auf einen Blick.",
    "Forecast toolkit": "Prognose-Werkzeuge",
    "Choose how you want to explore": "Wähle, wie du erkunden möchtest",
    "All existing app workflows stay available from the discovery page.":
        "Alle bestehenden App-Funktionen bleiben von der Startseite aus "
        "erreichbar.",
    "Answer a few trail preferences and get ranked recommendations for "
    "your date.":
        "Beantworte ein paar Fragen zu deinen Vorlieben und erhalte ein "
        "Ranking der Empfehlungen für dein Datum.",
    "Browse Swiss routes spatially with condition-aware color cues.":
        "Durchstöbere Schweizer Routen auf der Karte mit "
        "bedingungsabhängigen Farbhinweisen.",
    "Compare two to four routes side by side before committing.":
        "Vergleiche zwei bis vier Routen nebeneinander, bevor du dich "
        "entscheidest.",
    "Review model status, training tools, metrics, and project context.":
        "Modellstatus, Trainingswerkzeuge, Kennzahlen und Projektkontext "
        "einsehen.",
    "Time": "Dauer",
    "Ascent": "Aufstieg",
    "Length": "Länge",

    # --- Find page ------------------------------------------------------
    "Find my best hike": "Meine beste Wanderung finden",
    "Tell us what kind of day you want and when. We cross-reference your "
    "preferences with the live weather forecast and rank matching hikes "
    "safest first.":
        "Sag uns, was für einen Tag du dir wünschst und wann. Wir gleichen "
        "deine Vorlieben mit der aktuellen Wetterprognose ab und sortieren "
        "passende Wanderungen — die sichersten zuerst.",
    "AI trail finder": "KI-Wegfinder",
    "Tune your trail day": "Stelle deinen Wandertag ein",
    "Filter by region, grade, distance and altitude. The ranking still "
    "uses the same forecast and model logic underneath.":
        "Filtere nach Region, Schwierigkeit, Distanz und Höhe. Das Ranking "
        "nutzt dabei weiterhin dieselbe Prognose- und Modelllogik.",
    "Personalized search": "Personalisierte Suche",
    "Cantons": "Kantone",
    "Any canton": "Beliebiger Kanton",
    "Leave empty to search all Swiss cantons.":
        "Leer lassen, um alle Schweizer Kantone zu durchsuchen.",
    "Regions": "Regionen",
    "Any region": "Beliebige Region",
    "Alps · Pre-Alps · Jura · Mittelland. Empty = all.":
        "Alpen · Voralpen · Jura · Mittelland. Leer = alle.",
    "SAC grade": "SAC-Schwierigkeit",
    "Any grade": "Beliebige Schwierigkeit",
    "T1 = strolling · T6 = serious alpine. Empty = all.":
        "T1 = Spazieren · T6 = anspruchsvolles Alpingelände. Leer = alle.",
    "Distance": "Distanz",
    "Route length in kilometres.": "Routenlänge in Kilometern.",
    "Highest point": "Höchster Punkt",
    "Maximum altitude reached by the trail.":
        "Maximale vom Weg erreichte Höhe.",
    "Date window": "Zeitfenster",
    "Today": "Heute",
    "Pick a date": "Datum wählen",
    "Forecasts cover today + the next {n} days.":
        "Prognosen umfassen heute + die nächsten {n} Tage.",
    "Date": "Datum",
    "🧭 Find my best hikes": "🧭 Meine besten Wanderungen finden",
    "No trails matched your quiz answers. Loosen the filters and try "
    "again.":
        "Keine Wege passen zu deinen Antworten. Lockere die Filter und "
        "versuche es erneut.",
    "Ranked **{n}** matching trail(s) for **{d}**. 🟢 {safe} · 🟠 "
    "{borderline} · 🔴 {avoid} · ⚪ {nodata}":
        "**{n}** passende(r) Weg(e) für **{d}** sortiert. 🟢 {safe} · 🟠 "
        "{borderline} · 🔴 {avoid} · ⚪ {nodata}",
    "⚠️ {n} trail(s) couldn't be scored — show details":
        "⚠️ {n} Weg(e) konnten nicht bewertet werden — Details anzeigen",
    "These trails appear in the list with **no data**. The most common "
    "cause is a transient Open-Meteo API hiccup — usually fixes itself; "
    "click **🔁 Re-run search** above to retry.":
        "Diese Wege erscheinen in der Liste mit **keine Daten**. Häufigste "
        "Ursache ist eine kurzzeitige Störung der Open-Meteo-API — behebt "
        "sich meist von selbst; klicke oben auf **🔁 Suche erneut "
        "ausführen**.",
    "**Sample error message(s):**": "**Beispiel-Fehlermeldung(en):**",
    "**Affected trails:**": "**Betroffene Wege:**",
    "Top {n} hikes": "Top-{n}-Wanderungen",
    "Open any recommendation for the route map, weather breakdown, tricky "
    "parts, photos and reports.":
        "Öffne eine Empfehlung für Routenkarte, Wetteraufschlüsselung, "
        "knifflige Stellen, Fotos und Berichte.",
    "Ranked recommendations": "Sortierte Empfehlungen",
    "Show the other {n} matches": "Die übrigen {n} Treffer anzeigen",
    "Recent reports from hikers": "Aktuelle Berichte von Wandernden",
    "Community reports become training signal the next time the model is "
    "retrained.":
        "Community-Berichte werden beim nächsten Modelltraining als "
        "Trainingssignal verwendet.",
    "Trail notes": "Wegnotizen",
    "No reports yet. Open any trail's detail page and submit one after "
    "your hike — they go straight into the model on the next retrain.":
        "Noch keine Berichte. Öffne die Detailseite eines Wegs und reiche "
        "nach deiner Wanderung einen ein — sie fliessen beim nächsten "
        "Training direkt ins Modell ein.",
    "_no comment_": "_kein Kommentar_",
    "View details": "Details anzeigen",
    "Safety note": "Sicherheitshinweis",
    "👆 Fill in the filters and hit **Find matching hikes** to see your "
    "ranked recommendations.":
        "👆 Fülle die Filter aus und klicke auf **Meine besten Wanderungen "
        "finden**, um deine sortierten Empfehlungen zu sehen.",
    "✖ Clear & restart": "✖ Zurücksetzen & neu starten",
    "No trails match your quiz answers. Try widening the canton, "
    "difficulty, or length filters.":
        "Keine Wege passen zu deinen Antworten. Erweitere die Filter für "
        "Kanton, Schwierigkeit oder Länge.",
    "No trails seeded. Restart the app or run bootstrap.":
        "Keine Wege geladen. Starte die App neu oder führe den Bootstrap "
        "aus.",
    "Checking the forecast for {n} trail(s)…":
        "Prognose für {n} Weg(e) wird geprüft …",
    "Scored {done}/{total} trails…":
        "{done}/{total} Wege bewertet …",

    # --- Map page -------------------------------------------------------
    "Trail map": "Wegkarte",
    "Browse Switzerland by canton, then zoom into individual trails with "
    "condition-aware colors for the date you choose.":
        "Durchstöbere die Schweiz nach Kanton und zoome dann in einzelne "
        "Wege hinein — mit bedingungsabhängigen Farben für das von dir "
        "gewählte Datum.",
    "Map discovery": "Kartenerkundung",
    "📅 Date to assess": "📅 Zu bewertendes Datum",
    "⚠️ {n} trail(s) couldn't be fetched (network blip or Open-Meteo "
    "rate-limit). Refresh the page to retry.":
        "⚠️ {n} Weg(e) konnten nicht abgerufen werden (Netzwerkstörung "
        "oder Open-Meteo-Ratenlimit). Lade die Seite neu, um es erneut zu "
        "versuchen.",
    "Drill into a canton": "In einen Kanton hineinzoomen",
    "Click any canton on the map or use these quick buttons to zoom into "
    "individual trails.":
        "Klicke auf einen Kanton auf der Karte oder nutze diese "
        "Schnellschaltflächen, um in einzelne Wege hineinzuzoomen.",
    "Browse by region": "Nach Region durchsuchen",
    "Data coverage": "Datenabdeckung",
    "{count} trails": "{count} Wege",
    "Average verdict": "Durchschnittliche Einschätzung",
    "Click marker again or use the button below to drill in.":
        "Klicke die Markierung erneut oder nutze die Schaltfläche unten, um "
        "hineinzuzoomen.",
    "Pick from the dropdown below to open the full trail page.":
        "Wähle aus der Liste unten, um die volle Wegseite zu öffnen.",
    "safe cantons": "sichere Kantone",
    "borderline cantons": "grenzwertige Kantone",
    "avoid cantons": "zu meidende Kantone",
    "No trails recorded for {canton}.":
        "Keine Wege für {canton} erfasst.",
    "Open a trail detail page": "Eine Weg-Detailseite öffnen",
    "Pick a trail to see route notes, forecast interpretation, photos and "
    "reports.":
        "Wähle einen Weg, um Wegnotizen, Prognosedeutung, Fotos und "
        "Berichte zu sehen.",
    "Trail selector": "Wegauswahl",
    "Trail": "Weg",
    "→ Open trail detail": "→ Weg-Details öffnen",
    "Trails in {canton}": "Wege in {canton}",
    "Showing every trail in {canton} for {d}. Click a marker or use the "
    "selector below.":
        "Alle Wege in {canton} für {d}. Klicke auf eine Markierung oder "
        "nutze die Auswahl unten.",
    "Canton detail": "Kantonsdetail",
    "← All cantons": "← Alle Kantone",
    "Canton overview": "Kantonsübersicht",
    "Each bubble is a Swiss canton, colored by the average trail verdict "
    "for {d}. Bigger bubble means more trails.":
        "Jede Blase ist ein Schweizer Kanton, eingefärbt nach der "
        "durchschnittlichen Wegeinschätzung für {d}. Grössere Blase = mehr "
        "Wege.",
    "At a glance": "Auf einen Blick",

    # --- Compare page ---------------------------------------------------
    "Compare trails": "Wege vergleichen",
    "Pit two to four routes against each other for the same day, then "
    "open the strongest candidate for full route detail.":
        "Stelle zwei bis vier Routen für denselben Tag gegenüber und "
        "öffne anschliessend den stärksten Kandidaten für die vollen "
        "Wegdetails.",
    "Route comparison": "Routenvergleich",
    "Build your shortlist": "Erstelle deine Auswahlliste",
    "Choose a date and compare two to four candidate hikes under the same "
    "forecast window.":
        "Wähle ein Datum und vergleiche zwei bis vier Wanderungen im "
        "selben Prognosezeitraum.",
    "Side-by-side planning": "Planung nebeneinander",
    "Date to compare": "Zu vergleichendes Datum",
    "Pick {min}–{max} trails": "{min}–{max} Wege auswählen",
    "Use the search box to filter — start typing a trail name.":
        "Nutze das Suchfeld zum Filtern — beginne, einen Wegnamen "
        "einzutippen.",
    "Select between **{min}** and **{max}** trails to compare. Tip: use "
    "the search box to filter the dropdown.":
        "Wähle zwischen **{min}** und **{max}** Wegen zum Vergleichen. "
        "Tipp: Nutze das Suchfeld, um die Auswahlliste zu filtern.",
    "Predicted risk": "Vorhergesagtes Risiko",
    "Lower is better: SAFE sits at the calmer end of the scale, AVOID at "
    "the stop-sign end.":
        "Niedriger ist besser: SICHER liegt am ruhigen Ende der Skala, "
        "MEIDEN am Stoppschild-Ende.",
    "Model verdict": "Modelleinschätzung",
    "Risk score (1=SAFE, 3=AVOID)": "Risikowert (1=SICHER, 3=MEIDEN)",
    "Weather profile": "Wetterprofil",
    "Normalized indicators show why routes with similar grades can "
    "diverge on the same day.":
        "Normierte Indikatoren zeigen, warum Routen mit ähnlicher "
        "Schwierigkeit am selben Tag unterschiedlich ausfallen können.",
    "Forecast shape": "Prognoseform",
    "Numbers side by side": "Zahlen nebeneinander",
    "The raw weather and route attributes behind the visual comparison.":
        "Die Roh-Wetter- und Routendaten hinter dem visuellen Vergleich.",
    "Decision table": "Entscheidungstabelle",
    "Jump from comparison into the full route page for maps, hazards and "
    "photos.":
        "Springe vom Vergleich auf die volle Routenseite mit Karten, "
        "Gefahren und Fotos.",
    "selected routes": "ausgewählte Routen",
    "Temp": "Temp.",
    "Wind": "Wind",
    "Precip": "Niederschlag",
    "Cloud": "Bewölkung",
    "Snowline": "Schneegrenze",
    "Grade": "Schwierigkeit",
    "Verdict": "Einschätzung",
    "Confidence": "Zuversicht",
    "Temp °C": "Temp. °C",
    "Wind km/h": "Wind km/h",
    "Precip mm": "Niederschlag mm",
    "Snowline m": "Schneegrenze m",
    "Trail max m": "Weg max. m",

    # --- About page -----------------------------------------------------
    "About this app": "Über diese App",
    "Swiss Alpine Hiking Condition Forecaster combines trail catalogue "
    "data, weather caches and a trained model into route-level condition "
    "guidance.":
        "Die Prognose für Wanderbedingungen in den Schweizer Alpen "
        "verbindet Wegkatalogdaten, Wetterspeicher und ein trainiertes "
        "Modell zu weggenauen Bedingungshinweisen.",
    "Project and model": "Projekt und Modell",
    "Why this tool exists": "Warum es dieses Werkzeug gibt",
    "Raw weather numbers are useful, but hikers also need a quick answer "
    "about whether a given trail is a good idea today.":
        "Reine Wetterzahlen sind nützlich, doch Wandernde brauchen auch "
        "eine schnelle Antwort, ob ein bestimmter Weg heute eine gute Idee "
        "ist.",
    "Problem": "Problem",
    "Initial setup": "Ersteinrichtung",
    "Seed historical weather and retrain the model when the local cache "
    "needs rebuilding.":
        "Lade historisches Wetter und trainiere das Modell neu, wenn der "
        "lokale Speicher neu aufgebaut werden muss.",
    "Model operations": "Modellbetrieb",
    "weather rows in DB": "Wetterzeilen in der DB",
    "trails seeded": "geladene Wege",
    "model file": "Modelldatei",
    "trained": "trainiert",
    "not yet": "noch nicht",
    "Years of history to fetch": "Abzurufende Jahre an Historie",
    "⬇️ Seed historical weather (all trails)":
        "⬇️ Historisches Wetter laden (alle Wege)",
    "Fetching archive…": "Archiv wird abgerufen …",
    "Fetching archive… {name} ({i}/{total})":
        "Archiv wird abgerufen … {name} ({i}/{total})",
    "Done with {n} errors:": "Abgeschlossen mit {n} Fehlern:",
    "Historical weather seeded for all trails.":
        "Historisches Wetter für alle Wege geladen.",
    "🧠 Retrain model": "🧠 Modell neu trainieren",
    "Training Random Forest…": "Random Forest wird trainiert …",
    "Trained! Accuracy: {acc} on {n} rows.":
        "Trainiert! Genauigkeit: {acc} bei {n} Zeilen.",
    "Retrain failed: {err}": "Neutraining fehlgeschlagen: {err}",
    "Model performance": "Modellleistung",
    "Training metrics appear after retraining from the current local "
    "database.":
        "Trainingskennzahlen erscheinen nach dem Neutraining aus der "
        "aktuellen lokalen Datenbank.",
    "Evaluation": "Auswertung",
    "Metrics will appear here after the first retrain. Click **Retrain "
    "model** above.":
        "Kennzahlen erscheinen hier nach dem ersten Neutraining. Klicke "
        "oben auf **Modell neu trainieren**.",
    "accuracy": "Genauigkeit",
    "rows trained": "trainierte Zeilen",
    "model version": "Modellversion",
    "Confusion matrix": "Konfusionsmatrix",
    "Predicted": "Vorhergesagt",
    "Actual": "Tatsächlich",
    "Count": "Anzahl",
    "Classification report": "Klassifikationsbericht",
    "Feature importance": "Merkmalswichtigkeit",
    "Importance": "Wichtigkeit",
    "Feature": "Merkmal",
    "Data sources": "Datenquellen",
    "Free public APIs and local seeded data power the app.":
        "Kostenlose öffentliche APIs und lokal geladene Daten betreiben "
        "die App.",
    "Attribution": "Quellenangabe",

    # --- Planner page ---------------------------------------------------
    "🗓️ Trail planner": "🗓️ Wanderplaner",
    "Tell us what kind of hike you want and when. We will find the best "
    "trails predicted SAFE on that day.":
        "Sag uns, welche Art von Wanderung du willst und wann. Wir finden "
        "die besten Wege, die für diesen Tag als SICHER vorhergesagt "
        "werden.",
    "Difficulty (SAC scale)": "Schwierigkeit (SAC-Skala)",
    "T1 = easy hiking path · T6 = difficult alpine route.":
        "T1 = leichter Wanderweg · T6 = schwierige Alpinroute.",
    "Region (optional)": "Region (optional)",
    "Leave empty to search all regions.":
        "Leer lassen, um alle Regionen zu durchsuchen.",
    "Target date": "Zieldatum",
    "Find trails": "Wege finden",
    "Querying forecast data…": "Prognosedaten werden abgefragt …",
    "No trails match those filters. Try widening the difficulty or "
    "region.":
        "Keine Wege passen zu diesen Filtern. Erweitere die Schwierigkeit "
        "oder Region.",
    "Checking forecasts…": "Prognosen werden geprüft …",
    "No forecast data found for any matching trail on that date.":
        "Keine Prognosedaten für einen passenden Weg an diesem Datum "
        "gefunden.",
    "**{safe} of {total} trails** predicted SAFE on {d}.":
        "**{safe} von {total} Wegen** für {d} als SICHER vorhergesagt.",
    "Canton": "Kanton",
    "Difficulty": "Schwierigkeit",
    "Source": "Quelle",
    "Max alt m": "Max. Höhe m",

    # --- Trail Detail page ----------------------------------------------
    "Trail detail": "Wegdetails",
    "Choose a route from Find or Map to see forecast interpretation, "
    "route context, hazards and photos.":
        "Wähle eine Route über Finden oder Karte, um Prognosedeutung, "
        "Routenkontext, Gefahren und Fotos zu sehen.",
    "Route intelligence": "Routen-Insights",
    "No trail selected yet. Open **🧭 Find a hike** for a quiz-based "
    "ranking, or **🗺️ Map** to browse all trails visually.":
        "Noch kein Weg ausgewählt. Öffne **🧭 Wanderung finden** für ein "
        "fragebasiertes Ranking oder **🗺️ Karte**, um alle Wege visuell "
        "zu durchstöbern.",
    "Go to Find a hike": "Zu Wanderung finden",
    "Browse the map": "Karte durchsuchen",
    "Trail #{id} not found in the database.":
        "Weg #{id} nicht in der Datenbank gefunden.",
    "Estimated time": "Geschätzte Dauer",
    "Max altitude": "Maximale Höhe",
    "📅 Date to assess ": "📅 Zu bewertendes Datum ",
    "🔀 Compare with another trail": "🔀 Mit anderem Weg vergleichen",
    "Opens Compare with {name} preselected.":
        "Öffnet Vergleichen mit vorausgewähltem {name}.",
    "Find more hikes": "Weitere Wanderungen finden",
    "Back to map": "Zurück zur Karte",
    "⚠️ **Safety lock:** {caveat}": "⚠️ **Sicherheitssperre:** {caveat}",
    "Overview": "Übersicht",
    "Route map": "Routenkarte",
    "Weather": "Wetter",
    "Tricky parts": "Knifflige Stellen",
    "Photos": "Fotos",
    "At a glance ": "Auf einen Blick ",
    "Core route facts and the cached forecast snapshot for the selected "
    "date.":
        "Wichtige Routenfakten und der gespeicherte Prognose-Schnappschuss "
        "für das gewählte Datum.",
    "Elevation range": "Höhenbereich",
    "Difference between min and max altitude.":
        "Unterschied zwischen minimaler und maximaler Höhe.",
    "Difficulty (SAC)": "Schwierigkeit (SAC)",
    "#### Snapshot for this date": "#### Schnappschuss für dieses Datum",
    "No cached weather snapshot for this date. Use **🔄 Refresh weather** "
    "in the sidebar to fetch one.":
        "Kein gespeicherter Wetter-Schnappschuss für dieses Datum. Nutze "
        "**🔄 Wetter aktualisieren** in der Seitenleiste, um einen "
        "abzurufen.",
    "🌡️ Temp": "🌡️ Temp.",
    "💨 Wind": "💨 Wind",
    "☔ Precip": "☔ Niederschlag",
    "❄️ Snowline": "❄️ Schneegrenze",
    "Verdict source: **{source}** · Confidence: **{conf}**":
        "Quelle der Einschätzung: **{source}** · Zuversicht: **{conf}**",
    "Route on the map": "Route auf der Karte",
    "Approximate loop geometry with route context and hazard markers.":
        "Ungefähre Rundweg-Geometrie mit Routenkontext und "
        "Gefahrenmarkierungen.",
    "Note: detailed GPX traces aren't bundled with the seeded trails, so "
    "the loop drawn here is **approximate** — a circle centred on the "
    "official start point with the same total length. Use it for "
    "orientation, not navigation.":
        "Hinweis: Detaillierte GPX-Tracks sind nicht in den geladenen "
        "Wegen enthalten, daher ist der hier gezeichnete Rundweg "
        "**ungefähr** — ein Kreis um den offiziellen Startpunkt mit "
        "derselben Gesamtlänge. Nutze ihn zur Orientierung, nicht zur "
        "Navigation.",
    "≈{km} km loop": "≈{km} km Rundweg",
    "Start · {name}": "Start · {name}",
    "Summit · approx. {alt} m": "Gipfel · ca. {alt} m",
    "🟡 = caution · 🔴 = serious hazard. Hover any diamond on the map for "
    "details.":
        "🟡 = Vorsicht · 🔴 = ernste Gefahr. Fahre über eine Raute auf der "
        "Karte für Details.",
    "#### ⛰️ Elevation profile": "#### ⛰️ Höhenprofil",
    "Snowline · {alt} m": "Schneegrenze · {alt} m",
    "Distance (km)": "Distanz (km)",
    "Altitude (m)": "Höhe (m)",
    "Elevation": "Höhe",
    "Tricky parts and what to pack": "Knifflige Stellen und Ausrüstung",
    "Terrain, weather and logistics notes generated from route grade and "
    "forecast conditions.":
        "Hinweise zu Gelände, Wetter und Logistik, erstellt aus "
        "Wegschwierigkeit und Prognosebedingungen.",
    "Safety notes": "Sicherheitshinweise",
    "Why is it considered {verdict}?":
        "Warum gilt es als {verdict}?",
    "The same verdict logic is broken down into readable weather and "
    "terrain signals.":
        "Dieselbe Einschätzungslogik, aufgeschlüsselt in lesbare Wetter- "
        "und Geländesignale.",
    "Forecast explanation": "Prognoseerklärung",
    "##### Top vs. bottom weather": "##### Wetter oben vs. unten",
    "Forecasts are reported at one point. We project them to the trail's "
    "min and max altitudes using the standard lapse rate (−6.5 °C / 1000 "
    "m of climb). Treat as a guide, not a guarantee.":
        "Prognosen gelten für einen einzelnen Punkt. Wir projizieren sie "
        "mit der Standard-Temperaturabnahme (−6,5 °C / 1000 Höhenmeter) "
        "auf die minimale und maximale Höhe des Wegs. Als Richtwert, nicht "
        "als Garantie zu verstehen.",
    "⛰️ Top of the trail": "⛰️ Oberes Wegende",
    "🌲 Bottom of the trail": "🌲 Unteres Wegende",
    "##### Top reasons": "##### Wichtigste Gründe",
    "##### Per-indicator breakdown": "##### Aufschlüsselung je Indikator",
    "🌡️ Temperature": "🌡️ Temperatur",
    "☔ Precipitation": "☔ Niederschlag",
    "☁️ Cloud cover": "☁️ Bewölkung",
    "❄️ Snowline vs. trail max": "❄️ Schneegrenze vs. Weghöhe max.",
    "The whole week at a glance": "Die ganze Woche auf einen Blick",
    "Use the seven-day outlook to find a better window if today looks "
    "mixed.":
        "Nutze die Sieben-Tage-Aussicht, um ein besseres Zeitfenster zu "
        "finden, falls heute durchwachsen aussieht.",
    "Forecast window": "Prognosezeitraum",
    "Use this to find the best day to go — verdicts here use the same "
    "safety logic as the headline above.":
        "Damit findest du den besten Tag — die Einschätzungen hier nutzen "
        "dieselbe Sicherheitslogik wie die Überschrift oben.",
    "##### Daily verdicts (next 7 days)":
        "##### Tägliche Einschätzungen (nächste 7 Tage)",
    "Refresh the cache to populate the 7-day forecast.":
        "Aktualisiere den Speicher, um die 7-Tage-Prognose zu füllen.",
    "Day with a blue outline = the date you're currently viewing above.":
        "Tag mit blauem Rahmen = das Datum, das du oben gerade ansiehst.",
    "📈 7-day timeline (temperature · wind · precip)":
        "📈 7-Tage-Verlauf (Temperatur · Wind · Niederschlag)",
    "Temp (°C)": "Temp. (°C)",
    "Wind (km/h)": "Wind (km/h)",
    "Precip (mm)": "Niederschlag (mm)",
    "Temperature (°C)": "Temperatur (°C)",
    "Wind (km/h) · Precip (mm)": "Wind (km/h) · Niederschlag (mm)",
    "No forecast cached for this day.":
        "Keine Prognose für diesen Tag gespeichert.",
    "💨 {wind} km/h wind": "💨 {wind} km/h Wind",
    "☔ {precip} mm precip": "☔ {precip} mm Niederschlag",
    "❄️ snowline {margin} m {marker} you":
        "❄️ Schneegrenze {margin} m {marker} dir",
    "above": "über",
    "below": "unter",
    "🌟 **Best day to go:** {d} — {verdict} ({conf} confidence).":
        "🌟 **Bester Tag:** {d} — {verdict} ({conf} Zuversicht).",
    " Note: {grade} routes are never marked SAFE; this is the best "
    "*weather*, not a safety endorsement.":
        " Hinweis: {grade}-Routen werden nie als SICHER markiert; dies ist "
        "das beste *Wetter*, keine Sicherheitsfreigabe.",
    " Consider rescheduling if you can.":
        " Verschiebe es nach Möglichkeit.",
    "🌗 **Best window this week:** {d} — BORDERLINE.{msg}":
        "🌗 **Bestes Zeitfenster diese Woche:** {d} — GRENZWERTIG.{msg}",
    "⛔ No safe day in the next 7. Earliest watchable day: {d} "
    "({verdict}).":
        "⛔ Kein sicherer Tag in den nächsten 7. Frühester beobachtbarer "
        "Tag: {d} ({verdict}).",
    "Pictures of the route": "Bilder der Route",
    "Free-licensed Wikimedia Commons images for visual context.":
        "Frei lizenzierte Bilder von Wikimedia Commons für visuellen "
        "Kontext.",
    "Searching Wikimedia Commons…": "Wikimedia Commons wird durchsucht …",
    "No Commons photos found for *{name}*. Try clicking the trail name on "
    "Wikipedia for context, or submit your own via the report form "
    "below.":
        "Keine Commons-Fotos für *{name}* gefunden. Suche den Wegnamen zum "
        "Kontext auf Wikipedia oder reiche unten über das Berichtsformular "
        "eigene ein.",
    "Photos pulled from Wikimedia Commons — click any image to see the "
    "original, photographer, and licence terms.":
        "Fotos von Wikimedia Commons — klicke auf ein Bild, um Original, "
        "Fotograf:in und Lizenzbedingungen zu sehen.",
    "source ↗": "Quelle ↗",
    "Hiked {name}? Submit a report":
        "{name} gewandert? Reiche einen Bericht ein",
    "Your report becomes ground truth on the next model retrain and "
    "helps verdicts improve.":
        "Dein Bericht wird beim nächsten Modelltraining zur Referenz und "
        "hilft, die Einschätzungen zu verbessern.",
    "Community signal": "Community-Signal",
    "Date hiked": "Wanderdatum",
    "Conditions you found": "Vorgefundene Bedingungen",
    "What was it like?": "Wie war es?",
    "e.g. 'Section above 2300 m had verglas — needed crampons.'":
        "z. B. „Abschnitt über 2300 m hatte Blankeis — Steigeisen nötig.“",
    "Submit report": "Bericht einreichen",
    "Report saved for {name}. Thank you 🙏":
        "Bericht für {name} gespeichert. Danke 🙏",

    # --- Verdict / forecast interpretation (utils/trail_detail.py) ------
    "very cold": "sehr kalt",
    "winter gear and avalanche awareness essential":
        "Winterausrüstung und Lawinenbewusstsein unerlässlich",
    "cold": "kalt",
    "expect ice on shaded sections":
        "Eis auf schattigen Abschnitten zu erwarten",
    "cool": "kühl",
    "comfortable for uphill effort":
        "angenehm für den Aufstieg",
    "mild": "mild",
    "ideal hiking temperature": "ideale Wandertemperatur",
    "warm": "warm",
    "carry extra water": "zusätzliches Wasser mitnehmen",
    "hot": "heiss",
    "start early, watch for heat exhaustion":
        "früh starten, auf Hitzeerschöpfung achten",
    "light": "schwach",
    "negligible on the trail": "auf dem Weg vernachlässigbar",
    "moderate": "mässig",
    "noticeable on ridges": "auf Graten spürbar",
    "strong": "stark",
    "exposed traverses can feel unsafe":
        "exponierte Querungen können unsicher wirken",
    "very strong": "sehr stark",
    "consider postponing — gusts threaten balance on ridges":
        "Verschiebung erwägen — Böen gefährden das Gleichgewicht auf Graten",
    "dry": "trocken",
    "no precipitation expected": "kein Niederschlag erwartet",
    "light showers": "leichte Schauer",
    "a shell jacket is enough": "eine Regenjacke genügt",
    "rainy": "regnerisch",
    "wet rocks and slippery descents":
        "nasse Felsen und rutschige Abstiege",
    "heavy rain": "starker Regen",
    "rivers in spate, lightning risk on ridges":
        "Hochwasser führende Bäche, Blitzgefahr auf Graten",
    "mostly sunny — strong UV at altitude":
        "überwiegend sonnig — starke UV-Strahlung in der Höhe",
    "partly cloudy — pleasant light":
        "teils bewölkt — angenehmes Licht",
    "overcast — limited views": "bedeckt — eingeschränkte Sicht",
    "fully clouded — visibility may drop in fog":
        "vollständig bewölkt — Sicht kann bei Nebel sinken",
    "No cached forecast for this day yet — refresh the weather from the "
    "sidebar to see an interpretation.":
        "Noch keine gespeicherte Prognose für diesen Tag — aktualisiere "
        "das Wetter in der Seitenleiste, um eine Deutung zu sehen.",
    "**{temp} °C** — {band}; {note}.":
        "**{temp} °C** — {band}; {note}.",
    "**{wind} km/h** — {band}; {note}.":
        "**{wind} km/h** — {band}; {note}.",
    "**{precip} mm** — {band}; {note}.":
        "**{precip} mm** — {band}; {note}.",
    "**{cloud}%** — {note}.": "**{cloud} %** — {note}.",
    "Snowline at **{snow} m** sits {margin} m above the trail's max "
    "altitude ({max} m) — route is snow-free.":
        "Schneegrenze bei **{snow} m** liegt {margin} m über der maximalen "
        "Weghöhe ({max} m) — Route ist schneefrei.",
    "Snowline at **{snow} m** is only {margin} m above the summit ({max} "
    "m) — patchy snow possible near the top.":
        "Schneegrenze bei **{snow} m** liegt nur {margin} m über dem "
        "Gipfel ({max} m) — vereinzelt Schnee nahe der Spitze möglich.",
    "Snowline at **{snow} m** is {margin} m **below** the summit ({max} "
    "m) — expect snow on the upper section.":
        "Schneegrenze bei **{snow} m** liegt {margin} m **unter** dem "
        "Gipfel ({max} m) — Schnee auf dem oberen Abschnitt zu erwarten.",
    "Comfortable temperature ({temp} °C).":
        "Angenehme Temperatur ({temp} °C).",
    "Cold enough ({temp} °C) to need full winter gear.":
        "Kalt genug ({temp} °C), um volle Winterausrüstung zu brauchen.",
    "Heat ({temp} °C) raises dehydration risk.":
        "Hitze ({temp} °C) erhöht das Dehydrierungsrisiko.",
    "Wind is light ({wind} km/h).": "Wind ist schwach ({wind} km/h).",
    "Strong gusts ({wind} km/h) on exposed sections.":
        "Starke Böen ({wind} km/h) auf exponierten Abschnitten.",
    "Dry conditions — no rain forecast.":
        "Trockene Bedingungen — kein Regen vorhergesagt.",
    "Rain ({precip} mm) — wet rock + slippery descents.":
        "Regen ({precip} mm) — nasser Fels + rutschige Abstiege.",
    "Snow on the upper section (snowline {snow} m < trail max {max} m).":
        "Schnee auf dem oberen Abschnitt (Schneegrenze {snow} m < Weghöhe "
        "max. {max} m).",
    "A mix of indicators — see the per-feature breakdown above for the "
    "full picture.":
        "Eine Mischung von Indikatoren — siehe die Aufschlüsselung oben "
        "für das Gesamtbild.",
    "✅ The *weather* is favourable — but this is a {grade} route and we "
    "never call T4–T6 hikes SAFE. Treat the conditions as a green light "
    "for the sky, not for the route. Read the **Tricky parts** tab.":
        "✅ Das *Wetter* ist günstig — aber dies ist eine {grade}-Route, "
        "und wir bezeichnen T4–T6-Wanderungen nie als SICHER. Sieh die "
        "Bedingungen als grünes Licht für den Himmel, nicht für die Route. "
        "Lies den Tab **Knifflige Stellen**.",
    "⚠️ Mixed signals on a {grade} route — that combination calls for a "
    "hard look at your experience and your turn-back plan before you set "
    "off.":
        "⚠️ Gemischte Signale auf einer {grade}-Route — diese Kombination "
        "verlangt einen ehrlichen Blick auf deine Erfahrung und deinen "
        "Umkehrplan, bevor du losgehst.",
    "⛔ On a {grade} route, today's weather pushes the day past safe. "
    "Postpone — the mountain isn't going anywhere.":
        "⛔ Auf einer {grade}-Route bringt das heutige Wetter den Tag über "
        "das Sichere hinaus. Verschiebe es — der Berg läuft nicht weg.",
    "✅ Weather looks good. **T3 is still demanding terrain** — pack poles "
    "and proper boots, and turn back if you feel unsteady.":
        "✅ Das Wetter sieht gut aus. **T3 bleibt anspruchsvolles "
        "Gelände** — nimm Stöcke und feste Schuhe mit und kehre um, wenn "
        "du dich unsicher fühlst.",
    "⚠️ Mixed conditions on a T3 route. Be ready to call it short.":
        "⚠️ Gemischte Bedingungen auf einer T3-Route. Sei bereit, "
        "abzubrechen.",
    "⛔ Today's weather plus T3 terrain is a postpone. Try a lower "
    "alternative or wait for clearer conditions.":
        "⛔ Das heutige Wetter plus T3-Gelände bedeutet verschieben. "
        "Versuche eine tiefere Alternative oder warte auf klarere "
        "Bedingungen.",
    "✅ Conditions look favourable. Pack the basics and enjoy.":
        "✅ Die Bedingungen sehen günstig aus. Nimm die Grundausrüstung "
        "mit und geniesse es.",
    "⚠️ Conditions are mixed — bring extra layers and reassess at the "
    "trailhead.":
        "⚠️ Die Bedingungen sind durchwachsen — nimm zusätzliche "
        "Kleidungsschichten mit und beurteile am Ausgangspunkt neu.",
    "⛔ Conditions point to a postpone. The trail is safer on a different "
    "day.":
        "⛔ Die Bedingungen sprechen für ein Verschieben. Der Weg ist an "
        "einem anderen Tag sicherer.",
    "Forecast cached — see the breakdown below.":
        "Prognose gespeichert — siehe Aufschlüsselung unten.",
    "⚠️ **Terrain caveat:** {grade} routes carry inherent risk — "
    "exposure, scrambling, or alpine commitment. Good weather is "
    "necessary but not sufficient.":
        "⚠️ **Geländevorbehalt:** {grade}-Routen bergen ein "
        "grundsätzliches Risiko — Exposition, Kraxeln oder alpine "
        "Anforderungen. Gutes Wetter ist notwendig, aber nicht "
        "ausreichend.",

    # --- Tricky-parts cards ---------------------------------------------
    "Safety": "Sicherheit",
    "Terrain": "Gelände",
    "Effort": "Anstrengung",
    "Logistics": "Logistik",
    "Physiology": "Physiologie",
    "Conditions": "Bedingungen",
    "Good weather is not enough on this grade":
        "Gutes Wetter reicht auf dieser Schwierigkeit nicht",
    "This is a **{grade}** route. The verdict above reflects sky and air "
    "conditions only — it doesn't account for your fitness, your "
    "route-finding skill, what to do if you twist an ankle two hours from "
    "the nearest road, or how the terrain reacts to fading light. **If "
    "you are in any doubt, turn back.** Better an aborted hike than a "
    "rescue call (or worse).":
        "Dies ist eine **{grade}**-Route. Die Einschätzung oben "
        "berücksichtigt nur Himmels- und Luftbedingungen — nicht deine "
        "Fitness, deine Orientierungsfähigkeit, was zu tun ist, wenn du "
        "dir zwei Stunden von der nächsten Strasse den Knöchel verdrehst, "
        "oder wie das Gelände auf nachlassendes Licht reagiert. **Kehre im "
        "Zweifel um.** Lieber eine abgebrochene Wanderung als ein "
        "Rettungsruf (oder Schlimmeres).",
    "Easy hiking path (T1)": "Leichter Wanderweg (T1)",
    "Wide, well-graded path with no exposure. Trainers are fine. Suitable "
    "for families and absolute beginners.":
        "Breiter, gut angelegter Weg ohne Exposition. Turnschuhe genügen. "
        "Für Familien und absolute Anfänger:innen geeignet.",
    "Mountain hiking trail (T2)": "Bergwanderweg (T2)",
    "Mostly maintained, occasional uneven terrain. Hiking shoes "
    "recommended; basic mountain awareness needed. Watch your footing on "
    "wet sections.":
        "Meist gepflegt, gelegentlich unebenes Gelände. Wanderschuhe "
        "empfohlen; grundlegendes Bergbewusstsein nötig. Achte auf "
        "nassen Abschnitten auf deinen Tritt.",
    "Demanding mountain hike (T3) — read this first":
        "Anspruchsvolle Bergwanderung (T3) — lies dies zuerst",
    "Steep sections, partly exposed terrain, scree and unstable footing. "
    "**Surefootedness is mandatory** — a slip can mean a long fall and "
    "serious injury. Hiking poles and stiff-soled boots are essential. "
    "Reconsider if you are tired, hiking alone, or unfamiliar with "
    "mountain terrain.":
        "Steile Abschnitte, teils exponiertes Gelände, Geröll und "
        "unsicherer Tritt. **Trittsicherheit ist Pflicht** — ein Ausrutscher "
        "kann einen langen Sturz und schwere Verletzungen bedeuten. "
        "Wanderstöcke und Schuhe mit steifer Sohle sind unerlässlich. "
        "Überdenke es, wenn du müde bist, allein wanderst oder mit "
        "Berggelände nicht vertraut bist.",
    "Alpine hike (T4) — this is not a regular hike":
        "Alpinwanderung (T4) — dies ist keine gewöhnliche Wanderung",
    "Trail is intermittent; route-finding is required. Use of hands "
    "needed in places. **Exposure can be lethal in the event of a slip.** "
    "Stiff boots, a helmet for falling rock, and prior alpine experience "
    "are required. Solo hiking is strongly discouraged. Even in perfect "
    "weather this terrain demands constant attention; a single moment of "
    "inattention can be fatal.":
        "Der Weg ist nur teilweise vorhanden; Orientierung ist nötig. "
        "Stellenweise ist Einsatz der Hände erforderlich. **Exposition "
        "kann bei einem Ausrutscher tödlich sein.** Feste Schuhe, ein "
        "Helm gegen Steinschlag und alpine Vorerfahrung sind nötig. Vom "
        "Alleingehen wird dringend abgeraten. Selbst bei perfektem Wetter "
        "verlangt dieses Gelände ständige Aufmerksamkeit; ein einziger "
        "Moment der Unachtsamkeit kann tödlich sein.",
    "Demanding alpine route (T5) — alpine skills required":
        "Anspruchsvolle Alpinroute (T5) — alpine Fähigkeiten nötig",
    "Climbing passages up to UIAA grade II, sustained exposure for long "
    "stretches. Helmet, harness and rope may be needed; glacier travel is "
    "possible — carry crampons + ice axe and **know how to use them**. "
    "Going alone is not appropriate for this grade. If you have any doubt "
    "about your skills, hire a certified mountain guide.":
        "Kletterstellen bis UIAA-Grad II, anhaltende Exposition über lange "
        "Strecken. Helm, Gurt und Seil können nötig sein; "
        "Gletscherbegehung ist möglich — führe Steigeisen + Pickel mit und "
        "**wisse, wie man sie benutzt**. Alleingehen ist für diese "
        "Schwierigkeit nicht angemessen. Bei Zweifeln an deinem Können "
        "engagiere eine:n zertifizierte:n Bergführer:in.",
    "Difficult alpine route (T6) — for experts only":
        "Schwierige Alpinroute (T6) — nur für Expert:innen",
    "Sustained climbing (UIAA II–III), glacier travel, severe exposure "
    "for hours at a time. Mountaineering kit and a competent partner are "
    "essential. **This is mountaineering, not hiking.** Without prior "
    "alpine experience and a partner you trust with your life, do NOT "
    "attempt — hire a guide or pick a different objective.":
        "Anhaltendes Klettern (UIAA II–III), Gletscherbegehung, schwere "
        "Exposition über Stunden. Hochtourenausrüstung und ein:e "
        "kompetente:r Partner:in sind unerlässlich. **Das ist "
        "Bergsteigen, nicht Wandern.** Ohne alpine Vorerfahrung und eine:n "
        "Partner:in, dem/der du dein Leben anvertraust, versuche es "
        "NICHT — engagiere eine:n Bergführer:in oder wähle ein anderes "
        "Ziel.",
    "Have an emergency plan": "Habe einen Notfallplan",
    "Tell someone your route and expected return time. Carry a charged "
    "phone, a head torch, and a basic first-aid kit. Switzerland: Rega "
    "air-rescue **1414**, mountain rescue **117**. Mobile coverage in "
    "alpine valleys can be patchy — don't rely on it.":
        "Sag jemandem deine Route und die erwartete Rückkehrzeit. Führe "
        "ein geladenes Handy, eine Stirnlampe und ein einfaches "
        "Erste-Hilfe-Set mit. Schweiz: Rega-Luftrettung **1414**, "
        "Bergrettung **117**. Der Mobilfunkempfang in Alpentälern kann "
        "lückenhaft sein — verlass dich nicht darauf.",
    "Big climb — {n} m of elevation gain":
        "Grosser Aufstieg — {n} Höhenmeter",
    "Pace yourself: roughly 4–6 hours of sustained ascent. Eat early, "
    "refill often.":
        "Teile dir die Kräfte ein: rund 4–6 Stunden anhaltender Aufstieg. "
        "Iss früh, fülle oft nach.",
    "Moderate climb — {n} m of gain":
        "Mässiger Aufstieg — {n} Höhenmeter",
    "Plan for ~2–3 hours uphill. Steady pace beats stop-start bursts.":
        "Plane ~2–3 Stunden bergauf. Ein gleichmässiges Tempo schlägt "
        "ruckartige Schübe.",
    "Long day — {km} km": "Langer Tag — {km} km",
    "Start at first light. Bring two litres of water and a real lunch.":
        "Starte bei Tagesanbruch. Nimm zwei Liter Wasser und ein richtiges "
        "Mittagessen mit.",
    "High altitude — peaks at {n} m": "Grosse Höhe — Gipfel bei {n} m",
    "Thinner air; expect a 10–20% slower pace. Mild altitude headache is "
    "common.":
        "Dünnere Luft; rechne mit 10–20 % langsamerem Tempo. Leichte "
        "Höhenkopfschmerzen sind häufig.",
    "Subalpine peak — {n} m": "Subalpiner Gipfel — {n} m",
    "Sun is intense above 2000 m. Cap, sunglasses, factor 50 sunscreen.":
        "Die Sonne ist über 2000 m intensiv. Mütze, Sonnenbrille, "
        "Sonnencreme mit Faktor 50.",
    "Snow on the upper {n} m of the route":
        "Schnee auf den oberen {n} m der Route",
    "{severity}The snowline ({snowline} m) sits below the summit ({max} "
    "m). Expect verglas (clear ice on rock) on north-facing sections — "
    "this is invisible and deadly. Microspikes minimum; crampons + ice "
    "axe if you're venturing onto snowfields. Turn back if you don't have "
    "them.":
        "{severity}Die Schneegrenze ({snowline} m) liegt unter dem Gipfel "
        "({max} m). Rechne mit Blankeis (klares Eis auf Fels) auf "
        "nordseitigen Abschnitten — unsichtbar und tödlich. Mindestens "
        "Mikrospikes; Steigeisen + Pickel, wenn du dich auf Schneefelder "
        "wagst. Kehre um, wenn du sie nicht hast.",
    "**serious**: ": "**ernst**: ",
    "Dangerous winds — {n} km/h": "Gefährlicher Wind — {n} km/h",
    "Gusts at this strength routinely knock hikers off ridges. Stay below "
    "tree line; postpone any exposed traverse, summit or aiguille. This "
    "is **postpone weather**, not push-on weather.":
        "Böen dieser Stärke werfen Wandernde regelmässig von Graten. Bleib "
        "unter der Baumgrenze; verschiebe jede exponierte Querung, jeden "
        "Gipfel oder jede Nadel. Das ist **Verschiebewetter**, kein "
        "Weiter-so-Wetter.",
    "Notable wind — {n} km/h": "Spürbarer Wind — {n} km/h",
    "Manageable on flat ground but treacherous on exposed ridges and "
    "cornices. If your route includes either, reconsider.":
        "Auf flachem Boden beherrschbar, aber tückisch auf exponierten "
        "Graten und Wechten. Falls deine Route eines davon enthält, "
        "überdenke es.",
    "Heavy precipitation — {n} mm": "Starker Niederschlag — {n} mm",
    "Rivers swell quickly; previously easy crossings become impassable. "
    "**Lightning is the leading cause of death** on exposed Swiss summits "
    "in summer — get off ridges before storms develop and stay off until "
    "they pass.":
        "Bäche schwellen schnell an; zuvor einfache Übergänge werden "
        "unpassierbar. **Blitze sind die häufigste Todesursache** auf "
        "exponierten Schweizer Gipfeln im Sommer — verlasse Grate, bevor "
        "Gewitter entstehen, und bleibe fern, bis sie vorüber sind.",
    "Wet rock — {n} mm forecast": "Nasser Fels — {n} mm vorhergesagt",
    "Limestone and slabs lose much of their friction when wet. Descents "
    "become the crux. Allow extra time and consider an easier "
    "alternative.":
        "Kalkstein und Platten verlieren bei Nässe viel Reibung. Abstiege "
        "werden zur Schlüsselstelle. Plane mehr Zeit ein und erwäge eine "
        "leichtere Alternative.",
    "Hypothermia conditions ({n} °C)":
        "Unterkühlungsgefahr ({n} °C)",
    "Below −5 °C with any wind, hypothermia is a real risk. Full winter "
    "layering, spare gloves, hot drink, and a buddy. Solo winter hiking "
    "at this temperature is not sensible.":
        "Unter −5 °C ist Unterkühlung bei jedem Wind ein echtes Risiko. "
        "Volle Winterkleidung, Ersatzhandschuhe, ein heisses Getränk und "
        "Begleitung. Alleingang im Winter bei dieser Temperatur ist nicht "
        "vernünftig.",
    "Cold forecast ({n} °C)": "Kalte Prognose ({n} °C)",
    "Expect ice on shaded sections of trail before noon. Insulating "
    "layers, gloves, and watch fingers/toes during stops.":
        "Rechne vor Mittag mit Eis auf schattigen Wegabschnitten. "
        "Isolierende Kleidungsschichten, Handschuhe, und achte bei Pausen "
        "auf Finger/Zehen.",
    "Nothing technical flagged": "Nichts Technisches gemeldet",
    "On this grade, standard hiking kit and the usual mountain common "
    "sense (water, layers, a map) are enough. Still check the weather an "
    "hour before you leave — alpine forecasts move.":
        "Auf dieser Schwierigkeit genügen normale Wanderausrüstung und der "
        "übliche Bergverstand (Wasser, Kleidungsschichten, eine Karte). "
        "Prüfe das Wetter trotzdem eine Stunde vor dem Aufbruch — alpine "
        "Prognosen ändern sich.",

    # --- Route-map hazard markers (utils/trail_detail.py) ---------------
    "Exposed alpine section ({grade}) — falling rock + scrambling":
        "Exponierter Alpinabschnitt ({grade}) — Steinschlag + Kraxeln",
    "Steep, partly exposed terrain — surefootedness required":
        "Steiles, teils exponiertes Gelände — Trittsicherheit erforderlich",
    "Snowline ({snowline} m) below summit ({max} m) — verglas possible":
        "Schneegrenze ({snowline} m) unter dem Gipfel ({max} m) — Blankeis "
        "möglich",
    "Exposed ridge — {n} km/h wind": "Exponierter Grat — {n} km/h Wind",
    "Wet rock on descent — {n} mm precipitation":
        "Nasser Fels im Abstieg — {n} mm Niederschlag",

    # --- SAC grade labels (utils/trail_detail.py) -----------------------
    "T1 · Easy hike": "T1 · Leichte Wanderung",
    "T2 · Mountain hike": "T2 · Bergwanderung",
    "T3 · Demanding mountain hike": "T3 · Anspruchsvolle Bergwanderung",
    "T4 · Alpine hike": "T4 · Alpinwanderung",
    "T5 · Demanding alpine route": "T5 · Anspruchsvolle Alpinroute",
    "T6 · Difficult alpine route": "T6 · Schwierige Alpinroute",

    # --- Naismith time units --------------------------------------------
    "{m} min": "{m} Min.",
    "{h} h": "{h} Std.",
    "{h} h {m} min": "{h} Std. {m} Min.",

    # --- Difficulty names (utils/predictions.py caveats) ----------------
    "easy hike": "leichte Wanderung",
    "mountain hike": "Bergwanderung",
    "demanding mountain hike": "anspruchsvolle Bergwanderung",
    "alpine hike": "Alpinwanderung",
    "demanding alpine hike": "anspruchsvolle Alpinwanderung",
    "difficult alpine hike": "schwierige Alpinwanderung",
    "This is a {grade} ({name}). Even with perfect weather, the terrain "
    "itself carries serious risk — a slip on exposed ground can be "
    "lethal. We never mark T4–T6 routes as SAFE; treat the conditions as "
    "a green light for the *weather*, not for the *route*.":
        "Dies ist eine {grade} ({name}). Selbst bei perfektem Wetter birgt "
        "das Gelände selbst ein ernstes Risiko — ein Ausrutscher auf "
        "exponiertem Boden kann tödlich sein. Wir markieren T4–T6-Routen "
        "nie als SICHER; sieh die Bedingungen als grünes Licht für das "
        "*Wetter*, nicht für die *Route*.",
    "wind {wind} km/h on exposed climbing terrain":
        "Wind {wind} km/h auf exponiertem Klettergelände",
    "precipitation {precip} mm — wet rock above 2500 m turns scrambling "
    "deadly":
        "Niederschlag {precip} mm — nasser Fels über 2500 m macht Kraxeln "
        "tödlich",
    "snowline {snowline} m within 200 m of the summit ({max} m) — verglas "
    "and hidden ice likely":
        "Schneegrenze {snowline} m innerhalb von 200 m des Gipfels ({max} "
        "m) — Blankeis und verstecktes Eis wahrscheinlich",
    "On a {grade} route, any of these is a stop sign: {concerns}.":
        "Auf einer {grade}-Route ist jedes davon ein Stoppschild: "
        "{concerns}.",
    "T3 demands surefootedness on steep, partly exposed terrain. A fall "
    "here can mean a serious injury. Hiking poles and proper boots are "
    "non-negotiable; turn back if you feel unsteady.":
        "T3 verlangt Trittsicherheit auf steilem, teils exponiertem "
        "Gelände. Ein Sturz hier kann eine schwere Verletzung bedeuten. "
        "Wanderstöcke und feste Schuhe sind Pflicht; kehre um, wenn du "
        "dich unsicher fühlst.",
}
