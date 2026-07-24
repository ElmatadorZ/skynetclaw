# THE HOUSE — vNext Architecture & Roadmap
### From a collection of agents to an institution that remembers, deliberates, learns, and improves.

> Status: **architecture proposal — no code until this roadmap is approved.**
> Author: Chief Architect, THE HOUSE. Grounded in the real codebase (16,264 lines
> backend Python, `main.py` 5,982 lines / 93 routes, 35 modules, 4 SQLite DBs,
> 5 HTML front-ends). Phases 1–6 already have a working v1 foundation (built in the
> previous cycle); this document assesses it honestly and defines what vNext must add
> to make it a true institution.

---

## 0. Reading this document

The mission lists seven phases, but the required *output* is ten architecture
artifacts. This document delivers the ten artifacts and folds the seven phases into
them. Section map:

| # | Required deliverable | Where |
|---|---|---|
| 1 | Current Architecture Assessment | §1 |
| 2 | Architectural Debt Analysis | §2 |
| 3 | Future-State Architecture | §3 |
| 4 | Dependency Graph | §4 |
| 5 | Database Design | §5 |
| 6 | API Design | §6 |
| 7 | Folder Structure | §7 |
| 8 | UI Architecture (Council Chamber) | §8 |
| 9 | Implementation Roadmap | §9 |
| 10 | Risk Analysis | §10 |

Phase designs (Memory, Archive, Constitution, Reputation, Atlas V2, Scout V2,
Chamber) appear inside §3 and §5–§8, each tagged with honest status:
**[LAID]** v1 exists, **[GAP]** designed but not built, **[DEBT]** exists but wrong shape.

---

## 1. Current Architecture Assessment

### 1.1 What THE HOUSE is today
A FastAPI backend (`main.py`, 5,982 lines, 93 routes) fronting a single autonomous
agent loop (`agent_run`, SSE streaming, one model tool-calling at a time), plus ~35
satellite modules mounted onto the app. A 14-member council exists conceptually
(Commander, Atlas, Analyst, Strategist, Skeptic, Auditor, Governor, Architect, Scout,
Storyteller, Concierge, Forecaster, Sentinel, Executor) and is realised three ways:
as **prompt personas** injected into the loop, as a **6-specialist async fan-out**
(`agent_council.run_council`), and as **folder-based skills** (15 skills, trigger-routed).

### 1.2 Subsystems that exist and work
- **Live agent loop** — `agent_run`: mission ledger sign-off (COMPLETE/INCOMPLETE/
  PROBLEM), Scout delegation on failure, ATLAS counsel injection, and **L3 Compound
  Mind + L6 Cosmic Mind** decomposition (replaces linear 1-2-3 planning).
- **Council** — `agent_council.run_council`: 6 specialists in parallel, aggregate
  verdict, Skeptic veto. Reached today only via the `agentic_workflow` endpoint.
- **Institutional Memory v1 [LAID]** — `council_memory`, `deliberation_archive`,
  `house_constitution`, `agent_reputation`, `outcome_tracker`, `atlas_system_map`,
  `obsidian_knowledge_protocol`, `council_intelligence_api`, `institutional_db`
  (one schema owner, 6 tables, 9 indexes, migrations + rollback, 48 tests / 92%).
- **Skills** — folder-based, bilingual trigger routing, index + DB sync.
- **Governance** — `governance.py` (GTS-1 task state, GPS-2 permission, GOP-3 loop bounds).
- **Knowledge** — `obsidian_tools.py` → vault `<YOUR_VAULT>` (Johnny Decimal).
- **Self-* layer** — `metacognition`, `self_awareness`, `self_debug`, `volition_engine`,
  `skynet_genesis_masterpiece` (L0–L8 stages), `openclaw_port` (trajectory/diary).

### 1.3 Data & interface surfaces
- **DBs:** `skynerclaw.db` (200 KB, primary — skills, connections, agent_runs,
  institutional tables), `chat_history.db` (124 KB), `openclaw.db` (28 KB), `data.db` (empty).
- **Front-ends:** `index.html` (197 KB monolith — main UI), `THE CONTINENTAL DIVISION.html`
  (123 KB — high-ceremony command theatre, closest thing to a chamber),
  `masterpiece_dashboard.html`, `council_dashboard.html` (new), `bridge_console.html`.

