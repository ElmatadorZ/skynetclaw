-- 001 institutional_memory DOWN (rollback). Drops only institutional tables.
DROP INDEX IF EXISTS idx_sessions_ts;
DROP INDEX IF EXISTS idx_contrib_agent;
DROP INDEX IF EXISTS idx_contrib_session;
DROP INDEX IF EXISTS idx_archive_date;
DROP INDEX IF EXISTS idx_archive_session;
DROP INDEX IF EXISTS idx_pred_status;
DROP INDEX IF EXISTS idx_pred_agent;
DROP INDEX IF EXISTS idx_pred_due30;
DROP INDEX IF EXISTS idx_reputation_score;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS agent_reputation;
DROP TABLE IF EXISTS deliberation_archive;
DROP TABLE IF EXISTS council_contributions;
DROP TABLE IF EXISTS council_sessions;
DELETE FROM schema_migrations WHERE version=1;
