# ADR-0014 — State Consolidation: One Truth as a Canonical Provenance Graph

- **Status:** **Accepted for Planned Execution** (operator ruling 2026-07-19; four
  amendments recorded below). **P0 executed 2026-07-19** — see Execution record.
  Ratified as *Implemented* only after Acceptance Tests (Forward AND Reverse trace)
  pass on real data.
- **Date:** 2026-07-19 · **Blast radius:** Medium-Large (state layer; no cognitive-logic change)
- **Evidence base:** [docs/state/EVIDENCE_INVENTORY.md](../state/EVIDENCE_INVENTORY.md) — measured census, not assumption
- **Under:** ADR-0013 (Cognitive Constitutional Architecture — identity: *explicit semantics*; migration step 2 names this ADR), the House Bible ([backend/ARCHITECTURE.md](../../backend/ARCHITECTURE.md): "one bus, one truth")
- **Enables (downstream, in order):** Canonical Provenance Graph → Cognitive Trace Layer **as a projection** → Capability Graph → ADR-0016 → evidence-derived Cognitive Genome
- **Relates:** RFC-0001 (Reality Grading pilot — must not be disturbed; Observatory phase)

## Context

The Bible declares *one truth in one institutional DB*. The measured reality (inventory,
2026-07-19): 6 databases, 27 JSON state files, 8 audit streams, 226 trajectory blobs, and
per-workspace mission ledgers outside any census. **But the census also shows the drift is
narrower than feared** — two DBs are dead orphans, two are 9-row/3-row satellites, and
`skynerclaw.db` already holds every institutional table. The genuinely architectural
problems are exactly four:

1. **Mission-truth split-brain** — `agent_runs` (DB) *and* unregistered per-workspace
   `_MISSION_LEDGER.json` both claim mission outcome truth.
2. **Audit split three ways** — `constitution_audits` (DB) + `audit_trail.jsonl` +
   `kernel_audit.jsonl`, against the Bible's single journal.
3. **Co-owned state files** — `settings.json` (3 writers), `governance_config.json` (2),
   `atlas_genome.json` (3): no single owner, silent-conflict risk.
4. **Unpersisted decision traces** — DIF/DIC DecisionReports exist only in memory; the one
   missing fragment of the Cognitive Trace Layer.

## Decision

### The spine: One Truth is a Canonical Provenance Graph

"One truth" is not merely *one database* — it is *one connected account of why things are
true*. Every authoritative record must be **reachable by typed links** from the events that
produced it (operator's formulation: One Truth says there is a single truth; the Provenance
Graph says **how truths connect** — and that is the substrate the Cognitive Trace Layer
projects from).

**Prefer constraint over complexity:** no graph database, no new subsystem. The graph is
realized as **ID-linking conventions on existing tables** plus one thin `provenance_edges`
table (`from_kind, from_id, edge_type, to_kind, to_id, ts`) for links that have no natural
foreign key today. The Cognitive Trace Layer then becomes a **recursive query (projection)**
— never a Project.

Canonical trace chain (all fragments measured as already existing except D4):

```
mission (agent_runs) ─▶ trajectory blob ─▶ hypothesis (predictions)
      ─▶ evidence (sha256 · judge version) ─▶ evaluation ─▶ validated episode
      ─▶ belief revision (belief_changes) ─▶ [future] promotion ─▶ [D4] decision report
```

### The four decisions

**D1 — Mission truth: the DB is authoritative; the workspace ledger becomes a projection.**
`agent_runs` (+ a `mission_signoff` extension: status, files, done_when, ledger_id) is the
single mission record. Per-workspace `_MISSION_LEDGER.json` is regenerated *from* the DB as
a local convenience view — kept (operators and agents read it in-workspace) but demoted:
derived, never authoritative. *Consequence:* RFC-0001's judge will read the DB first
(workspace file as fallback) — a judge-semantics change ⇒ **JUDGE_VERSION bumps to rg-2**
per Learning Integrity #2, and only **after** the current pilot's episodes are graded under
rg-1 (never mid-pilot).