### 1.4 Honest verdict
The parts of an institution exist as **organs without a nervous system**. Memory is
stored but not *consulted* during deliberation. The council deliberates but is not the
primary path — most work is single-agent. Predictions can be recorded but nothing
*extracts* them, so the learning loop is open. The interface is dashboards, not a place.
THE HOUSE remembers in a filing cabinet nobody opens mid-meeting.

---

## 2. Architectural Debt Analysis

Ranked by leverage (impact × likelihood of causing failure).

| # | Debt | Evidence | Consequence | Severity |
|---|---|---|---|---|
| D1 | **`main.py` monolith** | 5,982 lines, 93 routes, LLM streaming + tools + DB + skill-text + endpoints in one file | Every change is high-risk; merge hell; the FUSE stale-size quirk truncates edits | **Critical** |
| D2 | **Open learning loop** | `predictions` table exists; no extractor pulls forecasts from council runs; no scheduler runs 30/90/180 reviews | Reputation never updates from reality → "learns" is aspirational | **Critical** |
| D3 | **Council is not the spine** | Deliberation lives in a side endpoint; `agent_run` is single-agent | The institution rarely actually deliberates | **High** |
| D4 | **Memory not consulted in-loop** | `recall()` exists but isn't injected before deliberation | Constitution R6 (historical comparison) unenforced in practice | **High** |
| D5 | **Constitution is advisory** | injected as text; `check_compliance` exists but is not a gate | Rules are suggestions, not governance | **High** |
| D6 | **DB sprawl** | 4 SQLite files, no unified data-access layer, schema spread across modules | Migration risk; FUSE write-locks; no single source of truth | **Medium** |
| D7 | **Front-end monoliths** | 197 KB + 123 KB single HTML files, no component system | UI changes are brittle; 5 competing surfaces | **Medium** |
| D8 | **Reputation model incomplete** | no time-decay, no consistency metric (Phase 4 asks for both) | Stale reputations; gaming by volume | **Medium** |
| D9 | **No background scheduler** | reviews, decay, archive integrity are all manual | Time-based institutional behaviour can't happen | **Medium** |
| D10 | **Identity scatter** | agent names differ across roster (OPV codes), council roles, skills, reputation table | Joins by string; drift | **Low-Med** |

---

## 3. Future-State Architecture

### 3.1 The one-sentence target
A **deliberation-first institution**: directives enter a Chamber, the Council
deliberates *with its own history in front of it*, the Constitution gates the verdict,
the verdict + its predictions are archived, and a clock later grades those predictions
and moves reputations — closing the loop.

### 3.2 Layered model

```
┌─────────────────────────────────────────────────────────────────────┐
│  L7  CHAMBER (UI)        The House — cinematic, obsidian+gold         │
│                          directive in · deliberation theatre · verdict│
├─────────────────────────────────────────────────────────────────────┤
│  L6  INSTITUTION API     /api/house/* — directive, session, recall,   │
│                          reputation, outcomes, constitution, chamber  │
├─────────────────────────────────────────────────────────────────────┤
│  L5  DELIBERATION CORE   Convener → Recall → Council(14) → Constitution│
│      [GAP: Convener]     Gate → Verdict → Prediction Extractor        │
├─────────────────────────────────────────────────────────────────────┤
│  L4  INSTITUTIONAL       Memory · Archive · Reputation · Outcome ·     │
│      MEMORY [LAID]       Constitution · Atlas V2 · Scout V2           │
├─────────────────────────────────────────────────────────────────────┤
│  L3  COGNITION           agent_run loop · Compound Mind L3/L6 ·        │
│                          agent_council fan-out · skills router        │
├─────────────────────────────────────────────────────────────────────┤
│  L2  GOVERNANCE          GTS-1 state · GPS-2 permission · GOP-3 loops  │
├─────────────────────────────────────────────────────────────────────┤
│  L1  DATA                institutional_db (one owner) · KnowledgeStore │
│      [DEBT: unify]       (Obsidian) · vector recall [GAP]             │
├─────────────────────────────────────────────────────────────────────┤
│  L0  RUNTIME             FastAPI · SSE · LLM adapter · scheduler [GAP] │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.3 The closed loop (the heart of vNext)

```
   Operator directive
        │
        ▼
   ┌──────────┐   recall(directive)     ┌────────────────────┐
   │ CONVENER │◄────────────────────────│ Council Memory      │
   │  [GAP]   │  "here is what the House │ (prior verdicts,    │
   └────┬─────┘   decided before"        │  dissent, outcomes) │
        │                                 └────────────────────┘
        ▼
   ┌────────────────────┐   constitution gate   ┌──────────────┐
   │ COUNCIL (14)        │──────────────────────►│ Constitution │
   │ deliberate w/ history│   check_compliance    │  enforce     │
   └────┬───────────────┘   (block if invalid)   └──────────────┘
        │ verdict + confidence + dissent
        ▼
   ┌────────────────────┐   extract forecasts    ┌──────────────┐
   │ PREDICTION EXTRACTOR│──────────────────────►│ predictions   │
   │  [GAP]              │   (statement+invalid.) │  (scheduled)  │
   └────┬───────────────┘                         └──────┬───────┘
        ▼                                                 │ 30/90/180d
   ┌────────────────────┐                                 ▼
   │ DELIBERATION ARCHIVE│                          ┌──────────────┐
   │ SQLite + Obsidian   │                          │ OUTCOME CLOCK │
   └────────────────────┘                          │  [GAP: sched] │
                                                     └──────┬───────┘
                                                            ▼
                                                     ┌──────────────┐
                                                     │ REPUTATION    │
                                                     │ +decay +consist│
                                                     └──────────────┘
