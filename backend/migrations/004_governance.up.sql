-- 004 governance (M3) UP — self-contained (matches institutional_db._ensure_columns)
CREATE TABLE IF NOT EXISTS minority_positions (
    id TEXT PRIMARY KEY, session_id TEXT, agent TEXT NOT NULL, position TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '', stance TEXT NOT NULL DEFAULT 'dissent', ts REAL NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0, proven_correct INTEGER, resolved_at REAL NOT NULL DEFAULT 0.0,
    vindication_applied INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_minority_session ON minority_positions(session_id);
CREATE INDEX IF NOT EXISTS idx_minority_agent   ON minority_positions(agent);
CREATE INDEX IF NOT EXISTS idx_minority_resolved ON minority_positions(resolved, proven_correct);
ALTER TABLE constitution_audits ADD COLUMN waivers TEXT NOT NULL DEFAULT '[]';
ALTER TABLE constitution_audits ADD COLUMN decision TEXT NOT NULL DEFAULT '';
ALTER TABLE constitution_audits ADD COLUMN n_minority INTEGER NOT NULL DEFAULT 0;
ALTER TABLE constitution_audits ADD COLUMN governance_score REAL NOT NULL DEFAULT 0.0;
ALTER TABLE constitution_audits ADD COLUMN record_json TEXT NOT NULL DEFAULT '{}';
INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (4, 'governance_engine_m3', strftime('%s','now'));
