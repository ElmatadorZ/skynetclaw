"""
services/goal_management_service.py — GoalManagementService
===========================================================
Owns the Goal Engine; provides goal normalisation and attainment queries to the rest of
the capability. Services orchestrate engines; engines never talk to each other.
"""
from __future__ import annotations

from typing import Dict, List

from ..contracts import Goal, WorldVars
from ..engines.goal_engine import DefaultGoalEngine


class GoalManagementService:
    def __init__(self, engine=None):
        self._engine = engine or DefaultGoalEngine()

    def normalize(self, goals: List[Goal], weights: Dict[str, float]) -> List[Goal]:
        return self._engine.normalize(goals, weights or {})

    def attainment(self, goals: List[Goal], world: WorldVars) -> Dict[str, float]:
        return {g.id: self._engine.progress(g, world) for g in goals}
