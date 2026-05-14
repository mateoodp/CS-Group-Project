"""Random Forest trail safety classifier.

Owner: TM4 (ML Lead). Support: TM5 (Feature Engineering).

The full pipeline from raw data to predictions (see Section 4 of the
product report for more detail):

    STEP 1: Load data. We JOIN weather_snapshots with rule labels from
            label_engine to build the training set.
    STEP 2: Feature engineering. We derive wind-chill, the snowline
            minus trail-max difference, and a 7-day rolling precip.
    STEP 3: Encode labels as numbers (SAFE=0, BORDERLINE=1, AVOID=2).
    STEP 4: Split into 80% train and 20% test, stratified by label.
    STEP 5: Train a Random Forest with 100 trees and depth 8.
    STEP 6: Evaluate: accuracy, confusion matrix, classification report.
    STEP 7: Save the trained model to ml/model.pkl.
    STEP 8: Predict by calling predict_proba and taking the argmax.
            The probability of that class becomes the confidence number.
    STEP 9: Read feature_importances_ from the model and show them as
            a bar chart on the About page.

Why a Random Forest and not something else?
  - It naturally handles non-linear interactions (e.g. cold + wind
    together is much worse than either alone, which is hypothermia).
  - It tolerates missing values well.
  - It gives us real probability scores, which we use as confidence.
  - The feature importances are easy to interpret and explain.
  - It is a beginner-friendly model that we can defend verbally in
    the graded Q&A.
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split

from data import db_manager, label_engine

MODEL_PATH: Path = Path(__file__).resolve().parent / "model.pkl"
METRICS_PATH: Path = Path(__file__).resolve().parent / "last_metrics.json"
MODEL_VERSION: str = "0.1.0-dev"

# The order of features matters and must not change. The saved model
# remembers the order it was trained on, so if we add or rearrange a
# feature we have to retrain from scratch.
#
# Features:
#   - 4 raw weather inputs: temperature, wind, precipitation, cloud cover.
#   - 3 engineered features we computed ourselves:
#       * snowline_minus_trailmax: how far the snowline sits above the
#         trail's highest point (negative means snow on the route).
#       * wind_chill_index: combined effect of temperature and wind.
#       * precip_7day_rolling: sum of rain over the last 7 days, used
#         as a proxy for how saturated the ground is.
FEATURE_COLUMNS: list[str] = [
    "temperature_c",
    "wind_speed_kmh",
    "precipitation_mm",
    "snowline_minus_trailmax",
    "wind_chill_index",
    "cloud_cover_pct",
    "precip_7day_rolling",
]

# We map the three text labels to numbers by hand. We could let sklearn's
# LabelEncoder do this for us, but if we did that the mapping might
# change between retrains (sklearn assigns numbers based on alphabetical
# order of whatever labels show up first). By writing it out explicitly
# we know the mapping is always the same.
LABEL_TO_CODE: dict[str, int] = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}
CODE_TO_LABEL: dict[int, str] = {v: k for k, v in LABEL_TO_CODE.items()}


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def wind_chill(temp_c: float, wind_kmh: float) -> float:
    """Compute the wind-chill temperature using the standard NWS formula.

    The formula is only valid when the temperature is at or below 10 C
    and the wind is at least 4.8 km/h. Outside those ranges we just
    return the raw temperature unchanged. This matches the official
    NWS guidance and avoids producing misleading numbers (for example
    a "wind chill" of 5 C on a warm sunny day).
    """
    if temp_c is None or wind_kmh is None:
        return temp_c
    # If either input is outside the valid range, the safe thing to do
    # is just return the raw temperature, per NWS guidance.
    if temp_c > 10.0 or wind_kmh < 4.8:
        return temp_c
    # NWS wind chill formula. The constants come straight from the
    # official equation. v is wind speed raised to the 0.16 power.
    v = wind_kmh ** 0.16
    return 13.12 + 0.6215 * temp_c - 11.37 * v + 0.3965 * temp_c * v


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived features expected by the model.

    Required input columns: ``trail_id``, ``snapshot_date``, ``temp_c``,
    ``wind_kmh``, ``precip_mm``, ``snowline_m``, ``cloud_pct``,
    ``trail_max_alt_m``.

    Returns a copy with all ``FEATURE_COLUMNS`` populated.
    """
    out = df.copy()
    # Sort the rows so each trail's days are in order. The 7-day rolling
    # sum we compute below only makes sense when the dates are contiguous,
    # so this sort is essential.
    out = out.sort_values(["trail_id", "snapshot_date"]).reset_index(drop=True)

    # Rename the raw weather columns into the standard names the model
    # was trained with. We do this so the feature dataframe always has
    # exactly the columns listed in FEATURE_COLUMNS.
    out["temperature_c"] = out["temp_c"]
    out["wind_speed_kmh"] = out["wind_kmh"]
    out["precipitation_mm"] = out["precip_mm"]
    out["cloud_cover_pct"] = out["cloud_pct"]
    # Snowline minus trail-max altitude. Positive means the snowline is
    # above the summit (snow-free route, safer). Negative means snow is
    # on the route. The size of the number tells us how much margin
    # exists either way.
    out["snowline_minus_trailmax"] = out["snowline_m"] - out["trail_max_alt_m"]
    # Wind chill combines temperature and wind into one feature. We
    # added this because cold air with wind is much more dangerous
    # than cold alone, but a tree split on temperature wouldn't capture
    # that on its own.
    out["wind_chill_index"] = [
        wind_chill(t, w) for t, w in zip(out["temp_c"], out["wind_kmh"])
    ]
    # pandas docs - https://pandas.pydata.org/docs/
    # 7-day rolling sum of precipitation for each trail. This is our
    # proxy for "how saturated is the ground". A trail that just got
    # a week of rain is muddier and more dangerous than one that's
    # been dry, even if today's forecast looks the same.
    # min_periods=1 means we don't get NaN for the first few days
    # before there's a full 7-day window of data.
    out["precip_7day_rolling"] = (
        out.groupby("trail_id")["precip_mm"]
        .rolling(window=7, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    return out


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_model(df: pd.DataFrame, label_col: str = "label") -> dict:
    """Train the Random Forest and persist it to ``MODEL_PATH``.

    ``df`` must contain ``FEATURE_COLUMNS`` and ``label_col``.
    """
    # sklearn's tree-based models don't handle NaN by default, so we
    # replace any missing values with 0.0 before fitting. This is the
    # same default we use later when predicting on real data.
    feats = df[FEATURE_COLUMNS].fillna(0.0)
    labels = df[label_col].map(LABEL_TO_CODE)

    # A classifier can't learn anything if all the training labels are
    # the same. We raise a helpful error early instead of letting
    # sklearn fail later with a less clear message.
    if labels.nunique() < 2:
        raise ValueError(
            "Cannot train: training data only contains one class. "
            "Seed more historical weather first."
        )

    # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
    # Stratified splitting keeps the same proportion of each label in
    # the train and test sets. sklearn refuses to do that if any class
    # has fewer than 2 samples, so we only use stratify when it's safe.
    stratify = labels if labels.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        feats, labels, test_size=0.2, random_state=42, stratify=stratify
    )

    # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
    # 100 trees and a max depth of 8 strikes a good balance for our
    # data size. Fewer trees would be noisier; deeper trees would risk
    # overfitting and would also make it harder to explain what the
    # model is doing. n_jobs=-1 tells sklearn to use every CPU core,
    # which makes training faster.
    model = RandomForestClassifier(
        n_estimators=100, max_depth=8, random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # Sort the features by importance (highest first) so the About
    # page can show which features the model relies on the most.
    # Random Forest computes this automatically using the Gini score.
    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda kv: kv[1],
        reverse=True,
    )
    # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
    # Build a single dictionary with all the evaluation numbers. This
    # gets passed back to the About page and also saved to disk as JSON
    # so the page can show metrics even after a fresh app reload.
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "confusion_matrix": confusion_matrix(
            y_test, y_pred, labels=list(LABEL_TO_CODE.values())
        ).tolist(),
        "classification_report": classification_report(
            y_test,
            y_pred,
            labels=list(LABEL_TO_CODE.values()),
            target_names=list(LABEL_TO_CODE.keys()),
            output_dict=True,
            zero_division=0,
        ),
        "feature_importances": [(f, float(v)) for f, v in importances],
        "n_samples": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "model_version": MODEL_VERSION,
        "label_distribution": {
            CODE_TO_LABEL[k]: int(v) for k, v in labels.value_counts().items()
        },
    }

    # scikit-learn model persistence pattern - https://scikit-learn.org/stable/model_persistence.html
    # Save the trained model to disk as a pickle file. From now on the
    # app can load this file and run predictions without retraining
    # every time it starts up.
    with MODEL_PATH.open("wb") as f:
        pickle.dump(model, f)

    return metrics


