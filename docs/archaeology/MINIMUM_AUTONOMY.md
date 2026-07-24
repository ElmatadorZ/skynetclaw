# Minimum Autonomy — measuring the human decisions on the belief loop

> **Measure only. No redesign, no proposal.** Count the human-gated transitions that
> currently sit between *evidence* and a *persistent, behaviour-changing belief*. This is a
> census of barriers as-built, not a plan to remove them. Tags: SUPPORTED / LIKELY / UNKNOWN.

## Definition used
A "true knowledge organism" (mission's phrasing) would require: evidence → **persisted**
belief → that belief **changes a future run** — autonomously. So the measurement is: *how
many transitions on that path are, as-built, gated by a human?*

## Census of human-gated transitions on the BELIEF path (SUPPORTED)
| # | Transition | Current gate (evidence) | Automated today? |
|---|---|---|---|
| 1 | candidate → **promoted** belief | belief_revision / first_principles: *"candidates ... humans / later protocols decide"* | **No** (human) |
| 2 | promoted belief → **persisted** | state-writes = 0 across belief organs → a human/protocol must write it | **No** (human) |
| 3 | persisted belief → **actuates** (changes a decision) | decision: *"does not decide for the runtime"*; calibration: *"MEASURE ONLY — does not alter any runtime decision"* | **No** (human) |
| 4 | contradicted belief → **retracted/demoted** | belief_revision: *"No promotion, no demotion, no correction ... humans decide"* | **No** (human) |
| 5 | hypothesis → **experiment executed** → measurement | experiment: *"Recommendation only — never runs anything"* | **No** (human) |

## The measurement (SUPPORTED)
- **Human-gated transitions on the belief loop: 5.**
- **Autonomously-closed transitions on the belief loop: 0.**
- Therefore the belief loop is, as-built, **0% autonomous** — every step from candidate to
  behaviour-changing persisted belief requires a human act.
- (For contrast, the **capability** loop is ~100% autonomous via reinforcement — but that is
  capability, not belief; and the **engineering** loop is autonomous-within-a-human-process.)

## Corollary (SUPPORTED)
The minimum number of human decisions for a *single* belief to travel the full loop today is
**5** (promote, persist, actuate, and — over its life — retract-when-contradicted and run-its-
experiment). None is currently automatable from the evidence: no organ writes, none branches,
one ("never runs anything") explicitly refuses to execute.

## UNKNOWNs
- Whether transitions 1–5 are *deliberately* human-gated (design) or simply *unbuilt* —
  **UNKNOWN** (the commit tags say "read-only" but state no intent about future closure).
- Whether a "later protocol" (referenced repeatedly as the non-human alternative to "humans
  decide") exists anywhere — **UNKNOWN / not found** in the evidence; every path terminates at
  a human today.

> This document measures the gap. It does not prescribe closing it (stop condition).
