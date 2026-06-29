"""SQLite connection management (WAL mode + busy_timeout) and schema migrations."""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from ..utils.path_util import db_path

_CURRENT_SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS endpoints (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,
  base_url      TEXT NOT NULL,
  api_key_enc   BLOB NOT NULL,
  provider_type TEXT NOT NULL DEFAULT 'openai-compat',
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS models (
  endpoint_id        INTEGER NOT NULL REFERENCES endpoints(id) ON DELETE CASCADE,
  model_id           TEXT NOT NULL,
  capabilities_json  TEXT NOT NULL DEFAULT '{}',
  context_length     INTEGER,
  raw_meta_json      TEXT,
  performance_json   TEXT NOT NULL DEFAULT '{}',
  last_discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (endpoint_id, model_id)
);

CREATE TABLE IF NOT EXISTS overrides (
  endpoint_id    INTEGER NOT NULL,
  model_id       TEXT NOT NULL,
  capability_key TEXT NOT NULL,
  value_json     TEXT NOT NULL,
  updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (endpoint_id, model_id, capability_key)
);

CREATE TABLE IF NOT EXISTS probe_runs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint_id  INTEGER NOT NULL,
  model_id     TEXT NOT NULL,
  capability   TEXT NOT NULL,
  ok           INTEGER NOT NULL,
  status       TEXT NOT NULL,
  latency_ms   INTEGER,
  raw_json     TEXT,
  error        TEXT,
  ran_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_probe_runs_lookup
  ON probe_runs(endpoint_id, model_id, capability, ran_at);

CREATE TABLE IF NOT EXISTS probe_jobs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint_id   INTEGER NOT NULL REFERENCES endpoints(id) ON DELETE CASCADE,
  model_id      TEXT NOT NULL,
  capability    TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending',
  priority      INTEGER NOT NULL DEFAULT 0,
  claimed_by    TEXT,
  claimed_at    TEXT,
  lease_until   TEXT,
  finished_at   TEXT,
  error         TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_probe_jobs_pending
  ON probe_jobs(status, priority DESC, id ASC);
CREATE INDEX IF NOT EXISTS idx_probe_jobs_lease
  ON probe_jobs(status, lease_until);

CREATE TABLE IF NOT EXISTS model_call_events (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint_id            INTEGER NOT NULL REFERENCES endpoints(id) ON DELETE CASCADE,
  model_id               TEXT NOT NULL,
  operation              TEXT NOT NULL,
  ok                     INTEGER NOT NULL,
  upstream_status         INTEGER NOT NULL,
  first_byte_ms          INTEGER,
  latency_ms             INTEGER,
  prompt_tokens          INTEGER,
  output_tokens          INTEGER,
  total_tokens           INTEGER,
  error_type             TEXT,
  created_at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_model_call_events_recent
  ON model_call_events(endpoint_id, model_id, created_at);

CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER PRIMARY KEY);
"""

_lock = threading.Lock()
_initialised = False


def _configure_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    cur = conn.execute("SELECT MAX(version) FROM _schema_version")
    row = cur.fetchone()
    current = row[0] if row and row[0] is not None else 0
    if current < 2:
        columns = {
            r["name"] for r in conn.execute("PRAGMA table_info(models)").fetchall()
        }
        if "performance_json" not in columns:
            conn.execute(
                "ALTER TABLE models ADD COLUMN performance_json TEXT NOT NULL DEFAULT '{}'"
            )
    if current < _CURRENT_SCHEMA_VERSION:
        conn.execute(
            "INSERT INTO _schema_version(version) VALUES (?)",
            (_CURRENT_SCHEMA_VERSION,),
        )
    conn.commit()


def init_db() -> None:
    """Idempotent: ensure DB file exists with current schema."""
    global _initialised
    with _lock:
        if _initialised:
            return
        path = db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            _configure_connection(conn)
            _migrate(conn)
        _initialised = True


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a configured SQLite connection. Caller owns transaction lifecycle."""
    init_db()
    conn = sqlite3.connect(db_path(), isolation_level=None)  # autocommit mode
    _configure_connection(conn)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Open a connection inside a BEGIN/COMMIT block (rolls back on exception)."""
    with connect() as conn:
        conn.execute("BEGIN")
        try:
            yield conn
        except Exception:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
