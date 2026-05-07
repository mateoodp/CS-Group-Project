"""Shared visual system for the Streamlit hiking app.

The functions here keep page-level styling consistent without touching
business logic. Pages can opt into the same alpine discovery look by calling
``apply_app_theme()`` and rendering small HTML helpers with
``unsafe_allow_html=True``.
"""

from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st


ALPINE_BACKGROUND_IMAGE: str = (
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4"
    "?auto=format&fit=crop&w=1800&q=85"
)

ALPINE_CARD_IMAGES: tuple[str, ...] = (
    "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1486911278844-a81c5267e227?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1527004013197-933c4bb611b3?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=85",
)


APP_THEME_CSS: str = (
    """
<style>
  :root {
    --bg: #F6F7F8;
    --ink: #14201c;
    --muted: #6b756f;
    --line: #e4e8e4;
    --pine: #173f35;
    --moss: #8ac35f;
    --sky: #dfeef2;
    --amber: #c9851e;
    --danger: #b7473f;
    --card: #ffffff;
  }

  html, body {
    background: var(--bg);
  }

  html, body, .stApp, [data-testid="stAppViewContainer"] {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
      "Segoe UI", sans-serif;
    color: var(--ink);
  }

  [data-testid="stAppViewContainer"] {
    background:
      linear-gradient(180deg, rgba(246,247,248,.76), rgba(246,247,248,.94)),
      url("__ALPINE_BACKGROUND_IMAGE__");
    background-attachment: fixed;
    background-position: center top;
    background-size: cover;
  }

  [data-testid="stAppViewContainer"]::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background: rgba(246, 247, 248, .18);
    backdrop-filter: saturate(1.05);
  }

  .block-container {
    max-width: 1280px;
    padding-left: 2.4rem;
    padding-right: 2.4rem;
    position: relative;
    z-index: 1;
  }

  .page-hero {
    background:
      linear-gradient(135deg, rgba(255,255,255,.92), rgba(255,255,255,.78)),
      linear-gradient(135deg, #eef5ea, #dfeef2);
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 30px;
    padding: 1.6rem 1.8rem;
    margin: .4rem 0 1.4rem;
    box-shadow: 0 22px 55px rgba(21, 39, 32, .08);
  }

  .page-hero.compact {
    padding: 1.25rem 1.45rem;
  }

  .page-eyebrow {
    color: var(--pine);
    font-size: .76rem;
    font-weight: 850;
    letter-spacing: .08em;
    text-transform: uppercase;
    margin-bottom: .55rem;
  }

  .page-hero h1 {
    color: var(--ink);
    font-size: clamp(2rem, 3.4vw, 3.7rem);
    line-height: 1;
    letter-spacing: 0;
    margin: 0 0 .65rem;
  }

  .page-hero p {
    color: var(--muted);
    font-size: 1.04rem;
    line-height: 1.65;
    max-width: 760px;
    margin: 0;
  }

  .chip-row, .stat-row {
    display: flex;
    flex-wrap: wrap;
    gap: .65rem;
    margin: 1rem 0 .2rem;
  }

  .chip, .status-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: .48rem .78rem;
    font-size: .82rem;
    font-weight: 800;
  }

  .chip {
    border: 1px solid var(--line);
    background: #fff;
    color: #31443c;
  }

  .stat-pill {
    background: rgba(255, 255, 255, .9);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: .82rem 1rem;
    min-width: 145px;
    box-shadow: 0 14px 32px rgba(21, 39, 32, .06);
  }

  .stat-pill strong {
    display: block;
    color: var(--ink);
    font-size: 1.15rem;
    line-height: 1.1;
  }

  .stat-pill span {
    color: var(--muted);
    font-size: .76rem;
    font-weight: 800;
    text-transform: uppercase;
  }

  .section-heading {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 1rem;
    margin: 1.8rem 0 .9rem;
  }

  .section-heading h2 {
    color: var(--ink);
    font-size: 1.7rem;
    line-height: 1.08;
    letter-spacing: 0;
    margin: 0;
  }

  .section-heading p {
    color: var(--muted);
    margin: .35rem 0 0;
    max-width: 580px;
  }

  .soft-panel {
    background: var(--card);
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 26px;
    padding: 1.2rem;
    box-shadow: 0 18px 42px rgba(21, 39, 32, .08);
    margin-bottom: 1rem;
  }

  .soft-panel.tight {
    padding: .9rem;
  }

  .status-pill.safe { background: #e9f6df; color: #346b22; }
  .status-pill.borderline { background: #fff1d8; color: var(--amber); }
  .status-pill.avoid { background: #fbe3df; color: var(--danger); }
  .status-pill.unknown { background: #eef0f1; color: #6b756f; }

  [data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 20px;
    padding: .95rem 1rem;
    box-shadow: 0 14px 32px rgba(21, 39, 32, .06);
  }

  div[data-testid="stForm"] {
    background: #ffffff;
    border: 1px solid rgba(20, 32, 28, .07);
    border-radius: 28px;
    padding: 1rem 1.1rem 1.2rem;
    box-shadow: 0 18px 42px rgba(21, 39, 32, .08);
  }

  [data-testid="stWidgetLabel"] {
    color: var(--ink);
    font-size: .82rem;
    font-weight: 850;
    letter-spacing: 0;
    margin-bottom: .35rem;
  }

  [data-testid="stWidgetLabel"] p {
    color: var(--ink);
    font-size: .82rem;
    font-weight: 850;
    letter-spacing: 0;
  }

  div[data-baseweb="select"] > div,
  div[data-baseweb="input"] > div,
  div[data-testid="stDateInput"] input,
  div[data-testid="stTextInput"] input,
  div[data-testid="stTextArea"] textarea {
    border-radius: 16px;
    border-color: rgba(20, 32, 28, .12);
    background-color: rgba(255, 255, 255, .92);
    color: var(--ink);
    box-shadow: 0 10px 24px rgba(21, 39, 32, .04);
  }

  div[data-baseweb="select"] span,
  div[data-baseweb="input"] input,
  div[data-testid="stDateInput"] input,
  div[data-testid="stTextArea"] textarea {
    color: var(--ink);
    font-size: .94rem;
  }

  div[data-baseweb="tag"] {
    border-radius: 999px;
    background: #eef5ea;
    color: var(--pine);
    font-weight: 800;
  }

  div[data-testid="stSlider"] [data-testid="stThumbValue"] {
    color: var(--pine);
    font-weight: 850;
  }

  div[data-testid="stRadio"] label {
    color: #31443c;
    font-weight: 750;
  }

  div[data-testid="stExpander"] {
    border-radius: 20px;
    border-color: rgba(20, 32, 28, .09);
    background: #ffffff;
  }

  .stTabs [data-baseweb="tab-list"] {
    gap: .35rem;
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: .35rem;
  }

  .stTabs [data-baseweb="tab"] {
    border-radius: 999px;
    color: #53635c;
    font-weight: 800;
    padding-left: 1rem;
    padding-right: 1rem;
  }

  .stTabs [aria-selected="true"] {
    background: var(--pine);
    color: #ffffff;
  }

  div[data-testid="stPageLink"] a,
  div.stButton > button {
    border-radius: 999px;
    border: 1px solid rgba(23, 63, 53, .14);
    font-weight: 800;
    box-shadow: 0 10px 22px rgba(21, 39, 32, .06);
  }

  div.stButton > button[kind="primary"] {
    background: var(--pine);
    border-color: var(--pine);
  }

  iframe {
    border-radius: 24px;
  }

  @media (max-width: 900px) {
    .block-container {
      padding-left: 1.15rem;
      padding-right: 1.15rem;
    }

    .page-hero {
      border-radius: 24px;
      padding: 1.25rem;
    }

    .section-heading {
      display: block;
    }
  }
</style>
""".replace(
        "__ALPINE_BACKGROUND_IMAGE__", ALPINE_BACKGROUND_IMAGE
    )
)


