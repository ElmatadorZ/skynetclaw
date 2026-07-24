# HOSTILE ARCHITECTURE REVIEW — Institutional Memory (THE HOUSE)
### Independent Principal Engineer · adversarial audit · *the system is not approved by default*

> Scope: `institutional_db.py`, `council_memory.py`, `deliberation_archive.py`,
> `house_constitution.py`, `agent_reputation.py`, `outcome_tracker.py`,
> `atlas_system_map.py`, `obsidian_knowledge_protocol.py`,
> `council_intelligence_api.py`, `scheduler.py`, `extractor.py`, migrations, tests.
> Every claim below is backed by a measurement or a reproduction run against the
> actual code, not opinion.

## Verdict up front
**DO NOT APPROVE for scale.** The system is functionally correct on toy inputs
(63 tests, 94% line coverage) but contains **four critical defects** that make its
three headline promises — *learn, evaluate, remember* — partially false in
practice. The reputation system scores **1 of 14 agents**. Recall surfaces
**proven-wrong verdicts as authority**. Scores **inflate without bound**. And the
data layer **takes a write-lock on every read**. Coverage is high; correctness of
the *institution* is not.

---

## Evidence appendix (measured, not asserted)

| Probe | Result |
|---|---|
| `ensure_schema()` cost | **0.73 ms/call**, executed on *every* read and write (executescript + commit) |
| `recall()` @ 90k sessions | 6.0 ms but **returns from a 500-row window — blind to 99.5% of history** |
| `due_reviews(30)` @ 90k | **320 ms** (46,800 rows, no LIMIT); `review_summary` = 353 ms, called daily + by dashboard |
| Reputation attribution | predictions attributed to **`{Forecaster}` only** → 13/14 agents frozen at 1000 |
| Score inflation | 50 correct calls → **score 1600, unbounded**; decay keyed to `updated_at` which outcomes refresh → no mean-reversion for active agents |
| Recall vs correctness | a verdict graded **incorrect** is still recalled; recalled item has **no correctness field** |
| Re-deliberation | same directive run twice → **2 sessions, 2 predictions** (no content dedupe) |
| `apply_outcome` atomicity | **3 connections / 3 commits** + full-table consistency scan, non-transactional |
| DB growth | ~0.42 MB / 1k sessions (predictions+sessions only); ~38 MB @ 90k |

---

## 1. CRITICAL ISSUES (must fix before any further scale)

### C1 — The reputation system scores only one of fourteen agents
`extractor.extract_predictions` hard-codes `"agent": "Forecaster"` for every
prediction. Outcomes flow only to Forecaster via `evaluate → apply_outcome`.
**Reproduced:** extracted-prediction agent set = `{Forecaster}`. The Analyst,
Skeptic, Strategist, Atlas, etc. never accrue wins/losses/score — `record_contribution`
only nudges *quality* averages, never the score/accuracy that the leaderboard,
`best_and_worst`, and the dashboard rank on. **Consequence:** "Agent Reputation"
is decorative for 13/14 of the House. The institution cannot actually tell which
members are good — the core Phase-4 promise is unmet.

### C2 — Memory is a hallucination source: recall ignores whether the past was right
`council_memory.recall()` ranks prior sessions by token-Jaccard on the directive
**with no reference to the outcome of those sessions**. **Reproduced:** a verdict
later graded `incorrect` is still returned by recall, and the returned record has
no correctness/outcome field. When recall is injected into a new deliberation
(the M2 plan), the House will cite its own **disproven** conclusions as precedent.
Obsolete and reversed decisions contaminate future reasoning with equal authority
to validated ones. This is the single most dangerous property in the system.

### C3 — Unbounded score inflation; decay never bites active agents
`apply_outcome` adds `K·(actual−0.5)` with a **fixed 0.5 expectation and no ceiling**.
`apply_decay` regresses toward baseline by time since `updated_at` — but
`apply_outcome` *and* `record_contribution` both refresh `updated_at`, so an
active agent's "time since" is always ~0 and decay is a no-op. **Reproduced:** 50
correct calls → score **1600**, and a decay pass left it at **1600**. A loud,
frequently-graded agent inflates indefinitely; mean-reversion only touches agents
who go idle — the opposite of what's wanted. Score is not a calibrated skill
estimate; it's a tally that only goes up for the active.

