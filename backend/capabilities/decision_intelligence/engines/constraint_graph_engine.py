"""
engines/constraint_graph_engine.py — Constraint Graph Engine
============================================================
Single responsibility: judge a world state against constraints. This is a THIN ADAPTER
over the reused subsystems — it does NOT re-implement constraint solving:

  · numeric constraints on world variables (a DSL line grammar: "var >= 5", "cost <= 100")
    are evaluated directly and deterministically;
  · richer logical constraints are delegated to the Cognitive Logic Engine (`logic/`) via
    the Decision Intelligence Framework where a full model is supplied.

Reuse, not duplication (ADR-0012). Pure and deterministic.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import re
from typing import List

from ..contracts import WorldVars

_OPS = {
    "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b, ">": lambda a, b: a > b,
    "==": lambda a, b: abs(a - b) <= 1e-9, "!=": lambda a, b: abs(a - b) > 1e-9,
}
# longest operators first so "<=" is matched before "<"
_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?)\s*$")


class DefaultConstraintEngine:
    name = "default"

    def _parse(self, text: str):
        for raw in re.split(r"[\n;]+", text or ""):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = _LINE.match(line)
            yield (m.group(1), m.group(2), float(m.group(3)), line) if m else (None, None, None, line)

    def violations(self, world: WorldVars, text: str) -> List[str]:
        out: List[str] = []
        for var, op, rhs, line in self._parse(text):
            if var is None:
                continue                       # unparseable lines are ignored, never invented
            lhs = _num(world.get(var))
            if lhs is None:
                out.append(f"{line}  [variable '{var}' absent from world state]")
                continue
            if not _OPS[op](lhs, rhs):
                out.append(f"{line}  [actual {var}={lhs}]")
        return out

    def feasible(self, world: WorldVars, text: str) -> bool:
        return not self.violations(world, text)

    def penalty(self, world: WorldVars, text: str) -> float:
        """Graded penalty: magnitude of violation, normalised. Deterministic. A hard
        infeasibility yields a large but finite penalty so utility can still rank."""
        total = 0.0
        for var, op, rhs, line in self._parse(text):
            if var is None:
                continue
            lhs = _num(world.get(var))
            if lhs is None:
                total += 1.0
                continue
            if not _OPS[op](lhs, rhs):
                total += 1.0 + abs(lhs - rhs) / (abs(rhs) + 1.0)
        return total


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
