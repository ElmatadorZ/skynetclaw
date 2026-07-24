"""
engines/planner_engine.py — Planner Engine
==========================================
Single responsibility: from a pool of candidate actions, produce the set the decision
layer will weigh. HARD RULE (ADR-0012): a planner NEVER returns one action — it returns
MULTIPLE candidates, each already carrying benefits / costs / resources / risks /
dependencies / confidence. The planner's job is to FILTER (drop resource-infeasible or
dependency-broken candidates) and ORDER deterministically — not to pick a winner (that is
the Decision engine).

Two built-in planners demonstrate pluggability:
  · DefaultPlannerEngine   — resource + dependency feasibility filter.
  · ConservativePlannerEngine — additionally drops candidates below a confidence floor.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import List

from ..contracts import ActionCandidate, Goal, ResourceVector, WorldVars


class DefaultPlannerEngine:
    name = "default"
    confidence_floor = 0.0

    def generate(self, world: WorldVars, goals: List[Goal], resources: ResourceVector,
                 candidates: List[ActionCandidate]) -> List[ActionCandidate]:
        have_ids = {c.id for c in candidates}
        out: List[ActionCandidate] = []
        for c in candidates:
            if not resources.covers(c.required_resources):
                continue                                    # cannot afford → not a candidate
            if any(dep not in have_ids for dep in c.dependencies):
                continue                                    # unmet dependency → drop
            if c.estimated_confidence < self.confidence_floor:
                continue
            out.append(c)
        if not out:
            # never return zero: the honest fallback is the baseline no-op if present
            out = [c for c in candidates if c.id == "noop"] or list(candidates[:1])
        # deterministic order: higher confidence first, then id
        return sorted(out, key=lambda c: (-c.estimated_confidence, c.id))


class ConservativePlannerEngine(DefaultPlannerEngine):
    name = "conservative"
    confidence_floor = 0.4
