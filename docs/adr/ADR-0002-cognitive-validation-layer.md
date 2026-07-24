# ADR-0002 — Cognitive Validation Layer (CVL)

**Status:** Accepted · **Date:** 2026-07-13 · **Blast radius:** Large
**Supersedes/extends:** ADR-0001 (RVL)
**Constitution:** SkynetClaw Engineering Constitution v1.0 (Articles I–V, VIII, IX, X, XI, XII)

## Context

ADR-0001 introduced the Reasoning Validation Layer (RVL): an extensible framework
that validated the model's *reasoning* (arithmetic first) before an answer was
accepted. In use it became clear the framework's value is not specific to
reasoning — the same Observe/Validate/Repair machinery can guard **every**
cognitive capability SkynetClaw exercises before it commits to a response or an
autonomous action.

The operator directed the evolution: RVL → **Cognitive Validation Layer (CVL)**,
the single **cognitive quality gate** before any response or autonomous action is
accepted. Arithmetic becomes the first of many *cognitive* validators.

## Decision

**1. Scope: validate every cognitive capability, organized by domain.**
Each validator declares a `domain`:

| Domain | Guards | First validator |
|---|---|---|
| `reasoning` | math, logic, units, consistency of claims | **ArithmeticValidator** (shipped) |
| `safety` | leaked secrets, unsafe content in output/actions | **SecretLeakValidator** (shipped) |
| `memory` | claims about stored/recalled facts match the store | roadmap |
| `planning` | a plan exists, is ordered, has no dangling deps | roadmap |
| `tool_use` | tool calls are well-formed and arguments are valid | roadmap |
| `production` | "production-ready" claims meet the prod checklist | roadmap |

**2. Pipeline (operator's design): Observe → Diagnose → Repair → Explain → Validate → Accept.**
- **Observe** — a validator extracts the claims/artifacts it can check.
- **Diagnose** — it reports the issue *and its root cause* (`Issue.diagnosis`), not
  merely "wrong".
- **Repair** — CVL renders a correction prompt fed back to the model.
- **Explain** — CVL emits a **human-readable audit record** of every finding, its
  diagnosis, and the repair action taken. This is mandatory for every automatic
  repair — transparency and auditability are first-class, not a side effect.
- **Validate** — the caller re-runs CVL after the correction.
- **Accept** — errors block acceptance until fixed (bounded by the existing
  completion-rejection budget); if still failing, the answer ships **flagged**,
  never as a clean SUCCESS.

**3. The cognitive quality gate.**
CVL runs at the agent completion gate today (before a response is accepted). The
architecture is designed to also run before an autonomous state-changing action —
the Safety/tool_use validators are the migration target for the existing
`guidance_check` (G1) act-boundary gate, so eventually one pipeline guards both
"before you answer" and "before you act".

## Engineering Council (Article IX) — condensed

- **Architect:** domain-tagged validators + one pipeline avoid a gate per concern;
  Open-Closed preserved. ✅
- **Skeptic:** "cognitive" must not be aspirational — ship ≥2 domains now.
  → Reasoning + Safety both shipped and eval-locked. ✅
- **Security:** a secret-leak validator on the *output* is a real, new safety win.
  Patterns kept conservative to avoid false-positives. ✅
- **Reliability:** `validate()` never raises; a broken validator is skipped, the
  mission proceeds. ✅
- **Performance:** deterministic regex/arithmetic, no model call — negligible cost
  at the gate. ✅
- **Maintainer:** `reasoning_validation.py` kept as a re-export shim so no import
  breaks. ✅

## Alternatives

1. **Keep RVL reasoning-only, add sibling layers per capability** — rejected:
   duplicates registry/pipeline/gate wiring N times (DRY / Open-Closed violation).
2. **One giant validator with if/else per concern** — rejected: not Open-Closed;
   untestable in isolation.
3. **Rename the module to `cognitive_validation` with a hard cutover** — rejected
   in favor of a compat shim so existing imports keep working (Maintainer lens).

## Consequences

- New: `backend/cognitive_validation.py` (framework + `Issue.domain`/`diagnosis`,
  `by_domain()`, `explanation` in the pipeline result, `ArithmeticValidator`
  [reasoning], `SecretLeakValidator` [safety]).
- `backend/reasoning_validation.py` → deprecated re-export shim.
- Completion gate emits `cognitive_invalid` / `cognitive_unverified` /
  `cognitive_note` with `domains` + `explanation`; publishes `cognitive_invalid`
  to house_sync for the audit trail.
- Eval: `cvl_arithmetic_validator`, `cvl_multi_domain`, `cvl_is_extensible`.

## Rollback Plan

Revert the completion-gate block to the ADR-0001 RVL form and drop
`cognitive_validation.py` (the shim re-export makes this a code-only revert). No
persistent state or API contract depends on CVL.

## Verification (Article XI)

Unit self-test (multi-domain catch, explanation emitted, no prose false-positive);
eval green incl. the three CVL cases; live: an answer with wrong arithmetic or a
leaked credential is re-prompted, and every repair produces an Explain record.
*Honest limit:* end-to-end model repair depends on the 14B producing a defect in a
run that also completes — the deterministic validators guarantee the catch when a
defect is present.

## SCB Impact (Article XII)

Primary: **SCB-002 Quantitative** (reasoning) + a new **Security/Safety** invariant
(no credential ships in a response). Framework now maps 1:1 to SCB dimensions via
`Issue.scb_category`, so future SCB weaknesses become "register another validator".

## Future Roadmap

Per-domain validators, each an isolated PR on the same pattern: reasoning
(equation, logic, unit, consistency — migrate CEE); memory (recall-consistency);
planning (dependency-graph, ordering); tool_use (arg schema); production
(prod-readiness checklist). Then migrate `completion_evidence` and `guidance_check`
under CVL so one pipeline guards both **response** and **autonomous action**.
