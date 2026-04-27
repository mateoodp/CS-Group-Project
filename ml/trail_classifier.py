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

def wind_chill(temp_c: float, wind_kmh: float) -> float:
    """Standard NWS wind-chill formula (valid for T ≤ 10°C, wind ≥ 4.8 km/h).

    Returns ``temp_c`` unchanged when out of valid range.
    """
    if temp_c is None or wind_kmh is None:
        return temp_c
    if temp_c > 10.0 or wind_kmh < 4.8:
        return temp_c
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
    out = out.sort_values(["trail_id", "snapshot_date"]).reset_index(drop=True)

    out["temperature_c"] = out["temp_c"]
    out["wind_speed_kmh"] = out["wind_kmh"]
    out["precipitation_mm"] = out["precip_mm"]
    out["cloud_cover_pct"] = out["cloud_pct"]
    out["snowline_minus_trailmax"] = out["snowline_m"] - out["trail_max_alt_m"]
    out["wind_chill_index"] = [
        wind_chill(t, w) for t, w in zip(out["temp_c"], out["wind_kmh"])
    ]
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
    feats = df[FEATURE_COLUMNS].fillna(0.0)
    labels = df[label_col].map(LABEL_TO_CODE)

    if labels.nunique() < 2:
        raise ValueError(
            "Cannot train: training data only contains one class. "
            "Seed more historical weather first."
        )

    stratify = labels if labels.value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        feats, labels, test_size=0.2, random_state=42, stratify=stratify
    )

    model = RandomForestClassifier(
        n_estimators=100, max_depth=8, random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    importances = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_),
        key=lambda kv: kv[1],
        reverse=True,
    )
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

    X = pd.DataFrame([[features_row.get(c, 0.0) for c in FEATURE_COLUMNS]],
                     columns=FEATURE_COLUMNS).fillna(0.0)
    proba = model.predict_proba(X)[0]
    code = int(np.argmax(proba))
    verdict = CODE_TO_LABEL[code]
    confidence = float(proba[code])

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
    proba = model.predict_proba(X)
    codes = np.argmax(proba, axis=1)

    out = df.copy()
    out["verdict"] = [CODE_TO_LABEL[c] for c in codes]
    out["confidence"] = proba[np.arange(len(codes)), codes]
    return out


# ---------------------------------------------------------------------------
# Retraining (user-driven)
# ---------------------------------------------------------------------------

def _load_training_frame() -> pd.DataFrame:
    """Pull weather_snapshots + trail max_alt → labelled DataFrame."""
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

    df["label"] = label_engine.label_dataframe(df)

    # Override bootstrap labels with any user_reports for the same (trail, date).
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


def retrain_from_db() -> dict:
    """Full retrain using the current ``weather_snapshots`` + ``user_reports``."""
    df = _load_training_frame()
    df = engineer_features(df)
    return train_model(df, label_col="label")


# ---------------------------------------------------------------------------
# CLI helper — python -m ml.trail_classifier
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Retraining model from database…")
    metrics = retrain_from_db()
    print(f"Accuracy: {metrics['accuracy']:.2%}")
    print(f"Rows trained: {metrics['n_samples']}")
    print(f"Model saved to {MODEL_PATH}")
