"""
services/planning_service.py — PlanningService
==============================================
Owns the Action Generator + Planner engines (both pluggable via the registry). Produces
the MULTIPLE candidate actions the decision layer weighs — never a single action. Also
exposes single-step regeneration used by the Adaptation service.
"""
from __future__ import annotations

from typing import List, Optional

from ..contracts import ActionCandidate, Goal, ResourceVector, WorldVars
from ..registry import PLANNERS, ACTION_GENERATORS


class PlanningService:
    def __init__(self, planner: str = "default", action_generator: str = "default"):
        self._planner = PLANNERS.create(planner)
        self._generator = ACTION_GENERATORS.create(action_generator)

    def candidates(self, world: WorldVars, goals: List[Goal], resources: ResourceVector,
                   seed: Optional[List[ActionCandidate]] = None) -> List[ActionCandidate]:
        pool = self._generator.candidates(world, goals, resources, seed)
        plan = self._planner.generate(world, goals, resources, pool)
        # HARD invariant (ADR-0012): the planner must return a non-empty LIST.
        if not isinstance(plan, list) or not plan:
            raise RuntimeError("planner violated contract: must return >=1 candidate action")
        return plan

    def regenerate_step(self, step: ActionCandidate, world: WorldVars,
                        goals: List[Goal], resources: ResourceVector) -> ActionCandidate:
        """Re-derive one step for adaptive re-planning. Deterministic: pick the highest-
        confidence feasible candidate that still serves the step's variables, else keep it."""
        cands = self.candidates(world, goals, resources, seed=[step])
        step_vars = set(step.effect_map())
        serving = [c for c in cands if set(c.effect_map()) & step_vars] or cands
        return max(serving, key=lambda c: (c.estimated_confidence, c.id))
