# Migration V2 → V3

> V3 is a substrate change, not a feature change. The same engines run on new kernels.
> Migration is additive, flagged, and ordered so each kernel is proven before the next
> depends on it. Honors "no breaking changes; no second rewrite."
> Parent: [V3-Architecture](../v3/V3-Architecture.md)

## 1. The one structural move
Make the **Journal** the source of truth; make every store a **projection**. Everything
else in V3 is layered on that. So the Journal goes first, behind a flag, with the V2
stores still authoritative until projections reach parity.

## 2. Order (each step proven before the next)
```
S0  Contract Registry   seed current event schemas at v1; validate-only (no enforce)
S1  Journal             durable append log; EventBus becomes a Journal subscriber;
                        stores become projections via outbox (V2 reads unchanged)
S2  Constitution        load signed invariants; enforce BELOW governance (fail-closed)
S3  Identity & Capability assign delegated identities to the 14 agents; cap-check tools
S4  Scheduler           admission + leases + quotas; budgets become enforced
S5  Model Gateway       runtime orchestrator → queue/batch/workers serving on leases
S6  Supervisor          supervision tree over kernels/engines/agents
S7  Epistemic Kernel    envelope over KG; Council votes reference claims
S8  Mental Model Engine projection over Epistemic+Identity+Journal (read-only)
S9  Reality Boundary   airlock for irreversible external effects; wrap mutating tools
                       (at-most-once + reconcile + compensation/gate); Gateway shares
                       the `egress-io` lib (red-teamed in — see RedTeam-KernelStressTest)
```
S9 ordering note: Reality Boundary depends on the Journal (intent/result events) and
the Constitution (irreversible→gate), so it lands after S1–S2; it is sequenced last only
because it was discovered last (by red-team), not because of a dependency — it may be
pulled earlier once those two are on, and should be, since it is what makes the
Supervisor's let-it-crash safe at the egress boundary.
S0–S1 are the load-bearing change; S2–S8 each become trivial once the Journal exists,
because they are mostly *projections and policies over events*.

## 3. Per-step exit criteria
A flag flips on-by-default only when: V2 parity holds, telemetry shows no regression,
and flag-off rollback is verified. Identical discipline to the
[V2 MigrationPlan](../v2/MigrationPlan.md).

## 4. Data migration (additive, backed up)
- **Journal**: new append-only store (`journal.db` → external log later). One-time
  backfill replays existing `house_state`/KG/audit rows as historical events
  (idempotent). Backup first.
- **Constitution**: `config/constitution.yaml` + signature; seeded from rules
  SkynetClaw already honors ("no destructive action without approval", "never bypass
  GPS-2", "never modify audit").
- **Epistemic**: existing KG nodes get a default envelope; additive.
- No destructive schema change without backup + operator approval (a Constitutional
  article now enforces this).

## 5. Compatibility guarantees
- The V2 engine docs ([Mission](../v2/MissionEngine.md), [Council](../v2/CouncilEngine.md),
  [Execution](../v2/ExecutionStateMachine.md), [Reflection](../v2/ReflectionEngine.md),
  [Knowledge](../v2/KnowledgeGraph.md), [Dashboard](../v2/DashboardArchitecture.md))
  remain valid; V3 changes what they stand *on*, not what they *do*.
- `/api/agent/run` and the V1/V2 UI keep working through all steps.
- All flags off ⇒ system behaves exactly as V2.

## 6. After migration: the Freeze
Once S0–S8 are on and proven, the architecture is **frozen**
([V3-Architecture §9](V3-Architecture.md#9-architecture-freeze)). The next work is
building real missions on this substrate and *proving* the kernels under load — not
designing more. New kernels require passing the [DecisionLog](DecisionLog.md) test.
