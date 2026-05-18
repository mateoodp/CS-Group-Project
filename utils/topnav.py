"""Horizontal top navigation bar. Replaces Streamlit's vertical sidebar nav.

Every page should call ``render_top_nav()`` right after ``st.set_page_config``.
The function does three things:

    1. Injects CSS that hides Streamlit's automatic sidebar page list,
       because we want our own clean horizontal nav at the top instead.
    2. Renders four equally-spaced page links (Find, Map, Compare, About)
       as a single row using st.page_link.
    3. Draws a thin line under the nav so visually it reads as a header.

Trail Detail is on purpose NOT in this nav. The only way to reach it is
by clicking a trail card from Find, Map or Compare. We did this so the
nav stays tidy and the user always lands on a real trail (not an empty
Trail Detail page).
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

import streamlit as st

from utils.i18n import get_lang, render_language_toggle


# ---------------------------------------------------------------------------
# The CSS below hides Streamlit's default sidebar page list and trims the
# top-of-page padding so our horizontal nav reads as the real page header.
# ---------------------------------------------------------------------------

# Streamlit custom CSS pattern - https://docs.streamlit.io
# These selectors target the data-testid attributes that Streamlit puts
# on its internal elements. We use them to hide pieces of the default UI
# (the auto sidebar nav, the deploy/toolbar bar) and to restyle the
# page-link buttons so they look like rounded pills.
_NAV_CSS: str = """
<style>
  /* Hide Streamlit's auto-generated sidebar page navigation. */
  [data-testid="stSidebarNav"] { display: none; }

  /* Hide Streamlit's top toolbar (Deploy button + kebab menu) so our
     horizontal nav becomes the real page header. */
  header[data-testid="stHeader"] { display: none; }
  [data-testid="stToolbar"] { display: none; }

  .block-container {
    padding-top: 1.1rem;
  }

  .nav-brand {
    margin-top: 0;
  }

  div[data-testid="stPageLink"] a {
    min-height: 2.55rem;
    border-radius: 999px;
    color: #31443c;
    text-decoration: none;
    font-weight: 750;
    /* Keep each nav label on one line and centred so a longer word
       (e.g. the German labels) never wraps or spills out of its pill. */
    justify-content: center;
    white-space: nowrap;
    font-size: .93rem;
  }

  div[data-testid="stPageLink"] a p {
    white-space: nowrap;
  }

  div[data-testid="stPageLink"] a:hover {
    background: #ffffff;
    color: #173f35;
  }

  .nav-rule {
    margin: .55rem 0 1.4rem;
    border: 0;
    border-top: 1px solid #e4e8e4;
  }

  /* Right-align the language switch and slim it down so it reads as a
     compact control sitting in the top-right corner of the header. */
  div[data-testid="stSegmentedControl"] {
    display: flex;
    justify-content: flex-end;
  }

  div[data-testid="stSegmentedControl"] button {
    padding-top: .35rem;
    padding-bottom: .35rem;
  }
</style>
"""


# One source of truth for the four nav entries we show. Each tuple is
# (page file path, {lang: label}, icon). The labels are kept short — and
# the German ones deliberately concise — so every tab fits its narrow
# column without wrapping. If we ever rename a page file, we update it
# here in one place and the navigation stays consistent everywhere.
NAV_ENTRIES: list[tuple[str, dict[str, str], str]] = [
    ("pages/1_Find.py", {"en": "Find a hike", "de": "Finden"}, "🧭"),
    ("pages/2_Map.py", {"en": "Map", "de": "Karte"}, "🗺️"),
    ("pages/3_Compare.py", {"en": "Compare", "de": "Vergleich"}, "🔀"),
    ("pages/4_About.py", {"en": "About", "de": "Über"}, "ℹ️"),
]

# The app brand is a proper name, so it stays identical in every language.
BRAND_NAME: str = "Swiss Hike Forecaster"


def render_top_nav() -> None:
    """Draw the top navigation bar. Call this once per page."""
    # Streamlit custom CSS pattern - https://docs.streamlit.io
    st.markdown(_NAV_CSS, unsafe_allow_html=True)

    # The left column is twice as wide because it holds the app brand,
    # which has a longer label. Then one equal-width column per nav entry,
    # and a final narrow column on the right for the language switch.
    cols = st.columns([2] + [1] * len(NAV_ENTRIES) + [1], gap="small")
    with cols[0]:
        st.page_link(
            "app.py",
            label=BRAND_NAME,
            icon="🏔️",
            width="stretch",
        )
    # Nav labels follow the language switch; the brand name above does not.
    lang = get_lang()
    for col, (path, label, icon) in zip(cols[1:-1], NAV_ENTRIES):
        with col:
            st.page_link(
                path,
                label=label.get(lang, label["en"]),
                icon=icon,
                width="stretch",
            )
    # The EN/DE switch lives in the last column — the top-right corner of
    # every page, because every page calls render_top_nav().
    with cols[-1]:
        render_language_toggle()
    st.markdown("<hr class='nav-rule'>", unsafe_allow_html=True)