def apply_app_theme() -> None:
    """Inject the shared alpine discovery theme."""
    st.markdown(APP_THEME_CSS, unsafe_allow_html=True)


def status_class(label: str | None) -> str:
    """Return a CSS class for a verdict-like label."""
    normalized = str(label or "").lower().replace("today", "").strip()
    if "safe" in normalized:
        return "safe"
    if "borderline" in normalized:
        return "borderline"
    if "avoid" in normalized:
        return "avoid"
    return "unknown"


def image_for_index(index: int) -> str:
    """Return a stable alpine card image for a zero-based card index."""
    return ALPINE_CARD_IMAGES[index % len(ALPINE_CARD_IMAGES)]


def page_hero(title: str, subtitle: str, eyebrow: str = "Swiss Hike Forecaster") -> str:
    """HTML for a consistent page hero."""
    return (
        '<div class="page-hero">'
        f'<div class="page-eyebrow">{escape(eyebrow)}</div>'
        f"<h1>{escape(title)}</h1>"
        f"<p>{escape(subtitle)}</p>"
        "</div>"
    )


def section_heading(title: str, subtitle: str, eyebrow: str | None = None) -> str:
    """HTML for section headings used below page heroes."""
    eyebrow_html = (
        f'<div class="page-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    )
    return (
        '<div class="section-heading">'
        "<div>"
        f"{eyebrow_html}<h2>{escape(title)}</h2>"
        f"<p>{escape(subtitle)}</p>"
        "</div>"
        "</div>"
    )


def stat_pills_html(items: Iterable[tuple[str, str]]) -> str:
    """Render small statistic pills from ``(label, value)`` pairs."""
    pills = "".join(
        f'<div class="stat-pill"><strong>{escape(str(value))}</strong>'
        f"<span>{escape(str(label))}</span></div>"
        for label, value in items
    )
    return f'<div class="stat-row">{pills}</div>'


def status_pill(label: str) -> str:
    """Render a compact verdict/status pill."""
    return (
        f'<span class="status-pill {status_class(label)}">'
        f"{escape(str(label))}</span>"
    )
