"""
services/world_state_service.py — WorldStateService
===================================================
Owns the World State Engine; applies actions and computes diffs. Holds the current world
as mutable service state (the rest of the capability treats world snapshots immutably).
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ..contracts import ActionCandidate, WorldVars
from ..engines.world_state_engine import DefaultWorldStateEngine


class WorldStateService:
    def __init__(self, world: WorldVars = None, engine=None):
        self._engine = engine or DefaultWorldStateEngine()
        self._world: WorldVars = dict(world or {})

    @property
    def world(self) -> WorldVars:
        return dict(self._world)

    def set_world(self, world: WorldVars) -> None:
        self._world = dict(world)

    def project(self, action: ActionCandidate, days: int, world: WorldVars = None) -> WorldVars:
        return self._engine.apply(self._world if world is None else world, action, days)

    def diff(self, before: WorldVars, after: WorldVars) -> Dict[str, Tuple[Any, Any]]:
        return self._engine.diff(before, after)
