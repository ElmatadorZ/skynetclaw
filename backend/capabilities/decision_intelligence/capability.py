"""
capability.py — DecisionIntelligenceCapability (the facade)
===========================================================
The first-class capability that "sits above reasoning": it composes the ten services into
one auditable, deterministic decision act and enforces the validation gate. This is the
only object callers need.

Pipeline (see docs sequence diagram):
    normalize goals ─▶ generate MULTIPLE candidates ─▶ simulate each over horizons ─▶
    score (weighted utility + penalties) ─▶ Pareto front ─▶ select (pluggable policy) ─▶
    Review Board (counter-example + challenges) ─▶ Validation Gate (CVL + DIF) ─▶ result

Deterministic replay: `decide(request)` with a fixed set of registered plugins yields a
byte-identical `DecisionResult`. Model-free (no LLM anywhere in the path).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import engines  # noqa: F401  (registers built-in plugins on import)
from .contracts import (
    ActionCandidate, Decision, DecisionRequest, Goal, Plan, PlanPatch, ResourceVector,
    ReviewVerdict, SimOutcome, WorldVars,
)
from .registry import snapshot
from .services import (
    GoalManagementService, WorldStateService, ConstraintService, PlanningService,
    SimulationService, UtilityService, DecisionService, ReviewBoardService,
    AdaptationService, LearningService,
)
from .validators import DecisionValidationGate, GateResult


@dataclass
class DecisionResult:
    decision: Decision
    verdict: ReviewVerdict
    gate: GateResult
    accepted: bool
    outcomes: Dict[str, SimOutcome]
    candidates: List[ActionCandidate]
    plugins: Dict[str, str] = field(default_factory=dict)
    trace: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "decision": self.decision.as_dict(),
            "verdict": self.verdict.as_dict(),
            "gate": self.gate.as_dict(),
            "outcomes": {k: v.as_dict() for k, v in sorted(self.outcomes.items())},
            "candidates": [c.as_dict() for c in self.candidates],
            "plugins": self.plugins,
            "trace": self.trace,
        }


class DecisionIntelligenceCapability:
    """Facade. Construct once (optionally with a learning ledger path); call `decide()`."""

    name = "decision_intelligence"

    def __init__(self, learning_ledger: Optional[str] = None):
        self._goals = GoalManagementService()
        self._constraints = ConstraintService()
        self._gate = DecisionValidationGate(self._constraints)
        self._learning = LearningService(ledger_path=learning_ledger)

    # — main entry —
    def decide(self, request: DecisionRequest) -> DecisionResult:
        trace: List[str] = []
        # services that depend on the request's chosen plugins are built per-call so a
        # different planner/utility/simulator/policy is honoured (deterministic replay).
        planning = PlanningService(planner=request.planner)
        simulation = SimulationService(simulator=request.simulator)
        utility = UtilityService(utility=request.utility)
        decision_svc = DecisionService(policy=request.policy)
        review = ReviewBoardService()

        world = dict(request.world)
        goals = self._goals.normalize(request.goals, request.weights)
        trace.append(f"normalized {len(goals)} goal(s)")

        # 1) MULTIPLE candidates (planner contract enforced inside PlanningService)
        candidates = planning.candidates(world, goals, request.available_resources,
                                         seed=request.seed_actions)
        trace.append(f"generated {len(candidates)} candidate action(s)")

        # 2) simulate each over the horizons
        outcomes = simulation.simulate_all(world, candidates, request.horizons)

        # 3) constraint penalties per candidate (projected world at the far horizon)
        penalties: Dict[str, float] = {}
        projected: Dict[str, WorldVars] = {}
        far = max(request.horizons)
        for a in candidates:
            pw = outcomes[a.id].at(far).expected if outcomes[a.id].at(far) else world
            projected[a.id] = pw
            penalties[a.id] = self._constraints.penalty(pw, request.constraints_text)

        # 4) utility + Pareto
        scores = utility.evaluate_all(candidates, outcomes, goals, penalties)
        front = utility.pareto_front(scores)
        trace.append(f"scored candidates; pareto front = {front}")

        # 5) select
        actions = {a.id: a for a in candidates}
        decision = decision_svc.decide(scores, actions, front)
        trace.append(f"selected: {decision.chosen.id if decision.chosen else None}")

        # 6) review board (counter-example + adversarial challenges)
        verdict = review.review(decision, world, goals, outcomes,
                                request.constraints_text, request.confidence_threshold)
        trace.append(f"review: {'accepted' if verdict.accepted else 'rejected'} "
                     f"({len(verdict.challenges)} challenge(s))")

        # 7) validation gate (5 validations; integrates CVL + DIF)
        chosen_pw = projected.get(decision.chosen.id, world) if decision.chosen else world
        gate = self._gate.validate(
            decision=decision, verdict=verdict, projected_world=chosen_pw,
            constraints_text=request.constraints_text,
            confidence_threshold=request.confidence_threshold,
            decision_text=decision.explanation)
        trace.append(f"gate: {'PASS' if gate.ok else 'FAIL'} {gate.checks}")

        accepted = verdict.accepted and gate.ok
        return DecisionResult(decision=decision, verdict=verdict, gate=gate,
                              accepted=accepted, outcomes=outcomes, candidates=candidates,
                              plugins={"planner": request.planner, "utility": request.utility,
                                       "simulator": request.simulator, "policy": request.policy},
                              trace=trace)

    # — adaptive re-planning (minimal patch) —
    def adapt(self, plan: Plan, old_world: WorldVars, new_world: WorldVars,
              goals: List[Goal], resources: ResourceVector,
              planner: str = "default") -> PlanPatch:
        planning = PlanningService(planner=planner)
        adaptation = AdaptationService(planning)
        return adaptation.adapt(plan, old_world, new_world, self._goals.normalize(goals, {}),
                                resources)

    # — learning —
    def record_outcome(self, item: Dict[str, Any]) -> None:
        self._learning.record(item)

    def learn(self, history: Optional[List[Dict[str, Any]]] = None):
        return self._learning.learn(history)

    # — introspection —
    def plugins(self) -> Dict[str, List[str]]:
        return snapshot()
