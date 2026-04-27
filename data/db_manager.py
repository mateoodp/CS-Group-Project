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

SCHEMA_VERSION: int = 2  # bump whenever the schema changes (auto-migrates)

SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS schema_meta (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS trails (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    canton       TEXT    NOT NULL,
    region       TEXT    NOT NULL,           -- Alps / Pre-Alps / Jura / Mittelland
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

    Safe to call on every app start. If the persisted ``schema_meta.version``
    differs from ``SCHEMA_VERSION``, all tables are dropped and recreated
    (acceptable while the project is pre-submission; replace with a real
    migration before any data we care about lives in the DB).
    """
    with get_connection() as conn:
        _migrate_if_needed(conn)
        conn.executescript(SCHEMA_SQL)
        _stamp_version(conn)
        _seed_trails_if_empty(conn)


def _migrate_if_needed(conn: sqlite3.Connection) -> None:
    """Drop all tables if the persisted schema version is stale or missing."""
    try:
        row = conn.execute("SELECT version FROM schema_meta;").fetchone()
        current = row["version"] if row else 0
    except sqlite3.OperationalError:
        current = 0

    if current == SCHEMA_VERSION:
        return

    for tbl in ("predictions", "user_reports", "weather_snapshots",
                "trails", "schema_meta"):
        conn.execute(f"DROP TABLE IF EXISTS {tbl};")


def _stamp_version(conn: sqlite3.Connection) -> None:
    """Persist the current schema version. Idempotent."""
    conn.execute("DELETE FROM schema_meta;")
    conn.execute("INSERT INTO schema_meta (version) VALUES (?);", (SCHEMA_VERSION,))


def _seed_trails_if_empty(conn: sqlite3.Connection) -> None:
    """Populate ``trails`` from ``trails_seed.json`` if the table is empty."""
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
            (name, canton, region, difficulty, min_alt_m, max_alt_m, lat, lon, length_km)
        VALUES (:name, :canton, :region, :difficulty, :min_alt_m, :max_alt_m, :lat, :lon, :length_km);
        """,
        trails,
    )


# ---------------------------------------------------------------------------
# Public API — trails
# ---------------------------------------------------------------------------

def get_all_trails() -> list[sqlite3.Row]:
    """Return every trail, ordered alphabetically by name."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM trails ORDER BY name COLLATE NOCASE;"
        ).fetchall()


def get_trail(trail_id: int) -> Optional[sqlite3.Row]:
    """Return a single trail by id, or ``None`` if it doesn't exist."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM trails WHERE id = ?;", (trail_id,)
        ).fetchone()


def get_filtered_trails(
    cantons: Optional[list[str]] = None,
    regions: Optional[list[str]] = None,
    difficulties: Optional[list[str]] = None,
    min_length_km: Optional[float] = None,
    max_length_km: Optional[float] = None,
    min_alt_m: Optional[int] = None,
    max_alt_m: Optional[int] = None,
) -> list[sqlite3.Row]:
    """Return trails matching every supplied filter (logical AND).

    ``None`` for any filter means "don't restrict on this dimension".
    Length filters apply to ``length_km``; altitude filters apply to
    ``max_alt_m`` (the highest point of the trail) since that's what
    determines snowline exposure.
    """
    clauses: list[str] = []
    params: list = []
    if cantons:
        clauses.append(f"canton IN ({','.join('?' * len(cantons))})")
        params.extend(cantons)
    if regions:
        clauses.append(f"region IN ({','.join('?' * len(regions))})")
        params.extend(regions)
    if difficulties:
        clauses.append(f"difficulty IN ({','.join('?' * len(difficulties))})")
        params.extend(difficulties)
    if min_length_km is not None:
        clauses.append("length_km >= ?")
        params.append(min_length_km)
    if max_length_km is not None:
        clauses.append("length_km <= ?")
        params.append(max_length_km)
    if min_alt_m is not None:
        clauses.append("max_alt_m >= ?")
        params.append(min_alt_m)
    if max_alt_m is not None:
        clauses.append("max_alt_m <= ?")
        params.append(max_alt_m)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT * FROM trails {where} ORDER BY name COLLATE NOCASE;",
            params,
        ).fetchall()


def get_trail_metadata() -> dict:
    """Return distinct values for each filterable dimension.

    Used by the sidebar to populate its multiselects without hard-coding
    canton lists.
    """
    with get_connection() as conn:
        cantons = [r[0] for r in conn.execute(
            "SELECT DISTINCT canton FROM trails ORDER BY canton;"
        ).fetchall()]
        regions = [r[0] for r in conn.execute(
            "SELECT DISTINCT region FROM trails ORDER BY region;"
        ).fetchall()]
        difficulties = [r[0] for r in conn.execute(
            "SELECT DISTINCT difficulty FROM trails ORDER BY difficulty;"
        ).fetchall()]
        bounds = conn.execute(
            "SELECT MIN(length_km), MAX(length_km), "
            "MIN(max_alt_m), MAX(max_alt_m) FROM trails;"
        ).fetchone()
    return {
        "cantons": cantons,
        "regions": regions,
        "difficulties": difficulties,
        "min_length_km": float(bounds[0] or 0),
        "max_length_km": float(bounds[1] or 0),
        "min_max_alt_m": int(bounds[2] or 0),
        "max_max_alt_m": int(bounds[3] or 0),
    }


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
    """Insert or update a weather snapshot for ``(trail_id, snapshot_date)``."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO weather_snapshots
                (trail_id, snapshot_date, temp_c, wind_kmh, precip_mm,
                 snowline_m, cloud_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trail_id, snapshot_date) DO UPDATE SET
                temp_c     = excluded.temp_c,
                wind_kmh   = excluded.wind_kmh,
                precip_mm  = excluded.precip_mm,
                snowline_m = excluded.snowline_m,
                cloud_pct  = excluded.cloud_pct;
            """,
            (
                trail_id,
                snapshot_date.isoformat() if isinstance(snapshot_date, date) else snapshot_date,
                temp_c,
                wind_kmh,
                precip_mm,
                snowline_m,
                cloud_pct,
            ),
        )


