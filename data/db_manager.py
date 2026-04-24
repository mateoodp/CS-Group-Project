"""SQLite database manager for the Hiking Forecaster.

Owner: TM2 (Database Lead)

All SQL lives here. Other modules must **never** execute raw SQL directly —
they call the functions in this module. This keeps the schema in one place
and makes testing easy.

Database: ``hiking_app.db`` (single file, created on first run).

Tables (see Section 3 of the product report for full schema):
    * ``trails``           — master list of 20 pre-loaded Swiss routes.
    * ``weather_snapshots`` — cached/live weather per trail per day.
    * ``user_reports``     — user-submitted ground-truth labels.
    * ``predictions``      — logged ML outputs (audit trail).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Paths & connection helpers
# ---------------------------------------------------------------------------

DB_PATH: Path = Path(__file__).resolve().parent.parent / "hiking_app.db"
TRAILS_SEED_PATH: Path = Path(__file__).resolve().parent / "trails_seed.json"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with sensible defaults.

    Use as a context manager::

        with get_connection() as conn:
            conn.execute(...)

    Enables foreign keys and returns rows as ``sqlite3.Row`` (dict-like).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema & bootstrap
# ---------------------------------------------------------------------------

SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS trails (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    canton       TEXT    NOT NULL,
    difficulty   TEXT    NOT NULL,           -- T1..T6 (SAC scale)
    min_alt_m    INTEGER NOT NULL,
    max_alt_m    INTEGER NOT NULL,
    lat          REAL    NOT NULL,
    lon          REAL    NOT NULL,
    length_km    REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS weather_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    trail_id       INTEGER NOT NULL,
    snapshot_date  TEXT    NOT NULL,         -- ISO YYYY-MM-DD
    temp_c         REAL,
    wind_kmh       REAL,
    precip_mm      REAL,
    snowline_m     REAL,
    cloud_pct      REAL,
    UNIQUE (trail_id, snapshot_date),
    FOREIGN KEY (trail_id) REFERENCES trails(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trail_id     INTEGER NOT NULL,
    report_date  TEXT    NOT NULL,
    user_label   TEXT    NOT NULL CHECK (user_label IN ('SAFE','BORDERLINE','AVOID')),
    comment      TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (trail_id) REFERENCES trails(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    trail_id         INTEGER NOT NULL,
    prediction_date  TEXT    NOT NULL,
    verdict          TEXT    NOT NULL CHECK (verdict IN ('SAFE','BORDERLINE','AVOID')),
    confidence       REAL    NOT NULL,       -- 0..1
    top_features     TEXT,                   -- JSON list of (feature, importance)
    model_version    TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (trail_id) REFERENCES trails(id) ON DELETE CASCADE
);
"""


def setup_db() -> None:
    """Create all tables (if missing) and seed the ``trails`` table once.

    Safe to call on every app start — uses ``CREATE TABLE IF NOT EXISTS`` and
    only seeds when the trails table is empty.
    """
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        _seed_trails_if_empty(conn)


def _seed_trails_if_empty(conn: sqlite3.Connection) -> None:
    """Populate ``trails`` from ``trails_seed.json`` if the table is empty.

    TODO (TM2): decide whether to also seed ``weather_snapshots`` with a few
    demo rows so the app renders something on first launch without needing
    a network call.
    """
    count = conn.execute("SELECT COUNT(*) FROM trails;").fetchone()[0]
    if count > 0:
        return

    if not TRAILS_SEED_PATH.exists():
        raise FileNotFoundError(f"Seed file missing: {TRAILS_SEED_PATH}")

    with TRAILS_SEED_PATH.open(encoding="utf-8") as f:
        trails = json.load(f)

    conn.executemany(
        """
        INSERT INTO trails
            (name, canton, difficulty, min_alt_m, max_alt_m, lat, lon, length_km)
        VALUES (:name, :canton, :difficulty, :min_alt_m, :max_alt_m, :lat, :lon, :length_km);
        """,
        trails,
    )


# ---------------------------------------------------------------------------
# Public API — trails
# ---------------------------------------------------------------------------

def get_all_trails() -> list[sqlite3.Row]:
    """Return every trail, ordered alphabetically by name.

    TODO (TM2): implement.
    """
    raise NotImplementedError


def get_trail(trail_id: int) -> Optional[sqlite3.Row]:
    """Return a single trail by id, or ``None`` if it doesn't exist.

    TODO (TM2): implement.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Public API — weather snapshots
# ---------------------------------------------------------------------------

def upsert_weather_snapshot(
    trail_id: int,
    snapshot_date: date,
    temp_c: float,
    wind_kmh: float,
    precip_mm: float,
    snowline_m: float,
    cloud_pct: float,
) -> None:
    """Insert or update a weather snapshot for ``(trail_id, snapshot_date)``.

    TODO (TM2): implement using INSERT ... ON CONFLICT(trail_id, snapshot_date)
    DO UPDATE SET ...
    """
    raise NotImplementedError


def get_weather_history(trail_id: int, days: int = 730) -> list[sqlite3.Row]:
    """Return the last ``days`` of weather snapshots for a trail.

    Used by the ML training loop (default 2 years).

    TODO (TM2): implement.
    """
    raise NotImplementedError


def get_weather_for_date(
    trail_id: int, snapshot_date: date
) -> Optional[sqlite3.Row]:
    """Return the weather snapshot for a single day, if cached.

    TODO (TM2): implement.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Public API — user reports
# ---------------------------------------------------------------------------

def insert_user_report(
    trail_id: int,
    report_date: date,
    user_label: str,
    comment: str = "",
) -> None:
    """Store a user-submitted ground-truth label.

    ``user_label`` must be one of ``"SAFE"``, ``"BORDERLINE"``, ``"AVOID"``.

    TODO (TM5): implement.
    """
    raise NotImplementedError


def get_recent_user_reports(limit: int = 20) -> list[sqlite3.Row]:
    """Return the N most recent user reports for the live feed.

    TODO (TM5): implement.
    """
    raise NotImplementedError


def get_all_user_reports() -> list[sqlite3.Row]:
    """Return every user report — used when retraining the model.

    TODO (TM4): implement.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Public API — predictions (audit trail)
# ---------------------------------------------------------------------------

def log_prediction(
    trail_id: int,
    prediction_date: date,
    verdict: str,
    confidence: float,
    top_features: list[tuple[str, float]],
    model_version: str,
) -> None:
    """Append a row to ``predictions`` for auditing / monitoring.

    TODO (TM4): implement. Serialise ``top_features`` as JSON.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# CLI helper — so teammates can run: python -m data.db_manager
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Setting up database at: {DB_PATH}")
    setup_db()
    print("✓ Database ready.")
