"""About page. Explains the project, lets graders retrain the model,
and shows the model's performance numbers after a retrain.

Owner: TM1 (layout) and TM4 (ML metrics).
"""
# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

import time

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
from utils.i18n import block, t
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


# Intro section. This text stays the same every time. It explains what
# problem the app is trying to solve and what makes it different from a
# regular weather forecast.
def render_problem_statement() -> None:
    st.markdown(
        section_heading(
            t("Why this tool exists"),
            t("Raw weather numbers are useful, but hikers also need a quick answer about whether a given trail is a good idea today."),
            t("Problem"),
        ),
        unsafe_allow_html=True,
    )
    st.markdown(block("about_problem_body"))


# ---------------------------------------------------------------------------
# Setup section
# ---------------------------------------------------------------------------


# Setup section. Two big buttons let the user (or a grader) download two
# years of historical weather and then retrain the model. We keep this on
# the About page so anyone reviewing the project can reproduce our results
# without using a terminal.
def render_setup_section() -> None:
    st.markdown(
        section_heading(
            t("Initial setup"),
            t("Seed historical weather and retrain the model when the local cache needs rebuilding."),
            t("Model operations"),
        ),
        unsafe_allow_html=True,
    )
    n_weather = len(db_manager.get_all_weather())
    has_model = trail_classifier.model_exists()
    st.markdown(
        stat_pills_html(
            [
                (t("weather rows in DB"), f"{n_weather:,}"),
                (t("trails seeded"), len(db_manager.get_all_trails())),
                (t("model file"), t("trained") if has_model else t("not yet")),
            ]
        ),
        unsafe_allow_html=True,
    )

    # Two buttons sitting next to each other. The left one downloads
    # historical weather (the training data) and the right one retrains
    # the ML model from whatever weather data is currently in the database.
    seed_col, train_col = st.columns(2)
    with seed_col:
        years = st.slider(t("Years of history to fetch"), 1, 2, 1,
                          key="seed_years")
        if st.button(t("⬇️ Seed historical weather (all trails)"),
                     width="stretch"):
            # Loop through every trail one by one, ask the Open-Meteo
            # archive for that location's past weather, and save it into
            # the local SQLite database. The progress bar gives the user
            # something to watch since this can take a while.
            trails = db_manager.get_all_trails()
            progress = st.progress(0.0, text=t("Fetching archive…"))
            errors: list[str] = []
            for i, trail in enumerate(trails):
                try:
                    # Open-Meteo Historical Archive - https://open-meteo.com/en/docs/historical-weather-api
                    weather_fetcher.seed_historical_weather(
                        trail["id"], trail["lat"], trail["lon"], years=years
                    )
                except Exception as e:
                    errors.append(f"{trail['name']}: {e}")
                progress.progress(
                    (i + 1) / len(trails),
                    text=t("Fetching archive… {name} ({i}/{total})",
                           name=trail["name"], i=i + 1, total=len(trails)),
                )
                # Open-Meteo's free archive endpoint caps at ~600 requests
                # per minute. Pacing each call by ~0.15s keeps us safely
                # under that ceiling while still finishing in well under a minute.
                time.sleep(0.15)
            progress.empty()
            if errors:
                st.warning(
                    t("Done with {n} errors:", n=len(errors))
                    + "\n\n" + "\n".join(errors[:5])
                )
            else:
                st.success(t("Historical weather seeded for all trails."))

    with train_col:
        if st.button(t("🧠 Retrain model"), type="primary", width="stretch"):
            try:
                # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
                # Train a new Random Forest using whatever weather data is
                # currently in the database. The spinner tells the user
                # something is happening so they don't think the app froze.
                with st.spinner(t("Training Random Forest…")):
                    metrics = trail_classifier.retrain_from_db()
                # Save the training metrics into session state so the
                # render_metrics() function below can pick them up and
                # show them in the dashboard.
                st.session_state["last_metrics"] = metrics
                st.success(
                    t("Trained! Accuracy: {acc} on {n} rows.",
                      acc=f"{metrics['accuracy']:.1%}",
                      n=f"{metrics['n_samples']:,}")
                )
            except Exception as e:
                st.error(t("Retrain failed: {err}", err=e))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


# The model performance section. After a retrain we show:
# - overall accuracy
# - a confusion matrix (so the grader can see which verdicts get mixed up)
# - the precision/recall report
# - a bar chart of which features the model relies on the most.
def render_metrics() -> None:
    st.markdown(
        section_heading(
            t("Model performance"),
            t("Training metrics appear after retraining from the current local database."),
            t("Evaluation"),
        ),
        unsafe_allow_html=True,
    )
    metrics = st.session_state.get("last_metrics")

    if metrics is None:
        st.info(
            t("Metrics will appear here after the first retrain. "
              "Click **Retrain model** above.")
        )
        return

    st.markdown(
        stat_pills_html(
            [
                (t("accuracy"), f"{metrics['accuracy']:.1%}"),
                (t("rows trained"), f"{metrics['n_samples']:,}"),
                (t("model version"), metrics["model_version"]),
            ]
        ),
        unsafe_allow_html=True,
    )

    # Adapted from Plotly Python docs - https://plotly.com/python/
    # Draw the confusion matrix as a heatmap. The rows are the real labels
    # and the columns are what the model predicted. The diagonal cells are
    # the correct answers; off-diagonal cells are where it got confused.
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
            colorbar=dict(title=t("Count")),
        )
    )
    fig.update_layout(
        title=t("Confusion matrix"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
        xaxis_title=t("Predicted"),
        yaxis_title=t("Actual"),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, width="stretch")

    # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
    # This is sklearn's standard "classification report". For each class
    # (SAFE, BORDERLINE, AVOID) it gives precision, recall and F1 score.
    # We render it as a plain dataframe so it's easy to read.
    st.subheader(t("Classification report"))
    rep = pd.DataFrame(metrics["classification_report"]).T
    st.dataframe(rep.round(3), width="stretch")

    # Adapted from Plotly Python docs - https://plotly.com/python/
    # Bar chart showing which features the Random Forest leaned on the most.
    # We sort ascending so the longest (most important) bar sits at the top.
    st.subheader(t("Feature importance"))
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
        labels={"Importance": t("Importance"), "Feature": t("Feature")},
    )
    fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, width="stretch")


# ---------------------------------------------------------------------------
# Attribution
# ---------------------------------------------------------------------------


# Attribution section. Lists the free data sources we use, with links.
# It's important to credit data providers, especially for an academic project.
def render_attribution() -> None:
    st.markdown(
        section_heading(
            t("Data sources"),
            t("Free public APIs and local seeded data power the app."),
            t("Attribution"),
        ),
        unsafe_allow_html=True,
    )
    st.markdown(block("about_attribution_body"))


# ---------------------------------------------------------------------------
# Page entry
# ---------------------------------------------------------------------------


# Main function for this page. It just stacks all the sections in order
# with a thin divider line between each. Streamlit calls this when the
# user opens the About page.
def main() -> None:
    render_top_nav()
    render_shared_sidebar()
    apply_app_theme()
    st.markdown(
        page_hero(
            t("About this app"),
            t("Swiss Alpine Hiking Condition Forecaster combines trail catalogue data, weather caches and a trained model into route-level condition guidance."),
            t("Project and model"),
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
