"""
engines/world_state_engine.py — World State Engine
==================================================
Single responsibility: represent and transform world state. It applies an action's
per-day effects over N days and computes a structural diff between two states. It does NOT
predict uncertainty (that is the simulator) and does NOT judge feasibility (constraints).
Pure and deterministic.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ..contracts import ActionCandidate, WorldVars


class DefaultWorldStateEngine:
    name = "default"

    def apply(self, world: WorldVars, action: ActionCandidate, days: int) -> WorldVars:
        """Apply `action.effects` (interpreted as per-day deltas) for `days`. Numeric vars
        accumulate; non-numeric vars are untouched. Deterministic; never mutates input."""
        out: Dict[str, Any] = dict(world)
        eff = action.effect_map()
        for var, per_day in eff.items():
            base = _num(out.get(var, 0.0))
            if base is None:
                out[var] = per_day * days          # var introduced by the action
            else:
                out[var] = base + per_day * days
        return out

    def diff(self, before: WorldVars, after: WorldVars) -> Dict[str, Tuple[Any, Any]]:
        keys = set(before) | set(after)
        changed: Dict[str, Tuple[Any, Any]] = {}
        for k in sorted(keys):
            b, a = before.get(k), after.get(k)
            if not _close(b, a):
                changed[k] = (b, a)
        return changed


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _close(a, b) -> bool:
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        return abs(na - nb) <= 1e-9
    return a == b
