# THE HOUSE MIND — House State Engine
### Memory is the past. Recall is retrieval. This is the present: the House's current understanding.

> A council is not intelligent because members talk. It becomes intelligent when it
> maintains a *shared* understanding. The House must behave as one mind, not fourteen.
> Status: **delivered, 129 tests pass, house_state 86% coverage, schema v5.**

---

## 1. Architecture

The House had memory, recall, briefing, governance — but it could not answer *what do we
know, what don't we know, what do we believe, why, and what changed our mind.* Those are
questions about the **present**, not the past. The House State Engine maintains a living
model of the House's own understanding that every member reads before deliberating and
updates after.

```
                            DELIBERATION FLOW
   Directive
      │
      ▼  recall_quality        (M2 Foundation — justified memories)
      ▼  deliberation_briefing (M2 — synthesized history)
      ▼  ┌──────────────────────────────────────────────────────┐
         │  HOUSE STATE  (house_state.py)  ← READ before deliberate│
         │  open_state(directive) → the living shared mind:        │
         │    known_fact · unknown_fact · hypothesis · belief ·    │
         │    contradiction · blind_spot · open_question ·         │
         │    minority · evidence   (+ overall confidence)         │
         │  format_state_for_council() injected into EVERY member  │
         └──────────────────────────────┬───────────────────────┘
      ▼  COUNCIL DELIBERATION (14 members reason from one shared state)
      ▼  ┌──────────────────────────────────────────────────────┐
         │  HOUSE STATE UPDATE  ← update_from_verdict()            │
         │    facts learned, the new belief (evolution LOGGED:     │
         │    who/why/evidence/confidence-impact), contradictions, │
         │    minority view                                        │
         └──────────────────────────────┬───────────────────────┘
      ▼  VERDICT
```

The engine is the **House Mind**: not memory, not recall — *current understanding*. It is
persistent (survives across sessions on the same question) and shared (one state, read by
all members), which is what turns fourteen talking agents into one reasoning institution.

---

## 2. Data Model (schema v5)

```
house_state    id · session_id · question · status(open|closed) · confidence · summary
               · created_at · updated_at
state_items    id · state_id → · kind · content · confidence · agent · evidence
               · status · superseded · ts
               kind ∈ {known_fact, unknown_fact, hypothesis, belief, contradiction,
                       blind_spot, open_question, minority, evidence}
belief_changes id · state_id → · item_id · previous · new · prev_confidence
               · new_confidence · reason · evidence · agent · ts
```

A generic `state_items` table (one row per atom of understanding) keeps the model open —
new kinds need no new tables. `belief_changes` is the **mind-change ledger**: every belief
that evolves is recorded with its previous/new content, the confidence impact, the reason,
the evidence, and the agent responsible. Indexes on `(state_id, kind)`, `(state_id,
superseded)`, and `(state_id, ts)` keep reads fast. FK cascade on delete.

---

## 3. Update Rules

- **One current belief.** Adding a belief supersedes the prior one (`superseded=1`) and
  writes a `belief_changes` row — the House holds a single current belief per state, with
  its full evolution preserved.
- **Confidence is derived, not asserted.** `overall_confidence = mean(current beliefs)`
  (or 0.7×mean(hypotheses) if no belief yet), **minus 0.1 per active contradiction and
  0.03 per open unknown.** Contradictions and ignorance lower confidence automatically.
- **Items are deduped** by `(state_id, kind, content)` so repeated assertions don't inflate.
- **update_from_verdict** maps a council verdict into the mind deterministically:
  Analyst `known`→known_facts, Analyst `unknown`/`data_gaps`→unknown_facts, Forecaster
  `scenario`→hypothesis, Skeptic dissent→contradiction + minority, and the aggregate
  recommendation→the new **belief** (evolution logged, agent = "Council").
- **Self-knowledge bootstrap.** A self-referential question (`blueprint`, `agent`, `skill`,
  `council`, `สภา`, `ตัวเอง`, …) seeds the state with **known facts about the House itself**
  — its 14 members, its installed skills + which members lack one, its vault path — so the
  House introspects instead of researching itself blindly. *(This is the direct fix for
  "สภาสั่งงานไม่รู้ตัวเอง".)*

---

## 4. Injection Strategy (the consciousness rule)

> Every member READS the House State before deliberation; every member MAY UPDATE it;
> all updates are LOGGED.

- **Council (`agent_council.run_council`):** after the brief, `open_state(task)` opens/reuses
  the living state and `format_state_for_council()` is injected via `context["house_mind"]`.
  `_ask_role` prepends it (House Mind first, then the historical brief) to **every** role's
  prompt — all fourteen reason from the same shared understanding. After the verdict,
  `update_from_verdict()` folds the outcome back into the state (the *House State Update*
  step) before the verdict is finalized.
