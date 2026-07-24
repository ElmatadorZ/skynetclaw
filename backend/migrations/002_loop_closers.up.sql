-- 002 loop_closers UP — THE HOUSE vNext M0 (idempotent)
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
CREATE INDEX IF NOT EXISTS idx_rephist_agent ON reputation_history(agent, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_session ON constitution_audits(session_id);
CREATE INDEX IF NOT EXISTS idx_jobs_due      ON scheduled_jobs(status, run_at);
CREATE INDEX IF NOT EXISTS idx_maps_session  ON system_maps(session_id);
-- v2 column adds (align migrate.py with institutional_db._ensure_columns)
ALTER TABLE agent_reputation ADD COLUMN consistency REAL NOT NULL DEFAULT 0.0;
ALTER TABLE predictions ADD COLUMN extracted_from TEXT NOT NULL DEFAULT '';
ALTER TABLE predictions ADD COLUMN horizon_primary TEXT NOT NULL DEFAULT '';
ALTER TABLE predictions ADD COLUMN metric TEXT NOT NULL DEFAULT '';
ALTER TABLE predictions ADD COLUMN direction TEXT NOT NULL DEFAULT '';
INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (2, 'memory_v2_loop_closers', strftime('%s','now'));
