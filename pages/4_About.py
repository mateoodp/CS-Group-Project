"""About page — ML metrics, feature importance, contribution matrix.

Owner: TM1 (layout + contribution matrix) · TM4 (ML metrics)

Sections:
    1. Project problem statement (Criterion 1).
    2. ML pipeline explanation (links to Section 4 of the product report).
    3. Model metrics:
        * accuracy
        * confusion matrix (Plotly heatmap)
        * classification report
    4. Feature importance — Plotly horizontal bar chart.
    5. Retrain Model button — triggers ``trail_classifier.retrain_from_db``.
    6. Contribution matrix — who did what.
    7. Data-source attribution.
"""

from __future__ import annotations

import streamlit as st

from ml import trail_classifier
from utils.constants import APP_TITLE, CONTRIBUTION_MATRIX

st.set_page_config(page_title=f"About · {APP_TITLE}", page_icon="ℹ️", layout="wide")


# ---------------------------------------------------------------------------
# Problem statement
# ---------------------------------------------------------------------------

def render_problem_statement() -> None:
    """Short, evidence-backed explanation of why the tool exists."""
    st.header("Why this tool exists")
    st.markdown(
        """
        Swiss alpine accidents kill **~20 hikers per year** and injure hundreds
        more — largely due to underestimated conditions. Existing apps
        (MeteoSwiss, SRF Meteo) display raw data. The Swiss Alpine Club (SAC)
        publishes avalanche bulletins, not trail-level go/no-go scores.

        This tool closes the gap: it takes seven meteorological variables,
        passes them through a trained Random Forest classifier, and outputs
        a single **SAFE / BORDERLINE / AVOID** verdict with confidence and
        the top 3 contributing factors.
        """
    )


# ---------------------------------------------------------------------------
# ML pipeline
# ---------------------------------------------------------------------------

def render_ml_pipeline() -> None:
    """Step-by-step ML pipeline with code references.

    TODO (TM4): implement. Show the 9 steps from ``trail_classifier.py``.
    """
    st.header("How the ML pipeline works")
    st.info("ML pipeline description renders here.")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def render_metrics() -> None:
    """Accuracy + confusion matrix + classification report.

    TODO (TM4): implement.
    """
    st.header("Model performance")
    col1, col2, col3 = st.columns(3)
    col1.metric("Accuracy", "—")
    col2.metric("Rows trained", "—")
    col3.metric("Model version", trail_classifier.MODEL_VERSION)
    st.info("Confusion matrix + classification report render here.")


def render_feature_importance() -> None:
    """Plotly horizontal bar chart of feature importances.

    TODO (TM4): implement.
    """
    st.subheader("Feature importance")
    st.info("Feature importance chart renders here.")


# ---------------------------------------------------------------------------
# Retrain button
# ---------------------------------------------------------------------------

def render_retrain_button() -> None:
    """Button that triggers a full retrain from the current DB state.

    NOTE (per product report): the button should ALWAYS be enabled during
    the demo — pre-seed 100 synthetic user reports so the retrain loop has
    something to chew on even if no real reports have arrived yet.

    TODO (TM4): implement.
    """
    if st.button("🔄 Retrain model", type="primary"):
        st.warning("TODO: call trail_classifier.retrain_from_db() and show metrics.")


# ---------------------------------------------------------------------------
# Contribution matrix
# ---------------------------------------------------------------------------

def render_contribution_matrix() -> None:
    """Colour-coded contribution matrix — Criterion 7.

    Reads ``CONTRIBUTION_MATRIX`` from ``utils/constants.py`` and renders
    it as a pandas DataFrame with colour coding:
        L (Lead)     → dark green
        M (Major)    → medium green
        S (Support)  → light green
        —            → white
    """
    import pandas as pd

    st.header("Contribution matrix")
    df = pd.DataFrame(CONTRIBUTION_MATRIX)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(
        "Legend: **L** = Lead · **M** = Major · **S** = Support · — = None. "
        "Cross-check with GitHub commit history per member."
    )


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

def render_attribution() -> None:
    """Data-source attribution — good academic practice."""
    st.header("Data sources")
    st.markdown(
        """
        - **Open-Meteo Forecast** · `api.open-meteo.com/v1/forecast` — free, no key.
        - **Open-Meteo Historical Archive** · `archive-api.open-meteo.com/v1/archive` — free, no key.
        - **Swisstopo GeoAdmin** · `api3.geo.admin.ch` — free federal geodata, no key.
        """
    )


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("ℹ️ About this app")
    render_problem_statement()
    st.divider()
    render_ml_pipeline()
    st.divider()
    render_metrics()
    render_feature_importance()
    render_retrain_button()
    st.divider()
    render_contribution_matrix()
    st.divider()
    render_attribution()


main()
