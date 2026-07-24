# ADR-0011 — Decision Intelligence Framework (auditable decisions over the Logic Engine)

**Status:** Accepted (implementing) · **Date:** 2026-07-18 · **Blast radius:** Medium (new isolated package; reuses an existing engine; no runtime rewiring)
**Constitution:** Articles II (root-cause), IV (capability-first), VIII (deterministic, no `eval`), XI (verify)
**Under:** ADR-0003 (Cognitive Kernel — validation/reasoning is one subsystem, not scattered), ADR-0007 (Capability-first), ADR-0008 (Cognitive Logic Engine)
**Relates:** Epic Trust (evidence-first), existing `backend/decision.py` (OX-DECISION-1, unrelated epistemic recommender)

## Context

The operator asked for a **Decision Intelligence Framework**: make every decision
auditable, and let reasoning reliably distinguish *correct / incorrect / impossible /
under-constrained / multiple-valid / contradiction* — never forcing a single answer
when several exist, and refusing unsupported conclusions.

Two facts shaped the design (root-cause discipline, Article II):

1. **The deterministic core already exists.** `backend/logic/` (ADR-0008, the
   Cognitive Logic Engine) is a finite-domain CSP reasoner that already provides the
   constraint model (`constraint_graph.py`), a deterministic no-`eval` solver with the
   exact 5-way status the mission asks for (`solver.py`), an independent verifier
   (`verifier.py`), reproducible proofs (`proof.py`), and minimal-conflict diagnostics
   (`diagnostics.py`). Re-implementing a second solver/verifier would create two CSP
   engines to keep in sync — the precise "capable but scattered, wired ad-hoc"
   duplication ADR-0003 exists to stop, and a new surface the Epic Trust freeze
   discourages.

2. **The name `decision` is taken.** `backend/decision.py` (OX-DECISION-1) is an
   existing read-only epistemic recommender imported by `main.py`, `calibration.py`,
   `observability.py`, and `theory.py`. A `decision/` package would shadow it.

## Decision

Build the Decision Intelligence Framework (DIF) as a **service layer** in a new,
collision-free package **`backend/decision_intelligence/`** that **reuses** the Logic
Engine for all solving/verification and adds only what is genuinely new. One CSP core.

```
backend/decision_intelligence/
  constraint_analyzer.py   Phase 1 — NL/formal → structured AnalysisModel
                           (facts · variables · constraints · unknowns · assumptions
                            · goals · missing_information). NEVER invents facts:
                            an extracted fact whose cited span is absent from the
                            source is demoted to an assumption or to missing_information.
  decision_engine.py       Phases 2 + Self-check — orchestrator. analyze → solve
                           (logic) → classify → counter-example → verify → confidence
                           → score → render the audit report. Bounded self-check loop.
  counter_example.py       Phase 3 — ACTIVE invalidation: search for a solution whose
                           GOAL differs from the candidate (a real attempt to prove the
                           answer wrong). If one exists and verifies, the unique claim
                           is rejected and the class becomes MULTIPLE/UNDERCONSTRAINED.
  decision_verifier.py     Phase 4 — audit view over logic.verify: PASS/FAIL for every
                           constraint AND every load-bearing assumption; overall verdict.
  confidence_engine.py     Phase 5 — confidence COMPUTED from five evidence components
                           (never a heuristic vibe): verified-constraint ratio, proof
                           completeness, information completeness, answer determinacy
                           (alternatives), assumption integrity. Hard gates + calibration.
  decision_score.py        Phase 6 — deterministic /100 auditability rubric from run
                           telemetry (reasoning accuracy /20, constraint tracking /15,
                           consistency /15, evidence usage /10, hallucination resistance
                           /10, decision quality /10, counter-example search /10,
                           self-verification /5, confidence calibration /5).
```

### Boundary: engine vs. framework

- **Logic Engine (ADR-0008)** = *exact reasoning*: given a constraint graph, SEARCH,
  VERIFY, PROVE, DIAGNOSE. Deterministic, decidable, no LLM.
- **DIF (this ADR)** = *auditable decision-making around* that reasoning: structured
  problem analysis with a no-fabrication guard, active counter-example invalidation,
  evidence-based confidence, a process-quality score, the self-check loop, and the
  human-readable audit report.

### Determinism & the LLM boundary (Article VIII)

