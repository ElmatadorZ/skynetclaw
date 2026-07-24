-- 004 governance DOWN (drops minority table; cannot drop columns in sqlite)
DROP INDEX IF EXISTS idx_minority_session;
DROP INDEX IF EXISTS idx_minority_agent;
DROP INDEX IF EXISTS idx_minority_resolved;
DROP TABLE IF EXISTS minority_positions;
DELETE FROM schema_migrations WHERE version=4;
