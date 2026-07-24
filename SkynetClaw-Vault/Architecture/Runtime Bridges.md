---
tags: [architecture, bridge, moc]
type: map-of-content
---

# Runtime Bridges — theory → enforced invariant

> The heart of the [[Genesis Paradigm]]: each bridge is a recovered theory turned into
> **running, measured code**. This is *the* mechanism by which the "research lab"
> becomes the agent's reliability. A theory volume with no bridge is a stock with no
> flow.

## The bridges built so far
| Bridge | Theory it enforces | Runtime file | In one line |
|---|---|---|---|
| [[CEE — Warrant Runtime]] | Theory of Warrant · **C1** | `backend/warrant_check.py` | flags claims of reading files that don't exist |
| [[Proprioception — Learning]] | Agency **Vol VI** (Learning) | `backend/self_context.py` | feeds the system's own failures forward as lessons |
| [[Planner — Vol IV Runtime]] | Agency **Vol IV** (Planning) | `backend/task_planner.py` | decompose → build across rounds → save the file |
| [[Governance — GPS-2]] | Agency **Vol VII** (Governance) | `backend/governance.py` | the reference monitor that bounds every action |
| **Guidance (G1)** | Agency **Vol V** (Execution) | `backend/guidance_check.py` | flags acts on targets nothing guided (deviant chains / invented targets) — C1's dual on the act side |

## The pattern (how to build the next one)
1. **Recover** the theory as pure philosophy (`docs/` — falsifiable, red-teamed).
2. Find the **cheapest, highest-value deterministic slice** (CEE started with ONE
   detector: fabricated file references).
3. Build it **decoupled + testable** (inject dependencies; a unit test locks it).
4. **Wire** it into the loop with a try/except so the House is unaffected if absent.
5. Add an **[[Eval Scoreboard|eval case]]** so a regression is caught by measurement.

## The loop the bridges close
```
                 ┌──────── forward arc (built) ────────┐
perceive → decide → act → outcome
   ▲  [reality_context]  [Planner]                     │
   │                                                     ▼
   └── Governance ◀── learn ◀──────────────────── outcome
        (Vol VII)      (Vol VI / Proprioception)   [+ CEE warrant check]
              └────────── the return arc ──────────┘
```

## Status: all theory volumes bridged (2026-07-10)
Vol V (G1, commit e2c3ebd) was the last bridge owed. Continuous evaluation runs
nightly via the institutional scheduler — the [[Eval Scoreboard]] is now a rate,
not a sample. The Theory of Agency runs end-to-end: every volume has enforcing
code, every bridge has an eval case.

## See also
[[Theory Stack Map]] · [[Genesis Paradigm]] · [[How This Vault Grows]] · [[🏠 HOME]]
