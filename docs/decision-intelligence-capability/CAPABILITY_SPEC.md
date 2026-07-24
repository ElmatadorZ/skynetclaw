# Capability Specification — Decision Intelligence

**Capability id:** `decision_intelligence` · **Layer:** above reasoning · **ADR:** [0012](../adr/ADR-0012-decision-intelligence-capability.md)

## Purpose

Transform reasoning into **verifiable, adaptive, resource-aware decision-making**: hold
goals, model world state, generate *multiple* resource-aware plans, simulate their
outcomes over time, weigh them by configurable objectives, choose and explain, have the
choice adversarially reviewed, adapt to world changes with minimal re-planning, and learn
from outcomes.

## Public surface

```python
from capabilities.decision_intelligence import (
    DecisionIntelligenceCapability, DecisionRequest, Goal, GoalDirection,
    ResourceVector, ActionCandidate)

cap = DecisionIntelligenceCapability(learning_ledger=None)
result = cap.decide(DecisionRequest(...))            # → DecisionResult
patch  = cap.adapt(plan, old_world, new_world, goals, resources)   # → PlanPatch
cap.record_outcome({...}); report = cap.learn()      # → LearningReport
cap.plugins()                                        # registered planners/utilities/...
```

## Guarantees (acceptance criteria)

| Criterion | How it is met | Test |
|---|---|---|
| Operates independently of any LLM | model-free; no LLM/HTTP import in the package graph | `test_dic_integration::t_llm_independence_and_reuse` |
| Deterministic replay | no RNG/wall-clock/`eval`; sorted iteration | `test_dic_integration::t_deterministic_replay`, `test_dic_stress` |
| Multiple planners | `registry.PLANNERS` (`default`, `conservative`) | `test_dic_integration::t_multiple_plugins` |
| Multiple utility functions | `registry.UTILITIES` (`weighted`, `risk_averse`) | same |
| Multiple simulators | `registry.SIMULATORS` (`trend`, `damped`) | `test_dic_simulation::t_multiple_simulators` |
| Plugin decision policies | `registry.POLICIES` (+ custom register) | `test_dic_integration::t_plugin_policy_override` |
| Future reinforcement learning | policy plugins + Learning ledger | `learning_service` + `POLICIES` |
| Backward compatibility | reused subsystems untouched; suites green | `test_logic`, `test_di_*`, `test_decision` |
| Never duplicate reasoning | Counter-example reuses DIF; Constraint reuses logic; Gate reuses CVL | `t_llm_independence_and_reuse` |

## Hard behavioral rules

1. **Planner never returns one action** — `PlanningService.candidates` raises if a planner
   returns an empty/singleton-non-list; the action generator always includes a `noop`
   baseline so ≥2 candidates exist.
2. **Never hardcode priorities** — every goal's importance is its configurable `weight`
   (overridable per-request via `DecisionRequest.weights`).
3. **Reject invalid plans** — infeasible candidates (constraint penalty > 0) are marked
   and cannot be accepted by the Validation Gate.
4. **Refuse weak decisions** — the Review Board rejects on low confidence, a verified
   counter-example, or uncertainty that dwarfs the signal.
5. **Adapt, don't re-plan** — a world change patches only the affected plan steps.

## Inputs / outputs

- **`DecisionRequest`** — world vars, goals, resources, horizons, weight overrides, plugin
  names (planner/utility/simulator/policy), confidence threshold, constraints text, seed
  actions.
- **`DecisionResult`** — `decision` (chosen/ranked/rejected/pareto/explanation), `verdict`
  (review), `gate` (5 validations), `accepted`, `outcomes` (per-action multi-horizon sim),
  `candidates`, `plugins`, `trace`. Fully `as_dict()`-serialisable for audit/replay.

## Non-goals (honest limits)

- Not a learned world model — the default simulator is a transparent trend/decay model
  (pluggable; a learned simulator can replace it behind `SimulatorEngine`).
- Not wired into the RC-1 agent runtime (Epic Trust freeze) — `decide()` API + tool schema
  are ready; registration is a deliberate follow-up.
