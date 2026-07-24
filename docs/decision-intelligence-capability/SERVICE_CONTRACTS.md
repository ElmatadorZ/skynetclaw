# Service Contracts — Decision Intelligence Capability

Ten services orchestrate the engines. A service owns engine instance(s), holds config/state,
and is the ONLY way engines communicate (engines never import each other). Services may
call services.

| Service | Owns engine(s) | Contract |
|---|---|---|
| `GoalManagementService` | Goal | `normalize(goals, weights) -> [Goal]`; `attainment(goals, world) -> {goal_id: 0..1}` |
| `WorldStateService` | WorldState | `project(action, days, world?) -> world`; `diff(before, after) -> {var:(old,new)}`; holds current world |
| `ConstraintService` | ConstraintGraph (adapts logic/DIF) | `feasible(world, text) -> bool`; `penalty(world, text) -> float`; `violations(world, text) -> [str]` |
| `PlanningService` | ActionGenerator + Planner | `candidates(world, goals, resources, seed?) -> [ActionCandidate]` (≥1, enforced); `regenerate_step(step, world, goals, resources) -> ActionCandidate` |
| `SimulationService` | OutcomeSimulation | `simulate(world, action, horizons) -> SimOutcome`; `simulate_all(...) -> {action_id: SimOutcome}` |
| `UtilityService` | UtilityEvaluation | `evaluate_all(actions, outcomes, goals, penalties) -> [UtilityScore]`; `pareto_front(scores) -> [action_id]` |
| `DecisionService` | DecisionSelection (+ policy plugin) | `decide(scores, actions, pareto_front) -> Decision` |
| `ReviewBoardService` | DecisionReview + CounterExample | `review(decision, world, goals, outcomes, constraints, threshold) -> ReviewVerdict` |
| `AdaptationService` | AdaptivePlanning (+ PlanningService) | `adapt(plan, old_world, new_world, goals, resources) -> PlanPatch` |
| `LearningService` | Learning (+ optional ledger) | `record(item)`; `learn(history?) -> LearningReport`; `history() -> [item]` |

## Composition rules

- **PlanningService** enforces the planner contract: a planner returning a non-list or
  empty result raises `RuntimeError` — a decision point always has candidates.
- **UtilityService** receives constraint penalties computed by **ConstraintService** (the
  capability wires this) so the utility engine stays pure.
- **ReviewBoardService** is the single place two engines meet: it runs the Counter Example
  engine and feeds the result to the Decision Review engine.
- **AdaptationService** calls **PlanningService** to regenerate only invalidated steps
  (service→service; the adaptive engine never calls another engine).

## State & determinism

Only `WorldStateService` (current world) and `LearningService` (history + optional ledger)
hold mutable state. Everything else is stateless given its inputs. The ledger is the only
side effect and is optional (in-memory by default), so the analysis is a pure function of
history — replayable.
