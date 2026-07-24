"""
engines/goal_engine.py — Goal Engine
====================================
Single responsibility: normalise goals (apply weight overrides, validate directions) and
measure a goal's ATTAINMENT (0..1) given a world state. No planning, no utility — just the
goal↔world relationship. Pure and deterministic.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List

from ..contracts import Goal, GoalDirection, WorldVars


class DefaultGoalEngine:
    name = "default"

    def normalize(self, goals: List[Goal], weights: Dict[str, float]) -> List[Goal]:
        out: List[Goal] = []
        for g in goals:
            w = float(weights.get(g.id, g.weight))
            out.append(replace(g, weight=max(0.0, w)))
        # deterministic order: by id
        return sorted(out, key=lambda g: g.id)

    def progress(self, goal: Goal, world: WorldVars) -> float:
        """Attainment in [0,1]. TARGET goals peak at the target and fall off with distance;
        MAX/MIN goals are normalised by a soft logistic so unbounded variables still map to
        [0,1] deterministically."""
        val = _num(world.get(goal.variable))
        if val is None:
            return 0.0
        if goal.direction == GoalDirection.TARGET and goal.target_value is not None:
            dist = abs(val - goal.target_value)
            if dist <= goal.tolerance:
                return 1.0
            span = abs(goal.target_value) if goal.target_value else 1.0
            return max(0.0, 1.0 - dist / (span + 1e-9))
        if goal.direction == GoalDirection.MINIMIZE:
            return _logistic(-val)
        return _logistic(val)   # MAXIMIZE


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _logistic(x: float) -> float:
    # smooth, bounded, deterministic; scaled so ~[-10,10] spans most of (0,1)
    import math
    return 1.0 / (1.0 + math.exp(-x / 5.0))
