"""Helpers that pick a nice picture for each trail card.

For every trail we try, in order:
    1. A hand-picked Wikimedia Commons photo we know is the real route.
    2. A live search on Wikimedia Commons using the trail name and location.
    3. As a last resort, a generic alpine photo from Unsplash, labelled
       as illustrative so the user knows it isn't the actual trail.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

import streamlit as st

from utils.trail_detail import fetch_trail_images


# Wikimedia Commons thumbnail endpoint - https://commons.wikimedia.org/w/api.php
# Serves resized JPEG/PNG thumbs for any file in Commons, addressed by filename.
COMMONS_THUMB_ENDPOINT: str = "https://commons.wikimedia.org/w/thumb.php"
UNSPLASH_FALLBACK_IMAGE: str = (
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4"
    "?auto=format&fit=crop&w=900&q=85"
)
FALLBACK_NOTICE: str = "Illustrative Unsplash image - not the actual route"

# Common hiking words we strip out of trail names before searching. Words
# like "loop" or "trail" match thousands of unrelated photos on Commons,
# so we drop them and search using only the unique parts of the name.
GENERIC_ROUTE_WORDS: set[str] = {
    "approach",
    "canton",
    "hike",
    "hiking",
    "loop",
    "mountain",
    "panorama",
    "pass",
    "rundweg",
    "switzerland",
    "trail",
    "via",
    "walk",
}

# For our most famous routes we just hard-code a Wikimedia Commons
# filename we already know is a good picture. If a trail name contains
# any of the keywords below, we go straight to that filename and skip
# the live search. This guarantees the top routes always look great.
KNOWN_ROUTE_IMAGE_FILES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("gornergrat",), "Aerial panorama of the Gornergrat 170622.jpg"),
    (("aletsch",), "Fieschertal VS - Aletsch Glacier (28235283066).jpg"),
    (
        ("mannlichen", "m\u00e4nnlichen", "kleine scheidegg"),
        "M\u00e4nnlichen to Kleine Scheidegg (305770894).jpg",
    ),
    (("rigi",), "Zugersee from Rigi panorama 20210905.jpg"),
    (
        ("oeschinensee", "oeschinen"),
        "Oeschinen Lake (Oeschinensee) panorama from above 140622.jpg",
    ),
    (("saas-fee", "saas fee", "hannig"), "Saas Fee Hannig.jpg"),
    (("matterhorn", "h\u00f6rnli", "hornli"), "Hornlihutte 20190717 1316.jpg"),
    (("eggishorn",), "3625 - Eggishorn viewed from Bettmerhorn.JPG"),
    (("albishorn",), "CH.ZH.Hausen-am-Albis 2022-07-02 Albishorn.jpg"),
)


def _row_value(row, key: str, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


# Build a Wikimedia Commons thumbnail URL for a given filename and width.
# Commons resizes the image for us when we hit this endpoint, so we don't
# have to download a giant original every time.
def _commons_thumb_url(filename: str, width: int = 900) -> str:
    normalized = filename.replace(" ", "_")
    return f"{COMMONS_THUMB_ENDPOINT}?f={quote(normalized, safe='')}&w={width}"


# Normalize a string for searching. We strip accents and anything that
# isn't a letter or number. This is so a search for "Maennlichen" matches
# a filename containing "Mannlichen" or "Männlichen", no matter how the
# original was spelled.
def _searchable_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text)


def _route_tokens(trail_name: str) -> list[str]:
    tokens = []
    for token in _searchable_text(trail_name).split():
        if len(token) < 3 or token in GENERIC_ROUTE_WORDS:
            continue
        tokens.append(token)
    return list(dict.fromkeys(tokens))


def _image_title_matches_route(filename: str, trail_name: str) -> bool:
    title = _searchable_text(filename)
    tokens = _route_tokens(trail_name)
    return bool(tokens) and any(token in title for token in tokens)


def _known_route_image_url(trail_name: str) -> str | None:
    normalized = trail_name.casefold()
    searchable = _searchable_text(trail_name)
    for needles, filename in KNOWN_ROUTE_IMAGE_FILES:
        if any(needle.casefold() in normalized or needle in searchable for needle in needles):
            return _commons_thumb_url(filename)
    return None


def _fallback_image_info() -> dict[str, str | bool]:
    return {
        "url": UNSPLASH_FALLBACK_IMAGE,
        "is_fallback": True,
        "notice": FALLBACK_NOTICE,
    }


def route_image_search_terms(trail) -> list[str]:
    """Build Wikimedia search terms from route name and location metadata."""
    name = str(_row_value(trail, "name", "") or "").strip()
    canton = str(_row_value(trail, "canton", "Switzerland") or "Switzerland")
    region = str(_row_value(trail, "region", "Alps") or "Alps")

    terms: list[str] = []
    if name:
        terms.append(f"{name} {canton} hiking")
        parts = [
            p.strip()
            for p in re.split(r"\s+(?:-|to|\u2014|\u2013|鈥\?)\s+", name)
            if p.strip()
        ]
        for part in parts:
            if part and part != name:
                terms.append(f"{part} mountain Switzerland")
    terms.append(f"{canton} {region} hiking Switzerland")
    return list(dict.fromkeys(terms))


# Streamlit caching pattern - https://docs.streamlit.io
# We cache image lookups for 24 hours. Wikimedia photos almost never
# change, so a long TTL means we only hit the network once per route
# per day. show_spinner=False hides the spinner Streamlit would otherwise
# show on first call, since the lookup is fast enough not to need it.
@st.cache_data(ttl=86400, show_spinner=False)
def _route_image_info_cached(
    trail_name: str,
    canton: str,
    region: str,
) -> dict[str, str | bool]:
    # Step 1: check our hand-picked list first. If the trail name matches
    # one of our well-known routes we return that image straight away.
    known_url = _known_route_image_url(trail_name)
    if known_url:
        return {"url": known_url, "is_fallback": False, "notice": ""}

    # Step 2: search Wikimedia Commons live. We try several query strings,
    # starting with the most specific (trail name + canton + "hiking") and
    # broadening if nothing matches. The first matching image wins.
    trail = {"name": trail_name, "canton": canton, "region": region}
    for term in route_image_search_terms(trail):
        images = fetch_trail_images(term, limit=5)
        for image in images:
            filename = str(image.get("title") or "").strip()
            if filename and _image_title_matches_route(filename, trail_name):
                return {
                    "url": _commons_thumb_url(filename),
                    "is_fallback": False,
                    "notice": "",
                }
    # Step 3: nothing matched. We return a generic alpine Unsplash photo
    # along with a notice telling the user it's just a stock image, not
    # the actual route. We never want to mislead users into thinking a
    # random photo shows the trail they're about to hike.
    return _fallback_image_info()


@st.cache_data(ttl=86400, show_spinner=False)
def _route_image_url_cached(
    trail_name: str,
    canton: str,
    region: str,
) -> str:
    return str(_route_image_info_cached(trail_name, canton, region)["url"])


def route_image_info(trail) -> dict[str, str | bool]:
    """Return image URL and fallback notice metadata for a route card."""
    return _route_image_info_cached(
        str(_row_value(trail, "name", "") or ""),
        str(_row_value(trail, "canton", "Switzerland") or "Switzerland"),
        str(_row_value(trail, "region", "Alps") or "Alps"),
    )


def route_image_url(trail) -> str:
    """Return a Wikimedia Commons image URL, or labelled Unsplash fallback."""
    return str(route_image_info(trail)["url"])


def trail_detail_url(trail) -> str:
    """Link target for opening Trail Detail with a concrete route selected."""
    return f"/Trail_Detail?trail_id={quote(str(_row_value(trail, 'id', '')))}"


def trail_id_from_query_params(query_params) -> int | None:
    """Read ``trail_id`` from Streamlit query params, accepting old/new shapes."""
    raw = None
    try:
        raw = query_params.get("trail_id")
    except AttributeError:
        return None
    # Older versions of Streamlit returned URL parameters as lists. Newer
    # versions return plain strings. We handle both so the page works no
    # matter which Streamlit version is installed.
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
