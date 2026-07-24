"""
institutional_db.py — central SQLite layer for THE HOUSE institutional memory
=============================================================================
Single owner of the institutional-memory schema. Every memory module imports
`connect` and `ensure_schema` from here so there is ONE source of truth.

v2 (M0): adds reputation_history, constitution_audits, system_maps,
scheduled_jobs, and new columns on agent_reputation + predictions. Column adds
are PRAGMA-checked so ensure_schema stays idempotent on an existing DB.

DB path resolves from env INSTITUTIONAL_DB, else backend/skynerclaw.db.
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import List, Optional, Tuple

_BASE = Path(__file__).parent
SCHEMA_VERSION = 5

# C4: schema is ensured ONCE per (process, db path). Hot-path callers use
# init_once() — a set-membership check after the first call — so reads never
# run executescript()/commit() and therefore never take a write lock.
_INITIALIZED: set = set()


def db_path() -> str:
    return os.environ.get("INSTITUTIONAL_DB") or str(_BASE / "skynerclaw.db")


def connect(path: Optional[str] = None) -> sqlite3.Connection:
    c = sqlite3.connect(path or db_path(), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY, name TEXT, applied_at REAL);

CREATE TABLE IF NOT EXISTS council_sessions (
    id TEXT PRIMARY KEY, ts REAL NOT NULL, directive TEXT NOT NULL,
    participants TEXT NOT NULL DEFAULT '[]', verdict TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0, evidence_summary TEXT NOT NULL DEFAULT '',
    dissent_summary TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL);

CREATE TABLE IF NOT EXISTS council_contributions (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, agent TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '', stance TEXT NOT NULL DEFAULT 'neutral',
    confidence REAL NOT NULL DEFAULT 0.0, evidence_quality REAL NOT NULL DEFAULT 0.0,
    critique_quality REAL NOT NULL DEFAULT 0.0, forecast_quality REAL NOT NULL DEFAULT 0.0,
    note TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES council_sessions(id) ON DELETE CASCADE);

CREATE TABLE IF NOT EXISTS deliberation_archive (
    id TEXT PRIMARY KEY, session_id TEXT, date TEXT NOT NULL, question TEXT NOT NULL,
    agents TEXT NOT NULL DEFAULT '[]', reasoning_summary TEXT NOT NULL DEFAULT '',
    final_verdict TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0.0,
    predicted_outcome TEXT NOT NULL DEFAULT '', obsidian_path TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES council_sessions(id) ON DELETE SET NULL);

CREATE TABLE IF NOT EXISTS agent_reputation (
    agent TEXT PRIMARY KEY, score REAL NOT NULL DEFAULT 1000.0,
    wins INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0, n_predictions INTEGER NOT NULL DEFAULT 0,
    n_correct INTEGER NOT NULL DEFAULT 0, accuracy_rate REAL NOT NULL DEFAULT 0.0,
    forecast_quality REAL NOT NULL DEFAULT 0.0, evidence_quality REAL NOT NULL DEFAULT 0.0,
    critique_quality REAL NOT NULL DEFAULT 0.0, updated_at REAL NOT NULL DEFAULT 0.0);

CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY, session_id TEXT, agent TEXT NOT NULL DEFAULT '',
    statement TEXT NOT NULL, predicted_outcome TEXT NOT NULL DEFAULT '',
    invalidation TEXT NOT NULL DEFAULT '', confidence REAL NOT NULL DEFAULT 0.0,
    made_at REAL NOT NULL, due_30 REAL NOT NULL DEFAULT 0.0, due_90 REAL NOT NULL DEFAULT 0.0,
    due_180 REAL NOT NULL DEFAULT 0.0, review_30 TEXT NOT NULL DEFAULT '',
    review_90 TEXT NOT NULL DEFAULT '', review_180 TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending', evaluated_at REAL NOT NULL DEFAULT 0.0,
    FOREIGN KEY (session_id) REFERENCES council_sessions(id) ON DELETE SET NULL);

-- v2 (M0) ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reputation_history (
    id TEXT PRIMARY KEY, agent TEXT NOT NULL, ts REAL NOT NULL,
    score REAL NOT NULL DEFAULT 0.0, accuracy_rate REAL NOT NULL DEFAULT 0.0,
    consistency REAL NOT NULL DEFAULT 0.0, event TEXT NOT NULL DEFAULT '');

CREATE TABLE IF NOT EXISTS constitution_audits (
    id TEXT PRIMARY KEY, session_id TEXT, ts REAL NOT NULL,
    score REAL NOT NULL DEFAULT 0.0, violations TEXT NOT NULL DEFAULT '[]',
    blocked INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS system_maps (
    id TEXT PRIMARY KEY, session_id TEXT, ts REAL NOT NULL,
    query TEXT NOT NULL DEFAULT '', layers TEXT NOT NULL DEFAULT '[]',
    map_json TEXT NOT NULL DEFAULT '{}');

CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, run_at REAL NOT NULL,
    last_run REAL NOT NULL DEFAULT 0.0, status TEXT NOT NULL DEFAULT 'pending',
    payload TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL DEFAULT 0.0);

CREATE INDEX IF NOT EXISTS idx_sessions_ts      ON council_sessions(ts DESC);
CREATE INDEX IF NOT EXISTS idx_contrib_agent    ON council_contributions(agent);
CREATE INDEX IF NOT EXISTS idx_contrib_session  ON council_contributions(session_id);
CREATE INDEX IF NOT EXISTS idx_archive_date     ON deliberation_archive(date DESC);
CREATE INDEX IF NOT EXISTS idx_archive_session  ON deliberation_archive(session_id);
CREATE INDEX IF NOT EXISTS idx_pred_status      ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_pred_agent       ON predictions(agent);
CREATE INDEX IF NOT EXISTS idx_pred_due30       ON predictions(due_30);
CREATE INDEX IF NOT EXISTS idx_reputation_score ON agent_reputation(score DESC);
CREATE INDEX IF NOT EXISTS idx_rephist_agent    ON reputation_history(agent, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_session    ON constitution_audits(session_id);
CREATE INDEX IF NOT EXISTS idx_jobs_due         ON scheduled_jobs(status, run_at);
CREATE INDEX IF NOT EXISTS idx_maps_session     ON system_maps(session_id);

-- v4 (M3 Governance): minority tracking — who disagreed, why, and whether vindicated
CREATE TABLE IF NOT EXISTS minority_positions (
    id TEXT PRIMARY KEY, session_id TEXT, agent TEXT NOT NULL, position TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '', stance TEXT NOT NULL DEFAULT 'dissent', ts REAL NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0, proven_correct INTEGER, resolved_at REAL NOT NULL DEFAULT 0.0,
    vindication_applied INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_minority_session ON minority_positions(session_id);
CREATE INDEX IF NOT EXISTS idx_minority_agent   ON minority_positions(agent);
CREATE INDEX IF NOT EXISTS idx_minority_resolved ON minority_positions(resolved, proven_correct);

-- v5 (HOUSE STATE ENGINE — the House Mind): a shared, living cognitive state
CREATE TABLE IF NOT EXISTS house_state (
    id TEXT PRIMARY KEY, session_id TEXT, question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open', confidence REAL NOT NULL DEFAULT 0.0,
    summary TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL DEFAULT 0.0);
CREATE TABLE IF NOT EXISTS state_items (
    id TEXT PRIMARY KEY, state_id TEXT NOT NULL, kind TEXT NOT NULL,
    content TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 0.0,
    agent TEXT NOT NULL DEFAULT '', evidence TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active', superseded INTEGER NOT NULL DEFAULT 0, ts REAL NOT NULL,
    FOREIGN KEY (state_id) REFERENCES house_state(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS belief_changes (
    id TEXT PRIMARY KEY, state_id TEXT NOT NULL, item_id TEXT,
    previous TEXT NOT NULL DEFAULT '', new TEXT NOT NULL DEFAULT '',
    prev_confidence REAL NOT NULL DEFAULT 0.0, new_confidence REAL NOT NULL DEFAULT 0.0,
    reason TEXT NOT NULL DEFAULT '', evidence TEXT NOT NULL DEFAULT '',
    agent TEXT NOT NULL DEFAULT '', ts REAL NOT NULL,
    FOREIGN KEY (state_id) REFERENCES house_state(id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS idx_state_session  ON house_state(session_id);
CREATE INDEX IF NOT EXISTS idx_state_status   ON house_state(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_state    ON state_items(state_id, kind);
CREATE INDEX IF NOT EXISTS idx_items_active   ON state_items(state_id, superseded);
CREATE INDEX IF NOT EXISTS idx_changes_state  ON belief_changes(state_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_pred_due30_rev   ON predictions(due_30, review_30);
CREATE INDEX IF NOT EXISTS idx_pred_due90_rev   ON predictions(due_90, review_90);
CREATE INDEX IF NOT EXISTS idx_pred_due180_rev  ON predictions(due_180, review_180);
"""