def load_model() -> RandomForestClassifier:
    """Load the pickled model. Raises FileNotFoundError if not yet trained."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No trained model at {MODEL_PATH}. "
            "Click 'Retrain model' on the About page first."
        )
    # scikit-learn model persistence pattern - https://scikit-learn.org/stable/model_persistence.html
    with MODEL_PATH.open("rb") as f:
        return pickle.load(f)


def model_exists() -> bool:
    return MODEL_PATH.exists()


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict(features_row: pd.Series | dict) -> tuple[str, float, list[tuple[str, float]]]:
    """Predict verdict + confidence + top-3 contributing features.

    ``features_row`` must contain every key in ``FEATURE_COLUMNS``.
    """
    model = load_model()
    if isinstance(features_row, dict):
        features_row = pd.Series(features_row)

    # Build a one-row dataframe with the features in the same exact
    # order the model was trained with. If a key is missing in the
    # input we default it to 0.0, so the call won't crash on partial data.
    X = pd.DataFrame([[features_row.get(c, 0.0) for c in FEATURE_COLUMNS]],
                     columns=FEATURE_COLUMNS).fillna(0.0)
    # predict_proba returns a probability for each class. We pick the
    # class with the highest probability as our verdict, and use that
    # probability itself as the confidence score shown to the user.
    proba = model.predict_proba(X)[0]
    code = int(np.argmax(proba))
    verdict = CODE_TO_LABEL[code]
    confidence = float(proba[code])

    # Also return the top 3 most important features overall. These don't
    # depend on the current input; they're a model-level property. The
    # UI attaches them next to the verdict as a quick "what mattered" hint.
    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda kv: kv[1],
        reverse=True,
    )[:3]
    return verdict, confidence, [(f, float(v)) for f, v in importances]


def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorised prediction over many rows. Returns df + verdict + confidence."""
    model = load_model()
    X = df[FEATURE_COLUMNS].fillna(0.0)
    # Calling predict_proba once with all rows at once is much faster
    # than looping in Python and calling it row by row. NumPy and
    # sklearn handle the heavy lifting in optimised C code.
    proba = model.predict_proba(X)
    codes = np.argmax(proba, axis=1)

    # Add two new columns to the dataframe: the predicted verdict
    # (as text) and the confidence (the probability the model
    # assigned to that verdict).
    out = df.copy()
    out["verdict"] = [CODE_TO_LABEL[c] for c in codes]
    out["confidence"] = proba[np.arange(len(codes)), codes]
    return out


