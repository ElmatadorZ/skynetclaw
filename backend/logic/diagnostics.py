"""
logic/diagnostics.py — explain WHY solving failed
=================================================
Single responsibility: for an UNSATISFIABLE problem, compute a **minimal
unsatisfiable set** (MUS) — an irreducible subset of constraints that is still
unsatisfiable but becomes satisfiable if any one is removed — and suggest a repair.

Algorithm: deletion-based MUS. Start from the full constraint set; try removing each
constraint; if the remainder is still UNSAT, that constraint is not needed (drop it).
What remains is minimal. Deterministic (constraints tried in order).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .constraint_graph import Constraint, ConstraintGraph
from .solver import Status, solve


def _unsat(graph: ConstraintGraph, subset: List[Constraint]) -> bool:
    g = ConstraintGraph(variables=dict(graph.variables), constraints=list(subset))
    return solve(g, max_solutions=1).status == Status.UNSATISFIABLE


@dataclass
class Diagnosis:
    minimal_conflict: List[str] = field(default_factory=list)   # descriptions
    conflict_constraints: List[Constraint] = field(default_factory=list)
    repair: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"minimal_conflict": self.minimal_conflict, "repair": self.repair}


def minimal_conflict(graph: ConstraintGraph) -> Diagnosis:
    """Deletion-based MUS. Assumes the full set is UNSAT; returns a minimal core."""
    core: List[Constraint] = list(graph.constraints)
    for c in list(graph.constraints):
        trial = [x for x in core if x is not c]
        if trial and _unsat(graph, trial):
            core = trial            # c was not needed for the conflict
    descs = [c.describe() for c in core]
    # repair: dropping / relaxing ANY one member of the MUS restores satisfiability
    repair = [f"remove or relax: {d}" for d in descs]
    if len(descs) >= 2:
        repair.append(f"the conflict is the JOINT of {len(descs)} constraints — "
                      f"they cannot all hold at once; keep at most {len(descs) - 1}.")
    return Diagnosis(minimal_conflict=descs, conflict_constraints=core, repair=repair)
