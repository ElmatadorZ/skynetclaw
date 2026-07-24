-- 003 loop_integrity (M1.5) UP — column adds applied idempotently by
-- institutional_db._ensure_columns(); this file records the version + indexes.
-- v3 column adds (C1 attribution + C3 Bayesian reputation)
ALTER TABLE predictions ADD COLUMN participants TEXT NOT NULL DEFAULT '[]';
ALTER TABLE predictions ADD COLUMN evidence_source TEXT NOT NULL DEFAULT '';
ALTER TABLE agent_reputation ADD COLUMN alpha REAL NOT NULL DEFAULT 1.0;
ALTER TABLE agent_reputation ADD COLUMN beta REAL NOT NULL DEFAULT 1.0;
ALTER TABLE agent_reputation ADD COLUMN last_outcome_at REAL NOT NULL DEFAULT 0.0;
ALTER TABLE agent_reputation ADD COLUMN brier_sum REAL NOT NULL DEFAULT 0.0;
ALTER TABLE agent_reputation ADD COLUMN brier_n INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_reputation ADD COLUMN calibration REAL NOT NULL DEFAULT 0.0;
CREATE INDEX IF NOT EXISTS idx_pred_due30_rev ON predictions(due_30, review_30);
CREATE INDEX IF NOT EXISTS idx_pred_due90_rev ON predictions(due_90, review_90);
CREATE INDEX IF NOT EXISTS idx_pred_due180_rev ON predictions(due_180, review_180);
CREATE INDEX IF NOT EXISTS idx_pred_extracted ON predictions(extracted_from);
INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (3, 'loop_integrity_m15', strftime('%s','now'));
