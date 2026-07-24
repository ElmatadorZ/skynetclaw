"""
engines/interfaces.py — stable Engine interfaces (Protocols)
============================================================
Every engine exposes a stable, minimal Protocol. Services depend on these Protocols, not
on concrete engines — so a planner/utility/simulator/policy can be swapped for a plugin
without touching any service (Open-Closed, Article IX). Engines NEVER import each other;
they import only `contracts` and this module.

The Protocols also encode the mission's hard rules structurally:
  · PlannerEngine.generate → List[ActionCandidate]  (a LIST — never a single action)
  · SimulatorEngine.simulate → SimOutcome with predictions at every requested horizon

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from ..contracts import (
    ActionCandidate, Decision, Goal, HorizonPrediction, Lesson, LearningReport,
    Plan, PlanPatch, ResourceVector, ReviewVerdict, SimOutcome, UtilityScore, WorldVars,
)


@runtime_checkable
class GoalEngine(Protocol):
    name: str
    def normalize(self, goals: List[Goal], weights: Dict[str, float]) -> List[Goal]: ...
    def progress(self, goal: Goal, world: WorldVars) -> float: ...     # 0..1 attainment


@runtime_checkable
class WorldStateEngine(Protocol):
    name: str
    def apply(self, world: WorldVars, action: ActionCandidate, days: int) -> WorldVars: ...
    def diff(self, before: WorldVars, after: WorldVars) -> Dict[str, Tuple[Any, Any]]: ...


@runtime_checkable
class ConstraintEngine(Protocol):
    name: str
    def feasible(self, world: WorldVars, text: str) -> bool: ...
    def penalty(self, world: WorldVars, text: str) -> float: ...
    def violations(self, world: WorldVars, text: str) -> List[str]: ...


@runtime_checkable
class ActionGeneratorEngine(Protocol):
    name: str
    def candidates(self, world: WorldVars, goals: List[Goal],
                   resources: ResourceVector,
                   seed: Optional[List[ActionCandidate]] = None) -> List[ActionCandidate]: ...


@runtime_checkable
class PlannerEngine(Protocol):
    name: str
    # HARD RULE: returns a LIST of candidates (>=1), never a single action.
    def generate(self, world: WorldVars, goals: List[Goal], resources: ResourceVector,
                 candidates: List[ActionCandidate]) -> List[ActionCandidate]: ...


@runtime_checkable
class SimulatorEngine(Protocol):
    name: str
    def simulate(self, world: WorldVars, action: ActionCandidate,
                 horizons: Tuple[int, ...]) -> SimOutcome: ...


@runtime_checkable
class UtilityEngine(Protocol):
    name: str
    def evaluate(self, action: ActionCandidate, outcome: SimOutcome, goals: List[Goal],
                 constraint_penalty: float, feasible: bool) -> UtilityScore: ...
    def pareto_front(self, scores: List[UtilityScore]) -> List[str]: ...


@runtime_checkable
class DecisionEngine(Protocol):
    name: str
    def select(self, scores: List[UtilityScore],
               actions: Dict[str, ActionCandidate],
               pareto_front: List[str]) -> Decision: ...


@runtime_checkable
class ReviewEngine(Protocol):
    name: str
    def review(self, decision: Decision, world: WorldVars, goals: List[Goal],
               outcomes: Dict[str, SimOutcome], constraints_text: str,
               confidence_threshold: float) -> ReviewVerdict: ...


@runtime_checkable
class CounterExampleEngine(Protocol):
    name: str
    def find(self, world: WorldVars, constraints_text: str,
             goals: List[Goal]) -> Optional[Dict[str, Any]]: ...


@runtime_checkable
class AdaptiveEngine(Protocol):
    name: str
    def patch(self, plan: Plan, old_world: WorldVars, new_world: WorldVars,
              regenerate) -> PlanPatch: ...


@runtime_checkable
class LearningEngine(Protocol):
    name: str
    def learn(self, history: List[Dict[str, Any]]) -> LearningReport: ...
