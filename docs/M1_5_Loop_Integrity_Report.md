# M1.5 — Loop Integrity: Fix Report
### Closing the four critical findings before M2. *Goal: trustworthiness, not features.*

> Scope: C1 Prediction Attribution · C2 Historical Recall · C3 Reputation · C4
> Persistence. No new features, no UI, no Chamber, no Atlas expansion. Every fix
> is backed by a regression test and a measurement.
> **Result: 79 tests pass (was 63), 93% coverage. The M2 gate is cleared.**

---

## 1. Root Cause Analysis

| ID | Defect | Root cause |
|---|---|---|
| **C1** | Reputation scored only 1 of 14 agents | `extractor` hard-coded `agent="Forecaster"`; outcomes never reached the agents who actually argued. Attribution was a constant, not derived from the deliberation. |
| **C2** | Recall surfaced proven-wrong verdicts as authority | `recall()` ranked on `similarity` alone, with **no join to outcomes**. The memory layer had no notion that a past verdict had been *graded*. |
| **C3** | Unbounded score inflation; decay never bit active agents | Score was a raw accumulator (`score += K·(actual−0.5)`) with no ceiling; decay was keyed to `updated_at`, which every outcome/contribution refreshed → "time since" was always ~0. Skill, recency, and calibration were conflated into one ever-growing tally. |
| **C4** | Every read took a write lock | `ensure_schema()` (an `executescript`+`commit`) ran at the top of *every* function — turning reads into writers. Schema validation was a per-call guard, not a boot step. |

The common theme: **the loop recorded data but never closed the epistemic feedback** — attribution, outcome, and recall were not wired to each other, so the system accumulated signal without accountability.

---

## 2. Fix Design

### C1 — Attribution integrity (`extractor.py`, `outcome_tracker.py`)
- Origin is **derived from which council block made the claim** (`ROLE_AGENT` map over all forward-capable roles: forecaster, atlas, strategist, analyst, skeptic), never hard-coded.
- Each prediction now carries **originating_agent · participants · confidence · evidence_source**. Whoever supplied the invalidation (often the Skeptic) or cited data (the Analyst) is recorded as a **participating agent**.
- `evaluate()` **distributes** the outcome to every attributed agent — originator at full weight, co-signers at 0.5 — passing the stated confidence for calibration.
- Verified: a forecast in the Atlas block attributes to **Atlas**; a council verdict now grades **Forecaster + Skeptic + Analyst** together.

### C2 — Outcome-weighted recall (`council_memory.py`)
- New rank = **similarity × historical_accuracy_factor × confidence_calibration**.
- Each candidate session is joined to its predictions' realised outcomes (`_session_outcomes`). Labels: `validated` (acc ≥ 0.6), `mixed`, `DISPROVEN` (acc < 0.4), `unverified` (no graded outcomes).
- **Disproven verdicts are rank-crushed AND always carry `warning=True`** — they can never appear as an unlabelled top result. Sort puts non-warned results first, then by rank.
- Verified: same-topic validated vs disproven sessions → validated ranks top (0.346), disproven sinks (0.035) with a `DISPROVEN` warning.

### C3 — Bayesian reputation (`agent_reputation.py`)
- **Beta-Bernoulli with exponential forgetting.** Each agent holds `(alpha, beta)`; skill = `alpha/(alpha+beta)` ∈ [0,1]. Before each update, evidence is forgotten toward the prior by time since the agent's **last graded outcome** (`last_outcome_at`, not `updated_at`).
- **Calibration** via Brier score on stated confidence vs outcome; **overconfidence** (high confidence, wrong) lowers calibration and is penalised.
- `score = 1000·skill·(1 − 0.3·(1−calibration))` → **bounded [0,1000]**, neutral 500.
- Consistency windowed to the recent 20 outcomes (recency). `apply_outcome` is now a **single transaction**.
- Verified: 50 correct → 969 (was 1600, unbounded); 1 bad → recovers 252→806; overconfident-wrong calibration 0.10 vs humble 0.91; idle agent fades 872→586 over a year.

### C4 — Persistence integrity (`institutional_db.py` + all modules)
- New `init_once(path)` ensures schema **once per process per DB**; hot paths call it instead of `ensure_schema`. After the first call it's a set-membership check — **reads no longer `executescript`/`commit`, so they never take a write lock**. `rollback()` invalidates the cache.
- `apply_outcome` made atomic; `due_reviews` **paginated**; `review_summary` uses indexed `COUNT` (`due_count`) instead of materialising rows; covering indexes `(due_x, review_x)` added.

