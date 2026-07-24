# M3 — Governance Engine
### The Constitution does not advise. It governs.

> Scope: turn the seven House rules from injected text into enforced law, require
> five records from every session, and track minority dissent over time so the House
> learns when a minority was right. Status: **delivered, 118 tests pass,
> governance_engine 92% coverage, schema v4.**

---

## 1. Architecture

Before M3 the Constitution was a system message — advice the council could ignore. M3
makes it a **gate**. Every verdict is enforced, recorded, and — when it breaks a binding
rule — **rejected**. Dissent becomes a tracked, first-class artifact.

```
        council verdict (run_council)
               │
               ▼
 ┌──────────────────────────────────────────────────────────────┐
 │  GOVERNANCE ENGINE  (governance_engine.py)                    │
 │                                                              │
 │  extract_records()  → the FIVE required records:             │
 │     majority_position · minority_positions · evidence_record │
 │     · confidence_record · uncertainty_record                 │
 │                                                              │
 │  enforce()          → check the 7 rules → violations →       │
 │     binding DECISION:  PASS / FLAGGED / REJECTED             │
 │       forecast w/o invalidation → REJECT (R4)                │
 │       claim w/o evidence        → REJECT (R1/R7)             │
 │       minority omitted          → REJECT (R5)                │
 │       uncertainty not stated    → FLAG   (R3)                │
 │       (rules may be WAIVED with a recorded reason)           │
 │                                                              │
 │  govern()           → persist governance record +           │
 │                        minority_positions                    │
 └───────────┬──────────────────────────────────┬─────────────┘
             │ REJECTED → verdict annotated       │
             ▼                                    ▼
   "⚖ GOVERNANCE REJECTED (R4): …"      constitution_audits (audit trail)
                                         minority_positions  (dissent ledger)
                                                  │
                            (30/90/180d later, outcomes land)
                                                  ▼
                                   on_outcome(session) — was the majority right?
                                     majority WRONG  → dissenters VINDICATED
                                       → proven_correct=1, reputation reward
                                     majority RIGHT  → dissent resolved, NOT punished
```

Two integration points (best-effort, guarded):
- **`agent_council.run_council`** — `enforce()` runs on the verdict before it ships;
  a REJECTED verdict is annotated; `_persist_council` calls `govern()` to write the
  audit + minorities.
- **`outcome_tracker.evaluate`** — when a session is fully graded, `on_outcome()`
  resolves its minorities and rewards vindicated dissent.

---

## 2. The Five Required Records

`extract_records(verdict)` derives, from every council verdict:

| Record | Source | Purpose |
|---|---|---|
| **majority_position** | `aggregate_recommendation` | the consensus that ships |
| **minority_positions** | Skeptic dissent verdict (REBUILD/FRAGILE/VETO/…) + any role with disagreement language | who disagreed and why — preserved, never erased |
| **evidence_record** | Analyst `known`/`inferred` + any block citing a source/data | what the position rests on |
| **confidence_record** | per-role stated `confidence` | how sure each member was |
| **uncertainty_record** | Analyst `unknown`/`data_gaps` + Forecaster early warnings | what the House admits it doesn't know |

A session that cannot produce these is, by construction, in violation.

---

## 3. Enforcement (binding law)

`enforce(verdict, records, waivers)` → `{decision, violations, waivers, governance_score, rejects, flags}`.

| Rule | Trigger | Severity |
|---|---|---|
| **R4** Forecasts require invalidation | a forward-looking forecast with no invalidation/early-warning condition | **REJECT** |
| **R1/R7** Evidence before opinion / traceability | a position reached with an empty evidence_record | **REJECT** |
| **R5** Minority preserved | dissent detected but no minority position recorded | **REJECT** |
| **R3** State uncertainty | empty uncertainty_record and no uncertainty language | **FLAG** |

- **Decision:** `REJECTED` if any non-waived REJECT violation; else `FLAGGED` if any flag;
  else `PASS`.
- **Governance score:** `(7 − violated_rules) / 7`, persisted per session.
- **Waivers:** a rule id can be explicitly waived (operator override); the violation moves
  to the `waivers` list (recorded, not silently dropped) and no longer rejects.

A REJECTED verdict ships with its aggregate prefixed `⚖ GOVERNANCE REJECTED (R4, …) — fix
before acting:` and `blocked=1` in the audit — the Constitution acted, it did not advise.