### C4 — The data layer takes a write lock on every read
Every public function in every module begins with `_db.ensure_schema(path)`, which
opens a connection and runs `executescript(SCHEMA_SQL)` (10 CREATEs + 13 indexes),
`_ensure_columns` (5 `PRAGMA table_info`), a migrations check, **and `commit()`**.
**Measured 0.73 ms each.** A single council persist triggers ~15 of these
(session + 6 contributions + reputation + archive + extraction). Under WAL,
`executescript`+`commit` acquires the write lock — so **reads serialize behind a
write**. At any real concurrency (the council runs inside async request handlers)
this is lock contention and write-amplification by design. `ensure_schema` must be
a once-per-process boot call, not a per-operation guard.

---

## 2. HIGH-RISK ISSUES

### H1 — `due_reviews` / `review_summary` are unbounded scans on the hot path
No `LIMIT`. **Measured 320 ms at a 47k backlog**, growing linearly. `review_summary`
runs it for all three horizons (353 ms) and is called by the dashboard *and* the
daily `outcome_clock_handler`. At 1M predictions with a review backlog this is
multi-second and blocks the request. Needs pagination + a covering index on
`(due_30, review_30)` etc. (current `idx_pred_due30` doesn't cover the `review=''`
predicate).

### H2 — "Historical recall" goes blind at scale
`recall` reads `ORDER BY ts DESC LIMIT 500` then scans in Python. **At 90k sessions
it sees the most recent 500 — 0.5% of memory.** A 10-year-old precedent is
unreachable by the exact subsystem whose job is historical comparison
(Constitution R6). The cap silently converts "institutional memory" into
"short-term memory." Requires FTS/vector indexing, not a Python loop.

### H3 — Scheduler: cadence not honored, no atomic claim, fires on every boot
`council_intelligence_api.register()` calls `enqueue(job_id="…decay_weekly")` with
`run_at` defaulting to **now** and `INSERT OR REPLACE` — so **every process restart
resets the job to fire immediately**, regardless of the weekly cadence. `tick()`
selects due jobs then updates them with **no atomic claim**, so a boot `catch_up`
racing a cron `POST /scheduler/tick` can **double-execute** (double decay, double
reschedule). Time-based institutional behaviour is therefore non-deterministic
across restarts.

### H4 — `apply_outcome` is non-atomic and self-amplifying
Three separate connections/commits (reputation update → consistency recompute →
history log) with a **full-table `compute_consistency` scan** in the middle. A
crash between commits leaves reputation updated but consistency/history missing.
The consistency scan also grows unbounded (H/M overlap). Must be a single
transaction.

### H5 — Re-deliberation pollutes memory and amplifies recall
`from_verdict` keys session id on `sha1(directive[:80]:ts)` and `record_prediction`
on `made_at=now` — so the **same directive deliberated twice creates two sessions
and two predictions** (reproduced). Because `_persist_council` fires on *every*
council run, a retried or repeated directive multiplies. Recall (token-based) then
returns several near-identical copies, manufacturing false "consensus/precedent"
from what was one decision. No content-hash dedupe exists.

### H6 — Blocking I/O and ~15 schema scripts inside the async council path
`_persist_council` runs synchronously before `run_council` returns: a synchronous
**Obsidian file write** (`deliberation_archive`) plus ~15 `ensure_schema` round
trips, inside an async request handler. If the vault is on a synced/network drive,
the event loop stalls. Persistence belongs on a background task/queue, not in the
request.

---

## 3. MEDIUM-RISK ISSUES

- **M1 — Consistency is all-time and full-scan.** `compute_consistency` reads
  *every* graded prediction for an agent on *every* outcome and uses no window, so
  an agent that reformed is penalised forever and cost grows with history. Should
  be a rolling window + incremental.