```

**The four [GAP] components are the real vNext build:** Convener, Prediction
Extractor, Outcome Clock (scheduler), and the Chamber UI — plus hardening Reputation
(decay + consistency) and turning the Constitution into an actual gate.

### 3.4 Phase status against the target

| Phase | Component | Status | vNext action |
|---|---|---|---|
| 1 | Council Memory Engine | **[LAID]** | add vector recall; inject recall into deliberation |
| 2 | Deliberation Archive | **[LAID]** | add retention policy + Obsidian MOC backfill |
| 3 | House Constitution | **[LAID]**/[DEBT] | promote from text → **enforcement gate** + validation hooks |
| 4 | Agent Reputation | **[LAID]**/[GAP] | add time-decay + consistency metric + scorecards |
| 5 | Atlas V2 | **[LAID]** | wire into Convener so macro queries auto-map |
| 6 | Scout V2 | **[LAID]** | wire `plan_write` as a pre-write gate on every Obsidian write |
| 7 | Council Chamber | **[GAP]** | net-new — §8 |
| — | Convener / Extractor / Clock | **[GAP]** | net-new — the loop closers |

---

## 4. Dependency Graph

### 4.1 Current (as-built)

```
                         main.py (monolith, 93 routes)
   ┌──────────────┬───────────┬──────────────┬─────────────┬────────────┐
   ▼              ▼           ▼              ▼             ▼            ▼
 agent_council  compound_   continental_  governance   skills_auto_  council_
   │            mind          relay          │           router       intelligence_api
   ▼              ▼                          ▼             ▼            │
 agentic_      llm_adapter              governance_    skills_       ┌──┴───────────────┐
 workflow        │                       config.json   loader        ▼      ▼      ▼     ▼
   │             ▼                                                  council_ agent_ outcome_ deliberation_
   └────► institutional memory ◄──────────────────────────────────  memory  reputation tracker  archive
                  │                                                     └──────┴───────┴────────┘
                  ▼                                                            ▼
            institutional_db ──► skynerclaw.db          obsidian_tools ──► <YOUR_VAULT>
