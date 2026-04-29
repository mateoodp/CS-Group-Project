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

  /* Reduce the top padding so the nav row sits flush with the window. */
  .block-container { padding-top: 1.5rem; }

  /* Style the horizontal nav row. */
  .top-nav {
    display: flex;
    gap: 6px;
    padding: 6px 8px;
    background: #f5f6f8;
    border-radius: 12px;
    margin-bottom: 18px;
    border: 1px solid #e6e8eb;
  }
  .top-nav-brand {
    font-weight: 700;
    color: #1a1a1a;
    padding: 6px 14px 6px 6px;
    border-right: 1px solid #e0e2e5;
    margin-right: 6px;
    align-self: center;
    white-space: nowrap;
  }

  /* Streamlit page links inside the nav: pill-style. */
  .top-nav [data-testid="stPageLink"] a {
    padding: 8px 16px;
    border-radius: 8px;
    color: #4a4a4a;
    text-decoration: none;
    font-weight: 500;
  }
  .top-nav [data-testid="stPageLink"] a:hover {
    background: #ffffff;
    color: #1a1a1a;
  }
</style>
"""


# Single source of truth for the visible nav entries. Keep in sync with
# the file paths under pages/ — this list drives both the rendered links
# and any "back to {section}" buttons inside the Trail Detail page.
NAV_ENTRIES: list[tuple[str, str, str]] = [
    ("pages/1_Find.py",    "Find a hike", "🧭"),
    ("pages/2_Map.py",     "Map",         "🗺️"),
    ("pages/3_Compare.py", "Compare",     "🔀"),
    ("pages/4_About.py",   "About",       "ℹ️"),
]


def render_top_nav() -> None:
    """Render the horizontal top nav. Call once per page."""
    st.markdown(_NAV_CSS, unsafe_allow_html=True)

    cols = st.columns([2] + [1] * len(NAV_ENTRIES), gap="small")
    with cols[0]:
        st.markdown(
            "<div style='font-weight:700; font-size:1.1rem; "
            "padding-top:6px;'>🏔️ Swiss Hike Forecaster</div>",
            unsafe_allow_html=True,
        )
    for col, (path, label, icon) in zip(cols[1:], NAV_ENTRIES):
        with col:
            st.page_link(path, label=label, icon=icon, use_container_width=True)
    st.markdown(
        "<hr style='margin:8px 0 18px; border:0; border-top:1px solid #e6e8eb;'>",
        unsafe_allow_html=True,
    )
