"""
services/utility_service.py — UtilityService
============================================
Owns the Utility Evaluation Engine (pluggable). Scores every action against weighted goals
with constraint penalties, and computes the Pareto front. Priorities are never hardcoded —
they arrive as goal weights. Constraint penalties are computed by the ConstraintService and
passed in (services orchestrate; the utility engine stays pure).
"""
from __future__ import annotations

from typing import Dict, List

from ..contracts import ActionCandidate, Goal, SimOutcome, UtilityScore
from ..registry import UTILITIES


class UtilityService:
    def __init__(self, utility: str = "weighted"):
        self._engine = UTILITIES.create(utility)

    def evaluate_all(self, actions: List[ActionCandidate], outcomes: Dict[str, SimOutcome],
                     goals: List[Goal], penalties: Dict[str, float]) -> List[UtilityScore]:
        scores: List[UtilityScore] = []
        for a in actions:
            pen = float(penalties.get(a.id, 0.0))
            scores.append(self._engine.evaluate(
                a, outcomes[a.id], goals, constraint_penalty=pen, feasible=(pen <= 1e-9)))
        return scores

    def pareto_front(self, scores: List[UtilityScore]) -> List[str]:
        return self._engine.pareto_front(scores)
