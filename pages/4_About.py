"""About page — ML metrics, feature importance, contribution matrix.

Owner: TM1 (layout + contribution matrix) · TM4 (ML metrics)
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import db_manager, weather_fetcher
from ml import trail_classifier
from utils.constants import (
    APP_TITLE,
    CONTRIBUTION_MATRIX,
    FEATURE_DISPLAY_NAMES,
)
from utils.sidebar import render_shared_sidebar

st.set_page_config(page_title=f"About · {APP_TITLE}", page_icon="ℹ️", layout="wide")


# ---------------------------------------------------------------------------
# Problem statement
# ---------------------------------------------------------------------------

def render_problem_statement() -> None:
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
# Pipeline
# ---------------------------------------------------------------------------

def render_ml_pipeline() -> None:
    st.header("How the ML pipeline works")
    st.markdown(
        """
        | Step | What happens | Module |
        |---|---|---|
        | 1 | Pull `weather_snapshots` from SQLite, JOIN trail max altitude | `data/db_manager.py` |
        | 2 | Engineer 7 features (wind chill, snowline delta, 7-day rolling rain…) | `ml/trail_classifier.py` |
        | 3 | Bootstrap labels via SAC-style rules; user reports override | `data/label_engine.py` |
        | 4 | Stratified 80/20 split | `train_test_split` |
        | 5 | Fit `RandomForestClassifier(n_estimators=100, max_depth=8)` | scikit-learn |
        | 6 | Evaluate: accuracy · confusion matrix · classification report | `sklearn.metrics` |
        | 7 | Pickle to `ml/model.pkl` | `pickle` |
        | 8 | Predict: `predict_proba` → verdict + confidence | `ml/trail_classifier.py` |
        | 9 | Surface top-3 feature importances in every prediction | About tab |
        """
    )


# ---------------------------------------------------------------------------
# Setup section
# ---------------------------------------------------------------------------

def render_setup_section() -> None:
    st.header("Initial setup")
    n_weather = len(db_manager.get_all_weather())
    has_model = trail_classifier.model_exists()
    c1, c2, c3 = st.columns(3)
    c1.metric("Weather rows in DB", f"{n_weather:,}")
    c2.metric("Trails seeded", f"{len(db_manager.get_all_trails())}")
    c3.metric(
        "Model file",
        "✅ trained" if has_model else "❌ not yet",
    )

    seed_col, train_col = st.columns(2)
    with seed_col:
        years = st.slider("Years of history to fetch", 1, 2, 1, key="seed_years")
        if st.button("⬇️ Seed historical weather (all 20 trails)"):
            trails = db_manager.get_all_trails()
            progress = st.progress(0.0, text="Fetching archive…")
            errors: list[str] = []
            for i, t in enumerate(trails):
                try:
                    weather_fetcher.seed_historical_weather(
                        t["id"], t["lat"], t["lon"], years=years
                    )
                except Exception as e:
                    errors.append(f"{t['name']}: {e}")
                progress.progress(
                    (i + 1) / len(trails),
                    text=f"Fetching archive… {t['name']} ({i+1}/{len(trails)})",
                )
            progress.empty()
            if errors:
                st.warning(
                    f"Done with {len(errors)} errors:\n\n" + "\n".join(errors[:5])
                )
            else:
                st.success("Historical weather seeded for all trails.")

    with train_col:
        if st.button("🧠 Retrain model", type="primary"):
            try:
                with st.spinner("Training Random Forest…"):
                    metrics = trail_classifier.retrain_from_db()
                st.session_state["last_metrics"] = metrics
                st.success(f"Trained! Accuracy: {metrics['accuracy']:.1%} "
                           f"on {metrics['n_samples']:,} rows.")
            except Exception as e:
                st.error(f"Retrain failed: {e}")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def render_metrics() -> None:
    st.header("Model performance")
    metrics = st.session_state.get("last_metrics")

    if metrics is None:
        st.info(
            "No metrics yet. Run the **Retrain model** button above to train "
            "the Random Forest and populate this section."
        )
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Accuracy", f"{metrics['accuracy']:.1%}")
    c2.metric("Rows trained", f"{metrics['n_samples']:,}")
    c3.metric("Model version", metrics["model_version"])

    cm = metrics["confusion_matrix"]
    labels = list(trail_classifier.LABEL_TO_CODE.keys())
    fig = go.Figure(
        data=go.Heatmap(
            z=cm, x=labels, y=labels,
            colorscale="Greens",
            text=cm, texttemplate="%{text}",
            colorbar=dict(title="Count"),
        )
    )
    fig.update_layout(
        title="Confusion matrix",
        height=380,
        xaxis_title="Predicted",
        yaxis_title="Actual",
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Classification report")
    rep = pd.DataFrame(metrics["classification_report"]).T
    st.dataframe(rep.round(3), use_container_width=True)

    st.subheader("Feature importance")
    imp_df = pd.DataFrame(
        metrics["feature_importances"], columns=["Feature", "Importance"]
    )
    imp_df["Feature"] = imp_df["Feature"].map(
        lambda f: FEATURE_DISPLAY_NAMES.get(f, f)
    )
    imp_df = imp_df.sort_values("Importance")
    fig2 = px.bar(
        imp_df, x="Importance", y="Feature", orientation="h",
        color="Importance", color_continuous_scale="Greens",
    )
    fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Contribution matrix
# ---------------------------------------------------------------------------

def render_contribution_matrix() -> None:
    st.header("Contribution matrix")
    df = pd.DataFrame(CONTRIBUTION_MATRIX)
    palette = {"L": "#1E7B3A", "M": "#52A370", "S": "#A8D5B7", "—": "#FFFFFF"}

    def colour(val: str) -> str:
        return f"background-color:{palette.get(val, '#FFFFFF')}; color:black;"

    styled = df.style.map(colour, subset=["TM1", "TM2", "TM3", "TM4", "TM5"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("Legend: **L** = Lead · **M** = Major · **S** = Support · — = None.")


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------

def render_attribution() -> None:
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
    render_shared_sidebar()
    st.title("ℹ️ About this app")
    render_problem_statement()
    st.divider()
    render_ml_pipeline()
    st.divider()
    render_setup_section()
    st.divider()
    render_metrics()
    st.divider()
    render_contribution_matrix()
    st.divider()
    render_attribution()


main()
