# Decision Intelligence Framework — Architecture

> Companion to [ADR-0011](../adr/ADR-0011-decision-intelligence-framework.md).
> DIF is a **service layer** over the Cognitive Logic Engine ([ADR-0008](../adr/ADR-0008-cognitive-logic-engine.md),
> `backend/logic/`). One CSP core; DIF adds auditability, active invalidation,
> evidence-based confidence, and a process score.

## Layering

```
                        ┌─────────────────────────────────────────────┐
   problem (NL/formal)  │  decision_intelligence/  (DIF — this ADR)    │
        │               │                                             │
        ▼               │  constraint_analyzer   Phase 1  (guarded)   │
  ┌───────────┐         │        │  AnalysisModel                      │
  │  analyze  │────────▶│  decision_engine       Phase 2 + self-check │
  └───────────┘         │        │                                     │
                        │        ├─▶ counter_example   Phase 3         │
                        │        ├─▶ decision_verifier  Phase 4        │
                        │        ├─▶ confidence_engine  Phase 5        │
                        │        └─▶ decision_score     Phase 6        │
                        │             │  DecisionReport → render_report │
                        └─────────────┼───────────────────────────────┘
                                      │ reuses (never re-implements)
                        ┌─────────────▼───────────────────────────────┐
                        │  logic/  (Cognitive Logic Engine — ADR-0008) │
                        │  constraint_graph · solver (5-way status) ·  │
                        │  verifier · proof · diagnostics (MUS)        │
                        └──────────────────────────────────────────────┘
```

## Data flow (one decision)

```
analyze ─▶ AnalysisModel ─▶ model.graph() ─▶ logic.solve ─▶ status
   │                                                          │
   │                                        ┌── SATISFIABLE ──┤── candidate = solutions[0]
   │                                        │      self-check: verify candidate;
   │                                        │      counter_example.search(goal-differing?)
   │                                        │        found+verified ─▶ reclassify MULTIPLE/UNDER
   │                                        │        none          ─▶ assert answer
   │                                        ├── UNSAT ── minimal_conflict ─▶ contradiction?
   │                                        ├── MULTIPLE/UNDER ── refuse unique (or upgrade if
   │                                        │                     the goal is constant across all)
   │                                        └── UNKNOWN ── refuse (budget/ill-formed)
   ▼
confidence_engine.assess(evidence) ─▶ decision_score.score(telemetry) ─▶ DecisionReport
```

## Module interfaces

```python
# constraint_analyzer.py  — Phase 1
analyze(problem="", *, model=None, graph=None, goals=None, unknowns=None,
        assumptions=None, missing_information=None, facts=None, llm=None) -> AnalysisModel
validate_model(model) -> list[str]                 # structural issues; [] == well-formed
AnalysisModel.graph() -> logic.ConstraintGraph      # hard constraints + flagged assumptions

# decision_engine.py  — Phase 2 + self-check + report
decide(problem="", *, model|graph|..., llm=None, max_selfcheck=8) -> DecisionReport
render_report(DecisionReport) -> str                # the OUTPUT FORMAT
class Classification(Enum): SATISFIABLE | UNSATISFIABLE | UNDERCONSTRAINED
                          | MULTIPLE_SOLUTIONS | UNKNOWN

# counter_example.py  — Phase 3
search_counter_example(model, candidate, goals=None) -> CounterExample   # active invalidation
invalidates_unique(CounterExample) -> bool          # found AND verified

# decision_verifier.py  — Phase 4
verify_decision(model, assignment) -> DecisionVerification   # per-constraint + assumption audit

# confidence_engine.py  — Phase 5
assess_confidence(*, classification, verification, counter_example, exhaustive,
                  proof_verified, grounded_facts, missing_information,
                  distinct_answer_count=1) -> ConfidenceReport

# decision_score.py  — Phase 6
score_decision(Telemetry) -> DecisionScore          # deterministic /100
```

## Guarantees & boundaries

- **Determinism** — for a fixed `AnalysisModel`, the whole pipeline is reproducible
  (the solver sorts variables/values; no `eval`; no randomness). Verified by
  `test_di_*` determinism checks.
- **No fabrication** — the only NL entry point is `constraint_analyzer`; any extracted
  fact whose cited span is absent from the source is demoted to a flagged assumption or
  to `missing_information`. It never becomes a hard constraint silently.
- **Refusal** — ill-formed/unsolvable framings and budget-exhausted searches return
  `UNKNOWN` with `answer_confidence == 0`. Multiple valid answers are never collapsed
  into one.
- **CONTRADICTION** is a diagnosis on `UNSATISFIABLE` (variable forced to two constants,
  or `Eq`/`Ne` on the same pair) — separate from capacity impossibility (pigeonhole).

## Tests

| File | Covers |
|---|---|
| `backend/tests/test_di_framework.py` | analyzer guard, verifier, counter-example, confidence gates, score rubric, engine classification, self-check, determinism |
| `backend/tests/test_di_benchmark.py` | logic grid, scheduling, CSP colouring, knight-and-knave, salary, graph, impossible, contradictory, underconstrained, multiple-valid, determinism |

Run: `python backend/tests/test_di_framework.py && python backend/tests/test_di_benchmark.py`
(or `python -m pytest backend/tests/test_di_*.py`).

## Not in scope (honest limits)

- Open-domain NL reasoning — DIF reasons over **finite-domain** models; prose must be
  framed into variables/constraints (guarded).
- Runtime wiring — DIF is **not** registered in `BUILTIN_TOOLS` yet (Epic Trust freeze).
  A `decide` tool schema + `decide()` API are ready; wiring is a deliberate follow-up.
