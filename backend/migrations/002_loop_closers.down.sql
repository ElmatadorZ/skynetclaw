-- 002 loop_closers DOWN (drops only v2 tables; sqlite cannot drop columns)
DROP INDEX IF EXISTS idx_rephist_agent;
DROP INDEX IF EXISTS idx_audit_session;
DROP INDEX IF EXISTS idx_jobs_due;
DROP INDEX IF EXISTS idx_maps_session;
DROP TABLE IF EXISTS scheduled_jobs;
DROP TABLE IF EXISTS system_maps;
DROP TABLE IF EXISTS constitution_audits;
DROP TABLE IF EXISTS reputation_history;
DELETE FROM schema_migrations WHERE version=2;
