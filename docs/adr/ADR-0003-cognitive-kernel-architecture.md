# ADR-0003 — Adopt the Cognitive Kernel architecture; pause validator development

**Status:** Accepted (Engineering Council reviewed — Accept with amendments A1–A6) · **Date:** 2026-07-13 · **Blast radius:** Large (architecture-defining)
**Constitution:** SkynetClaw Engineering Constitution v1.0 (Articles III, IV, V, IX, X)
**Related:** ADR-0001 (RVL), ADR-0002 (CVL) — CVL becomes a subsystem under this ADR.
**Artifact:** [docs/architecture/COGNITIVE_KERNEL_SPEC.md](../architecture/COGNITIVE_KERNEL_SPEC.md) v0.1

## Context

CVL (ADR-0002) generalized the "stable interface + registry + hook" pattern from
reasoning to every cognitive capability. The operator observed that the pattern's
real scope is the *whole system*: routing, memory (the Obsidian second brain), the
deliberation council, the planner, the execution loop, and the event bus are all
capable but scattered, wired ad-hoc to each other. CVL is best understood as the
**first subsystem of a Cognitive Kernel**, not a standalone framework.

The directive: **design the Cognitive Kernel Specification before building any
further validators** — architecture before drivers, the Linux-kernel discipline.

## Decision

1. **Adopt the Cognitive Kernel (CK) as SkynetClaw's core architecture**, defined by
   COGNITIVE_KERNEL_SPEC v0.1: a cognitive lifecycle, kernel services, an event
   model, a policy model, a cognitive state machine, and stable subsystem interfaces
   (memory, planning, validation, execution, governance).
2. **CVL is reclassified as the Validation Subsystem** — the reference conforming
   subsystem, not the whole framework.
3. **Pause validator development.** No new validator plugins are written until the
   spec is ratified and the foundational migration steps (Event envelope, Context +
   Memory interfaces, Policy-on-hooks) land. Future validators are then implemented
   as drivers on a real kernel.
4. **The kernel is interfaces + a thin orchestrator, migrated strangler-fig.** No
   big-bang rewrite; existing modules are adapted one-per-PR, system shippable
   throughout (Spec §8).

## Alternatives

1. **Keep shipping validators, defer the kernel** — rejected: compounds ad-hoc
   wiring; each validator would bake in assumptions the kernel later has to undo.
2. **Big-bang kernel rewrite** — rejected (Article V): unshippable for weeks, high
   blast radius; contradicts the strangler-fig principle now written into the spec.
3. **Informal design (no spec doc)** — rejected: a Large, foundational decision
   requires a ratifiable artifact and an ADR (Articles IX, X).

## Consequences

- New: `docs/architecture/COGNITIVE_KERNEL_SPEC.md` (v0.1, design-only).
- No runtime change; no code moved; no validators added. The repo behaves
  identically until a migration PR is opened under a future ADR.
- Roadmap reordered: framework-first (Event → Context/Memory → Policy → Scheduling/
  Execution split) *then* resume validators.

## Risks & mitigations

- **Over-engineering / god-object.** → Principle #1 (kernel = interfaces + thin
  orchestrator) and the strangler-fig migration are written into the spec as
  non-negotiable.
- **Analysis paralysis (spec never ships code).** → Spec §8 gives a concrete,
  ordered migration; §10 time-boxes open questions to ratification.
- **Physical envelope ignored.** → Principle #7 binds the kernel to the 16k ceiling
  and CPU-bound execution; the Context Service owns the budget.

## Verification (Article XI)

The deliverable is a specification, so verification is design-level (Spec §11) and is
**complete**: Engineering Council review across eight lenses + a four-mission
walkthrough against the state machine — see
[COGNITIVE_KERNEL_REVIEW.md](../architecture/COGNITIVE_KERNEL_REVIEW.md). Verdict:
*Accept with amendments A1–A6*, all folded into Spec v0.2. The walkthrough confirmed
no lifecycle phase is missing and that the state machine would have *prevented* the
historical 16k-overflow bug. This ADR is now Accepted; the next gate is migration
step 1 (Event envelope).

## SCB Impact (Article XII)

Indirect but broad: a formal lifecycle + policy hooks make every SCB dimension a
first-class, testable stage rather than an emergent behavior — e.g. Planning
(SCB-005) gains a real dependency-DAG interface; Consistency/Quantitative (SCB-002/4)
become validators on a defined `PRE_COMMIT` hook.
