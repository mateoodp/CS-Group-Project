"""About page: problem statement, model setup, and performance metrics.

Owner: TM1 (layout) and TM4 (ML metrics).
"""
# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import db_manager, weather_fetcher
from ml import trail_classifier
from utils.constants import (
    APP_TITLE,
    FEATURE_DISPLAY_NAMES,
)
from utils.sidebar import render_shared_sidebar
from utils.theme import apply_app_theme, page_hero, section_heading, stat_pills_html
from utils.topnav import render_top_nav

# Streamlit pattern - https://docs.streamlit.io
# Page metadata. Must be the first Streamlit call on the page.
st.set_page_config(
    page_title=f"About · {APP_TITLE}",
    page_icon="ℹ️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# Problem statement
# ---------------------------------------------------------------------------


# Static intro section explaining the project's motivation and core claim.
def render_problem_statement() -> None:
    st.markdown(
        section_heading(
            "Why this tool exists",
            "Raw weather numbers are useful, but hikers also need a quick answer about whether a given trail is a good idea today.",
            "Problem",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        Hiking in the Swiss Alps is one of the best things you can do in
        summer, but it can also be dangerous. Around **20 people die every
        year** on Swiss alpine trails, and many more get injured. Most of
        these accidents happen because hikers did not realise how risky
        the conditions on a specific trail would actually be on that day.

        The weather apps people normally use (like MeteoSwiss or SRF Meteo)
        show numbers such as temperature, wind speed, or chance of rain.
        That information is useful, but it does not directly answer the
        question every hiker is really asking: "is this trail a good idea
        today?" The Swiss Alpine Club publishes avalanche warnings, but
        again not at the level of an individual hike.

        Our app tries to close that gap. You pick a trail and a date, and
        you get one clear answer: **SAFE**, **BORDERLINE**, or **AVOID**.
        The answer comes with a short explanation of the main reasons
        (for example "wind is too strong" or "the trail is above the snow
        line that day"), so you can decide for yourself whether to go,
        change your plans, or wait for better weather.
        """
    )


# ---------------------------------------------------------------------------
# Setup section
# ---------------------------------------------------------------------------


# Admin section: seed the weather archive for all trails and retrain the model.
# Kept on the About page so graders can reproduce results without using a CLI.
def render_setup_section() -> None:
    st.markdown(
        section_heading(
            "Initial setup",
            "Seed historical weather and retrain the model when the local cache needs rebuilding.",
            "Model operations",
        ),
        unsafe_allow_html=True,
    )
    n_weather = len(db_manager.get_all_weather())
    has_model = trail_classifier.model_exists()
    st.markdown(
        stat_pills_html(
            [
                ("weather rows in DB", f"{n_weather:,}"),
                ("trails seeded", len(db_manager.get_all_trails())),
                ("model file", "trained" if has_model else "not yet"),
            ]
        ),
        unsafe_allow_html=True,
    )

    # Two action buttons: seed historical weather (left) and retrain model (right).
    seed_col, train_col = st.columns(2)
    with seed_col:
        years = st.slider("Years of history to fetch", 1, 2, 1, key="seed_years")
        if st.button("⬇️ Seed historical weather (all trails)", width="stretch"):
            # Walk every trail, hit the Open-Meteo archive, and persist into the local DB.
            trails = db_manager.get_all_trails()
            progress = st.progress(0.0, text="Fetching archive…")
            errors: list[str] = []
            for i, t in enumerate(trails):
                try:
                    # Open-Meteo Historical Archive - https://open-meteo.com/en/docs/historical-weather-api
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
        if st.button("🧠 Retrain model", type="primary", width="stretch"):
            try:
                # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
                # Retrain triggers a fresh RandomForest fit on the current DB content.
                with st.spinner("Training Random Forest…"):
                    metrics = trail_classifier.retrain_from_db()
                # Stash the metrics in session state so render_metrics can display them.
                st.session_state["last_metrics"] = metrics
                st.success(
                    f"Trained! Accuracy: {metrics['accuracy']:.1%} "
                    f"on {metrics['n_samples']:,} rows."
                )
            except Exception as e:
                st.error(f"Retrain failed: {e}")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


# Renders the model performance section: accuracy pills, confusion matrix,
# classification report and feature importance bar chart.
def render_metrics() -> None:
    st.markdown(
        section_heading(
            "Model performance",
            "Training metrics appear after retraining from the current local database.",
            "Evaluation",
        ),
        unsafe_allow_html=True,
    )
    metrics = st.session_state.get("last_metrics")

    if metrics is None:
        st.info(
            "Metrics will appear here after the first retrain. "
            "Click **Retrain model** above."
        )
        return

    st.markdown(
        stat_pills_html(
            [
                ("accuracy", f"{metrics['accuracy']:.1%}"),
                ("rows trained", f"{metrics['n_samples']:,}"),
                ("model version", metrics["model_version"]),
            ]
        ),
        unsafe_allow_html=True,
    )

    # Adapted from Plotly Python docs - https://plotly.com/python/
    # Confusion matrix heatmap: rows = actual labels, columns = predicted labels.
    cm = metrics["confusion_matrix"]
    labels = list(trail_classifier.LABEL_TO_CODE.keys())
    fig = go.Figure(
        data=go.Heatmap(
            z=cm,
            x=labels,
            y=labels,
            colorscale="Greens",
            text=cm,
            texttemplate="%{text}",
            colorbar=dict(title="Count"),
        )
    )
    fig.update_layout(
        title="Confusion matrix",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
        xaxis_title="Predicted",
        yaxis_title="Actual",
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, width="stretch")

    # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
    # Standard per-class precision/recall/F1 from sklearn.metrics.classification_report.
    st.subheader("Classification report")
    rep = pd.DataFrame(metrics["classification_report"]).T
    st.dataframe(rep.round(3), width="stretch")

    # Adapted from Plotly Python docs - https://plotly.com/python/
    # Horizontal bar chart of RandomForest feature importances, sorted ascending.
    st.subheader("Feature importance")
    imp_df = pd.DataFrame(
        metrics["feature_importances"], columns=["Feature", "Importance"]
    )
    imp_df["Feature"] = imp_df["Feature"].map(lambda f: FEATURE_DISPLAY_NAMES.get(f, f))
    imp_df = imp_df.sort_values("Importance")
    fig2 = px.bar(
        imp_df,
        x="Importance",
        y="Feature",
        orientation="h",
        color="Importance",
        color_continuous_scale="Greens",
    )
    fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, width="stretch")


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------


# Static attribution section listing the third-party data sources we use.
def render_attribution() -> None:
    st.markdown(
        section_heading(
            "Data sources",
            "Free public APIs and local seeded data power the app.",
            "Attribution",
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        - **[Open-Meteo Forecast](https://open-meteo.com/en/docs)**: current and 7-day forecast, free, no key.
        - **[Open-Meteo Historical Archive](https://open-meteo.com/en/docs/historical-weather-api)**: up to two years of past weather, free, no key.
        - **[Swisstopo GeoAdmin](https://docs.geo.admin.ch/access-data/identify-features.html)**: Swiss federal geodata for trail elevation lookups, free, no key.
        """
    )


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------


# Page entry point. Stacks the About sections separated by st.divider lines.
def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    apply_app_theme()
    st.markdown(
        page_hero(
            "About this app",
            "Swiss Alpine Hiking Condition Forecaster combines trail catalogue data, weather caches and a trained model into route-level condition guidance.",
            "Project and model",
        ),
        unsafe_allow_html=True,
    )
    render_problem_statement()
    st.divider()
    render_setup_section()
    st.divider()
    render_metrics()
    st.divider()
    render_attribution()


main()
