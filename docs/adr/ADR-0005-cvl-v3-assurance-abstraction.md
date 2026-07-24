# ADR-0005 — CVL v3: replace "Validation" with "Assurance"

**Status:** Proposed (design only) · **Date:** 2026-07-13 · **Blast radius:** Large (abstraction-defining)
**Constitution:** Articles III (challenge), IV, V, IX, X · **Artifact:** [CVL_V3_COGNITIVE_ASSURANCE.md](../architecture/CVL_V3_COGNITIVE_ASSURANCE.md)
**Related:** ADR-0002 (CVL v1), ADR-0004 (CVL v2 domains), ADR-0003 (Cognitive Kernel).

## Context

Mandate: decide from first principles whether *Validation* is the correct abstraction
for a Cognitive Operating System, weighing Validation vs Diagnosis vs Assurance vs
Quality vs Verification vs Evidence. Prefer elegant architecture over backward
compatibility; the goal is the correct long-term architecture, not preserving CVL.

Finding: the six candidates are not synonyms but a **stack** — Evidence (substrate);
Verification & Validation (two evidence-producing methods: vs spec, vs intent);
Diagnosis (the interpretive engine); Assurance (the architecture that composes them
into a standing, justified-confidence argument); Quality (the emergent goal, never the
mechanism). Most of CVL's deterministic checks are in fact *verification*, so
"Cognitive Validation Layer" was already a mild misnomer. "Validation" is a
**checkpoint** abstraction with four OS-scale deficits: no memory (re-decides each
turn), no argument (verdict not justification), binary framing, and no scaling to
open-ended claims.

## Decision

Adopt **Assurance** as the organizing abstraction. Rename CVL → **CAE (Cognitive
Assurance Engine)**: a continuous, evidence-based process maintaining justified,
calibrated, auditable confidence that the system's **cognitive invariants** hold.
Verification and Validation demote to evidence-source *types*. The unit of record
shifts from *finding* to **Claim + Assurance Case**. Confidence becomes **persistent
and calibrated** (Bayesian, trained on outcomes) rather than a per-turn threshold.
Human oversight becomes a **first-class, tracked evidence source**, not a silent
bypass. The architecture is designed to **dissolve** — enforcer → auditor → teacher →
intrinsic — governed by a measured *assurance dividend*.

## Alternatives considered (and why rejected as the top-level)

- **Keep Validation** — a gate cannot carry confidence, argue, or scale to open-ended
  claims; simplicity is only apparent because today's claims are trivial.
- **Diagnosis** — reactive; the engine *inside* assurance, not the architecture.
- **Evidence** — the substrate, not an architecture; alone it neither decides nor
  guarantees.
- **Verification** — a method (vs spec), a subset of evidence-gathering.
- **Quality** — the goal, never the mechanism.

## Consequences

- Substantive (not cosmetic) changes: persistent carry-forward confidence, calibrated
  Bayesian confidence, evidence sources with learned likelihood ratios, human-as-
  evidence, claim+case as the unit of record.
- **No new kernel primitives** — CAE lives on the existing hooks/events/policy/repair;
  `CognitiveValidationPolicy` generalizes to "assure this hook's claims". Blast radius
  stays inside the layer.
- v1/v2 `validate()` is not preserved where it obstructs the model (elegance over
  compatibility), behind a thin shim only if free.
- Makes calibration (ECE/Brier) the headline metric and introduces the assurance
  dividend as the governing signal for handing autonomy back to the model.

## Self-challenge (recorded, Article III)

Over-engineering for arithmetic → graceful degeneration (trivial claim ⇒ trivial
case). Philosophy-theater → the five behavioral changes above. Calibration needs
outcome labels the system rarely gets → calibrate where outcomes are observable, stay
conservative elsewhere, track calibration coverage. Bureaucracy risk → the case is a
runtime object with a live decision/metric or it must not exist.

## Verification (design-level, Article XI)

Every abstraction is grounded in real components (safe_math as a verification source,
Outcome Clock for calibration, institutional memory for assurance memory, the operator
role as bounded human evidence, the kernel hooks/audit spine unchanged). Roadmap P1–P5
is phased and eval-gated; calibration-error-beats-baseline and dividend-without-escaped-
defects are hard gates. Implementation paused pending ratification.