- **M2 — Atlas V2 doesn't model; it templates.** `map_system` filters a hardcoded
  `LAYERS`/`LINKS` graph by which layer keywords the query hits. Drivers, feedback
  loops, and 2nd/3rd-order effects are **canned graph traversals identical for any
  query touching the same layers** — it does not analyse the query's actual
  content. This answers Phase 5 directly: **Atlas is returning structured metadata,
  not performing system mapping.** Genuine modeling needs the LLM to instantiate
  drivers/edges per query (and persist them to the already-built `system_maps`
  table, which is currently unused).
- **M3 — "confidence" is mislabeled.** `from_verdict` sets session confidence to
  the *average of writing-quality scores*, not any model/forecast confidence. The
  dashboard and any future gate read a number that means "how well-written," not
  "how sure." Semantic drift with downstream consequences.
- **M4 — Schema defined twice.** `institutional_db.SCHEMA_SQL` and
  `migrations/00x_*.sql` both define the tables → guaranteed eventual drift. Pick
  one source of truth (migrations) and have `ensure_schema` run them.
- **M5 — No connection pooling.** Connection-per-call + per-call WAL/FK pragmas.
  Cheap individually, but multiplied by C4's per-call `ensure_schema`.
- **M6 — History id collisions.** `reputation_history` id = `sha1(agent:event:time)`
  truncated; two events in the same second `INSERT OR REPLACE` over each other,
  silently dropping a trend point.

---

## 4. LOW-RISK ISSUES

- **L1 — f-string SQL columns.** `due_reviews`/`evaluate` interpolate
  `due_{horizon}` into SQL. Currently safe (horizon validated against `HORIZONS`),
  but it's an injection-shaped pattern one careless edit from a hole. Use a
  whitelist map to literal column names.
- **L2 — Path-traversal defense is single-layer.** `obsidian_tools` correctly
  resolves and rejects "path escapes vault," but `scout`/`archive` pass
  unvalidated LLM-authored `title`/`category` straight into `f"{category}/{title}.md"`.
  Defense-in-depth: validate at the Scout layer too.
- **L3 — Flat module namespace.** No package; imports depend on CWD/`sys.path`.
  Fragile under the planned refactor.
- **L4 — Coverage theatre.** 94% line coverage, **zero** concurrency, performance,
  inflation, or recall-correctness tests — i.e. none of the four critical defects
  has a test. Coverage measured the happy path.
- **L5 — `INSERT OR REPLACE` everywhere** masks logic errors by silently
  overwriting instead of failing; hides H5-class duplication until you query for it.

---

## 5. TECHNICAL DEBT

1. Dual schema source (code + migrations) — drift inevitable.
2. `ensure_schema`-per-call as a substitute for a boot/migration step.
3. Reputation conflates two unrelated signals under one `updated_at`
   (contribution-quality vs outcome) — couples decay to the wrong clock.
4. Token-Jaccard recall is a placeholder masquerading as the retrieval layer;
   the `system_maps` and `constitution_audits` tables are built but **unused**.
5. Single-agent extraction hard-codes the one role that happens to forecast,
   foreclosing real multi-agent accountability.
6. Persistence interleaved with deliberation (sync, in-request).

---

## 6. REFACTORING RECOMMENDATIONS (priority order)

1. **Move `ensure_schema` to boot only.** One call in app startup (or a migration
   step). Delete it from every read/write. *(fixes C4, big latency win.)*
2. **Attribute predictions to the agents who made the claim**, and let
   `apply_outcome` move score for each contributing agent (weighted by stance).
   *(fixes C1.)*
3. **Bind recall to outcomes.** Join `council_sessions → predictions/archive`;
   down-weight or exclude sessions whose predictions graded `incorrect`, add a
   `superseded_by` link, and decay by age. Never recall a disproven verdict as
   authority without labelling it as such. *(fixes C2.)*
