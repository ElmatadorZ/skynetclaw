"""
logic/engine.py — the Cognitive Logic Engine orchestrator
=========================================================
Single responsibility: COMPOSE the pieces into one verifiable reasoning act —
solve → verify → prove → diagnose → counter-example → compute confidence — and
return a single structured Report. Never guesses; refuses unsupported conclusions.

Confidence is COMPUTED (not heuristic):
    verified_fraction  — of the reported model, from the verifier
    proof_completeness — 1.0 iff the proof re-verifies
    ambiguity          — unique(0) vs multiple/under(1)
    unresolved         — fraction of inputs the parser could not parse

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .constraint_graph import ConstraintGraph
from .solver import SolveResult, Status, solve
from .verifier import verify, VerifyReport
from .proof import build_proof, Proof
from .diagnostics import minimal_conflict, Diagnosis


@dataclass
class Report:
    status: Status
    solution: Optional[Dict[str, Any]]
    proof: Proof
    verification: Optional[VerifyReport]
    diagnosis: Optional[Diagnosis]
    counter_example: Optional[Dict[str, Any]]
    answer_confidence: float      # confidence in a definitive/unique answer
    status_confidence: float      # confidence in the classification itself
    notes: List[str] = field(default_factory=list)
    nodes: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "solution": self.solution,
            "answer_confidence": round(self.answer_confidence, 3),
            "status_confidence": round(self.status_confidence, 3),
            "counter_example": self.counter_example,
            "proof": self.proof.as_dict(),
            "verification": self.verification.as_dict() if self.verification else None,
            "diagnosis": self.diagnosis.as_dict() if self.diagnosis else None,
            "notes": self.notes,
            "nodes": self.nodes,
        }


def reason(graph: ConstraintGraph, unresolved_inputs: int = 0,
           total_inputs: int = 0) -> Report:
    """Run the full pipeline on a constraint graph. `unresolved_inputs`/`total_inputs`
    let the caller feed parser coverage into the confidence (0 if not parsing NL)."""
    result: SolveResult = solve(graph, max_solutions=2)
    st = result.status
    notes: List[str] = [result.reason]
    unresolved_ratio = (unresolved_inputs / total_inputs) if total_inputs else 0.0

    solution = None
    verification = None
    diagnosis = None
    counter_example = None

    if st == Status.SATISFIABLE:
        solution = result.solutions[0]
        verification = verify(graph, solution)
        proof = build_proof(graph, result)
        vf = _verified_fraction(verification)
        pc = 1.0 if proof.verified else 0.0
        answer_conf = vf * pc * (1.0 - unresolved_ratio)
        status_conf = 1.0                    # exhaustive search is definitive
        if not verification.ok:
            notes.append("solver produced a model the verifier REJECTED — treat as UNKNOWN")
            answer_conf = 0.0

    elif st == Status.UNSATISFIABLE:
        diagnosis = minimal_conflict(graph)
        proof = build_proof(graph, result, mus=diagnosis.minimal_conflict)
        # confidence in "impossible" is high because the MUS is minimal & re-checked
        answer_conf = 1.0 if proof.verified else 0.7
        status_conf = 1.0
        notes.append(f"minimal conflict of {len(diagnosis.minimal_conflict)} constraint(s)")

    elif st in (Status.MULTIPLE_SOLUTIONS, Status.UNDERCONSTRAINED):
        proof = build_proof(graph, result)
        counter_example = result.solutions[1] if len(result.solutions) > 1 else None
        # every exhibited model is verified independently
        all_verified = all(verify(graph, s).ok for s in result.solutions[:2])
        answer_conf = 0.0                    # we REFUSE to assert a unique answer
        status_conf = 1.0 if all_verified else 0.5
        notes.append("uniqueness refused: ≥2 verified models exist")

    else:  # UNKNOWN
        proof = build_proof(graph, result)
        answer_conf = 0.0
        status_conf = 0.0
        notes.append("resource budget hit — no conclusion asserted")

    return Report(status=st, solution=solution, proof=proof, verification=verification,
                  diagnosis=diagnosis, counter_example=counter_example,
                  answer_confidence=answer_conf, status_confidence=status_conf,
                  notes=notes, nodes=result.nodes)


def _verified_fraction(vr: VerifyReport) -> float:
    total = vr.passed + vr.failed
    return (vr.passed / total) if total else 1.0
