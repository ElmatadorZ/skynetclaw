# ADR-0001 — Reasoning Validation Layer (RVL)

> **Superseded by [ADR-0002](ADR-0002-cognitive-validation-layer.md) (2026-07-13):**
> RVL evolved into the Cognitive Validation Layer (CVL). Arithmetic is now the
> `reasoning`-domain validator; the module lives in `cognitive_validation.py`
> (`reasoning_validation.py` is a compat shim). The design below stands as the
> origin of the framework.

**Status:** Superseded by ADR-0002 · **Date:** 2026-07-13 · **Blast radius:** Medium
**Constitution:** SkynetClaw Engineering Constitution v1.0 (Articles I, II, IV, V, VIII, X, XI, XII)

## Context

The SkynetClaw Benchmark (SCB) evaluation scored the platform 81.4/100 avg, with
the weakest dimension **SCB-002 Quantitative Reasoning = 62 (Intermediate)**: the
model produces wrong equations and, crucially, **does not verify its own numbers**
before answering. Meanwhile SCB-004 Consistency = 97 (Expert) — the system is
excellent at *detecting* inconsistency but never applies that strength to its own
arithmetic proactively.

Evidence (verified 2026-07-13): no dedicated arithmetic/equation verifier exists;
the closest components (`warrant_check` CEE-C1, `completion_evidence`,
`guidance_check` G1) validate *other* dimensions (fabricated files, absent
artifacts, deviant acts) but are scattered, not a framework.

The improvement is **harness-fixable without changing the 14B model** — a
deterministic check compensates for the model's arithmetic gap.

## Decision

Build a **Reasoning Validation Layer (RVL)** — an extensible validation framework,
not a one-off checker. Arithmetic is the **first validator plugin**.

Pipeline: **Observe → Validate → Repair → Re-Validate → Accept/Reject**.
- Validators implement a `Validator` protocol (`applicable`, `validate`) and
  `register()` themselves (Open-Closed: new validators need no pipeline change).
- `reasoning_validation.validate(text)` runs all applicable validators, collects
  `Issue`s, and renders a **repair prompt** the caller feeds back to the model.
- Wired at the agent completion gate beside `completion_evidence`: an error
  re-prompts (bounded by the existing completion-rejection budget); if still wrong
  after retries, the answer ships flagged, never as a clean SUCCESS.

## Alternatives

1. **Dedicated `calc_verifier.py`** (original proposal) — rejected: not extensible;
   would be duplicated for each future check (violates Open-Closed / DRY).
2. **Prompt the model to self-check** — rejected: a 14B model ignores such guidance
   (proven this session by the vault banner); validation must be deterministic.
3. **Fold into `completion_evidence`** — deferred: that module checks artifact
   existence, a different concern; RVL is the umbrella those validators can migrate
   into later.

## Trade-offs

- (+) Extensible across all SCB categories; deterministic; model-free; testable.
- (+) Reuses the existing completion-rejection retry loop (no new control flow).
- (−) A new gate adds a small risk of false-positive re-prompts → mitigated by
  narrow extraction (explicit `a op b = c` only) + an eval that proves prose does
  not trip it.

## Consequences

- New: `backend/reasoning_validation.py` (framework + `ArithmeticValidator`).
- Wired: agent completion gate emits `reasoning_invalid` / `reasoning_unverified`.
- Eval: `rvl_arithmetic_validator`, `rvl_is_extensible` lock the behavior.

## Rollback Plan

Remove the RVL block at the completion gate (the surrounding logic is unchanged)
and delete `reasoning_validation.py`. No persistent state, schema, or API contract
depends on it — rollback is a code revert.

## Verification (Article XI)

Unit self-test (catches wrong math, passes correct + prose); eval suite green
(33/33) incl. the two RVL cases; live: an answer containing a wrong calculation is
re-prompted and corrected before acceptance.

## SCB Impact (Article XII)

Primary: **SCB-002 Quantitative** (target 62 → 75+). Secondary: reinforces
SCB-004 Consistency. New SCB regression invariant: *arithmetic is verified before
an answer is accepted.*

## Future Roadmap

Next validator plugins (each an isolated PR, same pattern): equation, logic,
constraint, consistency (migrate CEE), confidence-calibration, citation, unit.
Longer term: migrate `completion_evidence` and `guidance_check` under the RVL
umbrella so all pre-acceptance validation shares one pipeline.
