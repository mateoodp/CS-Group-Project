"""Smoke tests — run with ``pytest``. Owner: TM2.

These are intentionally tiny. They verify that:

* modules import cleanly,
* constants are sane,
* the DB setup creates all 4 tables.

Real unit tests (e.g. for label_engine rules and ML predict) go in dedicated
``test_<module>.py`` files as features are implemented.
"""

from __future__ import annotations

import sqlite3

from utils import constants


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

def test_imports() -> None:
    """All top-level modules import without side effects."""
    from data import db_manager, label_engine, weather_fetcher  # noqa: F401
    from ml import trail_classifier  # noqa: F401


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_verdict_colours_complete() -> None:
    assert set(constants.VERDICT_COLOURS.keys()) == {"SAFE", "BORDERLINE", "AVOID"}


def test_risk_slider_bounds() -> None:
    assert constants.RISK_SLIDER_MIN < constants.DEFAULT_RISK_TOLERANCE < constants.RISK_SLIDER_MAX + 1


def test_contribution_matrix_rows() -> None:
    # 16 rows matches the product report.
    assert len(constants.CONTRIBUTION_MATRIX) == 16
    allowed = {"L", "M", "S", "—"}
    for row in constants.CONTRIBUTION_MATRIX:
        for member in ("TM1", "TM2", "TM3", "TM4", "TM5"):
            assert row[member] in allowed, f"Unexpected value: {row[member]!r}"


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def test_setup_db_creates_tables(tmp_path, monkeypatch) -> None:
    """``setup_db`` should create all 4 tables and seed trails."""
    from data import db_manager

    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db_manager, "DB_PATH", test_db)

    db_manager.setup_db()

    with sqlite3.connect(test_db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        }

    assert {"trails", "weather_snapshots", "user_reports", "predictions"} <= tables

    with sqlite3.connect(test_db) as conn:
        n_trails = conn.execute("SELECT COUNT(*) FROM trails").fetchone()[0]
    assert n_trails == 20, "Expected 20 seeded trails"
