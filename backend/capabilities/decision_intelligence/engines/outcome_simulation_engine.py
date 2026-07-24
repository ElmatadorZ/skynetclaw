"""
engines/outcome_simulation_engine.py — Outcome Simulation Engine
================================================================
Single responsibility: predict an action's outcome over time. Given (world, action), it
projects the world state at each requested horizon (default 5/10/20/30 days) WITH
uncertainty bounds. Deterministic — uncertainty is a closed-form function of the horizon
and the action's confidence, NOT sampling — so replay is exact.

Model (transparent, pluggable):
  expected(h) = world + effect_per_day * h                      (linear trend)
  spread(h)   = |effect_per_day| * h * (1 - confidence) * k     (widens with horizon)
  low/high    = expected ∓ spread
A second built-in simulator (DampedSimulatorEngine) applies diminishing returns to show
the interface supports multiple simulators.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Dict, Tuple

from ..contracts import ActionCandidate, HorizonPrediction, SimOutcome, WorldVars

_K = 0.5   # uncertainty scale


class TrendSimulatorEngine:
    name = "trend"

    def simulate(self, world: WorldVars, action: ActionCandidate,
                 horizons: Tuple[int, ...]) -> SimOutcome:
        eff = action.effect_map()
        conf = max(0.0, min(1.0, action.estimated_confidence))
        preds = []
        for h in sorted(set(horizons)):
            expected: Dict[str, float] = {}
            low: Dict[str, float] = {}
            high: Dict[str, float] = {}
            for var in sorted(set(world) | set(eff)):
                base = _num(world.get(var, 0.0)) or 0.0
                per_day = eff.get(var, 0.0)
                exp = base + self._project(per_day, h)
                spread = abs(per_day) * h * (1.0 - conf) * _K
                expected[var] = exp
                low[var] = exp - spread
                high[var] = exp + spread
            preds.append(HorizonPrediction(h, expected, low, high))
        return SimOutcome(action_id=action.id, predictions=tuple(preds))

    def _project(self, per_day: float, h: int) -> float:
        return per_day * h


class DampedSimulatorEngine(TrendSimulatorEngine):
    """Diminishing-returns simulator: later days contribute less. Same interface."""
    name = "damped"

    def _project(self, per_day: float, h: int) -> float:
        # sum_{d=1..h} per_day * damp^(d-1)  (closed form, deterministic)
        damp = 0.9
        if damp == 1.0:
            return per_day * h
        return per_day * (1 - damp ** h) / (1 - damp)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
