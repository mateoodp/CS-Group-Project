"""SQLite database manager for the Hiking Forecaster.

Owner: TM2 (Database Lead)

Every piece of SQL in the project lives in this one file. The rest of
the app never writes raw SQL. Instead, it calls the helper functions
below. Keeping all the SQL together makes the schema easy to update
and makes the code easier to test.

The database is a single file called ``hiking_app.db``. It gets created
automatically the first time the app starts.

Tables (full schema is in Section 3 of the product report):
    * trails: master list of pre-loaded Swiss routes (about 20 of them).
    * weather_snapshots: one row per (trail, date) with the weather.
    * user_reports: real labels submitted by users after a hike.
    * predictions: log of every model prediction (for auditing).
"""

# =============================================================================
# Source attribution
# -----------------------------------------------------------------------------
# Built with Claude (Anthropic) AI assistance during development.
# External sources are cited inline above the relevant code blocks.
# =============================================================================

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Paths & connection helpers
# ---------------------------------------------------------------------------

import os
# Work out where to save the database file. If the app is running on
# Streamlit Community Cloud (where the home directory is /home/appuser),
# only the /tmp folder is reliably writable, so we put the file there.
# When developing locally we keep it next to the repo root so it's easy
# to open with a database tool for inspection.
DB_PATH: Path = (Path("/tmp/hiking_app.db")
    if os.getenv("HOME") == "/home/appuser"
    else Path(__file__).resolve().parent.parent / "hiking_app.db")
TRAILS_SEED_PATH: Path = Path(__file__).resolve().parent / "trails_seed.json"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a database connection with the settings the app expects.

    Use this with a ``with`` block, like so::

        with get_connection() as conn:
            conn.execute(...)

    On entering the block we open the connection and configure it. On
    exiting the block we automatically commit any changes and close
    the connection. We also turn on foreign key enforcement and tell
    SQLite to return rows that work like dictionaries (so we can do
    ``row["name"]`` instead of ``row[0]``).
    """
    # Python sqlite3 stdlib - https://docs.python.org/3/library/sqlite3.html
    conn = sqlite3.connect(DB_PATH)
    # Row factory means every row supports both row[0] and row["column"]
    # access. The dictionary-style access is much easier to read.
    conn.row_factory = sqlite3.Row
    # SQLite has foreign key support but it's turned off by default.
    # We enable it per-connection so deletes cascade correctly.
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        # If the code in the ``with`` block finished without raising,
        # we commit the changes. The finally block always runs and
        # closes the connection so we never leak resources.
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema & bootstrap
# ---------------------------------------------------------------------------

SCHEMA_VERSION: int = 3  # bump whenever the schema OR seed catalogue changes

# Python sqlite3 stdlib - https://docs.python.org/3/library/sqlite3.html
# CREATE TABLE statements for the four real tables, plus a tiny extra
# table called schema_meta that records the schema version. Using
# CREATE TABLE IF NOT EXISTS means we can run this script over and over
# safely; it only creates a table the first time.
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
    """Get the database ready: create tables and seed initial trail list.

    Safe to call every time the app starts up. If the version stored
    in the database does not match SCHEMA_VERSION at the top of this
    file, we drop every table and rebuild from scratch. That's fine for
    a student project, but in a real product we'd write proper
    migration scripts instead.
    """
    with get_connection() as conn:
        # 1. Drop any stale tables. 2. Recreate them all. 3. Stamp the
        # new schema version. 4. Load the trail catalogue if the
        # trails table is empty.
        _migrate_if_needed(conn)
        conn.executescript(SCHEMA_SQL)
        _stamp_version(conn)
        _seed_trails_if_empty(conn)


def _migrate_if_needed(conn: sqlite3.Connection) -> None:
    """If the stored schema version is out of date, drop every table."""
    # Look up the version saved in schema_meta. If the table itself
    # doesn't exist yet (very first run of the app), the SELECT will
    # raise and we treat it as version 0, which forces a fresh build.
    try:
        row = conn.execute("SELECT version FROM schema_meta;").fetchone()
        current = row["version"] if row else 0
    except sqlite3.OperationalError:
        current = 0

    if current == SCHEMA_VERSION:
        return

    # We drop tables in reverse order of their dependencies. This is
    # because foreign keys would block us from dropping a "parent"
    # table while child tables still reference it.
    for tbl in ("predictions", "user_reports", "weather_snapshots",
                "trails", "schema_meta"):
        conn.execute(f"DROP TABLE IF EXISTS {tbl};")


def _stamp_version(conn: sqlite3.Connection) -> None:
    """Save the current schema version to the database. Safe to call repeatedly."""
    # We delete whatever was there before and insert a fresh row. That
    # way the schema_meta table always holds exactly one row, with the
    # current version number.
    conn.execute("DELETE FROM schema_meta;")
    conn.execute("INSERT INTO schema_meta (version) VALUES (?);", (SCHEMA_VERSION,))


def _seed_trails_if_empty(conn: sqlite3.Connection) -> None:
    """Fill the trails table from the seed JSON file (only if it's empty)."""
    # First we count the existing rows. If there are any, we skip the
    # load so the app never accidentally inserts duplicate trails across
    # restarts.
    count = conn.execute("SELECT COUNT(*) FROM trails;").fetchone()[0]
    if count > 0:
        return

    if not TRAILS_SEED_PATH.exists():
        raise FileNotFoundError(f"Seed file missing: {TRAILS_SEED_PATH}")

    with TRAILS_SEED_PATH.open(encoding="utf-8") as f:
        trails = json.load(f)

    # Python sqlite3 stdlib - https://docs.python.org/3/library/sqlite3.html
    # executemany loops over the trail list and runs the INSERT once per
    # entry, but in a single round-trip to the database. Much faster than
    # calling execute() in a Python loop.
    conn.executemany(
        """
        INSERT INTO trails
            (name, canton, region, difficulty, min_alt_m, max_alt_m, lat, lon, length_km)
        VALUES (:name, :canton, :region, :difficulty, :min_alt_m, :max_alt_m, :lat, :lon, :length_km);
        """,
        trails,
    )


# ---------------------------------------------------------------------------
# Public API - trails
# ---------------------------------------------------------------------------

def get_all_trails() -> list[sqlite3.Row]:
    """Return every trail, ordered alphabetically by name."""
    with get_connection() as conn:
        # COLLATE NOCASE sorts the names case-insensitively. This way a
        # trail starting with "Ä" appears next to one starting with "A",
        # which is what a user would expect alphabetically.
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
    """Return only the trails that match every filter the caller passed.

    Each filter is optional. Passing ``None`` for a filter means "don't
    restrict on this column". The filters are combined with AND, so a
    trail has to match all of them to be returned.

    The length filters work on the ``length_km`` column. The altitude
    filters work on ``max_alt_m`` (the trail's highest point), because
    that's the altitude that matters most for snowline exposure.
    """
    # We build the WHERE clause piece by piece based on which filters
    # were passed. We use parameter binding (the "?" placeholders) for
    # every value, which is the safe way to add user input to SQL
    # without opening ourselves up to SQL injection attacks.
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

    # Stick all the clauses together with AND. If the user gave no
    # filters at all, the WHERE part stays empty and we return every
    # trail in the database.
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT * FROM trails {where} ORDER BY name COLLATE NOCASE;",
            params,
        ).fetchall()


