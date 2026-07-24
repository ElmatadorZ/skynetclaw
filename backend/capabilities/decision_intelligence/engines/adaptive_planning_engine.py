"""
engines/adaptive_planning_engine.py — Adaptive Planning Engine
==============================================================
Single responsibility: when the world changes, DO NOT regenerate the whole plan. Reuse the
existing plan and produce a MINIMAL PATCH — regenerate only the steps whose assumptions the
change invalidated; keep everything else.

A step is "invalidated" iff a world variable it depends on (a variable it produces effects
on, or names in its benefits/risks) changed between old and new world. `regenerate` is a
caller-supplied pure function `(step, new_world) -> ActionCandidate` (the Adaptation
service passes one that routes through the Planner/ActionGenerator) — the engine never
calls another engine directly.

Pure and deterministic.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from ..contracts import ActionCandidate, Plan, PlanPatch, WorldVars

Regenerate = Callable[[ActionCandidate, WorldVars], ActionCandidate]


class AdaptivePlanningEngine:
    name = "default"

    def patch(self, plan: Plan, old_world: WorldVars, new_world: WorldVars,
              regenerate: Regenerate) -> PlanPatch:
        changed_vars = _changed_vars(old_world, new_world)
        new_steps: List[ActionCandidate] = []
        changed_steps: List[str] = []
        kept_steps: List[str] = []
        for step in plan.steps:
            if changed_vars & _step_vars(step):
                replacement = regenerate(step, new_world)
                new_steps.append(replacement)
                changed_steps.append(step.id)
            else:
                new_steps.append(step)
                kept_steps.append(step.id)
        reason = (f"world changed on {sorted(changed_vars)}; "
                  f"patched {len(changed_steps)} step(s), kept {len(kept_steps)}"
                  if changed_vars else "no relevant world change; plan reused unchanged")
        return PlanPatch(plan=Plan(id=plan.id, steps=tuple(new_steps)),
                         changed_steps=changed_steps, kept_steps=kept_steps, reason=reason)


def _changed_vars(old: WorldVars, new: WorldVars) -> set:
    keys = set(old) | set(new)
    out = set()
    for k in keys:
        if not _close(old.get(k), new.get(k)):
            out.add(k)
    return out


def _step_vars(step: ActionCandidate) -> set:
    return set(step.effect_map().keys())


def _close(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) <= 1e-9
    except (TypeError, ValueError):
        return a == b
