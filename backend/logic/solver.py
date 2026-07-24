"""
logic/solver.py — deterministic finite-domain CSP solver
========================================================
Single responsibility: SEARCH. Backtracking + forward-checking + MRV ordering, with
a hard node budget. Never guesses: returns exactly one of

    SATISFIABLE        exactly one solution (fully determined)
    MULTIPLE_SOLUTIONS ≥2 solutions, every variable constrained
    UNDERCONSTRAINED   ≥2 solutions AND ≥1 variable touched by no constraint
    UNSATISFIABLE      exhaustive search found none
    UNKNOWN            node budget exhausted before a definitive answer

Deterministic: variables/values are tried in a fixed, sorted order (ties broken by
name), so the same problem always yields the same trace and the same solutions.

The solver also records a `trace` of decisions and forced (unit-propagation) steps,
consumed by proof.py.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .constraint_graph import Assignment, Constraint, ConstraintGraph


class Status(str, Enum):
    SATISFIABLE = "SATISFIABLE"
    MULTIPLE_SOLUTIONS = "MULTIPLE_SOLUTIONS"
    UNDERCONSTRAINED = "UNDERCONSTRAINED"
    UNSATISFIABLE = "UNSATISFIABLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class SolveResult:
    status: Status
    solutions: List[Assignment] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    nodes: int = 0
    exhausted: bool = False
    reason: str = ""


def _consistent(graph: ConstraintGraph, a: Assignment) -> bool:
    """No constraint is DEFINITELY violated by the (partial) assignment a."""
    return not any(c.violated(a) for c in graph.constraints)


def _complete_and_valid(graph: ConstraintGraph, a: Assignment) -> bool:
    return all(v in a for v in graph.variables) and all(c.satisfied(a) for c in graph.constraints)


def solve(graph: ConstraintGraph, max_solutions: int = 2,
          node_budget: int = 300_000) -> SolveResult:
    """Enumerate up to `max_solutions` solutions (enough to classify uniqueness).
    Deterministic and budget-bounded."""
    var_names = sorted(graph.variables)                      # fixed order → deterministic
    domains0 = {v: list(graph.variables[v].domain) for v in var_names}
    solutions: List[Assignment] = []
    trace: List[Dict[str, Any]] = []
    stats = {"nodes": 0, "over": False}

    def forward_check(a: Assignment, domains: Dict[str, List[Any]]) -> Optional[Dict[str, List[Any]]]:
        """Prune values from unassigned domains that are already inconsistent; return
        the pruned domains, or None if any domain wipes out."""
        pruned = {v: list(d) for v, d in domains.items()}
        for v in var_names:
            if v in a:
                continue
            keep = []
            for val in pruned[v]:
                trial = dict(a); trial[v] = val
                if _consistent(graph, trial):
                    keep.append(val)
            if not keep:
                return None
            pruned[v] = keep
            if len(keep) == 1 and len(domains[v]) > 1:
                trace.append({"type": "propagate", "rule": "forward-check",
                              "derived": f"{v} = {keep[0]}",
                              "evidence": f"only remaining value for {v}"})
        return pruned

    def backtrack(a: Assignment, domains: Dict[str, List[Any]]) -> None:
        if stats["over"]:
            return
        stats["nodes"] += 1
        if stats["nodes"] > node_budget:
            stats["over"] = True
            return
        if len(a) == len(var_names):
            if _complete_and_valid(graph, a):
                solutions.append(dict(a))
            return
        # MRV: unassigned variable with the smallest current domain (ties by name)
        unassigned = [v for v in var_names if v not in a]
        var = min(unassigned, key=lambda v: (len(domains[v]), v))
        for val in sorted(domains[var], key=lambda x: (str(type(x)), _safe_key(x))):
            if len(solutions) >= max_solutions or stats["over"]:
                return
            trial = dict(a); trial[var] = val
            if not _consistent(graph, trial):
                continue
            trace.append({"type": "decision", "rule": "assign",
                          "derived": f"{var} = {val}", "evidence": "consistent choice"})
            pruned = forward_check(trial, domains)
            if pruned is not None:
                backtrack(trial, pruned)

    backtrack({}, domains0)

    exhausted = not stats["over"] and len(solutions) < max_solutions
    nodes = stats["nodes"]

    if stats["over"]:
        return SolveResult(Status.UNKNOWN, solutions, trace, nodes, False,
                           f"node budget {node_budget} exhausted — refusing to guess")
    if not solutions:
        return SolveResult(Status.UNSATISFIABLE, [], trace, nodes, True,
                           "exhaustive search found no solution")
    if len(solutions) == 1 and exhausted:
        return SolveResult(Status.SATISFIABLE, solutions, trace, nodes, True,
                           "exactly one solution (fully determined)")
    # ≥2 solutions (or capped at max_solutions with more possible)
    unconstrained = graph.unconstrained_vars()
    if unconstrained:
        return SolveResult(Status.UNDERCONSTRAINED, solutions, trace, nodes, exhausted,
                           f"multiple solutions and unconstrained variable(s): {unconstrained}")
    return SolveResult(Status.MULTIPLE_SOLUTIONS, solutions, trace, nodes, exhausted,
                       "several distinct valid solutions exist — uniqueness cannot be claimed")


def _safe_key(x: Any):
    try:
        return (0, x)
    except Exception:
        return (1, str(x))


def solve_all(graph: ConstraintGraph, cap: int = 10_000,
              node_budget: int = 1_000_000) -> SolveResult:
    """Enumerate ALL solutions (up to `cap`). Used by diagnostics / counter-example."""
    return solve(graph, max_solutions=cap, node_budget=node_budget)
