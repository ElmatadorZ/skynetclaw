"""
engines/utility_evaluation_engine.py — Utility Evaluation Engine
================================================================
Single responsibility: score an action's simulated outcome against the goals. NEVER uses
hardcoded priorities — every goal's importance is its configurable `weight`. Supports:
  · configurable weighted objectives (scalarisation = Σ weight_g · progress_g);
  · constraint penalties (subtracted, weighted);
  · Pareto comparison (dominance over the per-goal objective vector).

A second built-in (RiskAverseUtilityEngine) folds an action's confidence into the score to
show multiple utility functions are supported. Pure and deterministic.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import math
from typing import Dict, List

from ..contracts import ActionCandidate, Goal, GoalDirection, SimOutcome, UtilityScore

_PENALTY_WEIGHT = 1.0


class WeightedUtilityEngine:
    name = "weighted"
    risk_averse = False

    def evaluate(self, action: ActionCandidate, outcome: SimOutcome, goals: List[Goal],
                 constraint_penalty: float, feasible: bool) -> UtilityScore:
        # evaluate at the LONGEST horizon (the decision's planning horizon)
        pred = outcome.predictions[-1] if outcome.predictions else None
        world = pred.expected if pred else {}
        obj: Dict[str, float] = {}
        for g in goals:
            obj[g.id] = g.weight * _progress(g, world)
        scalar = sum(obj.values()) - _PENALTY_WEIGHT * constraint_penalty
        if self.risk_averse:
            scalar *= (0.5 + 0.5 * max(0.0, min(1.0, action.estimated_confidence)))
        return UtilityScore(
            action_id=action.id, scalar=scalar,
            objective_scores=tuple(sorted(obj.items())),
            constraint_penalty=constraint_penalty, feasible=feasible)

    def pareto_front(self, scores: List[UtilityScore]) -> List[str]:
        """Non-dominated set over the per-goal objective vectors (higher is better on every
        objective). Deterministic; ties keep both."""
        front: List[str] = []
        for s in scores:
            dominated = False
            for t in scores:
                if t.action_id == s.action_id:
                    continue
                if _dominates(t, s):
                    dominated = True
                    break
            if not dominated:
                front.append(s.action_id)
        return sorted(set(front))


class RiskAverseUtilityEngine(WeightedUtilityEngine):
    name = "risk_averse"
    risk_averse = True


def _progress(goal: Goal, world: Dict[str, float]) -> float:
    val = world.get(goal.variable)
    if val is None:
        return 0.0
    val = float(val)
    if goal.direction == GoalDirection.TARGET and goal.target_value is not None:
        dist = abs(val - goal.target_value)
        span = abs(goal.target_value) if goal.target_value else 1.0
        return max(0.0, 1.0 - dist / (span + 1e-9))
    if goal.direction == GoalDirection.MINIMIZE:
        return 1.0 / (1.0 + math.exp(val / 5.0))
    return 1.0 / (1.0 + math.exp(-val / 5.0))


def _dominates(a: UtilityScore, b: UtilityScore) -> bool:
    """a dominates b: a ≥ b on every objective and > on at least one."""
    am, bm = a.objective_map(), b.objective_map()
    keys = set(am) | set(bm)
    ge_all = all(am.get(k, 0.0) >= bm.get(k, 0.0) - 1e-12 for k in keys)
    gt_any = any(am.get(k, 0.0) > bm.get(k, 0.0) + 1e-12 for k in keys)
    return ge_all and gt_any