---

## 4. Minority Tracking (the new capability)

`minority_positions` table: `session_id · agent · position · reason · stance · ts ·
resolved · proven_correct · resolved_at · vindication_applied`.

- **Capture:** every dissent is recorded at `govern()` time — who disagreed, why.
- **Resolution:** `on_outcome(session)` runs when the session is **fully graded**. It
  reads the session's realised accuracy:
  - majority **wrong** (accuracy < 0.6) → every dissenter `proven_correct=1` and receives
    a reputation reward (`apply_outcome(correct, weight 0.5)`), applied once.
  - majority **right** → dissent `resolved`, `proven_correct=0`, and the dissenter is
    **not punished** — the House does not suppress minority viewpoints.
- **Learning:** `minority_scoreboard()` gives each member's dissent record and
  **vindication rate** — how often their disagreement proved right. This is how the House
  learns *whose dissent to weight*.

> Asymmetry is deliberate: right dissent is rewarded, wrong dissent is free. Disagreeing
> with the majority must never carry a penalty, or the House would learn to conform.

---

## 5. Governance Record (audit trail)

Per session, `constitution_audits` stores: `decision · governance_score · violations[] ·
waivers[] · n_minority · blocked · record_json` (the full five records + enforcement).
`governance_record(session_id)` returns the audit joined with its minority positions.

Read surface (API, `/api/council/…`):
```
GET /governance/{session_id}        full governance record + minorities
GET /governance/stats               decisions, minorities, vindicated, avg score
GET /minorities?vindicated=         the dissent ledger (optionally only vindicated)
GET /minorities/scoreboard          per-agent dissent + vindication rate
```

---

## 6. Failure Modes (and handling)

| Failure mode | Handling |
|---|---|
| Engine throws during a council run | both integration points wrap in `try/except`; deliberation proceeds (unenforced) rather than crashing |
| A legitimate verdict is wrongly REJECTED (false positive) | waivers provide an explicit, recorded override; thresholds are tunable; REJECT only on the three hard rules |
| Premature vindication (session partly graded) | `on_outcome` returns early until **no** predictions are pending |
| Double-reward of a vindicated dissenter | `vindication_applied` flag makes it idempotent |
| Punishing healthy dissent | by design, wrong dissent is never penalised |
| Heuristic extraction misses evidence/invalidation | conservative patterns; a missed invalidation rejects (safe-fail toward demanding rigor, not waving it through) |
| Schema drift (audit columns) | migration 004 + `_ensure_columns` keep `migrate.py` and `ensure_schema` identical; idempotent |

---

## 7. Tests (`tests/test_m3_governance.py`, +14 → 118 total)

- **Five records** extracted with correct shape.
- **Enforcement:** clean PASS; forecast-without-invalidation REJECTED (R4); claim-without-
  evidence REJECTED (R1); minority-omitted violation (R5); uncertainty-not-stated FLAGGED
  (R3); waiver lifts a rejection.
- **Audit trail:** govern persists record + minority; REJECTED → `blocked=1`.
- **Minority tracking:** right dissent rewarded; **wrong dissent not punished**;
  vindication waits for full grading; idempotent; scoreboard + stats.

Coverage: governance_engine **92%**; full suite **118 passed**.

---

## Success criteria — met
- Every session produces the five records (majority, minority, evidence, confidence, uncertainty).
- The Constitution **enforces**: forecasts without invalidation, claims without evidence,
  and omitted minorities are **rejected**; missing uncertainty is **flagged**.
- **Minority tracking** records who disagreed, why, and whether they were later proven right.
- The House **learns when dissent was right** (vindication + scoreboard) and **does not
  suppress minority viewpoints** (wrong dissent is never punished).
- A per-session **Governance Audit Trail** records violations, waivers, minorities, and a
  governance score.

### Files
- `backend/governance_engine.py` — the engine (new)
- `backend/institutional_db.py` — schema v4 (minority_positions + audit columns)
- `backend/migrations/004_governance.*.sql`
- `backend/agent_council.py` — enforce + annotate + govern wired into run_council
- `backend/outcome_tracker.py` — on_outcome resolution wired into evaluate
- `backend/council_intelligence_api.py` — governance + minority endpoints
- `backend/tests/test_m3_governance.py` — 14 tests
