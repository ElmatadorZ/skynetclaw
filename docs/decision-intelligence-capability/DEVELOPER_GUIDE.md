# Developer Guide — Decision Intelligence Capability

## Install / import

The capability is a package under `backend/`. With `backend/` on `sys.path` (the House's
convention):

```python
from capabilities.decision_intelligence import (
    DecisionIntelligenceCapability, DecisionRequest, Goal, GoalDirection,
    ResourceVector, ActionCandidate)
```

## Make a decision

```python
cap = DecisionIntelligenceCapability()

req = DecisionRequest(
    world={"revenue": 100.0, "cost": 50.0},
    goals=[
        Goal("grow", "revenue", GoalDirection.MAXIMIZE, weight=3.0),
        Goal("lean", "cost",    GoalDirection.MINIMIZE, weight=1.0),
    ],
    available_resources=ResourceVector.of({"budget": 100.0, "effort": 10.0}),
    seed_actions=[
        ActionCandidate(
            id="ads", description="Paid ads",
            effects=(("revenue", 4.0), ("cost", 2.0)),     # per-day deltas
            expected_benefits=("fast growth",),
            expected_costs=("ad spend",),
            required_resources=ResourceVector.of({"budget": 60, "effort": 3}),
            risks=("CAC may rise",),
            dependencies=(),
            estimated_confidence=0.65),
        ActionCandidate(
            id="seo", description="Organic SEO",
            effects=(("revenue", 1.5),),
            required_resources=ResourceVector.of({"effort": 4}),
            estimated_confidence=0.8),
    ],
    constraints_text="cost <= 200",     # numeric DSL; logic DSL also supported
    horizons=(5, 10, 20, 30),
    planner="default", utility="weighted", simulator="trend", policy="max_utility",
    confidence_threshold=0.35,
)

result = cap.decide(req)
print(result.accepted)                       # bool: verdict.ok AND gate.ok
print(result.decision.chosen.id)             # chosen action
print(result.decision.explanation)           # why
print(result.decision.pareto_front)          # non-dominated actions
print(result.gate.checks)                    # 5 validations
import json; print(json.dumps(result.as_dict(), indent=2, default=str))   # full audit
```

## Constraints

- **Numeric DSL** (checked by the Constraint engine, feeds utility penalties + the gate):
  `var <= n`, `>=`, `<`, `>`, `==`, `!=`, one per line/`;`.
- **Logic DSL** (routed to DIF/`logic/` by the Counter Example engine for real
  counter-example search): `a is b`, `a is not b`, `a < b`, `a is <value>`.

## Adapt to a changing world (minimal patch)

```python
from capabilities.decision_intelligence.contracts import Plan
patch = cap.adapt(Plan("launch", (stepA, stepB)),
                  old_world={"supply": 10.0, "demand": 5.0},
                  new_world={"supply": 3.0,  "demand": 5.0},   # supply shock
                  goals=[Goal("g", "supply")],
                  resources=ResourceVector.of({"effort": 5}))
print(patch.changed_steps, patch.kept_steps, patch.reason)     # only supply step changes
```

## Learn from a mission

```python
cap.record_outcome({"action_id": "ads", "accepted": True,
                    "predicted": 20, "actual": 22, "confidence": 0.65, "policy": "max_utility"})
report = cap.learn()
print(report.successful_patterns, report.failed_patterns,
      report.tradeoff_analysis, report.policy_improvements)
```

Persist the ledger by constructing `DecisionIntelligenceCapability(learning_ledger="…jsonl")`.

## Write a plugin

Implement the relevant Protocol from `engines/interfaces.py`, then register a factory:

```python
from capabilities.decision_intelligence.registry import SIMULATORS

class MyMonteCarloSim:            # must satisfy SimulatorEngine
    name = "montecarlo"
    def simulate(self, world, action, horizons): ...   # return SimOutcome (deterministic!)

SIMULATORS.register("montecarlo", MyMonteCarloSim)
# use it: DecisionRequest(..., simulator="montecarlo")
```

The same pattern applies to `PLANNERS`, `UTILITIES`, `POLICIES`, `ACTION_GENERATORS`.
Keep plugins deterministic (no RNG/wall-clock) to preserve replay.

## Testing

```
python backend/tests/test_dic_unit.py
python backend/tests/test_dic_integration.py
python backend/tests/test_dic_scenario.py
python backend/tests/test_dic_simulation.py
python backend/tests/test_dic_stress.py
# or: python -m pytest backend/tests/test_dic_*.py -q
```

## Design rules to keep

- Engines are pure and single-responsibility; **an engine never imports another engine**.
- Communication between engines happens **through services**.
- **Reuse** `logic/` / DIF / CVL — never re-implement solving, verification, or validation.
- Everything on the decision path stays **model-free and deterministic**.
