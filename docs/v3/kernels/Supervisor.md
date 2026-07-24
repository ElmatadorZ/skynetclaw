# Supervisor Kernel (Fault Tolerance / let-it-crash)

> At hundreds of agents, partial failure is the normal case, not the exception.
> Supervision trees, restart strategies, and isolation make failure structural and
> contained — not a cascade.
> Parent: [V3-Architecture](../V3-Architecture.md)

## 1. Why a kernel
V2's only resilience is a per-runtime circuit breaker. That protects a backend, not the
system. With many agents and engines, you need a **supervision hierarchy** that detects
failures, isolates them, and restarts the failed unit from a known-good state. This is a
distinct responsibility (liveness/recovery) that no other kernel owns.

## 2. Principle: let it crash
Units do **not** defensively swallow errors into corrupt half-states. A failing unit
**crashes cleanly**; its supervisor decides how to recover. Because state lives in the
[Journal](Journal.md) (units are stateless), restart is safe and resumes from the last
journaled checkpoint.

## 3. Supervision tree
```
root supervisor
├─ kernel supervisor      (Journal, Scheduler, Gateway, Epistemic) — restart: one-for-one
├─ engine supervisor      (Mission, Council, Execution, Reflection) — restart: rest-for-one
└─ agent supervisor(s)    (per mission/council) — restart: one-for-one, isolated per agent
```
- **one-for-one**: restart only the failed child.
- **rest-for-one**: restart the failed child and those started after it (dependents).
- **all-for-one**: restart the whole group (used sparingly, e.g. shared-state group).

## 4. Mechanisms
- **Health & heartbeats**: every supervised unit reports liveness; missed heartbeats →
  considered crashed.
- **Restart strategy + budget**: max restarts within a window; exceeding it escalates
  to the parent supervisor (prevents crash loops — pairs with `shadow_gate` anti-loop).
- **Isolation**: a crashing agent cannot corrupt siblings (no shared mutable state;
  communication only via the Journal).
- **Checkpoint/resume**: on restart, replay the unit's stream to its last checkpoint;
  idempotent node execution means no double-effects.
- **Bulkheads**: per-tenant/per-mission failure domains so one tenant's storm cannot
  take down others (pairs with Scheduler fairness).

## 5. Interface
```python
class Supervisor:
    def supervise(self, unit: Supervisable, *, strategy, max_restarts, window) -> Sup
    def heartbeat(self, unit_id: str) -> None
    def report_crash(self, unit_id: str, error) -> RestartDecision
    def escalate(self, unit_id: str) -> None
class Supervisable(Protocol):
    id: str
    def start(self): ...
    def stop(self): ...
    def checkpoint(self) -> CheckpointRef    # → Journal offset
```

## 6. Events
`unit.started`, `unit.heartbeat_missed`, `unit.crashed`, `unit.restarted`,
`unit.escalated`, `supervisor.budget_exceeded`. Journaled → failure analysis (an
observability metric) is just a query over these.

## 7. Single → distributed
Workstation: an in-proc supervision tree over threads/tasks. Organization: supervisors
become node-local for in-node units, with a top-level supervisor coordinating node
liveness; a dead node's missions are reassigned and replayed from the Journal on a
healthy node. Same tree shape, same restart semantics.

## 8. Compatibility
Wraps the existing runtime circuit breaker as one leaf strategy. With `supervisor` off,
units run unsupervised exactly as in V2. The agent state machine's BLOCKED/FAILED states
([ExecutionStateMachine](../../v2/ExecutionStateMachine.md)) feed restart decisions.