```

Key fact: **everything depends on `main.py`** because it owns the routes and the loop.
`institutional_db` is the only clean shared foundation. `agent_council` now depends on
`council_memory` + `deliberation_archive` (the auto-persist hook).

### 4.2 Target (vNext) — break the monolith into a spine

```
            ┌──────────────── chamber (front-end, componentised) ───────────────┐
            ▼
        house_api (router package)  ── /api/house/* ── thin controllers only
            │
            ▼
        deliberation_core   ── Convener · Council · Constitution-gate · Extractor
            │                     (orchestrates; owns no I/O)
   ┌────────┼─────────────┬───────────────┬───────────────┐
   ▼        ▼             ▼               ▼               ▼
 memory   reputation   outcome+clock   constitution    atlas_v2 / scout_v2
   └────────┴─────────────┴───────────────┴───────────────┘
                          ▼
                 data layer (institutional_db + KnowledgeStore + vector index)
```

Direction of dependencies points **downward only**. `deliberation_core` becomes the
new center of gravity; `main.py` shrinks to a runtime bootstrap that mounts routers.

---

## 5. Database Design

### 5.1 Current institutional schema (in `skynerclaw.db`) — **[LAID]**
`council_sessions`, `council_contributions`, `deliberation_archive`,
`agent_reputation`, `predictions`, `schema_migrations` (+9 indexes; FK cascade/setnull;
rollback drops only institutional tables).

### 5.2 vNext schema additions

```sql
-- Phase 4 hardening: reputation over time (decay + trend + consistency)
CREATE TABLE reputation_history (
    id TEXT PRIMARY KEY, agent TEXT, ts REAL,
    score REAL, accuracy_rate REAL, consistency REAL,
    event TEXT  -- 'outcome'|'decay'|'contribution'
);

-- Loop-closer: structured forecasts extracted from verdicts (supersedes free-text)
ALTER TABLE predictions ADD COLUMN extracted_from TEXT;     -- session_id
ALTER TABLE predictions ADD COLUMN horizon_primary TEXT;    -- 30|90|180
ALTER TABLE predictions ADD COLUMN metric TEXT;             -- what is measured
ALTER TABLE predictions ADD COLUMN direction TEXT;          -- up|down|flat|event

-- Constitution as gate: record every compliance check
CREATE TABLE constitution_audits (
    id TEXT PRIMARY KEY, session_id TEXT, ts REAL,
    score REAL, violations TEXT, blocked INTEGER  -- 1 if verdict rejected
);

-- Atlas V2 system maps persisted for recall/comparison
CREATE TABLE system_maps (
    id TEXT PRIMARY KEY, session_id TEXT, ts REAL,
    query TEXT, layers TEXT, map_json TEXT
);

-- Scheduler bookkeeping (Outcome Clock, decay job, archive integrity)
CREATE TABLE scheduled_jobs (
    id TEXT PRIMARY KEY, kind TEXT, run_at REAL, last_run REAL,
    status TEXT, payload TEXT
);
```

### 5.3 Data strategy decisions
- **One database, `skynerclaw.db`** is the institutional source of truth. Deprecate
  `data.db` (empty), quarantine `openclaw.db` behind its module, leave `chat_history.db`
  as the transcript store. No new DB files.
- **Vector recall [GAP]:** add a `recall_vectors` table (sqlite-vss or a numpy sidecar)
  so `recall()` upgrades from token-Jaccard to semantic. Optional, behind a flag.
- **Retention:** sessions/contributions kept indefinitely (institutional memory is the
  product). Archive notes never deleted — superseded ones get a `superseded_by` link.
  `scheduled_jobs` rows pruned after 90 days.

---

## 6. API Design

Consolidate scattered routes under a versioned institutional namespace. Existing
`/api/council/*` (already shipped) is absorbed and extended.

```
POST   /api/house/directive            issue a directive → opens a deliberation (SSE)
GET    /api/house/session/{id}         full session: verdict, contributions, dissent
GET    /api/house/sessions?filter=     filter/compare (agent, confidence, date, topic)
GET    /api/house/recall?q=            historical recall (semantic when enabled)

GET    /api/house/constitution         the 7 rules
POST   /api/house/constitution/check   run compliance on text → score + violations

GET    /api/house/reputation           leaderboard + scorecards
GET    /api/house/reputation/{agent}   scorecard: accuracy, consistency, trend, history
GET    /api/house/reputation/trends    consensus & confidence trends

GET    /api/house/outcomes/summary
GET    /api/house/outcomes/due/{30|90|180}
POST   /api/house/outcomes/{pid}/evaluate

GET    /api/house/atlas/map?q=         Atlas V2 civilization map (persisted)
POST   /api/house/scout/plan-write     Scout V2 pre-write gate (dedupe/link/JD)

GET    /api/house/chamber              serves the Chamber UI
WS     /api/house/chamber/stream       live deliberation events for the Chamber
```

Design rules: thin controllers (no business logic in routes), every route delegates to
a service module, SSE for the live loop, WebSocket for the Chamber's real-time theatre.
Backwards-compat: keep `/api/council/*` as aliases for one release, then deprecate.

---

## 7. Folder Structure

Target package layout — break the monolith without a big-bang rewrite.

```
backend/
├── app.py                        # NEW thin bootstrap: builds FastAPI, mounts routers
├── runtime/
│   ├── llm_adapter.py            # (moved) provider streaming
│   ├── scheduler.py              # NEW Outcome Clock + decay + integrity jobs
│   └── sse.py                    # NEW shared SSE/WS helpers
├── cognition/
│   ├── agent_loop.py             # (extracted from main.py) agent_run
│   ├── compound_mind.py          # L3/L6 (exists)
│   └── council.py                # agent_council (exists)
├── institution/                  # the subsystem — most already built
│   ├── institutional_db.py       # schema owner (exists)
│   ├── memory.py                 # council_memory (exists)
│   ├── archive.py                # deliberation_archive (exists)
│   ├── constitution.py           # house_constitution (exists) + gate hooks NEW
│   ├── reputation.py             # agent_reputation (exists) + decay/consistency NEW
│   ├── outcomes.py               # outcome_tracker (exists)
│   ├── convener.py               # NEW recall→brief→assemble council
│   ├── extractor.py              # NEW pull predictions from verdicts
│   ├── atlas_v2.py               # atlas_system_map (exists)
│   └── scout_v2.py               # obsidian_knowledge_protocol (exists)
├── governance/                   # governance.py (exists)
├── knowledge/                    # obsidian_tools + Scout gate
├── api/
│   └── house_router.py           # /api/house/* thin controllers (absorbs council_intelligence_api)
├── migrations/                   # 001 (exists) + 002 vNext
├── tests/                        # exists (92%); grows with each phase
└── web/
    └── chamber/                  # NEW componentised Chamber front-end
```

Migration is **strangler-pattern**: new code lands in packages, `main.py` routes are
moved one cluster at a time behind the new routers, old file kept until parity proven.

---

## 8. UI Architecture — THE COUNCIL CHAMBER (Phase 7)

> Not a dashboard. A place. The Operator issues a directive; the Council convenes.
> References: The Continental's High Table · Foundation · Dune · Palantir.

### 8.1 Principles
- The **center is the Council**, not charts. Analytics are a side drawer, never the stage.
- **Black obsidian + gold.** Restraint. Negative space. Weight. Ceremony over density.
- **Ritual cadence:** Convene → Deliberate → Dissent → Verdict → Seal. Each step has a
  beat; the UI breathes between them rather than dumping output.
- **Cinematic but legible:** motion serves meaning (a member "speaks" = their seat lights).

### 8.2 The stage — the Round Table

```
                          ◆ THE HOUSE ◆
                 directive: "____________________"  ⏎

              Forecaster   Strategist   Analyst
                    ◦          ◦          ◦
          Sentinel ◦                        ◦ Atlas
                                              
        Concierge ◦        ⟁ VERDICT ⟁        ◦ Skeptic
                          confidence ████░ 0.62
          Scout  ◦                        ◦ Auditor
                    ◦          ◦          ◦
               Governor    Storyteller   Executor
                       (Commander presides, center-top)

   ── dissent ribbon ───────────────────────────────────
   Skeptic ▸ REBUILD: liquidity thin; invalidation < 58k
```

- **14 seats** around an obsidian table. Idle = dim gold rim. Speaking = seat ignites,
  their contribution streams into a focus card. Dissent = seat pulses crimson and the
  **dissent ribbon** preserves the minority view (Constitution R5 made visible).
- **Center medallion** = the live verdict + confidence meter, forming as the council
  converges. The Constitution gate flashes a seal (✓) or rejects (✗ with the violated rule).

### 8.3 Component hierarchy

```
<Chamber>
├── <DirectiveBar>            issue directive; shows Convener's recall ("the House last ruled…")
├── <RoundTable>
│   ├── <Seat agent× 14>      state: idle|thinking|speaking|dissenting
│   ├── <FocusCard>           the currently-speaking member's reasoning (streamed)
│   └── <VerdictMedallion>    verdict + confidence + Constitution seal
├── <DissentRibbon>           preserved minority opinions
├── <RecallScroll>            prior comparable sessions (collapsible, Convener-fed)
└── <Antechamber> (drawer)    analytics: reputation, outcomes, learning trends
```

### 8.4 Interaction model
- **Directive → SSE/WS stream** of events: `convened`, `recall`, `member_speaking`,
  `dissent`, `verdict`, `sealed`. Each event drives one seat/medallion transition.
- **No spinner.** Latency is dressed as deliberation ("The Council is weighing…").
- **Operator verbs:** *Issue*, *Press* (ask a member to elaborate), *Seal* (accept),
  *Send back* (reject verdict → re-deliberate). These map to API calls, not form fields.
- **The Antechamber** holds the existing `council_dashboard.html` panels — reputation,
  outcomes, learning — reachable but never on the main stage.

### 8.5 Build approach
Single-page, componentised (web components or a light React build), obsidian theme
tokens, WebSocket client. It **replaces** the static council screen and supersedes the
scattered dashboards; `THE CONTINENTAL DIVISION.html` is the closest existing ancestor
and its ceremony language is the starting palette.

---

## 9. Implementation Roadmap

Sequenced by dependency and risk. Each milestone ships behind a flag, with tests, and
leaves the system runnable. **No code begins until this roadmap is approved.**

**M0 — Foundation hardening (1 unit)** · *enables everything*
- Verify/seed institutional schema on boot; add migration 002 (new tables/columns §5.2).
- Stand up `runtime/scheduler.py` skeleton (no jobs yet). Risk: low.

**M1 — Close the learning loop (2 units)** · *makes "learn" real* · addresses D2
- `extractor.py`: pull structured predictions from every council verdict.
- `scheduler.py` Outcome Clock: enqueue 30/90/180 reviews; surface "due" to Operator.
- Reputation hardening: time-decay + consistency metric + `reputation_history`.
- Tests: extraction, scheduling, decay math. Exit: a verdict produces gradable predictions.

**M2 — Deliberation-first spine (2 units)** · *makes the council the center* · D3,D4
- `convener.py`: on directive → `recall()` prior sessions → brief the council → run
  `run_council` with history in context. Inject Atlas V2 map for macro directives.
- Make `agent_run` able to *escalate* to a council deliberation. Exit: directives
  deliberate with their own history visible.

**M3 — Constitution as gate (1 unit)** · *governance, not suggestion* · D5
- Promote `check_compliance` to a **gate**: verdicts scoring < threshold are blocked or
  flagged; write `constitution_audits`. Validation hooks on archive + prediction writes.

**M4 — The Council Chamber (3 units)** · *the institution becomes a place* · D7
- Build `web/chamber/` per §8; WebSocket event stream; replace the static council screen.
- Antechamber absorbs existing dashboards. Exit: a directive runs end-to-end in the Chamber.

**M5 — Strangle the monolith (2 units, ongoing)** · *maintainability* · D1
- Extract `agent_run` and route clusters from `main.py` into `cognition/` + `api/`.
- Move one cluster per PR behind the new routers; keep `main.py` parity until proven.

**M6 — Knowledge & recall depth (1–2 units, optional)** · D6
- Scout V2 as a pre-write gate on all Obsidian writes; semantic vector recall behind a flag.

Critical path: **M0 → M1 → M2 → M3 → M4.** M5 runs in parallel after M2. M6 is optional.

---

## 10. Risk Analysis

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **`main.py` edits corrupt the running system** (size, FUSE truncation, 93 routes) | High | High | Strangler pattern; never big-bang; parse-verify edits; new code in packages, not `main.py` |
| R2 | **Prediction extraction is low-quality** (LLM emits vague forecasts) | Med | High | Structured extraction schema (metric/direction/invalidation); reject unfalsifiable forecasts at the gate (Constitution R4) |
| R3 | **Scheduler reliability** (reviews never fire; process not always up) | Med | High | Idempotent `scheduled_jobs` table + catch-up on boot; reviews are durable, not in-memory timers |
| R4 | **Reputation gaming / cold-start** (volume beats accuracy; new agents unrated) | Med | Med | Consistency metric + decay; Bayesian prior on small samples; separate quality vs outcome signals (already split) |
| R5 | **Constitution gate blocks legitimate verdicts** (false positives) | Med | Med | Start in *flag* mode, measure, only then *block*; per-rule thresholds; human override logged |
| R6 | **Chamber over-engineered / slow** (cinematic UI ships late) | Med | Med | Ship a static round table first; layer motion behind the working event stream; reuse Continental palette |
| R7 | **DB write contention** (FUSE locks in dev; WAL on prod) | Low-Med | Med | Single DB, WAL mode (already on), retries; dev uses native fs for tests |
| R8 | **Scope creep across 7 phases** | High | Med | This roadmap; flags; each milestone independently shippable and reversible |
| R9 | **Identity drift** (agent names mismatch across tables/roster/skills) | Med | Low-Med | Canonical agent registry; join on stable IDs, not display strings |
| R10 | **Vector recall dependency weight** | Low | Low | Keep behind a flag; token-Jaccard recall remains the default |

---

## Decision requested
The four loop-closers (Convener, Prediction Extractor, Outcome Clock, Constitution
gate) plus the Council Chamber are the vNext build; Phases 1, 2, 5, 6 are foundation
already laid and need only wiring. **Approve the roadmap (or reorder the milestones)
and I begin at M0.** No code is written until then.
