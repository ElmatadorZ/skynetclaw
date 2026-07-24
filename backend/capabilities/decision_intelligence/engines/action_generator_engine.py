"""
engines/action_generator_engine.py — Action Generator Engine
============================================================
Single responsibility: PROPOSE candidate actions from the world state and goals. It seeds
the planner's search space. Two sources, both deterministic:
  · caller-supplied `seed` actions (passed straight through, de-duplicated by id);
  · synthesised "move-the-needle" actions — one per goal that isn't yet attained, whose
    effect nudges the goal variable in its desired direction, with declared resources/risks.

It never fabricates benefits it cannot tie to a goal; a synthesised action's benefit names
the goal it serves. Pure and deterministic (no RNG).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import List, Optional

from ..contracts import ActionCandidate, Goal, GoalDirection, ResourceVector, WorldVars


class DefaultActionGeneratorEngine:
    name = "default"

    def candidates(self, world: WorldVars, goals: List[Goal],
                   resources: ResourceVector,
                   seed: Optional[List[ActionCandidate]] = None) -> List[ActionCandidate]:
        out: List[ActionCandidate] = []
        seen = set()

        for a in (seed or []):
            if a.id not in seen:
                out.append(a); seen.add(a.id)

        for g in sorted(goals, key=lambda x: x.id):
            aid = f"auto_{g.id}"
            if aid in seen:
                continue
            direction = 1.0 if g.direction != GoalDirection.MINIMIZE else -1.0
            if g.direction == GoalDirection.TARGET and g.target_value is not None:
                cur = _num(world.get(g.variable, 0.0)) or 0.0
                direction = 1.0 if g.target_value >= cur else -1.0
            step = direction * _step_for(g)
            out.append(ActionCandidate(
                id=aid,
                description=f"Advance goal '{g.id}' on variable '{g.variable}'",
                effects=((g.variable, step),),
                expected_benefits=(f"progress on goal:{g.id}",),
                expected_costs=("resource consumption over time",),
                required_resources=ResourceVector.of({"effort": 1.0}),
                risks=("effect may not materialise as modelled",),
                dependencies=(),
                estimated_confidence=0.5,
            ))
            seen.add(aid)

        # a deterministic "do nothing" baseline is always a candidate (opportunity cost view)
        if "noop" not in seen:
            out.append(ActionCandidate(
                id="noop", description="Take no action (baseline)",
                effects=(), expected_benefits=("preserves resources",),
                expected_costs=("no progress toward goals",),
                required_resources=ResourceVector(), risks=(), dependencies=(),
                estimated_confidence=0.9))
        return out


def _step_for(goal: Goal) -> float:
    if goal.direction == GoalDirection.TARGET and goal.target_value is not None:
        return max(0.1, abs(goal.target_value) * 0.05)
    return 1.0


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
