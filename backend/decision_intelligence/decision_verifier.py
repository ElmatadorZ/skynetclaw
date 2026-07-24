"""
decision_intelligence/decision_verifier.py — Phase 4: verify every conclusion
=============================================================================
Single responsibility: given a proposed assignment, produce an AUDIT of the decision —
a PASS/FAIL line for every constraint AND every assumption, plus which assumptions were
load-bearing (their removal would change satisfaction). Overall verdict = PASS iff the
Logic Engine's independent verifier accepts the assignment against all hard constraints.

This is a thin, honest adapter over `logic.verify` (the engine already checks every
constraint with "missing variable ⇒ FAIL, never an assumption"). DIF adds the
assumption-provenance view the audit report and confidence engine need.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import logic
from logic import ConstraintGraph
from .constraint_analyzer import AnalysisModel, ConstraintSpec


@dataclass
class CheckLine:
    description: str
    result: str            # "PASS" | "FAIL"
    is_assumption: bool
    load_bearing: bool = False   # for assumptions: does dropping it change the verdict?
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"description": self.description, "result": self.result,
                "is_assumption": self.is_assumption, "load_bearing": self.load_bearing,
                "detail": self.detail}


@dataclass
class DecisionVerification:
    ok: bool                                    # all HARD constraints hold
    lines: List[CheckLine] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    missing_assignments: List[str] = field(default_factory=list)
    load_bearing_assumptions: List[str] = field(default_factory=list)
    unverified_assumptions: List[str] = field(default_factory=list)

    @property
    def total_constraints(self) -> int:
        return self.passed + self.failed

    def as_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "passed": self.passed, "failed": self.failed,
                "missing_assignments": self.missing_assignments,
                "load_bearing_assumptions": self.load_bearing_assumptions,
                "unverified_assumptions": self.unverified_assumptions,
                "lines": [l.as_dict() for l in self.lines]}


def _describe_set(specs: List[ConstraintSpec]) -> Dict[str, ConstraintSpec]:
    return {cs.description: cs for cs in specs}


def verify_decision(model: AnalysisModel, assignment: Optional[Dict[str, Any]]) -> DecisionVerification:
    """Check `assignment` against the model. If assignment is None (no solution to
    verify — e.g. UNSAT/UNKNOWN), returns a not-ok verification with no lines."""
    if assignment is None:
        return DecisionVerification(ok=False, lines=[], passed=0, failed=0)

    graph = model.graph()
    base = logic.verify(graph, assignment)   # independent engine verifier

    # Map each engine CheckLine back to whether it came from an assumption.
    assumption_desc = {cs.description for cs in model.assumptions}
    lines: List[CheckLine] = []
    for l in base.lines:
        is_assum = l.constraint in assumption_desc
        lines.append(CheckLine(description=l.constraint, result=l.result,
                               is_assumption=is_assum, detail=l.detail))

    # Load-bearing assumptions: drop each assumption and re-verify the HARD set; if the
    # assignment still satisfies the hard constraints without it, it was NOT load-bearing.
    hard_graph = ConstraintGraph()
    for v in model.variables:
        hard_graph.add_var(v.name, v.domain)
    for cs in model.constraints:
        hard_graph.add(cs.constraint)
    hard_ok = logic.verify(hard_graph, assignment).ok

    load_bearing: List[str] = []
    unverified: List[str] = []
    for cs in model.assumptions:
        satisfied = cs.constraint.satisfied(assignment)
        if not satisfied:
            unverified.append(cs.description)      # assumption itself does not hold
        # is it load-bearing? build hard + this-only and compare to hard-only
        g2 = ConstraintGraph()
        for v in model.variables:
            g2.add_var(v.name, v.domain)
        for c2 in model.constraints:
            g2.add(c2.constraint)
        g2.add(cs.constraint)
        with_ok = logic.verify(g2, assignment).ok
        if with_ok != hard_ok or not satisfied:
            load_bearing.append(cs.description)

    return DecisionVerification(
        ok=base.ok, lines=lines, passed=base.passed, failed=base.failed,
        missing_assignments=list(base.missing_assignments),
        load_bearing_assumptions=sorted(set(load_bearing)),
        unverified_assumptions=sorted(set(unverified)),
    )
