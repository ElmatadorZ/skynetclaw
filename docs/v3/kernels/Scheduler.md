# Scheduler / Resource Governor Kernel

> Every OS has a scheduler. AI agent platforms think `Task → Agent`; an operating
> system thinks `Resource → Scheduler → Task`. This kernel arbitrates the finite
> GPU/VRAM/token/cost budget across hundreds of competing agents.
> Parent: [V3-Architecture](../V3-Architecture.md)

## 1. Why a kernel
One RTX 3060 is a hard ceiling. With hundreds of agents, the bottleneck is **resource
contention**, and V2 has nothing arbitrating it — `max_tokens`/`max_cost` are declared
but unenforced. Without admission control, quotas, leases, and preemption, the system
thrashes. This is the classic OS scheduler, applied to AI resources.

## 2. The inversion (first principle)
```
V2 (agent-centric):       Task → Agent → (grab whatever resource)
V3 (resource-centric):    Resource → Scheduler → lease → Task may run
```
No agent runs without a **lease**. A lease is a time-bounded grant of a resource slice.

## 3. Resources modeled
| Resource | Unit | Source |
|---|---|---|
| GPU / VRAM | MB · compute-slot | local GPU(s) + remote workers |
| Token budget | tokens / mission · / tenant | mission `resources` + tenant quota |
| Cost | USD / mission · / tenant | Model Gateway cost table |
| Concurrency | inflight slots per runtime | Model Gateway capacity |
| Tool rate | calls/sec per tool/service | tool category limits |

## 4. Mechanisms
- **Admission control**: a mission is ADMITTED only if its declared `resources` fit
  available quota; otherwise it queues (BLOCKED: awaiting-resources) — no overcommit.
- **Leasing**: agents request `lease(resource, amount, deadline)`; the Model Gateway
  serves inference only against a valid lease. Leases expire → no leaks.
- **Quotas**: per-tenant and per-mission ceilings (tokens/cost/concurrency).
- **Priority + preemption**: `critical > high > normal > low`; a higher-priority
  mission can **preempt** a lower one's lease (the preempted agent → PAUSED, resumable
  from its idempotent node — safe because state is in the Journal).
- **Backpressure**: when queues exceed thresholds, admission slows and producers are
  signalled (flow control) instead of melting down.
- **Fairness**: weighted fair queuing across tenants so one tenant cannot starve others.

## 5. Interface
```python
class Scheduler:
    def admit(self, mission: Mission) -> Admission        # fits quota? else queue
    def lease(self, principal, resource, amount, deadline) -> Lease | Wait
    def release(self, lease_id: str) -> None
    def preempt(self, lease_id: str, *, reason) -> None    # → PAUSED, resumable
    def quota(self, tenant: str) -> Quota
    def pressure(self) -> dict                              # backpressure signals
```

## 6. Events
`mission.admitted`, `mission.queued`, `lease.granted`, `lease.expired`,
`lease.preempted`, `quota.exceeded`, `scheduler.backpressure`. Journaled → utilization
and contention are fully observable.

## 7. Single → distributed
Workstation: an in-proc scheduling loop over the local GPU and one token budget.
Organization: a central scheduler service (or a partitioned/hierarchical scheduler per
cluster) leasing across a fleet of GPU workers; the lease abstraction is identical, so
agents and the Model Gateway are unchanged. Preemption stays safe because the Journal
makes every node resumable.

## 8. Compatibility
Mission `resources` budgets (already in V2's schema) become the scheduler's inputs.
With the `scheduler` flag off, a trivial pass-through scheduler grants every request
(V2 behavior). The local-first execution default is expressed as a scheduling/routing
preference, not a hardcode.
