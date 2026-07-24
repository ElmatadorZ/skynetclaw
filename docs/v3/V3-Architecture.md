# SkynetClaw V3 — Cognitive Operating System (Frozen Architecture)

> **STATUS: ARCHITECTURE FREEZE.** This is the final kernel set. After V3, the
> governing rule is: **"No new kernel without proving that an existing kernel cannot
> solve the problem."** See [DecisionLog](DecisionLog.md) and [Freeze](#9-architecture-freeze).
>
> Companion docs: [Audit-V2](Audit-V2.md) · [DecisionLog](DecisionLog.md) ·
> Kernels: [Constitution](kernels/Constitution.md) · [IdentityCapability](kernels/IdentityCapability.md) ·
> [Journal](kernels/Journal.md) · [Scheduler](kernels/Scheduler.md) ·
> [Supervisor](kernels/Supervisor.md) · [ContractRegistry](kernels/ContractRegistry.md) ·
> [ModelGateway](kernels/ModelGateway.md) · [EpistemicKernel](kernels/EpistemicKernel.md) ·
> [RealityBoundary](kernels/RealityBoundary.md) ·
> Engines: [MentalModelEngine](engines/MentalModelEngine.md) ·
> Red-team: [KernelStressTest](RedTeam-KernelStressTest.md)

## 1. Thesis
V2 designed cognition well but is a **well-modularized monolith**: engines are bound by
in-process method calls, an in-proc EventBus that dies on crash, single-writer SQLite,
and one DI graph in one process. Those four things turn "workstation → distributed AI
organization" into a *rewrite*, not a *config change*.

V3 adds **no cognition features**. It adds the **systems kernels** that let the *same*
engines run as one process today and as a fleet tomorrow. Plus three insights that
change the *substrate* of cognition itself:

1. **The log is the system.** Mission, Memory, Knowledge, Reflection are *projections*
   of a durable, causally-ordered event log — not sources of truth.
2. **Truth is first-class.** Knowledge carries confidence, evidence, source,
   contradiction, freshness, consensus. Councils vote on **truth**, not prompts.
3. **The system has a constitution.** Some invariants cannot be changed by *anyone* —
   not even the Governor. They sit *below* governance, as a kernel.

The result is not "an AI assistant" and not even "an AI OS" — it is a **Cognitive
Operating System**: a kernel for a digital organization that plans, learns, governs
itself, and reasons about *what it knows and who knows it*.

## 2. The non-negotiable invariant
**Network-shaped from day one, single-process by default.** Every kernel boundary has
the shape of a network boundary (message contracts, idempotent handlers, stateless
engines + external state) even while it runs in one process. Distribution becomes a
binding change in config, never a redesign. This is what "no second rewrite" *means*.

## 3. Layered model (V3 — constitution at the root)
```
┌──────────────────────────────────────────────────────────────────────────┐
│ CONSTITUTION        immutable invariants · root of trust · unchangeable    │ ← NEW kernel
├──────────────────────────────────────────────────────────────────────────┤
│ IDENTITY            principals: user · agent · tenant · service            │ ← kernel (was in V3 audit)
├──────────────────────────────────────────────────────────────────────────┤
│ JOURNAL             durable, causally-ordered event log = source of truth  │ ← NEW kernel (absorbs Semantic Clock)
├──────────────────────────────────────────────────────────────────────────┤
│ SCHEDULER           resource governor · leases · quotas · preemption       │ ← NEW kernel
├──────────────────────────────────────────────────────────────────────────┤
│ CAPABILITY          scoped, time-bound authorizations issued under Identity │ ← kernel (Identity's 2nd plane)
├──────────────────────────────────────────────────────────────────────────┤
│ ENGINES (cognition, choreographed only via the Journal):                   │
│   MISSION → COUNCIL → EXECUTION → REFLECTION                                │ ← V2 engines, reshaped
│   MENTAL MODEL ENGINE (Theory of Mind)                                     │ ← NEW engine (not kernel)
├──────────────────────────────────────────────────────────────────────────┤
│ KNOWLEDGE PLANE:  EPISTEMIC KERNEL (truth)  over  KNOWLEDGE GRAPH (data)   │ ← NEW kernel over V2 KG
├──────────────────────────────────────────────────────────────────────────┤
│ EGRESS BOUNDARY:  REALITY BOUNDARY (irreversible effects)  ‖  MODEL GATEWAY │ ← NEW kernel (RBK) + sibling MGW
│                   siblings, contradictory invariants, shared `egress-io` lib │
└──────────────────────────────────────────────────────────────────────────┘
  cross-cutting kernels/services: SUPERVISOR · CONTRACT REGISTRY
  cross-cutting: GOVERNANCE (mutable policy, enforced *within* Constitution) · OBSERVABILITY
```
Reads/decisions flow **down**; facts flow **up** as events appended to the Journal;
engines **never call each other** — they react to journaled events (choreography).

