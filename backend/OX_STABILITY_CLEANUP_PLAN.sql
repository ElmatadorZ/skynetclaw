-- ============================================================================
-- OX-STABILITY-1 · PHASE 5 · ONE-TIME CLEANUP PLAN  (skynerclaw.db)
-- ============================================================================
-- STATUS: GENERATED — DO NOT EXECUTE WITHOUT OPERATOR APPROVAL.
-- Strategy: ARCHIVE, never DELETE. Every statement is reversible from the backup
-- and from the snapshot tables created in STEP 1. Preview (SELECT) before each
-- mutation. Run inside a single transaction so a mistake rolls back cleanly.
--
-- Targets (from the runtime audit):
--   * 71 orphaned agent_runs stuck in 'running' (oldest ~15 days)
--   * house_state rows whose objective is reflection-error / diagnostic text
--   * stale 'open' house_state rows that never concluded (40/40 open)
-- ============================================================================


-- ── STEP 0 · BACKUP (run at the OS shell, NOT in sqlite) ────────────────────
--   # full physical backup before touching anything:
--   cp skynerclaw.db   skynerclaw.db.pre_ox_stability.bak
--   # or, consistent online backup:
--   sqlite3 skynerclaw.db ".backup 'skynerclaw.db.pre_ox_stability.bak'"
--   # verify the backup opens and row counts match before proceeding.


-- ── STEP 1 · IN-DB SNAPSHOTS (logical rollback source) ──────────────────────
-- Exact copies of the rows we will change, so we can restore field-by-field
-- even without the file backup.
CREATE TABLE IF NOT EXISTS _ox_bak_agent_runs   AS SELECT * FROM agent_runs   WHERE 0;
CREATE TABLE IF NOT EXISTS _ox_bak_house_state  AS SELECT * FROM house_state  WHERE 0;

INSERT INTO _ox_bak_agent_runs
  SELECT * FROM agent_runs
   WHERE status = 'running';

INSERT INTO _ox_bak_house_state
  SELECT * FROM house_state
   WHERE status IN ('open','active');


-- ── STEP 2 · PREVIEW (SELECT-only — review counts before any UPDATE) ────────
-- 2a. orphaned runs (running for > 30 min == not a live in-process request)
SELECT 'orphaned_runs' AS target, COUNT(*) AS rows
  FROM agent_runs
 WHERE status = 'running'
   AND started_at < (strftime('%s','now') - 1800);

-- 2b. reflection-error / diagnostic objectives that leaked into house_state
SELECT 'error_objectives' AS target, id, substr(question,1,80) AS objective
  FROM house_state
 WHERE status IN ('open','active')
   AND (
        lower(question) LIKE '%reflection phase failed%'
     OR lower(question) LIKE '%no learnings extracted%'
     OR lower(question) LIKE '%json parse failed%'
     OR lower(question) LIKE '%tool execution failed%'
     OR lower(question) LIKE '%traceback (most recent call%'
   );

-- 2c. stale open states (untouched > 7 days) — candidates to archive
SELECT 'stale_open_states' AS target, COUNT(*) AS rows
  FROM house_state
 WHERE status IN ('open','active')
   AND updated_at < (strftime('%s','now') - 7*86400);


-- ── STEP 3 · CLEANUP (wrap in a transaction; ROLLBACK if previews look wrong) ─
BEGIN TRANSACTION;

-- 3a. orphaned runs → 'interrupted' (truthful terminal status; reversible)
UPDATE agent_runs
   SET status   = 'interrupted',
       ended_at = COALESCE(ended_at, strftime('%s','now')),
       summary  = CASE WHEN summary IS NULL OR summary = ''
                       THEN '[ox-stability cleanup: orphaned running run]'
                       ELSE summary END
 WHERE status = 'running'
   AND started_at < (strftime('%s','now') - 1800);

-- 3b. reflection-error objectives → 'archived' (quarantined out of active + learning)
UPDATE house_state
   SET status     = 'archived',
       summary    = '[ox-stability cleanup: error-generated objective]',
       updated_at = strftime('%s','now')
 WHERE status IN ('open','active')
   AND (
        lower(question) LIKE '%reflection phase failed%'
     OR lower(question) LIKE '%no learnings extracted%'
     OR lower(question) LIKE '%json parse failed%'
     OR lower(question) LIKE '%tool execution failed%'
     OR lower(question) LIKE '%traceback (most recent call%'
   );

-- 3c. stale open states → 'archived' (keep history; just stop counting them active)
UPDATE house_state
   SET status     = 'archived',
       updated_at = strftime('%s','now')
 WHERE status IN ('open','active')
   AND updated_at < (strftime('%s','now') - 7*86400);

-- Review the row counts reported, THEN:
--   COMMIT;     -- to apply
--   ROLLBACK;   -- to abort (changes nothing)
COMMIT;


-- ── STEP 4 · POST-CHECK (should both be ~0 active garbage) ──────────────────
SELECT 'remaining_running'      AS check, COUNT(*) FROM agent_runs  WHERE status='running';
SELECT 'remaining_error_open'   AS check, COUNT(*) FROM house_state
  WHERE status IN ('open','active') AND lower(question) LIKE '%reflection phase failed%';
SELECT 'truthful_active_count'  AS check, COUNT(*) FROM house_state WHERE status IN ('open','active');


-- ── STEP 5 · ROLLBACK (if needed, AFTER commit, from the STEP-1 snapshots) ──
-- Restore the exact prior status/summary/ended_at for every changed row:
--   UPDATE agent_runs AS a
--      SET status   = (SELECT b.status   FROM _ox_bak_agent_runs b WHERE b.id = a.id),
--          ended_at = (SELECT b.ended_at FROM _ox_bak_agent_runs b WHERE b.id = a.id),
--          summary  = (SELECT b.summary  FROM _ox_bak_agent_runs b WHERE b.id = a.id)
--    WHERE a.id IN (SELECT id FROM _ox_bak_agent_runs);
--
--   UPDATE house_state AS h
--      SET status   = (SELECT b.status  FROM _ox_bak_house_state b WHERE b.id = h.id),
--          summary  = (SELECT b.summary FROM _ox_bak_house_state b WHERE b.id = h.id)
--    WHERE h.id IN (SELECT id FROM _ox_bak_house_state);
-- Or, simplest full rollback: restore skynerclaw.db.pre_ox_stability.bak.

-- ── STEP 6 · CLEANUP THE SNAPSHOTS (only once you are satisfied) ────────────
--   DROP TABLE _ox_bak_agent_runs;
--   DROP TABLE _ox_bak_house_state;
-- ============================================================================