def upsert_weather_snapshots_bulk(rows: list[dict]) -> None:
    """Bulk upsert. Each row dict needs the same keys as ``upsert_weather_snapshot``."""
    if not rows:
        return
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO weather_snapshots
                (trail_id, snapshot_date, temp_c, wind_kmh, precip_mm,
                 snowline_m, cloud_pct)
            VALUES (:trail_id, :snapshot_date, :temp_c, :wind_kmh, :precip_mm,
                    :snowline_m, :cloud_pct)
            ON CONFLICT(trail_id, snapshot_date) DO UPDATE SET
                temp_c     = excluded.temp_c,
                wind_kmh   = excluded.wind_kmh,
                precip_mm  = excluded.precip_mm,
                snowline_m = excluded.snowline_m,
                cloud_pct  = excluded.cloud_pct;
            """,
            rows,
        )


def get_weather_history(trail_id: int, days: int = 730) -> list[sqlite3.Row]:
    """Return the last ``days`` of weather snapshots for a trail (oldest first)."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM weather_snapshots
            WHERE trail_id = ?
            ORDER BY snapshot_date DESC
            LIMIT ?;
            """,
            (trail_id, days),
        ).fetchall()[::-1]


def get_all_weather() -> list[sqlite3.Row]:
    """Return every weather snapshot joined with its trail's max altitude."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT ws.*, t.max_alt_m AS trail_max_alt_m, t.name AS trail_name
            FROM weather_snapshots ws
            JOIN trails t ON t.id = ws.trail_id
            ORDER BY ws.trail_id, ws.snapshot_date;
            """
        ).fetchall()


def get_weather_for_date(
    trail_id: int, snapshot_date: date
) -> Optional[sqlite3.Row]:
    """Return the weather snapshot for a single day, if cached."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM weather_snapshots WHERE trail_id = ? AND snapshot_date = ?;",
            (trail_id, snapshot_date.isoformat() if isinstance(snapshot_date, date) else snapshot_date),
        ).fetchone()


def get_latest_snapshot_age_hours(trail_id: int) -> Optional[float]:
    """How many hours ago was the most recent ``snapshot_date`` for this trail?

    Returns ``None`` if there are no rows. Compares against the current date
    (snapshot_date is daily, so resolution is 24h, but we compute the gap
    relative to *today* to drive cache invalidation).
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(snapshot_date) AS latest
            FROM weather_snapshots
            WHERE trail_id = ?;
            """,
            (trail_id,),
        ).fetchone()
    if row is None or row["latest"] is None:
        return None
    latest = datetime.fromisoformat(row["latest"]).date()
    delta = (date.today() - latest).days
    return max(delta, 0) * 24.0


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
    """
    if user_label not in {"SAFE", "BORDERLINE", "AVOID"}:
        raise ValueError(f"Invalid user_label: {user_label!r}")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_reports (trail_id, report_date, user_label, comment)
            VALUES (?, ?, ?, ?);
            """,
            (
                trail_id,
                report_date.isoformat() if isinstance(report_date, date) else report_date,
                user_label,
                comment,
            ),
        )


def get_recent_user_reports(limit: int = 20) -> list[sqlite3.Row]:
    """Return the N most recent user reports for the live feed."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT ur.*, t.name AS trail_name
            FROM user_reports ur
            JOIN trails t ON t.id = ur.trail_id
            ORDER BY ur.created_at DESC
            LIMIT ?;
            """,
            (limit,),
        ).fetchall()


def get_all_user_reports() -> list[sqlite3.Row]:
    """Return every user report — used when retraining the model."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM user_reports ORDER BY created_at DESC;"
        ).fetchall()


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
    """Append a row to ``predictions`` for auditing / monitoring."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO predictions
                (trail_id, prediction_date, verdict, confidence,
                 top_features, model_version)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                trail_id,
                prediction_date.isoformat() if isinstance(prediction_date, date) else prediction_date,
                verdict,
                float(confidence),
                json.dumps(top_features),
                model_version,
            ),
        )


# ---------------------------------------------------------------------------
# CLI helper — so teammates can run: python -m data.db_manager
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Setting up database at: {DB_PATH}")
    setup_db()
    print("✓ Database ready.")
