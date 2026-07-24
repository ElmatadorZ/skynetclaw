# ADR-0004 — CVL v2: Cognitive Domain Architecture

**Status:** Proposed (design only) · **Date:** 2026-07-13 · **Blast radius:** Large (re-architecture)
**Constitution:** Articles III, IV, V, IX, X · **Artifact:** [CVL_V2_COGNITIVE_DOMAIN_ARCHITECTURE.md](../architecture/CVL_V2_COGNITIVE_DOMAIN_ARCHITECTURE.md)
**Related:** ADR-0002 (CVL v1), ADR-0003 (Cognitive Kernel — steps 1–6 complete).

## Context

The Cognitive Kernel foundation is complete (5 subsystems + operator role +
validator layer, all on one audit spine). CVL v1 is a flat list of three validators
(`arithmetic`, `expression`, `secret_leak`) with `domain` as an inert tag. The
directive: **stop adding validators; re-architect CVL as Cognitive Domains** — each
domain owning its Validator Drivers, Repair Strategy, Confidence, Explainability,
Severity, and Evaluation Metrics.

## Decision

Adopt the **Cognitive Domain Architecture** (spec v0.1): CVL becomes a registry of
Domains; a Domain is a registry of Drivers plus the behaviour policy for that
cognitive capability. Ten domains defined — Reasoning, Consistency, Citation, Safety,
Tool Use, Planning, Memory, Knowledge, Communication, Policy — each mapped to a kernel
hook, execution order, I/O, repair strategy, metrics, FP risks, and future validators.

Two load-bearing decisions:
1. **Confidence × Severity → Decision matrix** is the single false-positive guard: a
   low-confidence finding never blocks. Deterministic domains run at 1.0; heuristic
   domains start warnings-only.
2. **Metrics self-regulate authority:** a domain's measured FP-rate caps its
   confidence ceiling — a noisy domain auto-demotes from blocking to flagging. Growth
   is governed by measured precision, not by adding validators (directly answering
   "do not add validators blindly").

## Alternatives

1. **Keep the flat validator list, add more validators** — rejected: the directive,
   and it cannot express domain-level repair/severity/metrics or per-hook placement.
2. **One monolithic "quality" checker** — rejected: not Open-Closed, untestable per
   capability, no measurable SCB dimension.
3. **LLM-as-judge domains that can block** — rejected as a non-goal: non-deterministic
   gates are unsafe; heuristic judgment may only inform warnings.

## Consequences

- No new kernel primitives — v2 reuses the existing hooks, Policy engine, audit
  spine, and repair loop; `CognitiveValidationPolicy` generalises from "run CVL" to
  "run this hook's Domains". Blast radius stays inside CVL.
- CVL v2 makes the SCB benchmark a live property: each domain's metrics ARE its SCB
  score.
- A phased, precision-gated roadmap (spec §11) replaces ad-hoc validator additions.

## Verification (design-level, Article XI)

Spec traceability: every domain names its kernel hook and seed driver in real code
(`arithmetic`/`expression`/`secret_leak`/`warrant_check`/`guidance_check`,
`kernel_memory`, planner `_pcall`). Open questions (§10) are time-boxed to
ratification. Implementation stays paused until this ADR is accepted; each
subsequent phase is its own shippable, eval-gated change.

## Roadmap (summary — full in spec §11)

Phase 0 freeze v1 (done) → 1 domain abstraction (parity, no behaviour change) →
2 confidence+severity+repair matrix → 3 metrics + self-regulation → 4 new domains one
PR each, precision-gated (Consistency → Citation/Policy migrate → Tool Use → Planning
→ Memory → Communication/Knowledge warnings-only last) → 5 retire the flat registry.
Rule: no domain graduates to blocking until measured precision clears its budget.
