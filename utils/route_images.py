"""Route-specific image helpers for discovery cards."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote

import streamlit as st

from utils.trail_detail import fetch_trail_images


COMMONS_THUMB_ENDPOINT: str = "https://commons.wikimedia.org/w/thumb.php"
UNSPLASH_FALLBACK_IMAGE: str = (
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4"
    "?auto=format&fit=crop&w=900&q=85"
)
FALLBACK_NOTICE: str = "Illustrative Unsplash image - not the actual route"

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


def _commons_thumb_url(filename: str, width: int = 900) -> str:
    normalized = filename.replace(" ", "_")
    return f"{COMMONS_THUMB_ENDPOINT}?f={quote(normalized, safe='')}&w={width}"


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


@st.cache_data(ttl=86400, show_spinner=False)
def _route_image_info_cached(
    trail_name: str,
    canton: str,
    region: str,
) -> dict[str, str | bool]:
    known_url = _known_route_image_url(trail_name)
    if known_url:
        return {"url": known_url, "is_fallback": False, "notice": ""}

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
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
