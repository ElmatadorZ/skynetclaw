-- 001 institutional_memory UP — THE HOUSE
-- Mirrors institutional_db.SCHEMA_SQL. Idempotent (CREATE IF NOT EXISTS).
CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT, applied_at REAL);

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

CREATE INDEX IF NOT EXISTS idx_sessions_ts      ON council_sessions(ts DESC);
CREATE INDEX IF NOT EXISTS idx_contrib_agent    ON council_contributions(agent);
CREATE INDEX IF NOT EXISTS idx_contrib_session  ON council_contributions(session_id);
CREATE INDEX IF NOT EXISTS idx_archive_date     ON deliberation_archive(date DESC);
CREATE INDEX IF NOT EXISTS idx_archive_session  ON deliberation_archive(session_id);
CREATE INDEX IF NOT EXISTS idx_pred_status      ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_pred_agent       ON predictions(agent);
CREATE INDEX IF NOT EXISTS idx_pred_due30       ON predictions(due_30);
CREATE INDEX IF NOT EXISTS idx_reputation_score ON agent_reputation(score DESC);

INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (1, 'institutional_memory', strftime('%s','now'));