> **Semantic Migration Rule (operator amendment):** a judge-version bump SHALL carry a
> **Migration Note**, never a bare number: `{version, supersedes, reason, expected
> behavioral changes}`. A year from now, a version number alone cannot explain the past.

**D2 — The Canonical Event Journal.** All new audit events (constitution, kernel, runtime
trail) write to a single append-only `journal` table (`ts, source, actor, event, payload`)
in the institutional DB. Existing `.jsonl` audit files are **frozen as read-only archive —
never deleted** (Constitution Article 1: never modify or delete the audit log;
consolidation forward, preservation backward). *Named for its role, not its mechanics
(operator amendment): "forward-only" describes behavior; "canonical" describes purpose.*

**D3 — Single ownership for co-owned state.** Each of `settings.json`,
`governance_config.json`, `atlas_genome.json` gets exactly one owner module exposing a
read/write API; the other writers become callers. File formats unchanged (backward
compatible); only the write path narrows.

> **Elevated to Constitution (operator amendment)** — the **State Ownership Principle**
> is a system-level law, not an ADR-local decision: *"Every mutable state SHALL have
> exactly one authoritative writer. Derived projections MAY exist. Additional
> authoritative writers SHALL NOT."* Staged in
> [Constitution.md §9](../v3/kernels/Constitution.md) pending ceremony.

**D4 — Persist decision traces (completes the graph).** DIF `DecisionReport` / DIC
`DecisionResult` gain a `to_row()` persisted into the truth store, linked by provenance
edges to their mission. **Gated:** executes only post-freeze / on wiring approval — until
then it is the declared, designed gap.

> **Structure is canonical; language is a projection (operator amendment).** The persisted
> record stores the **decision structure** — `{mission, capabilities, evidence IDs,
> constraint IDs, policy IDs, decision, confidence}` — as canonical. Natural-language
> reasoning text is a *projection* rendered from that structure, never the stored truth:
> prose changes form; structure must stay stable.

### Guard rail (makes the ADR executable, not aspirational)

> **CI tripwire:** creating a new top-level state store (a `.db` or a root-level state
> `.json`) without an ADR reference fails the build. The drift that produced 6 DBs must be
> structurally impossible to repeat silently.

## Mechanical appendix (no architectural decision required)

- **T0 — delete dead weight** (verified zero code references; dated backup first):
  `data.db` (0 tables), `openclaw.db` (empty duplicate tables),
  `_house_archive_backup.json`, table `_ox_hc1_bak_house_state`.
- **T1 — absorb satellites:** `runtime_registry.db` (9 rows) and `runtime_metrics.db`
  (3 rows) become tables in the institutional DB; their single owners
  (`runtime_boot`, `runtime_metrics`) repoint.
- **Declare projections:** `skills_index`, `skills_capability_index`, `vision_probe_cache`,
  `runtime_inventory/rankings`, `driver_inventory`, `capabilities.json` are rebuildable
  caches — documented as such, excluded from any truth claim.
- **Charter:** `chat_history.db` is explicitly chartered as the *transcript store*
  (conversation logs are records of dialogue, not institutional beliefs) — merged only if
  a later evidence review shows cross-store joins are actually needed.
  *Operator's formulation, adopted:* **"Dialogue is evidence about cognition, not
  cognition itself"** — the transcript is an Evidence Source, never Canonical State.

## Execution phasing (Observatory-compatible)

| Phase | What | When | Pilot risk |
|---|---|---|---|
| P0 | T0 deletions + T1 absorption + tripwire | during the 7-day observation window | none (zero contact with the learning loop) |
| P1 | D3 ownership narrowing | after P0 | none |
| P2 | D2 one journal (forward-only) | after P1 | none (append path only) |
| P3 | D1 mission-truth swap + judge rg-2 | **after** the pilot's first episodes are graded under rg-1 | managed (judge version discipline) |
| P4 | D4 decision-trace persistence | post-freeze | n/a |

