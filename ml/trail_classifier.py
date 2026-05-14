"""Random Forest trail safety classifier.

Owner: TM4 (ML Lead) · Support: TM5 (Feature Engineering)

Pipeline (see Section 4 of the product report):

    STEP 1 — Load data     : JOIN weather_snapshots + labels from label_engine
    STEP 2 — Feature eng   : derive wind_chill, snowline_delta, 7-day precip
    STEP 3 — Encode labels : {SAFE:0, BORDERLINE:1, AVOID:2}
    STEP 4 — Train/test    : stratified 80/20 split
    STEP 5 — Train         : RandomForestClassifier(n_estimators=100, max_depth=8)
    STEP 6 — Evaluate      : accuracy, confusion matrix, classification report
    STEP 7 — Save          : pickle to ml/model.pkl
    STEP 8 — Predict       : model.predict_proba → verdict + confidence
    STEP 9 — Feature imp.  : model.feature_importances_ → bar chart in About tab

Why Random Forest? Non-linear interactions (cold + wind = hypothermia),
robust to missing values, native probability output, interpretable, and
beginner-friendly to defend in the Q&A.
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

# Feature order MUST be stable - changing it invalidates the saved model.
# Each feature: raw inputs (temperature, wind, precipitation, cloud), plus
# three engineered ones (snowline delta, wind-chill, 7-day rolling precip).
FEATURE_COLUMNS: list[str] = [
    "temperature_c",
    "wind_speed_kmh",
    "precipitation_mm",
    "snowline_minus_trailmax",
    "wind_chill_index",
    "cloud_cover_pct",
    "precip_7day_rolling",
]

# Manual label encoding (kept explicit rather than using sklearn's LabelEncoder
# because the mapping must remain stable across retrains).
LABEL_TO_CODE: dict[str, int] = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}
CODE_TO_LABEL: dict[int, str] = {v: k for k, v in LABEL_TO_CODE.items()}


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def wind_chill(temp_c: float, wind_kmh: float) -> float:
    """Standard NWS wind-chill formula (valid for T ≤ 10°C, wind ≥ 4.8 km/h).

    Returns ``temp_c`` unchanged when out of valid range.
    """
    if temp_c is None or wind_kmh is None:
        return temp_c
    # Outside the formula's valid domain, returning the raw temperature is the
    # documented NWS guidance (and avoids producing misleadingly cold numbers).
    if temp_c > 10.0 or wind_kmh < 4.8:
        return temp_c
    # Standard NWS coefficients; v is wind speed raised to the 0.16 power.
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
    # Sort by (trail, date) so the rolling-window calculation below is monotone.
    out = out.sort_values(["trail_id", "snapshot_date"]).reset_index(drop=True)

    # Rename the raw columns into the canonical feature names used by the model.
    out["temperature_c"] = out["temp_c"]
    out["wind_speed_kmh"] = out["wind_kmh"]
    out["precipitation_mm"] = out["precip_mm"]
    out["cloud_cover_pct"] = out["cloud_pct"]
    # Snowline delta: positive means snowline is above the summit (safer).
    out["snowline_minus_trailmax"] = out["snowline_m"] - out["trail_max_alt_m"]
    # Wind-chill captures the cold + wind interaction the rules cannot model alone.
    out["wind_chill_index"] = [
        wind_chill(t, w) for t, w in zip(out["temp_c"], out["wind_kmh"])
    ]
    # pandas docs - https://pandas.pydata.org/docs/
    # Per-trail 7-day rolling sum of precipitation proxies for ground saturation.
    # min_periods=1 keeps early days from becoming NaN.
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
    # NaN imputation: tree models are not NaN-tolerant in sklearn by default,
    # so we replace missing measurements with 0.0 before fitting.
    feats = df[FEATURE_COLUMNS].fillna(0.0)
    labels = df[label_col].map(LABEL_TO_CODE)

    # The model needs at least two classes to learn anything.
    if labels.nunique() < 2:
        raise ValueError(
            "Cannot train: training data only contains one class. "
            "Seed more historical weather first."
        )

    # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
    # Stratify only when every class has >= 2 samples, otherwise sklearn errors.
    stratify = labels if labels.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        feats, labels, test_size=0.2, random_state=42, stratify=stratify
    )

    # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
    # 100 trees with depth 8 is a good accuracy/interpretability trade-off for
    # this dataset size; n_jobs=-1 parallelises across all available cores.
    model = RandomForestClassifier(
        n_estimators=100, max_depth=8, random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # Rank features by Gini importance so the About page can show what matters.
    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda kv: kv[1],
        reverse=True,
    )
    # Adapted from scikit-learn docs - https://scikit-learn.org/stable/
    # Evaluation bundle: overall accuracy, full confusion matrix, and the
    # per-class precision/recall/F1 report. All serialised to JSON later.
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
    # Save the fitted estimator so the app can predict without retraining on every load.
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

    # Build a single-row DataFrame in the exact FEATURE_COLUMNS order; missing
    # keys default to 0.0 so the call cannot crash on partial inputs.
    X = pd.DataFrame([[features_row.get(c, 0.0) for c in FEATURE_COLUMNS]],
                     columns=FEATURE_COLUMNS).fillna(0.0)
    # predict_proba returns class probabilities; we report the argmax as verdict
    # and its probability as the confidence score shown in the UI.
    proba = model.predict_proba(X)[0]
    code = int(np.argmax(proba))
    verdict = CODE_TO_LABEL[code]
    confidence = float(proba[code])

    # Top-3 features by global importance, attached to every prediction so the
    # UI can display "why" alongside the verdict.
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
    # One predict_proba call for all rows is far cheaper than looping per-row.
    proba = model.predict_proba(X)
    codes = np.argmax(proba, axis=1)

    # Attach the verdict label and its associated probability back onto the frame.
    out = df.copy()
    out["verdict"] = [CODE_TO_LABEL[c] for c in codes]
    out["confidence"] = proba[np.arange(len(codes)), codes]
    return out


# ---------------------------------------------------------------------------
# Retraining (user-driven)
# ---------------------------------------------------------------------------

def _load_training_frame() -> pd.DataFrame:
    """Pull weather_snapshots + trail max_alt → labelled DataFrame."""
    # Pull every cached snapshot joined with the trail's max altitude.
    rows = db_manager.get_all_weather()
    if not rows:
        raise RuntimeError(
            "No weather data in the DB. Run 'Seed historical weather' first."
        )
    df = pd.DataFrame([dict(r) for r in rows])

    # Drop any rows missing the variables the labeller needs.
    needed = ["temp_c", "wind_kmh", "precip_mm", "snowline_m", "trail_max_alt_m"]
    df = df.dropna(subset=needed).reset_index(drop=True)
    if df.empty:
        raise RuntimeError("No usable weather rows (all are missing key fields).")

    # Step 1: bootstrap labels via the rule engine over the entire frame.
    df["label"] = label_engine.label_dataframe(df)

    # Step 2: override bootstrap labels with any user_reports for the same (trail, date).
    # pandas docs - https://pandas.pydata.org/docs/
    # Left-merge keeps every weather row, then fillna lets user labels win where they exist.
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
    """Write ``metrics`` to :data:`METRICS_PATH` as JSON, normalising numpy types.

    The About page reads this on cold start so the metrics section is
    populated without forcing every fresh app load to retrain.
    ``classification_report`` from sklearn nests both per-class dicts and
    a top-level ``accuracy`` scalar — both branches are handled here.
    """
    # First pass: convert any numpy arrays/scalars to plain Python (tolist).
    safe: dict = {
        k: (v.tolist() if hasattr(v, "tolist") else v)
        for k, v in metrics.items()
        if k != "classification_report"
    }
    # Second pass: classification_report has both per-class dicts and a scalar
    # "accuracy" key, so we handle both shapes explicitly.
    safe["classification_report"] = {
        cls: ({m: float(v) for m, v in vals.items()}
              if isinstance(vals, dict) else float(vals))
        for cls, vals in metrics["classification_report"].items()
    }
    METRICS_PATH.write_text(json.dumps(safe, indent=2))


def retrain_from_db() -> dict:
    """Full retrain using the current ``weather_snapshots`` + ``user_reports``."""
    # End-to-end pipeline: load + label, engineer features, fit, persist metrics.
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