Every guarantee comes from the **symbolic core**, which contains no LLM and no `eval`.
The only place natural language enters is `constraint_analyzer.analyze()`; that layer
is *extraction*, and it is guarded (cited-span verification) so it can never inject an
unsupported fact into the model. Given the same `AnalysisModel`, the entire pipeline —
classification, counter-example, verification, confidence, score, report — is bit-for-bit
reproducible. The benchmark suite therefore builds **formal** models directly, so the
acceptance tests are fully deterministic and independent of any model/runtime.

### Classification (Phase 2) and CONTRADICTION

The five classes are the Logic Engine's: `SATISFIABLE`, `UNSATISFIABLE`,
`UNDERCONSTRAINED`, `MULTIPLE_SOLUTIONS`, `UNKNOWN`. **CONTRADICTION** is not a sixth
class — it is a *diagnosis* attached to `UNSATISFIABLE`: DIF marks `contradiction=True`
when the minimal unsat-core is a *logical* conflict (a variable forced to two distinct
constants, or a constraint asserted alongside its negation), as opposed to a mere
capacity/pigeonhole impossibility. This cleanly separates the mission's "Contradictory"
from "Impossible" test families while keeping the solver's status set intact.

### Confidence formula (Phase 5, documented — not heuristic)

Each component ∈ [0,1], derived from run evidence:

| Component | From |
|---|---|
| `verified_constraint_ratio` | verifier: passed / total |
| `proof_completeness` | 1.0 iff solver search was exhaustive AND the proof re-verifies |
| `information_completeness` | 1 − missing_information / (grounded_facts + missing_information) |
| `answer_determinacy` | 1.0 if no goal-differing counter-example; else 1 / distinct-goal-values |
| `assumption_integrity` | 1 − unverified_load_bearing_assumptions / total_constraints |

`confidence = (Σ wᵢ·cᵢ)` under documented weights, then **gated**: `UNKNOWN ⇒ 0`;
verifier FAIL ⇒ 0; a surviving goal-differing counter-example ⇒ `answer_determinacy`
dominates so a "unique answer" confidence collapses. Calibration notes record every cap.

## Governance reconciliation

- **Cognitive Kernel (ADR-0003, validators paused):** DIF is not a rogue validator
  plugin. It is a *service composed over the existing reasoning subsystem*, consistent
  with "architecture before drivers": it adds no new stable-interface obligations and
  reuses the sanctioned engine. It slots under the Kernel's future Validation/Reasoning
  subsystem rather than forking one.
- **Epic Trust feature freeze (increase reliability or evidence):** DIF's entire purpose
  is auditability and evidence; it reuses the proven core instead of expanding it. It is
  an **isolated additive package** and is **not wired into the RC-1 agent runtime** by
  this ADR. A `decide()` API and a ready-to-register `decide` tool schema are provided;
  wiring them into `BUILTIN_TOOLS` is a deliberate, separate follow-up.

## Consequences

**Positive** — one CSP engine, no drift; every decision ships an auditable report
(analysis → candidates → decision → counter-example → verification → confidence →
score); impossible/ambiguous/multiple/contradiction are *detected*, not guessed;
unsupported conclusions are refused; output is deterministic.

**Costs / limits (honest)**
- DIF inherits the Logic Engine's scope: **finite-domain** problems and a **bounded**
  extraction grammar. Open-domain NL still requires the model to frame inputs; the guard
  bounds — but cannot fully eliminate — extraction error. Confidence in the *extraction*
  is surfaced separately from confidence in the *reasoning*.
- The `/100` decision score rates the **process** (was it auditable, did it search a
  counter-example, did it refuse when it should) — it is not a claim about real-world
  truth beyond what the constraints encode.
- Determinism holds for a fixed `AnalysisModel`; two different valid framings of the same
  prose can differ. That variance lives entirely in the guarded extraction layer.

## Verification (Article XI)

`backend/tests/test_di_*.py` + `test_di_benchmark.py`: unit tests per module and a
benchmark suite over formal models — logic grid, scheduling, CSP (map colouring),
knight-and-knave, salary, graph reasoning, plus **impossible** (pigeonhole → UNSAT, no
contradiction), **contradictory** (X=1 ∧ X=2 → UNSAT + contradiction), and
**underconstrained** (goal not determined) families. Asserts each acceptance criterion:
detect impossible / ambiguous / multiple / contradiction, refuse unsupported
conclusions, deterministic output, evidence-based confidence. All green before merge.

## Follow-ups

1. Register the `decide` tool in `BUILTIN_TOOLS` (post-freeze / when the agent should
   call verified decision-making directly).
2. Widen `constraint_analyzer` extraction families (schedules, comparatives) with guards.
3. Feed DIF's `decision_score` into the platform's evaluation ledger (Epic Trust).
