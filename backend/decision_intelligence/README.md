# decision_intelligence — Decision Intelligence Framework (DIF)

Auditable, deterministic decision-making layered over the Cognitive Logic Engine
(`backend/logic/`). Every decision distinguishes **correct / impossible /
underconstrained / multiple-valid / contradiction / unknown** and ships a full audit.

- Design: [ADR-0011](../../docs/adr/ADR-0011-decision-intelligence-framework.md)
- Architecture + interfaces: [docs/decision-intelligence/ARCHITECTURE.md](../../docs/decision-intelligence/ARCHITECTURE.md)

## Quick start

```python
import decision_intelligence as DI
from logic import ConstraintGraph, Eq, Ne

# Formal model (deterministic): x=2, x≠y, y≠3 over {1,2,3}; find y.
g = ConstraintGraph()
g.add_var("x", [1, 2, 3]).add_var("y", [1, 2, 3])
g.add(Eq("x", value=2)).add(Ne("x", b="y")).add(Ne("y", value=3))

report = DI.decide(graph=g, goals=["y"])
print(report.classification.value)   # SATISFIABLE
print(report.answer)                 # {'y': 1}
print(DI.render_report(report))      # full audit (OUTPUT FORMAT)
```

Guarded extraction from prose needs an `llm` callable returning the JSON schema in
`constraint_analyzer.extraction_prompt`; ungrounded statements are flagged, never
admitted as facts:

```python
report = DI.decide(problem="…", llm=my_llm)   # facts must cite verbatim source spans
```

## The six phases

| Module | Phase | Responsibility |
|---|---|---|
| `constraint_analyzer.py` | 1 | NL/formal → `AnalysisModel` (never invents facts) |
| `decision_engine.py` | 2 + self-check | classify, prove-the-answer-wrong loop, render report |
| `counter_example.py` | 3 | active invalidation — search a goal-differing verified solution |
| `decision_verifier.py` | 4 | PASS/FAIL for every constraint + assumption |
| `confidence_engine.py` | 5 | confidence from 5 evidence components + gates |
| `decision_score.py` | 6 | deterministic /100 auditability rubric |

## Design rules

- **Reuse, don't duplicate** — solving/verification/proof come from `logic/`. DIF adds
  only the decision-layer concerns.
- **Determinism** — fixed model ⇒ identical report. No `eval`, no randomness.
- **Honesty** — refuse (`UNKNOWN`, confidence 0) rather than guess; never force one
  answer when several valid ones exist.

## Tests

```
python backend/tests/test_di_framework.py     # unit + integration
python backend/tests/test_di_benchmark.py      # the 9 problem families
```