def get_trail_metadata() -> dict:
    """Return the unique values for each filter on the Find page.

    Pages use this to populate their dropdowns and sliders. We pull
    the values straight from the database so the controls always match
    the actual trail catalogue. That way we don't have to hand-code
    canton lists or worry about them going out of sync.
    """
    with get_connection() as conn:
        # We run one DISTINCT query for each list-style filter, and one
        # MIN/MAX query for the numeric slider ranges. Splitting it into
        # several small queries is cheap on a 20-row table and easier
        # to read than cramming everything into one mega-query.
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
# Public API - weather snapshots
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
        # SQLite supports an "UPSERT" pattern: try to INSERT, and if a
        # row with the same (trail_id, snapshot_date) already exists,
        # UPDATE its values instead. This way the caller doesn't have to
        # check "does this row exist?" before deciding what SQL to run.
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
        # Python sqlite3 stdlib - https://docs.python.org/3/library/sqlite3.html
        # executemany lets us run the same SQL statement many times in
        # one call. We use named parameters (the :name style) so the
        # field names line up with the dict keys. This is the path used
        # to seed historical weather: roughly 730 rows per trail.
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
        # We query in DESC order with a LIMIT so SQLite can use the
        # date column to find the newest rows quickly. Then we reverse
        # the list in Python ([::-1]) so the caller gets the dates in
        # chronological order (oldest first), which is what charts expect.
        return conn.execute(
            """
            SELECT * FROM weather_snapshots
            WHERE trail_id = ?
            ORDER BY snapshot_date DESC
            LIMIT ?;
            """,
            (trail_id, days),
        ).fetchall()[::-1]


