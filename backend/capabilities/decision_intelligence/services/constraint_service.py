"""
services/constraint_service.py — ConstraintService
==================================================
Owns the Constraint Graph Engine (a thin adapter over logic/DIF). Answers feasibility,
graded penalty, and violation lists for a world state against DSL/logical constraints.
"""
from __future__ import annotations

from typing import List

from ..contracts import WorldVars
from ..engines.constraint_graph_engine import DefaultConstraintEngine


class ConstraintService:
    def __init__(self, engine=None):
        self._engine = engine or DefaultConstraintEngine()

    def feasible(self, world: WorldVars, text: str) -> bool:
        return self._engine.feasible(world, text)

    def penalty(self, world: WorldVars, text: str) -> float:
        return self._engine.penalty(world, text)

    def violations(self, world: WorldVars, text: str) -> List[str]:
        return self._engine.violations(world, text)
