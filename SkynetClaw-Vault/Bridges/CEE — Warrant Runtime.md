---
tags: [bridge, security, invariant]
type: bridge
theory: Theory of Warrant (C1)
runtime: backend/warrant_check.py
commit: 2b87ff9
---

# CEE — Warrant Runtime (C1 made live)

> The **first** runtime bridge and the proof of concept for the [[Genesis Paradigm]]:
> the Theory of Warrant's **C1** ("presenting a zero-warrant belief AS warranted is a lie
> about warrant") became a runtime detector that fires on every agent completion.

## What it does
`warrant_check.detect_overclaims(text, workspace)` — a pure, deterministic detector.
First (and cheapest, highest-value) check: **fabricated file reference** — text that
claims *reading/observing* content from a file that does **not** exist in the workspace or
on disk (exactly the `example.txt` failure). Conservative: a path is flagged only when
asserted as READ, not as WRITE (a create-intent is not a lie), and absent from reality.
Workspace = the answer key.

## The loop it closes
Wired at the `agent_complete` hook: every run's output is checked, the verdict
(OK / OVERCLAIM) is **persisted** to `warrant_log.jsonl` (the durable observation log),
and a `warrant_violation` event is emitted. `GET /api/warrant/recent` exposes the log +
a live `overclaim_rate` → C1 as an *auditable runtime property*, not philosophy.

## The dual it pairs with
CEE catches **overclaim** (claiming a file that doesn't exist). Its dual — **underclaim**
(observing a file then losing it to context compression → falsely reporting UNKNOWN) — was
fixed in `mission_snapshot.py` (evidence-preserving compression). Both are C1 in the two
directions.

## Feeds
The overclaims it records are mined by [[Proprioception — Learning]] into forward-fed
lessons → a real loop between two bridges: *CEE records → proprioception feeds back*.

## See also
[[Runtime Bridges]] · [[Proprioception — Learning]] · [[Part I — Theory of Knowing]] · [[🏠 HOME]]
