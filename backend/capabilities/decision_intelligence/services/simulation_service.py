"""
services/simulation_service.py — SimulationService
==================================================
Owns the Outcome Simulation Engine (pluggable). Simulates each candidate action's outcome
across the requested horizons with uncertainty bounds. Deterministic replay.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ..contracts import ActionCandidate, SimOutcome, WorldVars, DEFAULT_HORIZONS
from ..registry import SIMULATORS


class SimulationService:
    def __init__(self, simulator: str = "trend"):
        self._sim = SIMULATORS.create(simulator)

    def simulate(self, world: WorldVars, action: ActionCandidate,
                 horizons: Tuple[int, ...] = DEFAULT_HORIZONS) -> SimOutcome:
        return self._sim.simulate(world, action, horizons)

    def simulate_all(self, world: WorldVars, actions: List[ActionCandidate],
                     horizons: Tuple[int, ...] = DEFAULT_HORIZONS) -> Dict[str, SimOutcome]:
        return {a.id: self._sim.simulate(world, a, horizons) for a in actions}