# Columns added in v2 to pre-existing tables (PRAGMA-checked → idempotent)
ADD_COLUMNS: List[Tuple[str, str, str]] = [
    ("agent_reputation", "consistency", "REAL NOT NULL DEFAULT 0.0"),
    ("predictions", "extracted_from", "TEXT NOT NULL DEFAULT ''"),
    ("predictions", "horizon_primary", "TEXT NOT NULL DEFAULT ''"),
    ("predictions", "metric", "TEXT NOT NULL DEFAULT ''"),
    ("predictions", "direction", "TEXT NOT NULL DEFAULT ''"),
    # C1: prediction attribution integrity
    ("predictions", "participants", "TEXT NOT NULL DEFAULT '[]'"),
    ("predictions", "evidence_source", "TEXT NOT NULL DEFAULT ''"),
    # C3: Bayesian reputation (Beta-Bernoulli + decay + calibration)
    ("agent_reputation", "alpha", "REAL NOT NULL DEFAULT 1.0"),
    ("agent_reputation", "beta", "REAL NOT NULL DEFAULT 1.0"),
    ("agent_reputation", "last_outcome_at", "REAL NOT NULL DEFAULT 0.0"),
    ("agent_reputation", "brier_sum", "REAL NOT NULL DEFAULT 0.0"),
    ("agent_reputation", "brier_n", "INTEGER NOT NULL DEFAULT 0"),
    ("agent_reputation", "calibration", "REAL NOT NULL DEFAULT 0.0"),
    # v6: the FULL council verdict travels with the session — summary-only
    # storage made predictions unrecoverable after the fact (16 sessions lost)
    ("council_sessions", "verdict_json", "TEXT NOT NULL DEFAULT '{}'"),
    # v7: 7-day horizon — operational predictions must not wait a month for
    # their first grading (learning latency). due_7=0.0 marks pre-v7 rows
    # (excluded from due queries — never retroactively due).
    ("predictions", "due_7", "REAL NOT NULL DEFAULT 0.0"),
    ("predictions", "review_7", "TEXT NOT NULL DEFAULT ''"),
    # v4 (M3 Governance): governance audit record on constitution_audits
    ("constitution_audits", "waivers", "TEXT NOT NULL DEFAULT '[]'"),
    ("constitution_audits", "decision", "TEXT NOT NULL DEFAULT ''"),
    ("constitution_audits", "n_minority", "INTEGER NOT NULL DEFAULT 0"),
    ("constitution_audits", "governance_score", "REAL NOT NULL DEFAULT 0.0"),
    ("constitution_audits", "record_json", "TEXT NOT NULL DEFAULT '{}'"),
]

