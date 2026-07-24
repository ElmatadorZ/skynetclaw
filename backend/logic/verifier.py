"""
logic/verifier.py — independent solution checker
================================================
Single responsibility: given a proposed solution, check it against EVERY constraint.
This is INDEPENDENT of the solver — a solution is only trusted once it re-verifies
here. No silent assumption: a constraint whose scope is not fully assigned is a FAIL,
never an assumption.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .constraint_graph import Assignment, Constraint, ConstraintGraph


@dataclass
class CheckLine:
    constraint: str
    result: str          # "PASS" | "FAIL"
    detail: str = ""


@dataclass
class VerifyReport:
    ok: bool
    lines: List[CheckLine] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    missing_assignments: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "passed": self.passed, "failed": self.failed,
                "missing_assignments": self.missing_assignments,
                "lines": [vars(l) for l in self.lines]}


def verify(graph: ConstraintGraph, solution: Assignment) -> VerifyReport:
    lines: List[CheckLine] = []
    passed = failed = 0

    # every declared variable must have an assignment from its domain — no assumption
    missing: List[str] = []
    for name, var in graph.variables.items():
        if name not in solution:
            missing.append(name)
        elif solution[name] not in var.domain:
            lines.append(CheckLine(f"domain({name})", "FAIL",
                                   f"{name}={solution[name]!r} not in its domain"))
            failed += 1

    for c in graph.constraints:
        scope_assigned = all(v in solution for v in c.scope)
        if not scope_assigned:
            lines.append(CheckLine(c.describe(), "FAIL",
                                   "unassigned variable(s) in scope — no assumption made"))
            failed += 1
            continue
        if c.satisfied(solution):
            lines.append(CheckLine(c.describe(), "PASS"))
            passed += 1
        else:
            lines.append(CheckLine(c.describe(), "FAIL", "constraint does not hold"))
            failed += 1

    ok = (failed == 0 and not missing)
    return VerifyReport(ok=ok, lines=lines, passed=passed, failed=failed,
                        missing_assignments=missing)
