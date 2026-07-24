# ADR-0008 — Cognitive Logic Engine (deterministic reasoning)

**Status:** Accepted (implementing incrementally) · **Date:** 2026-07-17 · **Blast radius:** Medium (new isolated package)
**Constitution:** Articles II (root-cause), IV, VIII (deterministic, no eval), XI (verify)
**Under:** ADR-0007 (Capability-first) — this realizes the **Reasoning** capability's
logical/constraint core as a deterministic Engine.

## Context

The model's free-form reasoning loses constraints over long chains, fails to detect
contradiction before answering, produces answers without proof, cannot distinguish
*impossible* from *under-constrained* from *multiple valid solutions*, and rarely
verifies itself. These are **architectural** problems: a language model is the wrong
substrate for constraint satisfaction. The fix is the same one that fixed arithmetic
(`safe_math`/`calculator`): **offload the exact reasoning to a deterministic engine**
the model frames inputs for and narrates outputs from.

## Decision

Build a **Cognitive Logic Engine** — a deterministic finite-domain constraint
reasoner in `backend/logic/`, single-responsibility modules:

```
logic/
  parser.py           NL / DSL → structured constraints (honest, bounded grammar)
  constraint_graph.py the constraint model + a queryable graph
  solver.py           backtracking CSP solver → 5-way status (never guesses)
  verifier.py         checks a solution against EVERY constraint (missing ⇒ FAIL)
  proof.py            step/evidence/rule/derived-fact proof (not chain-of-thought)
  diagnostics.py      minimal conflicting set + suggested repair for UNSAT
  engine.py           orchestrator + computed (non-heuristic) confidence
  benchmark.py        logic-grid · knight&knave · coloring · sudoku · scheduling · SAT/UNSAT/…
```

Core guarantees:
- **Deterministic** — same input ⇒ same output; no randomness, no `eval`, no model call.
- **Never guess** — status is one of `SATISFIABLE · UNSATISFIABLE · UNDERCONSTRAINED ·
  MULTIPLE_SOLUTIONS · UNKNOWN`. `UNKNOWN` (resource budget hit) is returned instead of
  hallucinating an answer.
- **No silent assumption** — the verifier fails a constraint whose variables aren't all
  assigned; it never assumes.
- **Proof, not narration** — every SAT answer carries a reproducible proof; every UNSAT
  carries a minimal unsatisfiable set (MUS).
- **Computed confidence** — a function of verified-constraint fraction, proof
  completeness, ambiguity (#solutions), and unresolved/unparsed inputs — not a heuristic.

## Scope & honesty (the hard boundary)

`parser.py` converts a **bounded, documented grammar** (relations, (in)equalities,
ordering, boolean logic) into constraints and **flags anything it cannot parse** — it
never silently drops information (that would be the exact failure we're fixing). Arbitrary
open-domain English is out of scope; the model does the NL→constraint framing and the
engine does the exact reasoning. This is the deterministic-offload contract, not an
NL-understanding claim.

## Alternatives

- Prompt the model to reason more carefully — rejected: non-deterministic, unverifiable,
  the very failure class in Context.
- Depend on an external SMT/SAT solver (z3) — deferred: a heavy dependency; a
  self-contained finite-domain CSP + proof/diagnostics covers the benchmark classes
  (logic grid, knights&knaves, coloring, sudoku, scheduling) with no third-party dep and
  full control over proofs. z3 can back a future numeric/theory extension.

## Consequences

- New isolated package; zero coupling to the God-Object main.py. Later wired as a tool
  (the calculator pattern) behind the kernel PRE_ACT hook.
- Reasoning becomes verifiable: a claim about a constraint problem ships with a proof or
  an honest UNKNOWN.

## Verification (Article XI)

Each module ships unit tests; an integration + benchmark suite exercises SAT, UNSAT,
under-constrained, multiple-solution, contradictory, logic-grid, knights&knaves, graph
coloring, sudoku, and scheduling — asserting the engine detects impossible/ambiguous,
refuses unsupported conclusions, and every produced proof re-verifies. Built and run
incrementally; no benchmark-specific prompt engineering.
