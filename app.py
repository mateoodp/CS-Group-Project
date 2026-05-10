"""Swiss Alpine Hiking Condition Forecaster — Streamlit entry point.

Owner: TM1 (Project Lead)
Supporting: TM2, TM3

This file is the landing screen and one-time bootstrap. Real work happens
on the four pages under ``pages/``:

    1. Find a hike (front door — quiz + date)
    2. Map         (visual overview)
    3. Compare     (side-by-side for one date)
    4. About       (ML pipeline + retrain)

Plus a hidden Trail Detail sub-page reachable by clicking any hike from
the four pages above. The horizontal nav at the top of every page comes
from :mod:`utils.topnav` — Streamlit's auto sidebar nav is hidden via CSS.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

from html import escape

import streamlit as st

from data import db_manager
from ml import trail_classifier
from utils.constants import APP_TITLE, DEFAULT_RISK_TOLERANCE
from utils.sidebar import render_shared_sidebar
from utils.theme import apply_app_theme
from utils.topnav import render_top_nav

# ---------------------------------------------------------------------------
# Page config — MUST be the first Streamlit command in the script.
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


LANDING_IMAGES: tuple[str, ...] = (
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1200&q=85",
    "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=1200&q=85",
    "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1200&q=85",
    "https://images.unsplash.com/photo-1486911278844-a81c5267e227?auto=format&fit=crop&w=1200&q=85",
    "https://images.unsplash.com/photo-1527004013197-933c4bb611b3?auto=format&fit=crop&w=1200&q=85",
    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=85",
)

PREFERRED_DESTINATIONS: tuple[str, ...] = (
    "Gornergrat Panorama",
    "Aletsch — Märjelensee",
    "Männlichen — Kleine Scheidegg",
    "Rigi Panorama",
    "Oeschinensee",
    "Saas-Fee — Hannig",
)

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

  .hero-card {
    border-radius: 32px;
    padding: .8rem;
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
  }

  .destination-img {
    height: 210px;
    border-radius: 22px;
    background-size: cover;
    background-position: center;
    margin-bottom: 1rem;
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
    min-height: 190px;
    border-radius: 26px;
    padding: 1.35rem;
    margin-bottom: .75rem;
  }

  .feature-icon {
    width: 46px;
    height: 46px;
    border-radius: 16px;
    display: grid;
    place-items: center;
    background: #eef5ea;
    color: var(--pine);
    font-size: 1.35rem;
    margin-bottom: 1.05rem;
  }

  .feature-card h3 {
    color: var(--ink);
    font-size: 1.12rem;
    margin: 0 0 .55rem;
  }

  .feature-card p {
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
    """Read a value from sqlite rows or dicts."""
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _landing_status_for_difficulty(difficulty: str) -> str:
    if difficulty in {"T4", "T5", "T6"}:
        return "Avoid"
    if difficulty == "T3":
        return "Borderline"
    return "Safe Today"


def _landing_duration_for_length(length_km: float) -> str:
    if length_km <= 5.5:
        return "Half day"
    if length_km <= 8:
        return "1 day"
    return "Full day"


def landing_card_from_trail_row(row, image_url: str) -> dict[str, str]:
    """Format one trail row for the discovery landing cards."""
    length_km = float(_row_value(row, "length_km", 0) or 0)
    difficulty = str(_row_value(row, "difficulty", "T2") or "T2")
    max_alt_m = int(_row_value(row, "max_alt_m", 0) or 0)
    canton = str(_row_value(row, "canton", "CH") or "CH")
    region = str(_row_value(row, "region", "Swiss Alps") or "Swiss Alps")
    title = str(_row_value(row, "name", "Swiss alpine trail") or "Swiss alpine trail")
    status = _landing_status_for_difficulty(difficulty)

    return {
        "title": title,
        "distance": f"{length_km:.1f} km",
        "duration": _landing_duration_for_length(length_km),
        "status": status,
        "status_class": status.lower()
        .replace(" ", "-")
        .replace("today", "")
        .strip("-"),
        "meta": f"{canton} · {region} · {difficulty} · {max_alt_m} m",
        "image_url": image_url,
    }


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


def _render_stats_pills(n_trails: int, n_weather: int, has_model: bool) -> None:
    model_label = "Ready" if has_model else "Retrain"
    model_hint = "model status"
    st.markdown(
        f"""
        <div class="stat-row">
          <div class="stat-pill"><strong>{n_trails}</strong><span>trail catalogue</span></div>
          <div class="stat-pill"><strong>{n_weather:,}</strong><span>weather rows cached</span></div>
          <div class="stat-pill"><strong>{model_label}</strong><span>{model_hint}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_hero_card(card: dict[str, str]) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
          <div class="hero-image" style="background-image:url('{escape(card["image_url"])}');">
            <div class="hero-card-content">
              <div>
                <div class="status {escape(card["status_class"])}">{escape(card["status"])}</div>
                <h2>{escape(card["title"])}</h2>
                <div class="card-meta">
                  <span class="glass-pill">{escape(card["duration"])}</span>
                  <span class="glass-pill">{escape(card["distance"])}</span>
                  <span class="glass-pill">{escape(card["meta"])}</span>
                </div>
              </div>
              <div class="arrow-button">→</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_destination_card(card: dict[str, str]) -> None:
    st.markdown(
        f"""
        <div class="destination-card">
          <div class="destination-img" style="background-image:url('{escape(card["image_url"])}');"></div>
          <div class="destination-body">
            <h3>{escape(card["title"])}</h3>
            <div class="destination-meta">{escape(card["duration"])} · {escape(card["distance"])} · {escape(card["meta"])}</div>
            <span class="status {escape(card["status_class"])}">{escape(card["status"])}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def initialise_session_state() -> None:
    """Seed shared keys used across all pages."""
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
    """One-time setup: create SQLite tables and seed the trails table."""
    db_manager.setup_db()


def render_landing() -> None:
    n_trails = len(db_manager.get_all_trails())
    trails = db_manager.get_all_trails()
    n_weather = len(db_manager.get_all_weather())
    has_model = trail_classifier.model_exists()
    selected_trails = _select_landing_trails(trails)
    landing_cards = [
        landing_card_from_trail_row(trail, LANDING_IMAGES[i % len(LANDING_IMAGES)])
        for i, trail in enumerate(selected_trails)
    ]
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
            LANDING_IMAGES[0],
        )
    )

    apply_app_theme()
    st.markdown(LANDING_CSS, unsafe_allow_html=True)

    st.markdown('<section class="landing-section">', unsafe_allow_html=True)
    hero_left, hero_right = st.columns([1.08, 0.92], gap="large")
    with hero_left:
        st.markdown(
            """
            <div class="hero-copy">
              <div class="eyebrow">Swiss Alpine Hiking Condition Forecaster</div>
              <h1 class="hero-title">Discover Swiss Alpine Trails</h1>
              <p class="hero-subtitle">AI-powered hiking condition forecasts for safer alpine decisions</p>
              <div class="chip-row">
                <span class="chip active">All</span>
                <span class="chip">Hiking</span>
                <span class="chip">Canyoning</span>
                <span class="chip">Mountaineering</span>
                <span class="chip">Safe Today</span>
                <span class="chip">Borderline</span>
                <span class="chip">Avoid</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_stats_pills(n_trails, n_weather, has_model)
        cta_cols = st.columns([0.36, 0.34, 0.3], gap="small")
        with cta_cols[0]:
            st.page_link(
                "pages/1_Find.py",
                label="Find a hike",
                icon="🧭",
                width="stretch",
            )
        with cta_cols[1]:
            st.page_link(
                "pages/2_Map.py",
                label="Explore map",
                icon="🗺️",
                width="stretch",
            )
    with hero_right:
        _render_hero_card(featured)

    st.markdown("</section>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="section-heading">
          <div>
            <div class="eyebrow">Recommended routes</div>
            <h2>Top destinations</h2>
          </div>
          <p>Large alpine views, practical trail stats, and condition cues at a glance.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    destination_cols = st.columns(3, gap="large")
    for i, card in enumerate(landing_cards[:6]):
        with destination_cols[i % 3]:
            _render_destination_card(card)
            st.page_link(
                "pages/1_Find.py",
                label="Plan this route",
                icon="🥾",
                width="stretch",
            )

    st.markdown(
        """
        <div class="section-heading">
          <div>
            <div class="eyebrow">Forecast toolkit</div>
            <h2>Choose how you want to explore</h2>
          </div>
          <p>All existing app workflows stay available from the discovery page.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    feature_cards = [
        (
            "🧭",
            "Find a hike",
            "Answer a few trail preferences and get ranked recommendations for your date.",
            "pages/1_Find.py",
        ),
        (
            "🗺️",
            "Map",
            "Browse Swiss routes spatially with condition-aware color cues.",
            "pages/2_Map.py",
        ),
        (
            "🔀",
            "Compare",
            "Compare two to four routes side by side before committing.",
            "pages/3_Compare.py",
        ),
        (
            "ℹ️",
            "About",
            "Review model status, training tools, metrics, and project context.",
            "pages/4_About.py",
        ),
    ]
    feature_cols = st.columns(4, gap="large")
    for col, (icon, title, body, path) in zip(feature_cols, feature_cards):
        with col:
            st.markdown(
                f"""
                <div class="feature-card">
                  <div class="feature-icon">{escape(icon)}</div>
                  <h3>{escape(title)}</h3>
                  <p>{escape(body)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.page_link(path, label=f"Open {title}", width="stretch")


def main() -> None:
    bootstrap()
    initialise_session_state()
    render_top_nav()
    render_shared_sidebar()
    render_landing()


if __name__ == "__main__":
    main()