- **Autonomous loop (`main.py agent_run`):** at the ATLAS counsel block the current House
  Mind is opened/read and injected, and a `house_mind` SSE event is emitted for the UI.
- Both are **best-effort/guarded**: if the engine errors, deliberation proceeds.

---

## 5. Persistence Strategy

One SQLite database (`skynerclaw.db`), schema v5, self-contained migration `005_house_state`
(up/down, idempotent; verified through a full 001→005 apply). State **persists across
sessions**: the same question reuses its living state (token-similarity ≥ 0.6), so the
House's understanding *accumulates* rather than resetting each deliberation. States can be
`close`d with a summary; closed states drop out of `current()` and reuse. Reads are
lock-free (inherits the M1.5 `init_once` foundation).

---

## 6. Failure Modes (and handling)

| Failure mode | Handling |
|---|---|
| Engine unavailable / throws mid-run | guarded `try/except` at both injection points — deliberation continues unbriefed by state |
| Empty state (new question) | `read_state` returns empty groups; the injected block is minimal, not fabricated |
| Belief thrash (rapid flip-flop) | every change is logged with reason+evidence; the mind-change ledger makes thrash visible rather than hidden |
| Confidence inflation | confidence is *derived* and penalised by contradictions/unknowns — it cannot be asserted high while the House is ignorant |
| Wrong state reused (question drift) | reuse requires ≥0.6 token similarity; distinct questions get distinct states (tested) |
| Self-facts unavailable (no skills dir / vault) | each self-fact source is independently guarded; missing sources are simply omitted |
| Stale state | `updated_at` ordering; `current()` returns the most recently touched open state |
| Concurrent updates | item ids are content-hashed (idempotent upserts); belief supersession is single-writer within `run_council` |

---

## 7. Regression Tests (`tests/test_house_state.py`, +11 → 129 total)

- **The five questions** answerable on the mission's exact example ("Where are the Agent
  Blueprints?"): know / don't-know / believe / why / what-changed-our-mind.
- **Belief evolution:** Atlas 40%→70% with reason + evidence + agent + **confidence impact
  +0.3**; negative impact on revision-down; supersession (only one current belief).
- **Confidence:** contradictions lower it.
- **State reuse:** same question → one state; distinct questions → distinct states.
- **update_from_verdict:** facts, belief, contradictions, minority, hypotheses folded in.
- **Self-knowledge:** a self-referential question bootstraps "council of 14 members".
- **Consciousness rule:** `format_state_for_council` produces the shared block; `current()`
  returns the latest.

Coverage: house_state **86%** (uncovered lines are the production-only skills/vault scans);
full suite **129 passed**.

---

## 8. UI — THE HOUSE MIND (replaces the decorative center)

`backend/house_mind_panel.html` — a self-contained obsidian-and-gold panel that reads
`/api/council/state/current` + `/state/{id}/answer` + `/changes` and renders the House's
**current understanding**: the question, an overall-confidence ring, *What we know / What we
don't know / What we believe (with per-belief confidence bars and the reason) / Open
questions / Minority position / Contradictions / What recently changed our mind* (agent,
from→to, confidence impact, reason, evidence). It is the living mind at the center of the
chamber, not charts.

API:
```
GET /api/council/state/current          the House's current focus
GET /api/council/state/{id}             full state (grouped items + recent changes)
GET /api/council/state/{id}/answer      the five questions, answered
GET /api/council/state/{id}/changes     the mind-change ledger
```

---

## Success criteria — met
The House can now answer:
- **What do we know?** → known_fact items
- **What don't we know?** → unknown_fact + open_question items
- **What do we believe?** → current beliefs + confidence
- **Why do we believe it?** → evidence + each belief's recorded reason
- **What changed our mind?** → belief_changes (who, why, evidence, confidence impact)

Fourteen members now read one shared state before they speak and update it after — the
House reasons as one mind. **The House is self-aware.**

### Files
- `backend/house_state.py` — the House Mind (new)
- `backend/institutional_db.py` — schema v5 (house_state · state_items · belief_changes)
- `backend/migrations/005_house_state.*.sql`
- `backend/agent_council.py` — read-before / update-after wired into run_council; `_ask_role` injects the mind
- `backend/main.py` — House Mind injected into agent_run (ATLAS block)
- `backend/council_intelligence_api.py` — `/state/*` endpoints
- `backend/house_mind_panel.html` — THE HOUSE MIND center panel
- `backend/tests/test_house_state.py` — 11 tests
