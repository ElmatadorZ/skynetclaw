"""
engines/counter_example_engine.py — Counter Example Engine
==========================================================
Single responsibility: given world state + logical constraints + goals, search for a
counter-example that would invalidate a decision's assumptions. This is a THIN ADAPTER
over the Decision Intelligence Framework's counter-example search (`decision_intelligence`,
ADR-0011), which itself reuses the Cognitive Logic Engine — NO duplication (ADR-0012).

When no formal constraint model is supplied there is nothing decidable to refute, so it
honestly returns None (the Review engine then relies on its other challenges).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..contracts import Goal, WorldVars


class DIFCounterExampleEngine:
    name = "dif"

    def find(self, world: WorldVars, constraints_text: str,
             goals: List[Goal]) -> Optional[Dict[str, Any]]:
        text = (constraints_text or "").strip()
        if not text:
            return None
        try:
            import decision_intelligence as dif      # reused subsystem (ADR-0011)
            import logic
        except Exception:
            return None

        # A counter-example is only meaningful against REAL logical constraints. Map the
        # constraints (logic DSL — "a is b", "a is not b", "a < b", "a is <value>") onto a
        # finite-domain model of the world's integer variables. If NOTHING maps (e.g. the
        # text is purely numeric planning DSL like "cost <= 100", already handled by the
        # constraint gate), there is nothing decidable to refute → return None. This is the
        # honest guard against fabricating a counter-example from an unconstrained model.
        domain_vars = _int_vars(world)
        if not domain_vars:
            return None
        graph = logic.ConstraintGraph()
        for name, cur in domain_vars.items():
            lo, hi = int(cur) - 2, int(cur) + 2
            graph.add_var(name, list(range(lo, hi + 1)))
        relations = logic.parse(text).relations
        constraints, _problems = logic.to_constraints(relations, graph)
        if not constraints:
            return None                              # no logical constraints → nothing to refute
        for c in constraints:
            graph.add(c)

        parsed = dif.analyze(graph=graph,
                             goals=[g.variable for g in goals if g.variable in domain_vars])
        report = dif.decide(model=parsed)
        ce = report.counter_example
        if getattr(ce, "found", False) and getattr(ce, "verified", False):
            return ce.as_dict()
        return None


def _int_vars(world: WorldVars) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for k, v in world.items():
        try:
            fv = float(v)
            if abs(fv - round(fv)) <= 1e-9:
                out[k] = int(round(fv))
        except (TypeError, ValueError):
            continue
    return out