# Indexes on columns that are added via ADD_COLUMNS (must run AFTER _ensure_columns)
POST_COLUMN_SQL = """
CREATE INDEX IF NOT EXISTS idx_pred_extracted ON predictions(extracted_from);
"""

ROLLBACK_SQL = """
DROP INDEX IF EXISTS idx_sessions_ts;
DROP INDEX IF EXISTS idx_contrib_agent;
DROP INDEX IF EXISTS idx_contrib_session;
DROP INDEX IF EXISTS idx_archive_date;
DROP INDEX IF EXISTS idx_archive_session;
DROP INDEX IF EXISTS idx_pred_status;
DROP INDEX IF EXISTS idx_pred_agent;
DROP INDEX IF EXISTS idx_pred_due30;
DROP INDEX IF EXISTS idx_reputation_score;
DROP INDEX IF EXISTS idx_rephist_agent;
DROP INDEX IF EXISTS idx_audit_session;
DROP INDEX IF EXISTS idx_jobs_due;
DROP INDEX IF EXISTS idx_maps_session;
DROP TABLE IF EXISTS scheduled_jobs;
DROP TABLE IF EXISTS system_maps;
DROP TABLE IF EXISTS constitution_audits;
DROP TABLE IF EXISTS reputation_history;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS agent_reputation;
DROP TABLE IF EXISTS deliberation_archive;
DROP TABLE IF EXISTS council_contributions;
DROP TABLE IF EXISTS council_sessions;
DROP INDEX IF EXISTS idx_minority_session;
DROP INDEX IF EXISTS idx_minority_agent;
DROP INDEX IF EXISTS idx_minority_resolved;
DROP TABLE IF EXISTS minority_positions;
DROP TABLE IF EXISTS belief_changes;
DROP TABLE IF EXISTS state_items;
DROP TABLE IF EXISTS house_state;
DELETE FROM schema_migrations WHERE version IN (1,2,3,4,5);
"""


def _ensure_columns(c: sqlite3.Connection) -> None:
    for table, col, decl in ADD_COLUMNS:
        cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def ensure_schema(path: Optional[str] = None) -> None:
    """Create/upgrade all institutional tables, indexes, columns. Idempotent."""
    with connect(path) as c:
        c.executescript(SCHEMA_SQL)
        _ensure_columns(c)
        c.executescript(POST_COLUMN_SQL)
        for v, name in ((1, "institutional_memory"), (2, "memory_v2_loop_closers"), (3, "loop_integrity_m15"), (4, "governance_engine_m3"), (5, "house_state_engine")):
            if not c.execute("SELECT 1 FROM schema_migrations WHERE version=?", (v,)).fetchone():
                c.execute("INSERT INTO schema_migrations (version, name, applied_at) VALUES (?,?,?)",
                          (v, name, time.time()))
        c.commit()


def init_once(path: Optional[str] = None) -> None:
    """Ensure the schema exactly once per process per DB path (cheap after first).
    Hot paths call THIS, not ensure_schema — keeps reads lock-free."""
    key = path or db_path()
    if key in _INITIALIZED:
        return
    ensure_schema(path)
    _INITIALIZED.add(key)


def rollback(path: Optional[str] = None) -> None:
    with connect(path) as c:
        c.executescript(ROLLBACK_SQL)
        c.commit()
    _INITIALIZED.discard(path or db_path())


def current_version(path: Optional[str] = None) -> int:
    try:
        with connect(path) as c:
            row = c.execute("SELECT MAX(version) v FROM schema_migrations").fetchone()
            return int(row["v"]) if row and row["v"] is not None else 0
    except Exception:
        return 0


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    ensure_schema()
    print(f"[institutional_db] schema ensured at {db_path()} (v{current_version()})")
