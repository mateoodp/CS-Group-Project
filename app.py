"""Swiss Alpine Hiking Condition Forecaster. Streamlit entry point.

Owner: TM1 (Project Lead). Support: TM2, TM3.

This is the file Streamlit runs first. It does two things:
    1. One-time bootstrap (set up the database, seed initial state).
    2. Render the landing page that the user sees first.

The real features of the app live in four separate pages inside the
``pages/`` folder:

    1. Find a hike: the main entry point (quiz plus date picker).
    2. Map:         visual overview of Switzerland.
    3. Compare:     two to four routes side by side on one date.
    4. About:       project info plus ML retrain controls.

There is also a hidden Trail Detail page, reachable only by clicking a
trail card from one of the four pages above. The horizontal top nav
comes from utils.topnav, and we hide Streamlit's automatic sidebar
navigation with CSS.

To run the app locally:

    streamlit run app.py
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

from html import escape

import streamlit as st

from data import db_manager
from ml import trail_classifier
from utils.constants import APP_TITLE, DEFAULT_RISK_TOLERANCE, VERDICT_EMOJI
from utils.i18n import t, verdict_label
from utils.route_images import route_image_info, trail_detail_url
from utils.sidebar import render_shared_sidebar
from utils.theme import apply_app_theme
from utils.topnav import render_top_nav
from utils.trail_detail import difficulty_dots_html, naismith_time

# ---------------------------------------------------------------------------
# Page configuration. This call MUST come before any other Streamlit
# command on the page. It sets the browser tab title, the favicon, the
# page width, and whether the sidebar starts open.
# ---------------------------------------------------------------------------
# Streamlit pattern - https://docs.streamlit.io
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="mountain",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# A hand-picked list of iconic Swiss hikes that we'd like to feature on
# the landing page. The landing page looks for trails with these names
# first. If it can't find them in the database, it just falls back to
# whatever trails are seeded.
PREFERRED_DESTINATIONS: tuple[str, ...] = (
    "Gornergrat Panorama",
    "Aletsch 闂?M闂佺儵鏅濋悘姊沞lensee",
    "M闂佺儵鏅濋悘鎭榣ichen 闂?Kleine Scheidegg",
    "Rigi Panorama",
    "Oeschinensee",
    "Saas-Fee 闂?Hannig",
)

# The full block of CSS for just the landing page. It defines our alpine
# color palette (pine green, moss, amber, etc.), the layout for the hero
# section, the destination cards, the feature tiles, and a few mobile
# breakpoints. We keep it as one big string and inject it once near the
# top of the page.
LANDING_CSS: str = """
<style>
  :root {
    --bg: #F6F7F8;
    --ink: #14201c;
    --muted: #6b756f;
    --line: #e4e8e4;
    --pine: #173f35;
    --moss: #8ac35f;
    --amber: #c9851e;
    --danger: #b7473f;
    --card: #ffffff;
  }

  .block-container {
    max-width: 1280px;
    padding-left: 2.4rem;
    padding-right: 2.4rem;
    position: relative;
    z-index: 1;
  }

  .landing-section {
    margin-top: 1rem;
    margin-bottom: 2.4rem;
  }

  .eyebrow {
    color: var(--pine);
    font-size: .78rem;
    font-weight: 800;
    letter-spacing: .08em;
    text-transform: uppercase;
    margin-bottom: .9rem;
  }

  .hero-title {
    color: var(--ink);
    font-size: clamp(3.1rem, 5vw, 5.8rem);
    font-weight: 850;
    line-height: .96;
    margin: 0 0 1.1rem;
    letter-spacing: 0;
  }

  .hero-subtitle {
    color: var(--muted);
    font-size: 1.2rem;
    line-height: 1.75;
    max-width: 630px;
    margin: 0 0 1.5rem;
  }

  .chip-row, .stat-row {
    display: flex;
    flex-wrap: wrap;
    gap: .65rem;
    margin: 1.2rem 0;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--line);
    background: #fff;
    color: #31443c;
    border-radius: 999px;
    padding: .62rem 1rem;
    font-size: .92rem;
    font-weight: 700;
    box-shadow: 0 8px 24px rgba(21, 39, 32, .04);
  }

  .chip.active {
    color: #fff;
    background: var(--pine);
    border-color: var(--pine);
  }

  .stat-pill {
    background: rgba(255, 255, 255, .82);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: .9rem 1rem;
    min-width: 150px;
    box-shadow: 0 16px 34px rgba(21, 39, 32, .06);
  }

  .stat-pill strong {
    display: block;
    color: var(--ink);
    font-size: 1.18rem;
    line-height: 1.1;
  }

  .stat-pill span {
    color: var(--muted);
    font-size: .78rem;
    font-weight: 700;
    text-transform: uppercase;
  }

  .hero-copy {
    padding: 2rem 0 1rem;
  }

  .hero-card, .destination-card, .feature-card {
    background: var(--card);
    border: 1px solid rgba(20, 32, 28, .06);
    box-shadow: 0 24px 60px rgba(21, 39, 32, .12);
  }

  .route-card-link {
    display: block;
    color: inherit;
    cursor: pointer;
    text-decoration: none;
    position: relative;
  }

  .route-card-link:hover .hero-card,
  .route-card-link:hover .destination-card {
    transform: translateY(-3px);
    box-shadow: 0 30px 70px rgba(21, 39, 32, .16);
  }

  .hike-card-link {
    display: block;
    color: #14201c;
    cursor: pointer;
    text-decoration: none;
    margin-bottom: .65rem;
  }

  .hike-card-link:hover .hike-card {
    transform: translateY(-3px);
    box-shadow: 0 24px 52px rgba(21, 39, 32, .12);
  }

  .hike-card {
    background: #ffffff;
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 28px;
    padding: .72rem;
    margin-bottom: .65rem;
    position: relative;
    box-shadow: 0 18px 42px rgba(21, 39, 32, .08);
    transition: transform .18s ease, box-shadow .18s ease;
  }

  .hike-card-hitbox {
    position: absolute;
    inset: 0;
    z-index: 5;
    border-radius: 28px;
    text-decoration: none;
  }

  .hike-card-image {
    height: 210px;
    border-radius: 22px;
    background-size: cover;
    background-position: center;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
  }

  .hike-card-image::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,.04), rgba(0,0,0,.38));
  }

  .hike-card-image .verdict-pill {
    position: absolute;
    left: .85rem;
    bottom: .85rem;
    z-index: 1;
    margin-left: 0;
  }

  .hike-card-body {
    padding: 0 .35rem .4rem;
  }

  .hike-card-title {
    font-size: 1.18rem;
    font-weight: 850;
    color: #14201c;
    line-height: 1.3;
    margin-bottom: 10px;
  }

  .hike-card-meta {
    font-size: 0.85rem;
    color: #6b7177;
    margin-bottom: .75rem;
    min-height: 2.4rem;
  }

  .hike-card-meta,
  .hike-card-meta * {
    color: #6b7177;
  }

  .hike-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    border-top: 1px solid #edf0ed;
    padding-top: 12px;
  }

  .hike-stat-value {
    font-size: .98rem;
    font-weight: 850;
    color: #14201c;
  }

  .hike-stat-label {
    font-size: 0.72rem;
    color: #6b756f;
    margin-top: 2px;
    font-weight: 800;
    text-transform: uppercase;
  }

  .verdict-pill {
    display: inline-block;
    padding: 5px 11px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 850;
    color: white;
    vertical-align: middle;
    margin-left: 8px;
  }

  .verdict-pill.safe { background:#5f9f45; }
  .verdict-pill.borderline { background:#c9851e; }
  .verdict-pill.avoid { background:#b7473f; }
  .verdict-pill.unknown { background:#7c8580; }

  .hero-card {
    border-radius: 32px;
    padding: .8rem;
    position: relative;
    transition: transform .18s ease, box-shadow .18s ease;
  }

  .hero-image {
    min-height: 520px;
    border-radius: 26px;
    background-size: cover;
    background-position: center;
    position: relative;
    overflow: hidden;
  }

  .hero-image::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,.04) 20%, rgba(0,0,0,.58) 100%);
  }

  .hero-card-content {
    position: absolute;
    left: 1.4rem;
    right: 1.4rem;
    bottom: 1.4rem;
    z-index: 1;
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 1rem;
    color: #fff;
  }

  .hero-card-content h2 {
    font-size: 2rem;
    line-height: 1.05;
    margin: 0 0 .7rem;
    letter-spacing: 0;
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: .55rem;
    color: rgba(255, 255, 255, .9);
    font-weight: 750;
  }

  .glass-pill {
    border-radius: 999px;
    background: rgba(255, 255, 255, .18);
    border: 1px solid rgba(255, 255, 255, .28);
    padding: .48rem .75rem;
    backdrop-filter: blur(10px);
  }

  .image-notice {
    position: absolute;
    right: .85rem;
    top: .85rem;
    z-index: 2;
    border-radius: 999px;
    background: rgba(20, 32, 28, .74);
    color: #fff;
    padding: .42rem .68rem;
    font-size: .72rem;
    font-weight: 850;
    backdrop-filter: blur(10px);
  }

  .arrow-button {
    width: 52px;
    height: 52px;
    border-radius: 999px;
    background: #fff;
    color: var(--pine);
    display: grid;
    place-items: center;
    font-size: 1.35rem;
    font-weight: 900;
    flex: 0 0 auto;
  }

  .section-heading {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 1rem;
    margin: 2.6rem 0 1rem;
  }

  .section-heading h2 {
    color: var(--ink);
    font-size: 2rem;
    margin: 0;
    letter-spacing: 0;
  }

  .section-heading p {
    color: var(--muted);
    margin: 0;
  }

  .destination-card {
    border-radius: 28px;
    padding: .72rem;
    margin-bottom: .65rem;
    position: relative;
    transition: transform .18s ease, box-shadow .18s ease;
  }

  .destination-img {
    height: 210px;
    border-radius: 22px;
    background-size: cover;
    background-position: center;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
  }

  .destination-card h3 {
    color: var(--ink);
    font-size: 1.15rem;
    margin: 0 0 .35rem;
    line-height: 1.2;
  }

  .destination-body {
    padding: 0 .35rem .35rem;
  }

  .destination-meta {
    color: var(--muted);
    font-size: .9rem;
    margin-bottom: .7rem;
  }

  .status {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: .38rem .7rem;
    font-size: .78rem;
    font-weight: 850;
  }

  .status.safe { background: #e9f6df; color: #346b22; }
  .status.borderline { background: #fff1d8; color: var(--amber); }
  .status.avoid { background: #fbe3df; color: var(--danger); }

  .feature-card {
    display: block;
    min-height: 190px;
    border-radius: 26px;
    padding: 1.35rem;
    margin-bottom: .75rem;
    color: inherit;
    position: relative;
    text-decoration: none;
    transition: transform .18s ease, box-shadow .18s ease;
  }

  .feature-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 30px 70px rgba(21, 39, 32, .16);
  }

  .feature-header {
    display: flex;
    align-items: center;
    gap: .75rem;
    margin-bottom: .75rem;
  }

  .feature-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    background: #eef5ea;
    color: var(--pine);
    font-size: 1.25rem;
    flex-shrink: 0;
  }

  .feature-card h3,
  .feature-title {
    display: block;
    color: var(--ink);
    font-size: 1.12rem;
    font-weight: 850;
    margin: 0;
  }

  .feature-card p,
  .feature-body {
    display: block;
    color: var(--muted);
    line-height: 1.55;
    margin: 0;
    font-size: .94rem;
  }

  div[data-testid="stPageLink"] a {
    border-radius: 999px;
    border: 1px solid rgba(23, 63, 53, .12);
    background: #ffffff;
    color: var(--pine);
    font-weight: 800;
    box-shadow: 0 10px 22px rgba(21, 39, 32, .06);
  }

  div[data-testid="stPageLink"] a:hover {
    border-color: rgba(23, 63, 53, .28);
    background: #f8fbf6;
  }

  @media (max-width: 900px) {
    .block-container {
      padding-left: 1.2rem;
      padding-right: 1.2rem;
    }

    .hero-title {
      font-size: 3rem;
    }

    .hero-image {
      min-height: 420px;
    }

    .section-heading {
      display: block;
    }
  }
</style>
"""


def _row_value(row, key: str, default=None):
    """Read a value from a sqlite row or a dict, with a fallback.

    Throughout the code we sometimes get sqlite Row objects (which use
    bracket access) and sometimes plain dicts. This helper smooths over
    the difference so callers don't have to think about it.
    """
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


# Turn a SAC difficulty grade into a simple status label for the landing
# cards. T4 and above are alpine routes (we say "Avoid"), T3 is demanding
# ("Borderline"), and anything T2 or below is regular hiking ("Safe Today").
def _landing_status_for_difficulty(difficulty: str) -> str:
    if difficulty in {"T4", "T5", "T6"}:
        return "Avoid"
    if difficulty == "T3":
        return "Borderline"
    return "Safe Today"


def _landing_verdict_for_difficulty(difficulty: str) -> str:
    if difficulty in {"T4", "T5", "T6"}:
        return "AVOID"
    if difficulty == "T3":
        return "BORDERLINE"
    return "SAFE"


# Turn a trail length in kilometers into a friendly duration label like
# "Half day" or "Full day" for the landing card. These are rough buckets
# meant to give the user a quick sense of commitment, not a precise time.
def _landing_duration_for_length(length_km: float) -> str:
    if length_km <= 5.5:
        return "Half day"
    if length_km <= 8:
        return "1 day"
    return "Full day"


def landing_card_from_trail_row(
    row, image_url: str, image_notice: str = ""
) -> dict[str, str]:
    """Turn a trail database row into a dictionary the landing card uses."""
    # We read each field defensively (with _row_value) because rows may
    # come in as either sqlite Row objects or plain dicts. Then we
    # compute the formatted display strings, the verdict pill class
    # and color, and the URL to the trail detail page.
    trail_id = str(_row_value(row, "id", "") or "")
    length_km = float(_row_value(row, "length_km", 0) or 0)
    difficulty = str(_row_value(row, "difficulty", "T2") or "T2")
    min_alt_m = int(_row_value(row, "min_alt_m", 0) or 0)
    max_alt_m = int(_row_value(row, "max_alt_m", 0) or 0)
    canton = str(_row_value(row, "canton", "CH") or "CH")
    region = str(_row_value(row, "region", "Swiss Alps") or "Swiss Alps")
    title = str(_row_value(row, "name", "Swiss alpine trail") or "Swiss alpine trail")
    status = _landing_status_for_difficulty(difficulty)
    verdict = _landing_verdict_for_difficulty(difficulty)
    ascent = max(0, max_alt_m - min_alt_m)

    return {
        "title": title,
        "distance": f"{length_km:.1f} km",
        "duration": _landing_duration_for_length(length_km),
        "status": status,
        "status_class": status.lower()
        .replace(" ", "-")
        .replace("today", "")
        .strip("-"),
        "meta": (
            f"{canton} {chr(183)} {region} {chr(183)} "
            f"{difficulty} {chr(183)} {max_alt_m} m"
        ),
        "image_url": image_url,
        "image_notice": image_notice,
        "trail_id": trail_id,
        "detail_url": trail_detail_url(row) if trail_id else "#",
        "difficulty": difficulty,
        "difficulty_html": difficulty_dots_html(difficulty),
        "ascent": f"{ascent} m",
        "time_est": naismith_time(length_km, ascent),
        "length_value": f"{length_km:.1f} km",
        "verdict": verdict,
        "verdict_class": verdict.lower(),
        "verdict_emoji": VERDICT_EMOJI.get(verdict, ""),
    }


# Pick the six trails that go on the landing carousel. We first look
# for trails whose names match the curated PREFERRED_DESTINATIONS list,
# so iconic Swiss hikes always show up first. After that, if we still
# don't have six, we fill in any remaining slots with other trails
# from the database.
def _select_landing_trails(trails: list) -> list:
    selected = []
    used_ids = set()

    for preferred in PREFERRED_DESTINATIONS:
        match = next(
            (
                trail
                for trail in trails
                if preferred.lower() in str(trail["name"]).lower()
            ),
            None,
        )
        if match and match["id"] not in used_ids:
            selected.append(match)
            used_ids.add(match["id"])

    for trail in trails:
        if len(selected) >= 6:
            break
        if trail["id"] not in used_ids:
            selected.append(trail)
            used_ids.add(trail["id"])

    return selected


# Render the three small "stat pills" that sit under the hero copy
# (how many trails are in the catalogue, how many weather rows are
# cached, whether the model is trained yet). We build them as plain
# HTML so we have full control over the look.
def _render_stats_pills(n_trails: int, n_weather: int, has_model: bool) -> None:
    model_label = t("Ready") if has_model else t("Retrain")
    model_hint = t("model status")
    st.markdown(
        f"""
        <div class="stat-row">
          <div class="stat-pill"><strong>{n_trails}</strong><span>{t("trail catalogue")}</span></div>
          <div class="stat-pill"><strong>{n_weather:,}</strong><span>{t("weather rows cached")}</span></div>
          <div class="stat-pill"><strong>{model_label}</strong><span>{model_hint}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Render a single discovery card. Each card has an image, a verdict
# pill on top, the trail name and meta info, and a three-stat row at
# the bottom. We have to enable unsafe_allow_html because of the
# custom layout, so we run every text value through html.escape first.
# That way no user-supplied text can break out of its container or
# inject scripts.
def _render_home_hike_card(card: dict[str, str]) -> None:
    detail_url = escape(card["detail_url"])
    title = escape(card["title"])
    notice_html = (
        f'<span class="image-notice">{escape(card["image_notice"])}</span>'
        if card.get("image_notice")
        else ""
    )
    pill = (
        f'<span class="verdict-pill {escape(card["verdict_class"])}">'
        f'{escape(card["verdict_emoji"])} {escape(verdict_label(card["verdict"]))}</span>'
    )
    difficulty_html = str(
        card.get("difficulty_html") or difficulty_dots_html(str(card["difficulty"]))
    )
    html = (
        '<div class="hike-card-link">'
        '<div class="hike-card">'
        f'<a class="hike-card-hitbox" href="{detail_url}" aria-label="{title}"></a>'
        f'<div class="hike-card-image" style="background-image:url(\'{escape(card["image_url"])}\');">'
        f"{notice_html}{pill}"
        "</div>"
        '<div class="hike-card-body">'
        f'<div class="hike-card-title">{title}</div>'
        '<div class="hike-card-meta">'
        f"{difficulty_html}"
        '<div style="margin-top:.45rem;">'
        f'{escape(card["meta"])}'
        "</div>"
        "</div>"
        '<div class="hike-stats">'
        "<div>"
        f'<div class="hike-stat-value">{escape(card["time_est"])}</div>'
        f'<div class="hike-stat-label">{escape(t("Time"))}</div>'
        "</div>"
        "<div>"
        f'<div class="hike-stat-value">{escape(card["ascent"])}</div>'
        f'<div class="hike-stat-label">{escape(t("Ascent"))}</div>'
        "</div>"
        "<div>"
        f'<div class="hike-stat-value">{escape(card["length_value"])}</div>'
        f'<div class="hike-stat-label">{escape(t("Length"))}</div>'
        "</div>"
        "</div>"
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_hero_card(card: dict[str, str]) -> None:
    _render_home_hike_card(card)


def _render_destination_card(card: dict[str, str]) -> None:
    _render_home_hike_card(card)


# Render one of the four "Forecast toolkit" tiles at the bottom of
# the landing page. Each tile is a clickable card that links to one
# of the inner pages (Find, Map, Compare, About).
def _render_feature_card(icon_html: str, title: str, body: str, href: str) -> None:
    html = (
        f'<a class="feature-card feature-card-link" href="{escape(href)}">'
        f'<span class="feature-header">'
        f'<span class="feature-icon">{icon_html}</span>'
        f'<span class="feature-title">{escape(title)}</span>'
        f'</span>'
        f'<span class="feature-body">{escape(body)}</span>'
        "</a>"
    )
    st.markdown(html, unsafe_allow_html=True)


def initialise_session_state() -> None:
    """Create the shared session_state values that every page reads from."""
    # Streamlit pattern - https://docs.streamlit.io
    # setdefault only writes the value if the key isn't already there.
    # So if a page already set "selected_trail_id", we don't accidentally
    # overwrite it just because the landing page reruns.
    defaults: dict = {
        "selected_trail_id": None,
        "selected_date": None,
        "risk_tolerance": DEFAULT_RISK_TOLERANCE,
        "last_weather_refresh": None,
        "last_metrics": None,
        "compare_seed_trail_id": None,
        "compare_date": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def bootstrap() -> None:
    """One-time database setup.

    This creates the SQLite tables on first run, and loads the trail
    catalogue from trails_seed.json. It's safe to call on every app
    start because setup_db() checks before creating or seeding.
    """
    db_manager.setup_db()


# Build the full landing screen. Layout from top to bottom:
#  - Hero section with copy on the left and a featured trail card on the right.
#  - Section heading: "Top destinations".
#  - Three-column grid of up to six destination cards.
#  - Section heading: "Forecast toolkit".
#  - Four-column row of feature tiles (Find, Map, Compare, About).
def render_landing() -> None:
    n_trails = len(db_manager.get_all_trails())
    trails = db_manager.get_all_trails()
    n_weather = len(db_manager.get_all_weather())
    has_model = trail_classifier.model_exists()
    selected_trails = _select_landing_trails(trails)
    landing_cards = []
    for trail in selected_trails:
        image_info = route_image_info(trail)
        landing_cards.append(
            landing_card_from_trail_row(
                trail,
                str(image_info["url"]),
                str(image_info["notice"]),
            )
        )
    fallback_image_info = route_image_info(
        {"name": "Swiss Alps", "canton": "CH", "region": "Alps"}
    )
    featured = (
        landing_cards[0]
        if landing_cards
        else landing_card_from_trail_row(
            {
                "name": "Swiss Alpine Trail",
                "canton": "CH",
                "region": "Alps",
                "difficulty": "T2",
                "max_alt_m": 2400,
                "length_km": 6.0,
            },
            str(fallback_image_info["url"]),
            str(fallback_image_info["notice"]),
        )
    )

    apply_app_theme()
    st.markdown(LANDING_CSS, unsafe_allow_html=True)

    # Hero section. Two columns: text plus call-to-action buttons on
    # the left, featured trail card on the right. The left column is
    # slightly wider because the headline copy needs more room.
    st.markdown('<section class="landing-section">', unsafe_allow_html=True)
    # Streamlit pattern - https://docs.streamlit.io
    hero_left, hero_right = st.columns([1.08, 0.92], gap="large")
    with hero_left:
        st.markdown(
            f"""
            <div class="hero-copy">
              <div class="eyebrow">{escape(t("Swiss Alpine Hiking Condition Forecaster"))}</div>
              <h1 class="hero-title">{escape(t("Discover Swiss Alpine Trails"))}</h1>
              <p class="hero-subtitle">{escape(t("AI-powered hiking condition forecasts for safer alpine decisions"))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_stats_pills(n_trails, n_weather, has_model)
        cta_cols = st.columns([0.36, 0.34, 0.3], gap="small")
        with cta_cols[0]:
            st.page_link(
                "pages/1_Find.py",
                label=t("Find a hike"),
                icon="\U0001F9ED",
                width="stretch",
            )
        with cta_cols[1]:
            st.page_link(
                "pages/2_Map.py",
                label=t("Explore map"),
                icon="\U0001F5FA\uFE0F",
                width="stretch",
            )
    with hero_right:
        _render_hero_card(featured)

    st.markdown("</section>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="section-heading">
          <div>
            <div class="eyebrow">{escape(t("Recommended routes"))}</div>
            <h2>{escape(t("Top destinations"))}</h2>
          </div>
          <p>{escape(t("Large alpine views, practical trail stats, and condition cues at a glance."))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Three-column grid of destination cards. We show at most six.
    # The modulo (i % 3) makes the cards wrap to a new row every three.
    destination_cols = st.columns(3, gap="large")
    for i, card in enumerate(landing_cards[:6]):
        with destination_cols[i % 3]:
            _render_destination_card(card)

    st.markdown(
        f"""
        <div class="section-heading">
          <div>
            <div class="eyebrow">{escape(t("Forecast toolkit"))}</div>
            <h2>{escape(t("Choose how you want to explore"))}</h2>
          </div>
          <p>{escape(t("All existing app workflows stay available from the discovery page."))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    feature_cards = [
        (
            "🧭",
            t("Find a hike"),
            t("Answer a few trail preferences and get ranked recommendations for your date."),
            "/Find",
        ),
        (
            "🗺️",
            t("Map"),
            t("Browse Swiss routes spatially with condition-aware color cues."),
            "/Map",
        ),
        (
            "↔️",
            t("Compare"),
            t("Compare two to four routes side by side before committing."),
            "/Compare",
        ),
        (
            "ℹ️",
            t("About"),
            t("Review model status, training tools, metrics, and project context."),
            "/About",
        ),
    ]
    feature_cols = st.columns(4, gap="large")
    for col, (icon, title, body, path) in zip(feature_cols, feature_cards):
        with col:
            _render_feature_card(escape(icon), title, body, path)


# Entry point. Streamlit calls this when the user opens the app. We:
#   1. Make sure the database is set up.
#   2. Seed the shared session_state with defaults.
#   3. Draw the top navigation, the sidebar, and the landing page itself.
def main() -> None:
    bootstrap()
    initialise_session_state()
    render_top_nav()
    render_shared_sidebar()
    render_landing()


if __name__ == "__main__":
    main()
