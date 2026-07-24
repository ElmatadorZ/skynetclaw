# Reality Boundary Kernel (Effect / Actuation / Egress Transaction Manager)

> The 9th kernel — the **airlock between internal truth (the Journal) and the
> irreversible external world**. Forced by the red-team: no other kernel owns
> exactly-once external effect integrity, and the Supervisor's let-it-crash makes the
> gap actively dangerous.
> Parent: [V3-Architecture](../V3-Architecture.md) · Justification:
> [DecisionLog](../DecisionLog.md) · Evidence: [RedTeam](../RedTeam-KernelStressTest.md)

## 1. Why it is forced (not designed in)
It was *attacked into existence*. The internal idempotency of the [Journal](Journal.md)
(`stream, dedupe_key`) cannot reach outside the system — foreign endpoints do not honor
our dedupe key. A crash *after* an external effect but *before* journaling its result,
followed by a [Supervisor](Supervisor.md) restart + node replay, re-executes the
external effect (order placed twice, email sent twice). The let-it-crash kernel is the
*cause* of double-effect; the Reality Boundary is the cure. No existing kernel owns
this: Journal=internal truth, Scheduler=resources, Constitution=*forbids* but does not
*implement*, Identity/Capability=who/what (not how-many-times), Model Gateway=inference
effects only. → a distinct, ownerless single responsibility. See the DecisionLog test.

## 2. Single responsibility (one sentence, no "and")
> Guarantee that every irreversible external effect executes **at-most-once**, is
> durably bound to a journaled intent, and is **either reversible via a registered
> compensation or blocked pending a human gate**.

## 3. The honest contract (attacked, then weakened to the truth)
Exactly-once against an arbitrary endpoint is **impossible** (Two Generals). The RBK
therefore does **not** promise exactly-once in general; it promises:
- **at-most-once** via *single-flight* + intent-journaling + an idempotency token
  *when the endpoint cooperates* (most modern APIs accept an `Idempotency-Key`).
- **at-most-once + reconciliation** when the endpoint does **not** cooperate: the effect
  is wrapped so a post-crash *reconcile* query ("did this happen?") runs before any
  retry; if reconcile is impossible, the effect is **non-retryable** and a crash mid-
  effect escalates to a human gate (never a silent retry).
- **compensation** only where the external system supports it; a **non-compensable +
  non-reconcilable** effect is a Constitutional irreversible action → mandatory gate.

This honesty is itself a red-team result: a kernel that *claimed* exactly-once would be
incorrect.

## 4. The airlock protocol
```
agent effect request (capability + Scheduler lease)
  → Constitution.check (irreversible? compensable? → gate decision)
  → RBK: append INTENT to Journal  (effect:..., idempotency_key, reconcile_query, compensation)
  → execute via egress-io driver with the idempotency_key   ← the only place a foreign call is made
  → append RESULT to Journal  (success | failure | unknown)
  → on UNKNOWN after crash: reconcile() before any retry; if unreconcilable → gate
  → on FAILURE needing rollback: run registered compensation (a new forward effect)
```
Intent and result are **two journaled events** straddling the single foreign call —
the outbox/saga boundary, owned here, not smeared across the Execution engine.

## 5. Relationship to Model Gateway (sibling, not parent)
RBK and the [Model Gateway](ModelGateway.md) are **siblings at the egress boundary with
contradictory core invariants** (proven by Liskov in the DecisionLog):
- RBK = **per-effect individuation** (never coalesce; re-execute forbidden).
- MGW = **request coalescing / batching** (merge requests; re-execute safe).
A kernel cannot hold both. They **share plumbing** (driver registry, health, fallback,
egress accounting) extracted as a non-kernel library **`egress-io`** — shared code, not
merged responsibility.

## 6. Relationship to the other kernels
- **Constitution** decides *whether* an irreversible effect may proceed (gate); RBK
  *implements* the at-most-once + compensation mechanics within that ruling.
- **Capability** authorizes *that this actor may actuate this effect*; RBK enforces it.
- **Scheduler** leases the resource; RBK consumes the lease, never allocates.
- **Journal** stores intent/result; RBK is the only writer that pairs a journaled
  intent with a foreign side effect.
- **Supervisor** can now restart freely **because** RBK makes egress crash-safe — the
  two were in conflict; RBK resolves it.

## 7. Interface
```python
class RealityBoundary:
    def actuate(self, effect: Effect, *, capability, lease) -> EffectResult
        # effect = {kind, idempotency_key, payload, reconcile, compensation, reversible: bool}
    def reconcile(self, intent_id: str) -> EffectStatus      # "did this happen?"
    def compensate(self, effect_id: str, *, reason) -> EffectResult
    def register_driver(self, driver: EgressDriver) -> None  # egress-io plugin
```

## 8. Events
`effect.intent`, `effect.executed`, `effect.unknown`, `effect.reconciled`,
`effect.compensated`, `effect.gated`, `effect.failed`. All journaled → every irreversible
touch of the outside world is replayable and auditable (Constitution Art. 1).

## 9. Single → distributed
Workstation: in-proc actuation, SQLite intent log, idempotency keys to local/remote
APIs. Organization: RBK runs per egress-capable node; the "intent committed" decision
rides on the Journal's consensus (see [Journal §5b](Journal.md#5b-agreement-not-just-ordering));
during a partition, a non-reconcilable effect is **withheld** (fail-closed) rather than
risk a double-send from both halves. Interface unchanged.

## 10. Compatibility
New kernel, flag `reality_boundary`, default off → V3 behaves as before (effects run
unguarded, exactly as V2). Turning it on routes every state-mutating tool
(`write_file` is reconcilable; network POST/order/email are wrapped) through the airlock.
Existing tools register as effects with `reversible`/`reconcile` metadata; unmarked
tools default to **non-retryable + gate-on-crash** (safe default).
