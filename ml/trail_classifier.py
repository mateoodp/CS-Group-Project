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

from __future__ import annotations

import pickle
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

MODEL_PATH: Path = Path(__file__).resolve().parent / "model.pkl"
MODEL_VERSION: str = "0.1.0-dev"

# Feature order MUST be stable — changing it invalidates the saved model.
FEATURE_COLUMNS: list[str] = [
    "temperature_c",
    "wind_speed_kmh",
    "precipitation_mm",
    "snowline_minus_trailmax",
    "wind_chill_index",
    "cloud_cover_pct",
    "precip_7day_rolling",
]

LABEL_TO_CODE: dict[str, int] = {"SAFE": 0, "BORDERLINE": 1, "AVOID": 2}
CODE_TO_LABEL: dict[int, str] = {v: k for k, v in LABEL_TO_CODE.items()}


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived features expected by the model.

    Required input columns:
        temp_c, wind_kmh, precip_mm, snowline_m, cloud_pct, trail_max_alt_m,
        snapshot_date

    Adds the columns in ``FEATURE_COLUMNS`` that aren't already present:
        * ``snowline_minus_trailmax`` = snowline_m − trail_max_alt_m
        * ``wind_chill_index``       = standard NWS wind-chill formula
        * ``precip_7day_rolling``    = rolling sum per trail_id

    TODO (TM5): implement. Use ``df.groupby('trail_id')`` for the rolling sum.
    """
    raise NotImplementedError


def wind_chill(temp_c: float, wind_kmh: float) -> float:
    """Standard NWS wind-chill formula (valid for T ≤ 10°C, wind ≥ 4.8 km/h).

    Returns ``temp_c`` unchanged when the formula is out of its valid range —
    wind chill is only meaningful in cold, windy conditions.

    TODO (TM5): implement.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_model(df: pd.DataFrame, label_col: str = "label") -> dict:
    """Train the Random Forest and persist it to ``MODEL_PATH``.

    Returns a metrics dict::

        {
            "accuracy": 0.87,
            "confusion_matrix": [[...]],
            "classification_report": {...},
            "feature_importances": [("wind_speed_kmh", 0.23), ...],
            "n_samples": 14600,
            "model_version": "0.1.0-dev",
        }

    TODO (TM4): implement steps 4–7 from the module docstring.
    """
    raise NotImplementedError


def load_model() -> RandomForestClassifier:
    """Load the pickled model. Raises FileNotFoundError if not yet trained.

    TODO (TM4): implement.
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No trained model at {MODEL_PATH}. "
            "Run `python -m ml.trail_classifier` first."
        )
    with MODEL_PATH.open("rb") as f:
        return pickle.load(f)


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict(features_row: pd.Series | dict) -> tuple[str, float, list[tuple[str, float]]]:
    """Predict verdict + confidence + top-3 contributing features.

    Args:
        features_row: a mapping with keys from ``FEATURE_COLUMNS``.

    Returns:
        (verdict, confidence, top_features)
        - verdict: one of "SAFE", "BORDERLINE", "AVOID"
        - confidence: predicted class probability (0..1)
        - top_features: list of up to 3 (feature_name, importance) pairs

    TODO (TM4): implement. Use ``model.predict_proba`` and
    ``model.feature_importances_``.
    """
    raise NotImplementedError


def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorised prediction over many rows. Returns df + verdict + confidence.

    TODO (TM4): implement.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Retraining (user-driven)
# ---------------------------------------------------------------------------

def retrain_from_db() -> dict:
    """Full retrain using the current ``weather_snapshots`` + ``user_reports``.

    1. Pull weather history from the DB.
    2. Pull user reports — these override / enrich bootstrap labels.
    3. Run ``engineer_features`` and ``train_model``.
    4. Return the metrics dict for display in the About tab.

    TODO (TM4): implement.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# CLI helper — python -m ml.trail_classifier
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Retraining model from database…")
    metrics = retrain_from_db()
    print(f"Accuracy: {metrics['accuracy']:.2%}")
    print(f"Model saved to {MODEL_PATH}")
