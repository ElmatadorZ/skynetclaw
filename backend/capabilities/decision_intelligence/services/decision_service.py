"""
services/decision_service.py — DecisionService
==============================================
Owns the Decision Selection Engine with a pluggable policy (RL-ready). Ranks, compares,
rejects invalid candidates, chooses the best, and returns a Decision with an explanation.
"""
from __future__ import annotations

from typing import Dict, List

from ..contracts import ActionCandidate, Decision, UtilityScore
from ..engines.decision_selection_engine import DecisionSelectionEngine
from ..registry import POLICIES


class DecisionService:
    def __init__(self, policy: str = "max_utility"):
        policy_fn = POLICIES.create(policy)
        self._engine = DecisionSelectionEngine(policy=policy_fn, policy_name=policy)

    def decide(self, scores: List[UtilityScore], actions: Dict[str, ActionCandidate],
               pareto_front: List[str]) -> Decision:
        return self._engine.select(scores, actions, pareto_front)