def get_weather_history_range(trail_id: int, start_date, end_date) -> list[dict]:
    """Return weather snapshots between two dates (inclusive), oldest first."""
    # The caller might pass real Python date objects, or already-formatted
    # ISO date strings. We handle both. ``hasattr(x, "isoformat")`` is
    # True for date objects but False for strings.
    start_iso = start_date.isoformat() if hasattr(start_date, "isoformat") else start_date
    end_iso = end_date.isoformat() if hasattr(end_date, "isoformat") else end_date
    with get_connection() as conn:
        # SQL BETWEEN is inclusive on both ends (it includes both the
        # start and end values), which is exactly what the docstring promises.
        rows = conn.execute(
            """
            SELECT * FROM weather_snapshots
            WHERE trail_id = ? AND snapshot_date BETWEEN ? AND ?
            ORDER BY snapshot_date ASC;
            """,
            (trail_id, start_iso, end_iso),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_weather() -> list[sqlite3.Row]:
    """Return every weather snapshot joined with its trail's max altitude."""
    with get_connection() as conn:
        # We JOIN the weather rows against the trails table so each
        # weather row also includes the trail's max altitude. That way
        # the ML training pipeline can compute its "snowline minus
        # trail max" feature from this one query alone.
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


def get_all_snapshots_for_date(snapshot_date) -> dict[int, dict]:
    """Return ``{trail_id: snapshot_row}`` for every trail on one date.

    This is a single JOIN query, so it replaces the slow pattern of
    calling get_weather_for_date inside a loop. Pages that need
    verdicts for many trails at once (like the Map overview) use this.
    Each value is a plain dictionary that also includes the trail's
    max altitude, so callers don't need to make a second query just
    to compute the snowline difference.
    """
    iso = (
        snapshot_date.isoformat()
        if hasattr(snapshot_date, "isoformat")
        else snapshot_date
    )
    with get_connection() as conn:
        # One JOIN query covers every trail for the chosen day. Compared
        # to running get_weather_for_date inside a Python loop, this is
        # much faster on a page that needs verdicts for hundreds of trails.
        rows = conn.execute(
            """
            SELECT ws.*, t.max_alt_m
            FROM weather_snapshots ws
            JOIN trails t ON t.id = ws.trail_id
            WHERE ws.snapshot_date = ?;
            """,
            (iso,),
        ).fetchall()
    return {r["trail_id"]: dict(r) for r in rows}


def get_latest_snapshot_age_hours(trail_id: int) -> Optional[float]:
    """Return how old (in hours) the freshest weather row for a trail is.

    Returns ``None`` if no weather has been cached yet for this trail.
    Our snapshots are stored once per day, so the resolution is 24 hours.
    We compare against today's date, which is what the cache logic uses
    to decide whether to fetch fresh data from the API.
    """
    with get_connection() as conn:
        # We can take MAX of the date column even though it's stored as
        # a string, because ISO dates (YYYY-MM-DD) sort the same way
        # alphabetically as they do chronologically.
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
    # Turn the day-level difference into hours. If the latest cached row
    # is in the future (delta would be negative), we clamp it to zero
    # so the caller treats it as "fresh".
    delta = (date.today() - latest).days
    return max(delta, 0) * 24.0


# ---------------------------------------------------------------------------
# Public API - user reports
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
    # We do this validation in Python first. The database table also has
    # a CHECK constraint that enforces the same rule, but catching it in
    # Python lets us raise a clearer error message than the cryptic one
    # SQLite would return.
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
        # The JOIN brings in the trail name alongside each report, so the
        # UI doesn't have to run a second query just to look up names.
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


def get_report_distribution(trail_id: int, days: int = 30) -> dict[str, int]:
    """Count user reports by label for a trail over the past ``days`` days."""
    # We do the date math here in Python and only pass the resulting
    # cutoff string to SQLite. This keeps the SQL simple.
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with get_connection() as conn:
        # GROUP BY user_label gives us one row per label (SAFE,
        # BORDERLINE, AVOID) with how many times that label was used.
        rows = conn.execute(
            """
            SELECT user_label, COUNT(*) AS cnt
            FROM user_reports
            WHERE trail_id = ? AND report_date >= ?
            GROUP BY user_label;
            """,
            (trail_id, cutoff),
        ).fetchall()
    return {r["user_label"]: r["cnt"] for r in rows}


def get_all_user_reports() -> list[sqlite3.Row]:
    """Return every user report. The model retrain pulls from this list."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM user_reports ORDER BY created_at DESC;"
        ).fetchall()


# ---------------------------------------------------------------------------
# Public API - predictions (audit trail)
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
        # We convert the list of (feature, importance) tuples to a JSON
        # string before saving. This way the predictions table stays
        # flat (one row per prediction), but we still keep the ranked
        # feature list for later analysis.
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
# Small command-line helper. Lets teammates set up the database with
# "python -m data.db_manager" instead of opening Streamlit first.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Setting up database at: {DB_PATH}")
    setup_db()
    print("✓ Database ready.")