## 4. Kernel set (the frozen core — nine) — every one justified
| Kernel | Earns its place because | Dies without it |
|---|---|---|
| **Constitution** | Governance is mutable *by definition*; immutable invariants cannot live in a mutable policy engine | audit log can be rewritten, history overwritten, destructive acts rationalized away |
| **Identity & Capability** | distribution + autonomy + multi-tenant need an *actor* model and least-privilege | governance gates actions but not actors; no attribution, no tenancy |
| **Journal** | the only thing that makes in-proc→distributed a config change; gives recovery, replay, audit, and causal order | EventBus dies on crash → history lost → distribution = rewrite |
| **Scheduler / Resource Governor** | one GPU + hundreds of agents = contention is the hard wall | budgets are decoration; the system thrashes |
| **Supervisor** | hundreds of agents = partial failure is normal | one failure cascades system-wide |
| **Contract Registry** | events are the integration contract → they need versioned schemas | one event change breaks every subscriber |
| **Model Gateway** | serving hundreds of agents on finite GPU needs queue + batch + workers + leases | a "router that picks a connection" cannot scale |
| **Epistemic Kernel** | councils must vote on *truth*; truth-maintenance is behavior a *store* must not own | decisions are made on unverified, stale, or contradicted "facts" |
| **Reality Boundary** (9th, red-teamed in) | only kernel owning at-most-once irreversible external effect + compensation/gate; the airlock to the outside world | crash + Supervisor restart re-sends orders/emails; partition double-sends |

**None of these is a cognition feature.** All are systems kernels — exactly the mandate.
The 9th ([Reality Boundary](kernels/RealityBoundary.md)) was not designed in — it was
*attacked into existence* and admitted only by passing the [DecisionLog](DecisionLog.md)
test (see [RedTeam](RedTeam-KernelStressTest.md)). The Model Gateway sits beside it as a
**sibling, not a subtype** (their core invariants — coalescing vs individuation —
contradict), proven via a demotion test in the same red-team.

## 5. What V2 engines become (reshape, not rewrite)
- **EventBus → projection of the Journal** (same API, durable underneath).
- **Governance → mutable policy engine + boundary interceptor, enforced strictly
  *within* the Constitution** (Constitution > Governance, always).
- **Mission → event-sourced aggregate** (no longer a fat object; graph/log/timeline
  are streams projected from the Journal).
- **Council → durable saga** (choreography + timeout + compensation), voting on
  Epistemic truth, aware of peers via the Mental Model Engine.
- **Knowledge Graph → data plane** under the **Epistemic Kernel** (trust plane).
- **Runtime Orchestrator → Model Gateway** (queue/batch/workers/leases).
- **DI container → composition per *deployment unit*** (engines talk via Journal/RPC).

## 6. Semantic time (insight kept, kernel rejected)
"Semantic Clock" is **correct as an insight, wrong as a kernel.** Causal ordering is a
property the **Journal must already provide** to be a correct distributed log
(logical/vector clocks on every event). The "semantic timeline" (order by
dependency → decision → meaning) is a **projection / read model** over that order —
not a standalone kernel. Folding it in honors the anti-inflation rule. See
[Journal §Semantic ordering](kernels/Journal.md#5-causal--semantic-ordering).

## 7. Theory of Mind (engine, not kernel)
Agents must model *other agents'* beliefs/knowledge/confidence ("does Analyst know X?
how sure is Scout?"). This is real and missing in V2 — but it is **derivable** as a
per-observer **projection** over the Epistemic Kernel (what is believed) + Identity
(who is who) + Journal (who was exposed to which events). So it is an **engine** in the
cognition tier, not a kernel. See [MentalModelEngine](engines/MentalModelEngine.md).

## 8. Single → distributed = config, not rewrite
```
workstation:  Constitution=signed file · Identity=local tokens · Journal=SQLite append-log
              Scheduler=in-proc loop · Gateway=in-proc queue · all engines one process
organization: Constitution=signed+replicated · Identity=IdP · Journal=external log/broker
              Scheduler=central service · Gateway=fleet of model-workers · engines split
change:       config bindings only — contracts, idempotent handlers, projections unchanged
```

## 9. Architecture Freeze
**This kernel set is frozen at nine.** The risk after Constitution/Identity/Journal/
Scheduler/Supervisor/ContractRegistry/ModelGateway/Epistemic/RealityBoundary is no longer
"too small" — it is **Kernel Inflation** (kernels with overlapping responsibility).
Therefore the standing rule, enforced by review:

> **No new kernel without proving that an existing kernel cannot solve the problem.**

The freeze is not a wall against correction — it is a *bar*. The 9th kernel
([Reality Boundary](kernels/RealityBoundary.md)) cleared that bar: it was forced by a
red-team counterexample (crash mid-egress → double-effect), not by accumulation. The
same red-team also (a) *demoted-tested* the Model Gateway and kept it as a sibling, and
(b) found the Journal's agreement story *incorrect* and fixed it **inside** the kernel
(no 10th). The next phase is **building and proving**, not designing. A new kernel may be
proposed only with architectural evidence that the existing **nine** cannot absorb the
need (the same test applied to Semantic Clock in §6 and to Reality Boundary in the
[RedTeam](RedTeam-KernelStressTest.md)). Evolution by first principles, not by
accumulation. See [DecisionLog](DecisionLog.md) for every admit / reject / demote /
correct precedent.
