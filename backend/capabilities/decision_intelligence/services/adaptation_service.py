"""
services/adaptation_service.py — AdaptationService
==================================================
Owns the Adaptive Planning Engine. When the world changes, it patches an existing plan
minimally — reusing the PlanningService (service→service) to regenerate only the steps the
change invalidated, never re-planning from scratch.
"""
from __future__ import annotations

from typing import List

from ..contracts import Goal, Plan, PlanPatch, ResourceVector, WorldVars
from ..engines.adaptive_planning_engine import AdaptivePlanningEngine
from .planning_service import PlanningService


class AdaptationService:
    def __init__(self, planning_service: PlanningService, engine=None):
        self._planning = planning_service
        self._engine = engine or AdaptivePlanningEngine()

    def adapt(self, plan: Plan, old_world: WorldVars, new_world: WorldVars,
              goals: List[Goal], resources: ResourceVector) -> PlanPatch:
        def regenerate(step, world):
            return self._planning.regenerate_step(step, world, goals, resources)
        return self._engine.patch(plan, old_world, new_world, regenerate)
