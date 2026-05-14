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
</style>
"""


# One source of truth for the four nav entries we show. Each tuple is
# (page file path, label, icon). If we ever rename a page file, we update
# it here in one place and the navigation stays consistent everywhere.
NAV_ENTRIES: list[tuple[str, str, str]] = [
    ("pages/1_Find.py", "Find a hike", "🧭"),
    ("pages/2_Map.py", "Map", "🗺️"),
    ("pages/3_Compare.py", "Compare", "🔀"),
    ("pages/4_About.py", "About", "ℹ️"),
]


def render_top_nav() -> None:
    """Draw the top navigation bar. Call this once per page."""
    # Streamlit custom CSS pattern - https://docs.streamlit.io
    st.markdown(_NAV_CSS, unsafe_allow_html=True)

    # The left column is twice as wide because it holds the app brand,
    # which has a longer label. The other columns are equal width, one
    # per nav entry.
    cols = st.columns([2] + [1] * len(NAV_ENTRIES), gap="small")
    with cols[0]:
        st.page_link(
            "app.py",
            label="Swiss Hike Forecaster",
            icon="🏔️",
            width="stretch",
        )
    for col, (path, label, icon) in zip(cols[1:], NAV_ENTRIES):
        with col:
            st.page_link(path, label=label, icon=icon, width="stretch")
    st.markdown("<hr class='nav-rule'>", unsafe_allow_html=True)
