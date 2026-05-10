"""Horizontal top navigation — replaces Streamlit's vertical sidebar nav.

Call :func:`render_top_nav` at the very top of every page (right after
``st.set_page_config``). It does three things:

    1. Injects CSS that hides Streamlit's auto-generated sidebar page list,
       since we want a clean horizontal nav at the top instead.
    2. Renders four equal-width ``st.page_link`` widgets (Find · Map ·
       Compare · About) as a row.
    3. Adds a thin separator below the nav so it visually anchors as a header.

The Trail Detail page is deliberately **not** in the nav — users only
reach it by clicking a hike from one of the four primary pages.
"""

from __future__ import annotations

import streamlit as st


# ---------------------------------------------------------------------------
# Injected CSS — hides the default page list in the sidebar and tightens
# the top-of-page padding so the horizontal nav reads as the real header.
# ---------------------------------------------------------------------------

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


# Single source of truth for the visible nav entries. Keep in sync with
# the file paths under pages/ — this list drives both the rendered links
# and any "back to {section}" buttons inside the Trail Detail page.
NAV_ENTRIES: list[tuple[str, str, str]] = [
    ("pages/1_Find.py", "Find a hike", "🧭"),
    ("pages/2_Map.py", "Map", "🗺️"),
    ("pages/3_Compare.py", "Compare", "🔀"),
    ("pages/4_About.py", "About", "ℹ️"),
]


def render_top_nav() -> None:
    """Render the horizontal top nav. Call once per page."""
    st.markdown(_NAV_CSS, unsafe_allow_html=True)

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
