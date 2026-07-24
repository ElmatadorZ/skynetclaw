# THE HOUSE — Architecture Bible

Single-process, event-driven cognitive system. One bus, one truth, read-model
projections over one institutional DB. This document is the authoritative map of
state / event / projection ownership.

## System Map

```
OPERATOR ─▶ RUNTIME ─▶ COUNCIL ─▶ REASONING ─▶ HOUSE MIND ─▶ TIMELINE ─▶ MISSION ─▶ LEARNING ─▶ POLICY
                                         │
                                         ▼
                            house_sync.publish()  →  /api/house/events  (THE BUS)
                                         │
                        ┌────────────────┴────────────────┐
                THE CONTINENTAL DIVISION            council_intelligence.html
```

| Stage | Files |
|-------|-------|
| Runtime | `main.py` (`/api/agent/run`), `context_budget.py`, `mission_snapshot.py`, `continental_relay.py` |
| Council | `agent_council.py`, `agentic_workflow.py`, `main.py` (`/api/workflow/run`) |
| Reasoning | `agent_council.py` (`_extract_reasoning`, `_REASONING_MAP`) |
| House Mind | `house_state.py` (writer), `house_cognition.py` (projection) |
| Timeline | `belief_timeline.py` |
| Mission | `mission_command.py`, `openclaw_port_tier2.py` (`agent_runs`) |
| Learning | `learning_engine.py`, `outcome_tracker.py`, `extractor.py`, `agent_reputation.py` |
| Policy | `house_os.py`, `house_constitution.py`, `governance_engine.py` |
| Bus | `house_sync.py` |

## State Ownership (single source of truth)

| State | Owner | Persistence | Notes |
|-------|-------|-------------|-------|
| Cognitive state (known/unknown/belief/confidence) | `house_state.py` | `house_state`, `state_items` | authoritative |
| Belief revisions | `house_state.py` | `belief_changes` | drives timeline + learning |
| Predictions / outcomes | `outcome_tracker.py` | `predictions` | reality grading |
| Agent execution runs | `openclaw_port_tier2.py` | `agent_runs` | mission execution |
| Council sessions | `council_memory.py` | `council_sessions`, `council_contributions` | |
| Reputation | `agent_reputation.py` | `agent_reputation`, `reputation_history` | |
| Policies / Rules | `house_os.py` | `house_policies`, `house_rules` | provenance-linked |
| Minority positions | `governance_engine.py` | `minority_positions` | |
| **UI preferences** (model, connection) | `house_sync._STATE` | in-memory | only genuine cross-tab UI prefs; no bus equivalent |
| Mission state / active agents | event bus + DB (NOT `_STATE`) | — | the shadow `_STATE.mission`/`active_agents` were removed; every surface derives these from bus events |
| Runtime activity (replay) | `house_sync._EVENT_LOG` | in-memory ring (200) | |

DB: single SQLite `skynerclaw.db` (WAL).

## Event Ownership (producer → source → bus)

| Event family | Producer | `source` |
|--------------|----------|----------|
| `mission_started/updated/recovered`, `tool_started/completed/failed`, `budget_warning/critical` | `main.py` agent loop | `runtime` |
| `agent_started/thinking/completed`, `reasoning_*` | `agent_council` via `main.py` on_event | `council` |
| `house_*` | `house_cognition.diff_and_emit` | `house` |
| `timeline_*` | `belief_timeline.diff_and_emit` | `timeline` |
| `mission_*` | `mission_command.diff_and_emit` | `mission` |
| `lesson_*`, `behavior_*`, `repeat_*` | `learning_engine.diff_and_emit` | `learning` |
| `policy_*`, `rule_*` | `house_os` | `house_os` |

Envelope (one shape, one id): `{id, timestamp, type, source, payload}`. Each
logical fact is published **exactly once** (one council fact → one
`reasoning_*` event → one id → every surface).

## Projection Ownership (read-models + diff baselines)

All four projections are read-only over the DB and emit deltas via
`diff_and_emit`. Baselines are **scoped** so concurrent missions cannot interfere:

| Projection | Reads | Baseline | Scope key |
|-----------|-------|----------|-----------|
| `house_cognition` | `house_state.answer()` + scheduler | `_LAST` | **`state_id`** |
| `belief_timeline` | `house_state` + `belief_changes` | `_LAST_IDS` | **`state_id`** |
| `mission_command` | `house_state` + `agent_runs` | `_LAST` | **mission id** |
| `learning_engine` | `belief_changes` (Reality) + `predictions` | `_SEEN` | global (lesson ids are globally unique — correct) |

`reset()` clears all baselines (process restart re-emits each scope's current
state once — correct for newly-connected clients).

## Concurrency model
- Single process, single asyncio loop, single bus.
- Projection baselines keyed by `state_id` / mission id → **Mission A cannot
  suppress or trigger Mission B's events** (verified).
- Bus fan-out: per-subscriber `asyncio.Queue` + 200-event replay ring. No
  duplicate emission, no drop under paced load (verified to 1500 events).

## Known residual debt (tracked, not defects)
- `house_sync._STATE` now holds ONLY model + connection (genuine UI prefs). The
  `mission`/`active_agents` shadow copies were removed — one truth on the bus.
- Bus is in-memory single-process (by design — one House); a synchronous burst
  exceeding subscriber queue size could drop for a stalled client.
- `learning_engine` failure clustering is O(n²) (fine at current scale).