# ---------------------------------------------------------------------------
# Retraining (user-driven)
# ---------------------------------------------------------------------------

def _load_training_frame() -> pd.DataFrame:
    """Build the labelled DataFrame the model trains on."""
    # Read every weather snapshot in the database, joined with each
    # trail's max altitude. The join gives us everything we need to
    # compute the snowline-difference feature in one query.
    rows = db_manager.get_all_weather()
    if not rows:
        raise RuntimeError(
            "No weather data in the DB. Run 'Seed historical weather' first."
        )
    df = pd.DataFrame([dict(r) for r in rows])

    # The label engine needs all of these columns to compute a label.
    # If any are missing on a row, we drop that row instead of trying
    # to label it with incomplete data.
    needed = ["temp_c", "wind_kmh", "precip_mm", "snowline_m", "trail_max_alt_m"]
    df = df.dropna(subset=needed).reset_index(drop=True)
    if df.empty:
        raise RuntimeError("No usable weather rows (all are missing key fields).")

    # Step 1: generate a starting label for every row using the rule
    # engine. This is the "bootstrap" labelling.
    df["label"] = label_engine.label_dataframe(df)

    # Step 2: if a user has actually hiked a (trail, date) and reported
    # what conditions they found, that label should win over the rule
    # engine's guess. So we merge in the user reports and use their
    # labels wherever they exist.
    # pandas docs - https://pandas.pydata.org/docs/
    # A left merge keeps every weather row. After the merge, fillna
    # leaves the rule label in place anywhere the user didn't submit
    # their own report.
    user_rows = db_manager.get_all_user_reports()
    if user_rows:
        ur = pd.DataFrame([dict(r) for r in user_rows])
        ur = ur.rename(columns={"report_date": "snapshot_date", "user_label": "label"})
        ur = ur[["trail_id", "snapshot_date", "label"]]
        df = df.merge(
            ur, on=["trail_id", "snapshot_date"], how="left", suffixes=("", "_user")
        )
        df["label"] = df["label_user"].fillna(df["label"])
        df = df.drop(columns=["label_user"])

    return df


def _persist_metrics(metrics: dict) -> None:
    """Save the training metrics to disk as JSON.

    The About page reads this file when the app first starts. Without
    it, the metrics section would be blank until the user manually
    pressed "Retrain" again. The tricky bit is that sklearn's
    classification_report mixes per-class dictionaries with a single
    top-level "accuracy" number. We handle both shapes below so the
    JSON output is clean.
    """
    # First pass: turn any numpy arrays or scalars into plain Python
    # values. numpy's tolist() does this nicely. JSON can't serialise
    # numpy types directly, so we have to convert them first.
    safe: dict = {
        k: (v.tolist() if hasattr(v, "tolist") else v)
        for k, v in metrics.items()
        if k != "classification_report"
    }
    # Second pass: classification_report mixes dictionaries (one per
    # class) with a single scalar "accuracy" value. We convert both
    # shapes here so the resulting JSON is consistent.
    safe["classification_report"] = {
        cls: ({m: float(v) for m, v in vals.items()}
              if isinstance(vals, dict) else float(vals))
        for cls, vals in metrics["classification_report"].items()
    }
    METRICS_PATH.write_text(json.dumps(safe, indent=2))


def retrain_from_db() -> dict:
    """Run the full training pipeline using the current database contents."""
    # Step by step: load and label the data, compute the derived
    # features, fit a fresh Random Forest, then save the metrics
    # for the About page to read.
    df = _load_training_frame()
    df = engineer_features(df)
    metrics = train_model(df, label_col="label")
    _persist_metrics(metrics)
    return metrics


# ---------------------------------------------------------------------------
# CLI helper - python -m ml.trail_classifier
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Retraining model from database…")
    metrics = retrain_from_db()
    print(f"Accuracy: {metrics['accuracy']:.2%}")
    print(f"Rows trained: {metrics['n_samples']}")
    print(f"Model saved to {MODEL_PATH}")
