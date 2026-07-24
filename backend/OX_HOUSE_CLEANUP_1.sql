-- ============================================================================
-- OX-HOUSE-CLEANUP-1 · house_state restoration  (skynerclaw.db)
-- ============================================================================
-- STATUS: GENERATED FROM A LIVE AUDIT — DO NOT EXECUTE WITHOUT OPERATOR APPROVAL.
-- Strategy: ARCHIVE, never DELETE (no data loss; fully reversible).
-- Audit snapshot: 40 rows = 7 archived(already) + 33 open.
--   Of the 33 open:  2 error-generated · 2 duplicate · 16 abandoned ·
--                    4 punctuation-only · 9 valid.
-- After full cleanup: active_count == 9 (valid only); 0 error objectives visible.
-- ============================================================================


-- ── STEP 0 · BACKUP (OS shell, before anything) ─────────────────────────────
--   sqlite3 skynerclaw.db ".backup 'skynerclaw.db.pre_house_cleanup1.bak'"


-- ── STEP 1 · LOGICAL SNAPSHOT (in-DB rollback source) ───────────────────────
CREATE TABLE IF NOT EXISTS _ox_hc1_bak_house_state AS SELECT * FROM house_state WHERE 0;
INSERT INTO _ox_hc1_bak_house_state
  SELECT * FROM house_state WHERE id IN (
    -- error-generated
    'hs_746ec906bdde','hs_e88eaf10e9db',
    -- duplicate
    'hs_72c663bd36ee','hs_0ea817abfa4c',
    -- punctuation-only titles
    'hs_74285dea0cd7','hs_e9977daffa20','hs_95e8ca3e14a3','hs_09cfa39c6b7f',
    -- abandoned (0% confidence, no cognitive content, no progress)
    'hs_1e58777e0d6b','hs_f733a013370a','hs_e583cd9911cb','hs_3224ad368012',
    'hs_1e9a227aae1b','hs_996b13342717','hs_208ca0372d5d','hs_2b66c3c092ff',
    'hs_32e1dc90b18a','hs_62daf7d63464','hs_db5f71f6fee6','hs_0c0f6cb7dd27',
    'hs_ac59ac97d316','hs_cc2220b3878f','hs_2761f3d34d0a','hs_37e51cfe3f37'
  );


-- ── STEP 2 · PREVIEW (run first; confirm the rows are what you expect) ──────
SELECT id, status, confidence, substr(question,1,60) q
  FROM house_state
 WHERE id IN (SELECT id FROM _ox_hc1_bak_house_state)
 ORDER BY status, updated_at DESC;


-- ── STEP 3 · CLEANUP (transaction; ROLLBACK if the preview looked wrong) ────
BEGIN TRANSACTION;

-- TIER 1 — error-generated objectives (the "LLM reflection phase failed" rows)
UPDATE house_state
   SET status='archived', summary='[house-cleanup-1: error-generated objective]',
       updated_at=strftime('%s','now')
 WHERE id IN ('hs_746ec906bdde','hs_e88eaf10e9db') AND status='open';

-- TIER 1 — punctuation-only "missions" ("...", ".....") — not real objectives
UPDATE house_state
   SET status='archived', summary='[house-cleanup-1: empty/punctuation title]',
       updated_at=strftime('%s','now')
 WHERE id IN ('hs_74285dea0cd7','hs_e9977daffa20','hs_95e8ca3e14a3','hs_09cfa39c6b7f')
   AND status='open';

-- TIER 2 — duplicates (collapse into their surviving canonical sibling)
UPDATE house_state
   SET status='archived', summary='[house-cleanup-1: duplicate, collapsed]',
       updated_at=strftime('%s','now')
 WHERE id IN ('hs_72c663bd36ee','hs_0ea817abfa4c') AND status='open';

-- TIER 3 — abandoned (0% confidence, no state_items, no progress).
--          NOTE: a few of these are incomplete real directives (e.g. the stock-
--          dashboard elicitation fragments). Archiving loses nothing (reversible);
--          omit any id here you wish to keep as active.
UPDATE house_state
   SET status='archived', summary='[house-cleanup-1: abandoned, 0% no-progress]',
       updated_at=strftime('%s','now')
 WHERE id IN (
   'hs_1e58777e0d6b','hs_f733a013370a','hs_e583cd9911cb','hs_3224ad368012',
   'hs_1e9a227aae1b','hs_996b13342717','hs_208ca0372d5d','hs_2b66c3c092ff',
   'hs_32e1dc90b18a','hs_62daf7d63464','hs_db5f71f6fee6','hs_0c0f6cb7dd27',
   'hs_ac59ac97d316','hs_cc2220b3878f','hs_2761f3d34d0a','hs_37e51cfe3f37'
 ) AND status='open';

-- review row counts, THEN  COMMIT;  (or  ROLLBACK;  to abort)
COMMIT;


-- ── STEP 4 · POST-CHECK (expected: error_open=0, active≈9) ──────────────────
SELECT 'error_open' c, COUNT(*) n FROM house_state
  WHERE status='open' AND lower(question) LIKE '%reflection phase failed%';
SELECT 'active_count' c, COUNT(*) n FROM house_state WHERE status IN ('open','active');
SELECT status, COUNT(*) n FROM house_state GROUP BY status;


-- ── STEP 5 · ROLLBACK (after commit, from the STEP-1 snapshot) ──────────────
--   UPDATE house_state AS h
--      SET status  = (SELECT b.status  FROM _ox_hc1_bak_house_state b WHERE b.id=h.id),
--          summary = (SELECT b.summary FROM _ox_hc1_bak_house_state b WHERE b.id=h.id),
--          updated_at = (SELECT b.updated_at FROM _ox_hc1_bak_house_state b WHERE b.id=h.id)
--    WHERE h.id IN (SELECT id FROM _ox_hc1_bak_house_state);
--   -- or restore skynerclaw.db.pre_house_cleanup1.bak

-- ── STEP 6 · DROP SNAPSHOT (only once satisfied) ────────────────────────────
--   DROP TABLE _ox_hc1_bak_house_state;
-- ============================================================================
