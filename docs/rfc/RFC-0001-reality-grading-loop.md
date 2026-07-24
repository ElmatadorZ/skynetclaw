# RFC-0001 — Reality Grading Loop (Learning Integrity)

- **Type:** RFC / design note — deliberately NOT an ADR (this is wiring, not new
  architecture; per ADR-0013's burden of proof: *pilot before ratify*)
- **Date:** 2026-07-19 · **Scope:** small, provable fast
- **Status:** ✅ **Accepted for Pilot** (operator ruling 2026-07-19). Code is a
  pilot deployment; git commits are *checkpoints*, not ratification. **Ratification
  (ADR-0016) waits for the pilot success criteria below** — the exit criteria decide,
  not the architect's feelings.
- **Learning Integrity Principles (candidates for ADR-0013 upon evidence):**
  > **#1 — The system SHALL NOT amplify knowledge that has not first been anchored
  > against external reality.** (anchor first, then amplify)
  >
  > **#2 — Every validated episode SHALL reference immutable evidence** — artifact
  > hashes, ledger id, timestamps, and the **judge version** that evaluated it. A
  > future judge change must never silently rewrite what an old verdict meant
  > (dataset-versioning discipline, applied to cognition).
  >
  > **#3 — Evidence Normalization: all providers SHALL be evaluated against the same
  > observable evidence. Provider assertions SHALL NOT constitute evidence.**
  > A human, a robot, an external API, or another AI saying "success" carries the
  > same weight as a model saying it: none. Provider independence at the level of
  > truth evaluation, not merely at the API level (operator ruling 2026-07-19).

## Vocabulary (operator amendment)

A COMPLETE mission does not "stake a claim" — it proposes a **HYPOTHESIS**: a
falsifiable statement offered up to be refuted. The loop speaks the scientific method:

```
Mission → Hypothesis → Reality → Evaluation → Validated Episode
```

**Evidence Normalization:** whether GPT, Claude, Nemotron, or a human says
"success" carries no weight — the judge reads the same filesystem and ledger for
every provider. This is ADR-0013's provider independence, applied at the evidence
layer.

## Problem — an integrity bug, not a missing feature

The system declares "learning from reality," but reality never re-enters the system
for missions:

| Loop stage | Status (measured 2026-07-19) |
|---|---|
| Outcome clock (`scheduler` + `outcome_review` job) | ✅ ALIVE — armed by `council_intelligence_api`, ticks every 10 min, ran today |
| `evaluate()` → reputation + minority + **House-Mind belief revision** | ✅ code complete (`outcome_tracker.py:128`) |
| Predictions from **council** sessions | ✅ 7 exist (via `extractor`) |
| Predictions from **missions** | ❌ **zero** in 226 agent runs — missions never stake a claim |
| Auto-judge for mission claims | ❌ `auto_judge` only grades `metric~"eval"` vs the scoreboard |

So the pipeline `Prediction → Reality → Grade → Belief Revision` is complete but
**starved**: the clock dutifully reviews an empty queue. Lessons are synthesized from
*ungraded* episodes — they are opinion, not knowledge.

## Design — two wires and one judge (nothing else)

```
Mission end (Commander sign-off, main.py)
   │  W1: record_mission_prediction()          ← stake an OBSERVABLE claim
   ▼
predictions table  (statement: "mission outcome COMPLETE will hold";
                    predicted_outcome: {files, workspace, ledger_id} — machine-checkable)
   │  existing outcome clock (daily; first review at the 7-day horizon)
   ▼
W2: mission auto-judge                          ← reality = FILESYSTEM + LEDGER,
   correct   = all signed artifacts exist          never the model's own claims
   partial   = some exist                          (the external anchor)
   incorrect = none exist / ledger overturned
   ▼
existing evaluate()  → reputation · minority resolution · House-Mind belief revision
   ▼
W3: validated episodes                          ← sessions whose claims graded correct;
                                                   the trusted base for future recall/promotion
```

- **W1** hooks the existing sign-off block (`_ledger_sign`, `main.py`), which already
  carries everything needed: status, `files_touched`, `done_when`, session id. Only
  `COMPLETE` missions with artifacts stake a claim. Deduped via `has_pending`.
- **W2** extends `outcome_tracker.auto_judge` by delegation (a `mission_artifacts`
  metric branch → `reality_grading.judge_mission_prediction`). The judge reads the
  filesystem and `_MISSION_LEDGER.json` — observable, model-independent reality.
- **W3** exposes `validated_sessions()` — the **Validated Episode** layer:
  `Episode → Reality Grade → Validated Episode → (later) Lesson/Recall/Promotion`.
  This RFC only *creates* the layer; consuming it in recall/promotion is the next,
  separately-measured step.

## Non-goals (deliberately)
- No recall-quality work, no capability promotion, no chat-path recall (those are the
  *amplify* half — they wait until this anchor produces evidence).
- No new horizon semantics: "outcome will hold" is honestly a 7-day claim; the first
  grade lands at the existing 7-day review (per `outcome_tracker`'s own design note).
- No new tables, no schema change — uses the existing `predictions` row shape.

## Pilot Success Criteria (operator-set; these decide, not the architect)
1. A **Hypothesis** is created automatically from a real COMPLETE mission
   (not from the test suite).
2. At least one **Validated Episode** results from an evaluation against real
   evidence, with its immutable-evidence payload intact (Principle #2).
3. A **Belief Revision** occurs from a Validated Episode with zero human
   intervention (existing `revise_from_outcome` path).

All three must occur **in real operation** — evidence from `loop_summary()`, never
from tests. When they hold — and only then — the pattern
`Validated Episode → Semantic Knowledge → Capability → Policy` may be proposed
as **ADR-0016**.

## Pilot status (operator ruling 2026-07-19)

```
RFC-0001 → Implementation ✅ → Deployment Ready ✅ → Live Observation ◀ current
        → Evidence Review → ADR-0016
```

| Item | Status |
|---|---|
| RFC-0001 | ✅ Accepted for Pilot |
| Reality Grading Loop | ✅ Implemented |
| Hypothesis vocabulary | ✅ Adopted |
| Evidence Normalization | ✅ Principle #3 (pinned above) |
| Immutable evidence | ✅ Sufficient for pilot |
| ADR-0016 | ⏸️ Deferred pending live evidence |

What the pilot lacks is **time, not architecture** — the git history is a checkpoint
trail (engineering), never a ratification (constitutional); those gates are separate
by design. **Project phase: OBSERVATORY, not Development** — from here the most
valuable output is not new code but data from real operation. The architect's question
changes from *"what should we design next?"* to *"what should we measure next?"*

## The Observatory (single observation surface)

`reality_grading.vital_signs()` is the **Canonical Health API**. No subsystem invents
its own learning metrics; every consumer reads this one surface:

```
Learning Loop → vital_signs() → /api/learning/loop → Dashboard → Evidence Review → Governance
```

`GET /api/learning/dashboard` renders the vital signs — not KPIs, a **pulse**:

| Vital sign | Question it answers |
|---|---|
| Hypotheses Staked | does the system dare to predict? |
| Due for Review | how much awaits reality's judgment? |
| Validated Episodes | how much knowledge survived reality? |
| Belief Revisions (from reality) | how often did reality change our mind? |
| Promotion Candidates / Rate | knowledge ready to be elevated / actually elevated |
| Abstain Rate | how often does the judge honestly say "unknown"? |
| Reality Coverage | % of COMPLETE missions that staked a hypothesis |

Verdict states: `WAITING_FIRST_HYPOTHESIS → AWAITING_REALITY → VALIDATING → ALIVE`
("ALIVE" = the full cycle observed: a validated episode has changed a belief).
No-data metrics render as **"no data yet"**, never as fake zeros.

## Technical Debt — recorded for the ADR-0016 backlog

> **Full epistemic provenance is three-dimensional.** Every learning artifact should
> eventually carry **(Evidence Version, Judge Version, Learning Policy Version)** so
> the system can always answer: *what did it learn, from what evidence, under which
> judge and which learning policy?* The pilot records the first two
> (`evidence.sha256`, `judge_version_at_stake`); **Learning Policy Version (LP-n)**
> is missing — without it, a capability promoted today under LP-1 cannot be
> distinguished from one promoted under a future LP-4. Not needed while promotion
> is dormant (`capabilities.json` empty); becomes REQUIRED the moment
> `Validated Episode → Capability` promotion switches on. This is the line between
> a *learning system* and an **auditable cognitive system**.

> **False Learning Rate** (ADR-0016 backlog): `validated → promoted → later reversed`.
> If a promoted capability must be withdrawn months later, that was false learning —
> the quality metric of any future Promotion Policy. Not measurable until promotion
> is live; recorded now so it is designed in, not bolted on.

---

*A learning system proves itself not by how much it remembers, but by how accurately
it changes its beliefs when reality disagrees.*

## Evidence trail
- 226 `agent_runs`, 7 predictions (council-only), `capabilities.json` empty — measured.
- Correction recorded: an earlier review claimed the outcome clock was never triggered;
  wrong — it is armed and ticking. The gap is upstream (no mission claims) and at the
  judge (no mission judge). This RFC fixes exactly those two points.
