# V2 Architecture Audit

> The systems-engineering audit that justifies V3. V2's cognition design is strong;
> its *integration model* is not distribution-ready. Each finding below maps to a V3
> kernel or reshape.
> Parent: [V3-Architecture](V3-Architecture.md)

## 1. Verdict
V2 is a **well-modularized monolith**. It is bound by (a) in-process method calls
between engines, (b) an in-proc EventBus that is lost on crash, (c) single-writer
SQLite, and (d) a single DI graph in one process. These four make "workstation →
distributed organization" a rewrite. V3 fixes the *integration model*, not the
cognition.

## 2. Missing kernels (a real OS has these; V2 does not)
| Missing | Why it is an architectural hole | Fixed by |
|---|---|---|
| Resource scheduler | one GPU + hundreds of agents contend with nothing arbitrating | [Scheduler](kernels/Scheduler.md) |
| Durable event log | EventBus dies on crash → no recovery/replay/audit; cannot distribute | [Journal](kernels/Journal.md) |
| Identity / capability | governance checks actions, not actors; no tenancy, no least-privilege | [IdentityCapability](kernels/IdentityCapability.md) |
| Supervision | partial failure is normal at scale; no restart strategy/isolation | [Supervisor](kernels/Supervisor.md) |
| Contract/schema registry | events as contracts need versioning | [ContractRegistry](kernels/ContractRegistry.md) |
| Immutable invariants | nothing is beyond Governor's reach; audit/history are mutable | [Constitution](kernels/Constitution.md) |
| Truth maintenance | knowledge has no confidence/evidence/contradiction model | [EpistemicKernel](kernels/EpistemicKernel.md) |

## 3. Bottlenecks
1. **In-proc EventBus** — single point, single process, lost on crash, no backpressure,
   cannot span machines. V2's "the bus becomes network later" is hand-waved; without
   an event-sourced data model *now*, that change is a rewrite.
2. **SQLite everywhere** — single-writer lock; hundreds of concurrent writers contend.
   KG + embeddings on SQLite = linear scan.
3. **Single DI graph in one process** — directly anti-distribution; engines that must
   deploy separately cannot communicate by in-memory method calls.
4. **Mission as a fat object** — graph+memory+log+timeline+reflection inline; hot and
   large. Should be an aggregate root over event-sourced streams.
5. **Synchronous council deliberation** — a blocking saga; needs async durable saga
   with timeout/compensation.

## 4. Hidden coupling
- `system_graph.py` does `import main as _m` — the knowledge/dependency graph imports
  the monolith.
- V2 contradicts itself: claims event-driven, yet injects `council`/`execution`/
  `reflection` into `MissionEngine` via constructor (in-proc calls = coupling).
  V3 rule: cross-engine = **choreography via the Journal**, never direct injection.
- Governance injected into every engine couples each to a governance impl. V3:
  governance is a **boundary interceptor + policy engine**, under the Constitution.
- `local-first ElmatadorZ` is a hardcoded default; routing policy is coupled to one
  machine's reality. V3: capacity-aware via the [Model Gateway](kernels/ModelGateway.md).

## 5. Scalability risks
- One GPU is a hard ceiling; needs a model-serving tier (queue/batch/workers).
- KG semantic search on SQLite embeddings = linear scan; needs a vector-index interface.
- Telemetry ring buffer in SQLite has high cardinality at scale; needs sampling.
- No backpressure / flow control anywhere.

## 6. Governance gaps
- No identity → no attribution, no per-tenant policy, no least-privilege per agent.
- Audit log is mutable SQLite on one node → must be append-only + tamper-evident
  (hash chain) under the Constitution.
- Policy has no versioning/signing; self-evolution proposals act on unversioned rules.
- No data governance (classification, retention, PII, egress beyond a single gate).
- No rate limit / quota (belongs to the Scheduler).

## 7. Long-term evolution constraint
"Distributed without rewrite" requires every boundary to be **network-shaped** (message
contracts, idempotent handlers, stateless engines + external state) from day one. V2
commits only at the *interface* level — insufficient, because an interface that passes
an in-memory object has different semantics (partial failure, ordering, idempotency)
than one that passes a message. V3 commits at the **contract + Journal** level.
