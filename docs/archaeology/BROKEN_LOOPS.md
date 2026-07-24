# Broken Loops — loops that appear closed but are open

> Every epistemic loop that *looks* like feedback but terminates before it changes future
> behaviour. Evidence = the organs' own comments in the live loop + persistence probe.
> Tags: SUPPORTED unless noted. Notation: `→ ⟂` marks the exact break point.

## The universal shape (SUPPORTED)
Every epistemic organ in the live loop follows the same path and breaks at the same place:
```
Evidence (logs) → recompute() → render_brief() → cur.append(prompt) + house_sync.publish(count)
   → ⟂ [NO persistence] → ⟂ [NO code branch] → (human reads UI)  ── STOP
next run: recompute from scratch (amnesiac)
```
The break is **double**: (1) nothing is written (Memory hop broken); (2) nothing branches on
it (Behaviour hop broken — control flow is identical with or without the brief).

## Loop-by-loop
| Loop | Appears to | Breaks at (evidence) |
|---|---|---|
| **belief_revision** | revise contradicted beliefs | `→ ⟂` "DETECTION ONLY. No promotion, no demotion, no correction" — drift is *rendered*, never applied |
| **first_principles** | promote cross-validated principles to rules | `→ ⟂` "candidates, not rules ... humans / later protocols decide" — never promoted in code |
| **theory** | establish cross-domain laws | `→ ⟂` "Awareness only — not laws" |
| **experiment** | run controlled experiments → measure → revise | `→ ⟂` "Recommendation only — **never runs anything**" — the experiment is *designed* and never *executed*, so no measurement returns, so nothing revises |
| **calibration** | correct over/under-confidence | `→ ⟂` "MEASURE ONLY — does not alter any runtime decision" (main.py:5911) |
| **decision** | decide the next action | `→ ⟂` "does not decide for the runtime ... advisory — no behavior change" |
| **paradigm** | shift the dominant framework | `→ ⟂` renders "PARADIGM SHIFT in progress"; no organ acts on it (state-writes=0) |
| **unknowns** | close known-unknowns | `→ ⟂` maps gaps; nothing consumes the map to schedule work in code |

## The single loop that is genuinely CLOSED (not broken)
- **reinforcement** → capability_weights.json → re-orders recalled tools. **SUPPORTED closed.**
  *But it is capability-scoring, not belief* (excluded by OBJECTIVE 1). The mission's target —
  belief — has **zero** closed loops.

## The one closed loop OUTSIDE cognition
- **engineering regression**: failure → fix → regression test → quality gate blocks merge.
  Genuinely closed and enforced (CHAOS-001, security 10/10) — but this is the **human dev
  process**, executed by a person, not the organism's own cognition.

## The pattern name (SUPPORTED)
These are **pseudo-feedback loops**: they contain observation and rendering but no
persistence and no actuation. Each terminates at `render → prompt-text / UI-event → human`.
The earlier report's "loop diagram" (Evidence→…→Institutional Memory) is, for belief,
**a description of a straight line that ends at a human**, drawn as a circle.

## Consequence
The Evidence→Decision→Memory→Future-Behaviour chain (OBJECTIVE 3) **breaks at the Memory
hop** for every belief organ — the decision is rendered but never stored, so it cannot reach
a *future* run; the next run rebuilds the identical brief from the same logs. **First break:
Memory. SUPPORTED.**
