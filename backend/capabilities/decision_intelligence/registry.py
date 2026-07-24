"""
registry.py — plugin registries for pluggable decision components
=================================================================
Deterministic, name-keyed registries that let the capability support MULTIPLE planners,
utility functions, simulators, and decision policies — and future reinforcement-learning
policies — without changing any service (Open-Closed). A `DecisionRequest` names the
plugins by string; the capability resolves them here.

Registration is idempotent and explicit; nothing is auto-discovered (determinism). The
built-in engines register themselves on import (see `builtins.py`).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Callable, Dict, Generic, List, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._factories: Dict[str, Callable[[], T]] = {}

    def register(self, name: str, factory: Callable[[], T]) -> None:
        self._factories[name] = factory      # last registration wins (explicit override)

    def create(self, name: str) -> T:
        if name not in self._factories:
            raise KeyError(f"no {self._kind} plugin named {name!r}; "
                           f"available: {sorted(self._factories)}")
        return self._factories[name]()

    def names(self) -> List[str]:
        return sorted(self._factories)

    def has(self, name: str) -> bool:
        return name in self._factories


# One registry per pluggable engine family the mission calls out.
PLANNERS: Registry = Registry("planner")
UTILITIES: Registry = Registry("utility")
SIMULATORS: Registry = Registry("simulator")
POLICIES: Registry = Registry("policy")          # decision-selection policies (RL-ready)
ACTION_GENERATORS: Registry = Registry("action_generator")


def snapshot() -> Dict[str, List[str]]:
    """Auditable view of everything registered (for docs / deterministic-replay records)."""
    return {"planners": PLANNERS.names(), "utilities": UTILITIES.names(),
            "simulators": SIMULATORS.names(), "policies": POLICIES.names(),
            "action_generators": ACTION_GENERATORS.names()}
