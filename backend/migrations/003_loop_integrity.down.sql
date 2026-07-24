-- 003 loop_integrity DOWN (drops added indexes; sqlite cannot drop columns)
DROP INDEX IF EXISTS idx_pred_due30_rev;
DROP INDEX IF EXISTS idx_pred_due90_rev;
DROP INDEX IF EXISTS idx_pred_due180_rev;
DROP INDEX IF EXISTS idx_pred_extracted;
DELETE FROM schema_migrations WHERE version=3;