## Execution record

**P0 — executed 2026-07-19** (backend down; dated backups verified byte-equal in
`backend/backups/adr0014_p0_20260719/` before any change):
- Absorbed `runtime_registry.db → models` (9 rows) and `runtime_metrics.db →
  runtime_metrics` (3 rows) into the institutional DB, row-counts verified equal;
  owners `runtime_boot._registry_db_path()` and `runtime_metrics._DB` repointed.
- Dropped stale OX backup table `_ox_hc1_bak_house_state` (full-DB backup taken first).
- Retired to backup (not destroyed): `data.db`, `openclaw.db`,
  `_house_archive_backup.json`.
- **Result: 6 databases → 2** (`skynerclaw.db` institutional, `chat_history.db`
  chartered transcript).
- Guard rail landed: `backend/tests/test_state_tripwire.py` — unchartered `.db` or new
  root-level state `.json` fails the suite; retirements stay retired. Adding a store
  requires editing the tripwire, which requires the chartering ADR (the edit IS the gate).
- Verification: tripwire 4/4 · repointed owners read absorbed tables · regression
  118/118 (institutional + learning + DI suites) · reality-grading pilot untouched.

P1 (D3 ownership) → next. P2 (Canonical Event Journal) → after P1. P3 (D1 + judge rg-2
with Migration Note) → deferred until the first rg-1 validated episode. P4 (D4) →
post-freeze.

## Counter-arguments (challenge mode, answered)

1. *"Re-plumbing state is the riskiest thing you can do to a stable single-box system."* —
   True for big-bang; this is why T0/T1 (dead weight) go first, every step has a dated
   backup, projections are regenerable, and D1 — the only semantics-touching step — waits
   for the pilot and announces itself via a judge-version bump. **Survives, phased.**
2. *"chat_history.db should merge too — otherwise it's still 2 DBs."* — One Truth is about
   *institutional belief*, not about the count of files; transcripts are evidence-of-
   dialogue, not beliefs. Chartering beats merging until a join is actually needed
   (constraint over complexity). **Survives as a charter.**
3. *"provenance_edges is a new subsystem in disguise."* — It is one table + conventions;
   the reading side is a projection. If it ever grows write-side logic, that is the signal
   it was wrong. **Survives with that tripwire stated.**

## Verification

- Store count after P0/P1: DBs 6 → 3 (institutional, transcript, —), root state JSONs
  reclassified (authoritative vs projection) with owners named in this ADR's tables.
- CI tripwires: new-store guard; single-writer guard for D3 files; T0 stays deleted.
- The CTL acceptance tests (later) — **both directions must pass** (operator amendment):
  - **Forward Trace:** one projection query reconstructs
    `mission → hypothesis → evidence → evaluation → belief revision` for any mission id.
  - **Reverse Trace:** from any `belief revision` id, the same graph answers
    *which evaluation → which evidence → which hypothesis → which mission* produced it.
  Forward and Reverse passing together — on real data — is the definition of the
  Canonical Provenance Graph being complete, and **that IS the Cognitive Trace Layer
  arriving as a projection.** These tests measure behavior, not schema.

## Consequences

**Positive** — the Bible becomes true again; the provenance graph gives CTL, Capability
Graph, ADR-0016, and an evidence-derived Genome one substrate; future drift is structurally
blocked, not policed by memory.

**Costs / honest limits** — D1 requires touching the sign-off path and the RFC-0001 judge
(sequenced, versioned); D2 is forward-only (historical audits stay in three archives —
unified *querying* of old audit history is deliberately out of scope); ROI of edge-table
generality is unproven until CTL's first real query (measured then, per Observatory
discipline).
