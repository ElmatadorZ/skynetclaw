# ADR-0006 — Create the Cognitive Analysis Framework (CAF)

**Status:** Proposed · **Date:** 2026-07-13 · **Blast radius:** Large
**Under:** ADR-0007 (Capability-first Architecture)
**Grounded in:** [CAPABILITY_MODEL.md](../specs/CAPABILITY_MODEL.md) · [CAF spec](../architecture/CAF_COGNITIVE_ANALYSIS_FRAMEWORK.md) · [Benchmark OS](../specs/BENCHMARK_OS.md)

Because the Capability Model and the CAF/Benchmark-OS specs now carry the design, this
ADR is deliberately small: it records the *decision*, not the design.

## Reason

The benchmark review found SCB-002 (Quantitative) = 62 and SCB-005 (Planning) = 78,
with the root cause in the **cognitive data plane**, not the harness. The Capability
Model formalizes it: the **Analysis** capability family (Decision, Cost-Benefit,
Sensitivity, Scenario, Risk, Financial, Optimization, Resource-Allocation) is almost
entirely `missing`. Today the system does structured analysis in free-form prose —
non-deterministic and unverifiable.

## Capability Gap

Analysis family maturity (Capability Model §3): **~0 present / ~7 missing.** These are
`Capability`-level gaps, each lacking Service · Engine · Tool · Validator. Verification
for them (`method_completeness`, `sensitivity_absent`, …) is also missing, so even
correct-looking analyses ship unassured.

## Decision

**Create the Cognitive Analysis Framework (CAF)** — the Service + Engine layer that
realizes the Analysis capability family as a plugin framework of **deterministic
analysis engines**, exposed as governed tools and checked by CVL/CAE validators
(CAF spec). Generalizes the proven `safe_math`/`calculator` pattern from arithmetic to
analysis. Paired with the **Benchmark OS** so every engine graduates only when a
benchmark category measures it (no blind growth).

## Create

- `AnalysisService` + `AnalysisEngine` plugin framework (CAF spec §4 contracts).
- Engines, ship-ordered by Capability-Model maturity × an existing benchmark category:
  Decision → Cost-Benefit → Finance/Unit-Economics → Sensitivity → Risk → Optimization
  → Forecast → Resource-Allocation.
- Each engine ships `conforms_to()` + its Validator + its Benchmark-OS category.
- The **Cognitive Orchestration Router** (task-shape → engine) so the framework is
  *routed to*, not merely available.

## Consequences

- Investment shifts to the cognitive data plane; the control plane (kernel, governance,
  audit) is reused unchanged — CAF adds **no kernel primitives**.
- Analysis becomes deterministic, traceable, and assured; SCB-002 target 62 → 80-85,
  plus new Financial/Decision/Risk categories.
- Establishes the first full worked example of Capability-first (ADR-0007):
  `Analysis → AnalysisService → engines → tools → validators`.
- Dependency chain for later ADRs: Planning-Engine-v2 and Confidence-Calibration follow
  the same five-layer pattern.

## Alternatives rejected

Prompt-engineer the model into better analysis (non-deterministic, unverifiable);
a bigger model (orthogonal — does not fix planning structure, calibration, or
measurement). Both fail the Capability-first test: they add no capability node with an
assured, measurable realization.

## Verification (design-level)

Each engine: `conforms_to()` + eval parity + a Benchmark-OS category showing the lift.
No engine ships without a benchmark exercising it. Implementation paused pending
ratification of ADR-0007 (principle) then this ADR.
