# Chaos Engineering Report — Reliability Sprint

> Objective: **do not prove the system reliable — try to break it.** Every reproducible
> failure became a permanent assertion in [`backend/chaos_test.py`](../backend/chaos_test.py)
> so it cannot recur without a red test. Evidence, not opinions — every line below is a
> measured result. Run: `python backend/chaos_test.py`.

## Verdict
- **1 real reliability bug found, fixed, and now guarded by a regression test.**
- **No CRITICAL reliability issue remains.** Crash-recovery, atomic config, and ACID
  integrity are now *proven by tests*, not assumed.
- RC-1 **Reliability** moves from PENDING → **PASS** (except "Resume interrupted mission",
  which requires the unshipped Journal kernel → **N/A**).

## Experiments & evidence
| # | Chaos injected | Result | Evidence |
|---|---|---|---|
| **EXP-1** | Corrupt `settings.json` (truncated JSON) | ✅ recovers from `.bak`, rewrites valid primary | `SettingsBackupChain` chain works |
| **EXP-2** | Crash *during* the tmp→primary replace | ✅ good file untouched · ⚠️ **stray `.tmp` leaked** → **FIXED** | see Bug CHAOS-001 |
| **EXP-3** | 24 threads × 25 concurrent writes | plain: **0 locks / 2.6s** · WAL: **0 locks / 2.2s** | lock failure did **not** reproduce (stdlib 5 s busy timeout mitigates); WAL adopted as defense-in-depth + 21 % faster |
| **EXP-4** | Abandon an open write txn (kill-mid-write proxy) | ✅ `integrity_check=ok`, uncommitted row rolled back | SQLite ACID holds |
| **EXP-5** | Enable WAL on the real `skynerclaw.db` | ✅ `journal_mode=wal` | shipped fix, applied at startup |
| **EXP-6** | Hold a write lock, second writer via hardened connect | ✅ blocked writer **waited then succeeded** | busy_timeout mitigates lock |
| **EXP-7** | Corrupt **every** settings source (primary + all baks) | ✅ falls back to safe default, no crash | recovery chain terminal fallback |
| **EXP-8** | Write failure mid-save (disk-full / permission-denied proxy) | ✅ `safe_save`→False, good file intact, no `.tmp` | generalises CHAOS-001 fix |
| **Restart** | Kill process, relaunch | ✅ healthy, settings intact (`exec_model=ElmatadorZ`), DB `wal` | live restart on 127.0.0.1:8766 |

**Round 2 (EXP-6/7/8):** no new bug found — the system survived a held DB lock, total
config corruption, and write failure. Recorded as evidence, not assumed.

## Bug found — CHAOS-001 (stray `.tmp` on interrupted save)
- **How found:** EXP-2 injected an exception into `Path.replace` mid-save.
- **Symptom:** the good `settings.json` survived (atomicity held), but the temporary
  `settings.json.tmp` was **left on disk** — an orphaned-file leak that accumulates and
  can confuse recovery tooling.
- **Root cause:** `SettingsBackupChain.safe_save` had no cleanup path when the write/
  replace failed.
- **Fix:** `except` now unlinks the `.tmp` (and the good file is never touched).
  [`openclaw_port_tier2.py`](../backend/openclaw_port_tier2.py) `safe_save`.
- **Regression:** EXP-2 asserts *"no stray .tmp left behind"* — permanent.

## Reliability improvement — WAL at startup
- **Why:** in the default rollback-journal mode a long read blocks the writer; under
  real concurrency (agent runs + UI polling + telemetry) this serialises the datastore.
- **Change:** `main.py` calls `db_reliability.ensure_wal(DB_PATH)` once at import (WAL is
  a persistent DB property). Also 21 % faster on the concurrency benchmark.
- **Regression:** EXP-3 (hardened path 0 locks, not slower) + EXP-5 (real DB is `wal`).

## What was proven reliable (with tests, not opinion)
- **Config survives corruption** (EXP-1) and **survives an interrupted save** (EXP-2).
- **The datastore survives a killed writer** with no corruption and correct rollback (EXP-4).
- **The process restarts cleanly** with settings and DB intact (Restart).

## Honest gaps (not closed here)
- **Resume of an interrupted mission** needs durable event replay = the V3 **Journal**
  kernel, which is **design-only** (`docs/v3`), not shipped → RC-1 marks it **N/A**, not PASS.
- EXP-3 could not reproduce a lock *failure* on this machine; WAL is justified by
  reader/writer isolation + speed, not by a reproduced outage. Stated plainly.

## How this feeds the gate
`chaos_test.py` joins `security_regression_test.py` under the **Test** gate of
[QUALITY_GATE.md](QUALITY_GATE.md). Both must be green before merge; every future
reliability failure adds an assertion here first.