---

## 3. Migration Plan

- **Migration 003** (`003_loop_integrity.up/down.sql`), schema **v3**.
- New columns (idempotent, PRAGMA-checked in `ensure_schema`; explicit `ALTER`s in the migration SQL so `migrate.py` and `ensure_schema` produce identical schemas — closes the dual-source drift the audit flagged):
  - `predictions`: `participants`, `evidence_source`
  - `agent_reputation`: `alpha`, `beta`, `last_outcome_at`, `brier_sum`, `brier_n`, `calibration`
- New covering indexes: `idx_pred_due30_rev`, `…90_rev`, `…180_rev`, `idx_pred_extracted`.
- **Backward compatible:** additive only. Existing rows keep working; `alpha/beta` default `1.0` (neutral), so un-graded agents read as skill 0.5. Down-migration drops the v3 indexes and version marker (SQLite cannot drop columns — documented; columns are harmless if 003 is rolled back).
- **Rollout:** `migrate.py up` (verified to apply 001→002→003 on a fresh DB and reproduce the exact v3 schema); `ensure_schema` self-heals on boot. Full down→up cycle verified idempotent.

---

## 4. Benchmark Results

| Metric | Before (audit) | After (M1.5) | Δ |
|---|---|---|---|
| Read latency (warm) | 0.82 ms (ensure_schema/call) | 0.44 ms (init_once cached) | **1.9× faster** |
| Read under held write lock | contends (read = writer) | **succeeds, 0.32 ms** | lock-free |
| `review_summary` @ 90k | ~353 ms | **13 ms** | **27× faster** |
| `due_reviews` @ 47k backlog | 320 ms (unbounded) | **3.9 ms** (paginated 500) | **82× faster** |
| Reputation after 50 correct | 1600 (unbounded) | **969** (bounded ≤ 1000) | inflation removed |

---

## 5. Regression Tests (`tests/test_m15_integrity.py`, +16)

Every success criterion is now guarded:
- **C1:** attribution not hard-coded (Atlas block → Atlas); prediction carries all four attribution fields; outcome distributes to all attributed agents.
- **C2:** disproven never ranks top; disproven carries warning label; failed predictions reduce rank; unverified stays neutral.
- **C3:** score bounded; one bad forecast not permanent; overconfidence penalised; recent matters / old fades; `apply_outcome` atomic; calibration tracked.
- **C4:** read succeeds under a held write lock; `init_once` is cached (0 `ensure_schema` calls after first); schema is v3.

Suite: **79 passed, 93% coverage.** Run from the mounted folder with
`python -m pytest tests/ -q -p no:cacheprovider --basetemp=/tmp/pbt`.

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bayesian scale shift confuses existing dashboards (neutral 500, not 1000) | High | Low | Documented; score still 0–1000, monotonic in skill; dashboards read the same field |
| `init_once` masks a needed schema upgrade if a new column is added without a version bump | Low | Med | `ensure_schema` still runs on boot via `register()`; bump `SCHEMA_VERSION` for new columns |
| Recall scan still bounded at 1000 rows (audit H2 not in C-scope) | Med | Med | **Explicitly tracked as scheduled debt** — FTS5/vector index is the fix; C2 only addresses *correctness weighting*, not window size. Flagged in code. |
| Participant weight (0.5) is a heuristic, not learned | Med | Low | Tunable constant; future calibration from data |
| Extractor still regex-heuristic (metric/direction quality) | Med | Med | Falsifiability gate (R4) holds; structured-LLM extraction is a later refinement, not a correctness blocker |
| Decay forgetting + calibration interact in edge cases (e.g., all-partial history) | Low | Low | Covered by tests; bounded by construction |

### Residual (NOT addressed in M1.5 — by design)
H2 recall window size, H5 re-deliberation dedupe, M2 Atlas templating, and the
Obsidian archive file-count explosion remain **scheduled debt**. M1.5's mandate was
the four *critical* findings only.

---

## Verdict
The four critical defects are resolved, each with a measurement and a regression
test. The House no longer (a) scores one agent, (b) recalls disproven verdicts as
authority, (c) inflates reputation without bound, or (d) takes a write lock on
reads. **The M2 gate is cleared** — the Convener can now safely inject recall and
reputation into live deliberation, because both now carry correctness, not just
recency.
