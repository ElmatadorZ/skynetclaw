---
tags: [bridge, learning, invariant]
type: bridge
theory: Agency Vol VI (Learning)
runtime: backend/self_context.py
commit: 01980a1
---

# Proprioception — Learning (the system learns from its own outcomes)

> The bridge [[Part II — Theory of Agency|Vol VI]] owes. **LT4:** the local model has
> frozen weights → it *cannot* learn in the weights → learning must relocate to a
> **persistent external store that changes future inputs**. SkynetClaw's learning organ is
> its **memory-of-itself**, not its weights.

## The distinction that matters
- A log that never changes a decision = **memory** (the system was here before this bridge).
- A log that **changes the next run** = **learning**. The differentia is
  *credit assignment* — a lesson is surfaced only when it is *relevant to the current task*.

## What it does
`self_context.build_self_context(db, task)` mines the system's own recorded outcomes into
**task-relevant, credit-assigned lessons** injected into the agent prompt:
- **warrant lessons** — recent OVERCLAIM verdicts from `warrant_log.jsonl` (the
  [[CEE — Warrant Runtime]] output): *"you asserted reading files that did not exist e.g. X
  — verify before asserting."*
- **run lessons** — recent FAILED `agent_runs` whose task **resembles** the current one
  (Jaccard overlap = the credit map): *"a similar past task ended [status] — don't repeat."*

## The discipline (from the system's own evidence)
**SILENT when nothing relevant was learned** (returns `""`) — the *F2 anti-noise rule*:
scaffolding noise degrades a weak model. Terse when it has. Aggregation-only.

## Acceptance test (the honest bar)
It is *learning* only if the lessons **change future behaviour**; if they only display, it
is monitoring. Measured by the [[Eval Scoreboard]] behavioral cases (which land in
`agent_runs` → mined here → the loop closes for free).

## See also
[[CEE — Warrant Runtime]] · [[Eval Scoreboard]] · [[Runtime Bridges]] · [[🏠 HOME]]