4. **Recalibrate reputation:** bounded/normalised score, decay keyed to a separate
   `last_outcome_at` (not `updated_at`), Bayesian prior for small samples, expected
   value from the agent's own rating. *(fixes C3.)*
5. **Make `apply_outcome` one transaction**; make consistency a windowed,
   incremental stat. *(fixes H4/M1.)*
6. **Paginate `due_reviews`** and add covering indexes on `(due_x, review_x)`.
   *(fixes H1.)*
7. **Replace recall internals with FTS5** (or a vector sidecar) so recall sees all
   history, not 500 rows. *(fixes H2.)*
8. **Scheduler:** atomic claim (`UPDATE … SET status='running' WHERE id=? AND
   status='pending'` then check rowcount); don't re-`enqueue` on boot if the job
   already exists; honor `run_at`. *(fixes H3.)*
9. **Move persistence off the request** to a background queue; make the Obsidian
   write async/deferred. *(fixes H6.)*
10. **Content-hash dedupe** sessions/predictions on `(normalised_directive,
    content)` within a window. *(fixes H5.)*
11. **Atlas:** instantiate drivers/edges per query via the model, persist to
    `system_maps`, keep the static graph only as a scaffold/prior. *(fixes M2.)*
12. **Single schema source** = migrations; delete `SCHEMA_SQL` duplication. *(M4.)*

---

## 7. STRESS TEST — 1 / 3 / 10 years

Assume two regimes: **moderate** (50 deliberations/day) and **heavy**
(500/day). Each deliberation ≈ 1 session + ~6 contributions + 1 archive row + 1
Obsidian file + ~1–2 predictions + history rows.

| Horizon | Moderate (50/day) | Heavy (500/day) |
|---|---|---|
| Sessions @1y / 3y / 10y | 18k / 55k / 183k | 183k / 548k / 1.8M |
| **SQLite size** (≈10–13 KB/deliberation all-in) | ~0.2 / 0.7 / 2.3 GB | ~2.3 / 7 / 23 GB |
| **Obsidian notes** (1/deliberation) | 18k / 55k / 183k files | 183k / 548k / **1.8M files** |
| `recall` visibility | already <3% at 1y | **<0.3% at 1y** |
| `due_reviews` latency | hundreds of ms once a backlog forms | **seconds**; daily clock job stalls |
| Maintenance | manual schema dual-source, no pooling | unworkable without the §6 fixes |

**The Obsidian archive is the first thing to break.** Obsidian's graph/index
degrades badly past ~50k notes; at heavy load the vault is unusable inside a year.
One note per deliberation with no rollup is unsustainable — archives need monthly
**rollup notes** (an MOC summarising N deliberations) with raw rows staying in
SQLite. **SQLite itself survives 10 years at moderate load**; the *access patterns*
(recall window, unbounded scans) fail long before the storage does.

---

## 8. LONG-TERM SUSTAINABILITY ASSESSMENT

**Storage:** sustainable (SQLite to multi-GB is fine). **Access patterns:** not
sustainable — recall blindness (H2) and unbounded scans (H1) make the system feel
*more forgetful and slower the more it remembers*, which is the exact inversion of
the mission. **Intelligence quality:** currently **negative-trending** — because
recall (C2) and reputation (C1/C3) feed bad signal back, more operation can make
the House *more* confidently wrong over time, not less. **Maintainability:** medium,
dragged down by dual schema and per-call `ensure_schema`.

**Bottom line for the build owner:** the v1/M0/M1 foundation is the right *shape* —
schema, modules, tests, migrations, scheduler are all real and the loop is wired.
But four defects mean the institution does not yet actually *learn from the right
signal* or *remember the right things*. **Fix C1–C4 before M2 (the Convener) ships**,
because M2 injects recall and reputation into live deliberation — wiring the two
most broken subsystems directly into the House's reasoning. Shipping M2 on top of
today's recall and reputation would operationalise the hallucination path, not
close it.

**Recommended gate:** M2 is **blocked** until C1, C2, C3, C4 are resolved and each
has a regression test. The other items are scheduled debt, not blockers.
