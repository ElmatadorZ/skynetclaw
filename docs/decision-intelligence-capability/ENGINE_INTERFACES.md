# Engine Interfaces — Decision Intelligence Capability

Twelve engines, each a **single responsibility**, each a **stable Protocol** in
`engines/interfaces.py`. Services depend on the Protocols, not the concretes — so any
engine can be swapped for a plugin (Open-Closed). **No engine imports another engine**;
each imports only `contracts`, `interfaces`, and reused substrate (`logic/`, DIF, CVL).

| Engine | Protocol | Signature (essentials) | Reuses |
|---|---|---|---|
| Goal | `GoalEngine` | `normalize(goals, weights) -> [Goal]`; `progress(goal, world) -> 0..1` | — |
| World State | `WorldStateEngine` | `apply(world, action, days) -> world`; `diff(before, after) -> {var:(old,new)}` | — |
| Constraint Graph | `ConstraintEngine` | `feasible/penalty/violations(world, text)` | `logic/` (+ DIF for models) |
| Action Generator | `ActionGeneratorEngine` | `candidates(world, goals, resources, seed?) -> [ActionCandidate]` | — |
| Planner | `PlannerEngine` | `generate(world, goals, resources, candidates) -> [ActionCandidate]` **(list, never one)** | — |
| Outcome Simulation | `SimulatorEngine` | `simulate(world, action, horizons) -> SimOutcome` (expected/low/high per horizon) | — |
| Utility Evaluation | `UtilityEngine` | `evaluate(action, outcome, goals, penalty, feasible) -> UtilityScore`; `pareto_front(scores) -> [id]` | — |
| Decision Selection | `DecisionEngine` | `select(scores, actions, pareto_front) -> Decision` (rank·reject·choose·explain) | policy plugin |
| Decision Review | `ReviewEngine` | `review(decision, world, goals, outcomes, constraints, threshold, counterexample?) -> ReviewVerdict` | — |
| Counter Example | `CounterExampleEngine` | `find(world, constraints_text, goals) -> dict | None` | **DIF** (`decision_intelligence`) |
| Adaptive Planning | `AdaptiveEngine` | `patch(plan, old_world, new_world, regenerate) -> PlanPatch` | — |
| Learning | `LearningEngine` | `learn(history) -> LearningReport` | — |

## Built-in implementations (pluggable)

| Family | Registry | Built-ins |
|---|---|---|
| Planner | `PLANNERS` | `default` (resource+dependency filter), `conservative` (+ confidence floor) |
| Utility | `UTILITIES` | `weighted` (Σ weightₒ·progressₒ − penalty), `risk_averse` (× confidence) |
| Simulator | `SIMULATORS` | `trend` (linear), `damped` (diminishing returns) |
| Policy | `POLICIES` | `max_utility`, `pareto_then_utility` |
| Action generator | `ACTION_GENERATORS` | `default` |

## Adding a plugin (example: an RL policy)

```python
from capabilities.decision_intelligence.registry import POLICIES

def rl_policy(scores, pareto_front):
    # scores: List[UtilityScore]; return chosen action_id (or None)
    return max((s for s in scores if s.feasible), key=lambda s: q_value(s), default=None) and ...

POLICIES.register("rl", lambda: rl_policy)
# then: DecisionRequest(..., policy="rl")
```

No service or engine changes — the registry + stable Protocol are the only contract.

## Determinism requirements for engine authors

- No RNG, no wall-clock, no `eval`, no network in the decision path.
- Iterate over sorted keys; break ties deterministically (by id).
- Pure functions of inputs (except `WorldStateService`/`LearningService` state).
