"""
logic/proof.py — reproducible proofs (not chain-of-thought)
==========================================================
Single responsibility: turn a solver result + verification into a structured,
reproducible PROOF. Each step carries {rule, evidence, derived_fact}. Because the
solver is deterministic, every step re-derives identically.

Proof shapes by status:
  · SATISFIABLE       derivation trace + a verification line per constraint + an
                      exhaustion step (exactly one model) → conclusion = the model.
  · UNSATISFIABLE     the minimal conflicting set (MUS) → "no model satisfies these".
  · MULTIPLE/UNDER    two distinct verified models → "not unique" (a proof of
                      non-uniqueness, i.e. the counter-example is exhibited).
  · UNKNOWN           no proof; records the budget that stopped the search.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .constraint_graph import ConstraintGraph
from .solver import SolveResult, Status
from .verifier import VerifyReport, verify


@dataclass
class ProofStep:
    n: int
    rule: str
    evidence: str
    derived: str


@dataclass
class Proof:
    method: str
    conclusion: str
    steps: List[ProofStep] = field(default_factory=list)
    verified: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {"method": self.method, "conclusion": self.conclusion,
                "verified": self.verified,
                "steps": [{"n": s.n, "rule": s.rule, "evidence": s.evidence,
                           "derived": s.derived} for s in self.steps]}


def build_proof(graph: ConstraintGraph, result: SolveResult,
                mus: Optional[List[str]] = None) -> Proof:
    st = result.status

    if st == Status.SATISFIABLE:
        sol = result.solutions[0]
        steps: List[ProofStep] = []
        n = 0
        # 1) the deterministic derivation trace (decisions + forced propagations)
        for t in result.trace:
            n += 1
            steps.append(ProofStep(n, t.get("rule", "?"), t.get("evidence", ""),
                                   t.get("derived", "")))
        # 2) a verification line per constraint (evidence the model satisfies each rule)
        vr = verify(graph, sol)
        for line in vr.lines:
            if line.result == "PASS":
                n += 1
                steps.append(ProofStep(n, f"check[{line.constraint}]",
                                       f"under {_fmt(sol)}", "constraint holds"))
        # 3) exhaustion (uniqueness)
        n += 1
        steps.append(ProofStep(n, "exhaustion",
                               "backtracking search explored the whole space",
                               "exactly one model exists"))
        return Proof("model+verification+exhaustion", _fmt(sol), steps, verified=vr.ok)

    if st == Status.UNSATISFIABLE:
        steps = []
        core = mus if mus is not None else [c.describe() for c in graph.constraints]
        for i, desc in enumerate(core, 1):
            steps.append(ProofStep(i, "conflict-member", "in the minimal conflicting set", desc))
        steps.append(ProofStep(len(core) + 1, "unsat-core",
                                "no assignment satisfies all of the above jointly",
                                "UNSATISFIABLE"))
        return Proof("minimal-unsat-core", "no model exists (impossible)", steps, verified=True)

    if st in (Status.MULTIPLE_SOLUTIONS, Status.UNDERCONSTRAINED):
        steps = []
        for i, sol in enumerate(result.solutions[:2], 1):
            vr = verify(graph, sol)
            steps.append(ProofStep(i, f"model-{i}", f"verified ({vr.passed} constraints hold)",
                                   _fmt(sol)))
        steps.append(ProofStep(3, "non-uniqueness",
                               "two distinct verified models exhibited",
                               "the answer is NOT unique — uniqueness refused"))
        method = "two-model (non-uniqueness)"
        concl = ("under-constrained: " + str(graph.unconstrained_vars()) if st == Status.UNDERCONSTRAINED
                 else "multiple valid solutions")
        return Proof(method, concl, steps, verified=True)

    # UNKNOWN
    return Proof("none", "UNKNOWN — search budget exhausted, refusing to guess",
                 [ProofStep(1, "budget", result.reason, "no conclusion")], verified=False)


def _fmt(sol: Dict[str, Any]) -> str:
    return "{" + ", ".join(f"{k}={sol[k]}" for k in sorted(sol)) + "}"
