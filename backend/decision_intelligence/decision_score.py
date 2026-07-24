"""
decision_intelligence/decision_score.py — Phase 6: the /100 auditability rubric
===============================================================================
Single responsibility: score the QUALITY OF THE REASONING PROCESS deterministically
from run telemetry — not the real-world truth of the answer, but how auditable,
disciplined, and honest the decision act was. Given identical telemetry the score is
identical.

Rubric (mission-defined):
    Reasoning Accuracy ........... /20   solver status internally consistent + verified
    Constraint Tracking .......... /15   every constraint represented AND checked
    Consistency .................. /15   no verified counter-example contradicts a unique claim
    Evidence Usage ............... /10   facts grounded in cited source spans
    Hallucination Resistance ..... /10   ungrounded statements flagged, not admitted as fact
    Decision Quality ............. /10   didn't force one answer when multiple / refused UNKNOWN
    Counter Example Search ....... /10   an invalidation attempt actually ran
    Self Verification ............ /5    the candidate was independently verified
    Confidence Calibration ....... /5    confidence within the calibrated band for the class
    TOTAL ........................ /100

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

MAX = {
    "reasoning_accuracy": 20, "constraint_tracking": 15, "consistency": 15,
    "evidence_usage": 10, "hallucination_resistance": 10, "decision_quality": 10,
    "counter_example_search": 10, "self_verification": 5, "confidence_calibration": 5,
}


@dataclass
class Telemetry:
    classification: str = "UNKNOWN"
    verifier_ran: bool = False
    verifier_ok: bool = False
    constraints_total: int = 0
    constraints_checked: int = 0
    counter_example_ran: bool = False
    counter_example_found: bool = False
    counter_example_verified: bool = False
    forced_single_answer: bool = False       # did we assert a unique answer?
    grounded_facts: int = 0
    ungrounded_statements: int = 0
    ungrounded_flagged: int = 0               # of the ungrounded, how many were flagged
    answer_confidence: float = 0.0
    status_confidence: float = 0.0
    exhaustive: bool = False
    proof_verified: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return dict(vars(self))


@dataclass
class DecisionScore:
    breakdown: Dict[str, int] = field(default_factory=dict)
    total: int = 0
    max_total: int = 100
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"total": self.total, "max_total": self.max_total,
                "breakdown": self.breakdown, "notes": self.notes}

    def render(self) -> str:
        label = {
            "reasoning_accuracy": "Reasoning Accuracy",
            "constraint_tracking": "Constraint Tracking",
            "consistency": "Consistency",
            "evidence_usage": "Evidence Usage",
            "hallucination_resistance": "Hallucination Resistance",
            "decision_quality": "Decision Quality",
            "counter_example_search": "Counter Example Search",
            "self_verification": "Self Verification",
            "confidence_calibration": "Confidence Calibration",
        }
        lines = []
        for k in MAX:
            dots = "." * max(4, 30 - len(label[k]))
            lines.append(f"  {label[k]} {dots} {self.breakdown.get(k, 0)}/{MAX[k]}")
        lines.append(f"  {'TOTAL':<30} {self.total}/{self.max_total}")
        return "\n".join(lines)


def _calibrated(t: Telemetry) -> bool:
    """Is the reported confidence within the band the class demands?"""
    cls, ac = t.classification, t.answer_confidence
    if cls == "UNKNOWN":
        return ac == 0.0
    if cls in ("MULTIPLE_SOLUTIONS", "UNDERCONSTRAINED"):
        return ac <= 0.5                         # must not assert a confident unique answer
    if cls == "UNSATISFIABLE":
        return t.status_confidence >= 0.6
    if cls == "SATISFIABLE":
        # if verified & exhaustive, confidence should be meaningfully positive
        return ac > 0.0 if (t.verifier_ok and t.exhaustive) else True
    return True


def score_decision(t: Telemetry) -> DecisionScore:
    b: Dict[str, int] = {}
    notes: List[str] = []

    # Reasoning Accuracy /20 — status is backed by verification (SAT) or a proof (UNSAT),
    # and nothing was asserted for UNKNOWN.
    if t.classification == "SATISFIABLE":
        b["reasoning_accuracy"] = 20 if (t.verifier_ran and t.verifier_ok and t.proof_verified) else 8
    elif t.classification == "UNSATISFIABLE":
        b["reasoning_accuracy"] = 20 if t.proof_verified else 10
    elif t.classification in ("MULTIPLE_SOLUTIONS", "UNDERCONSTRAINED"):
        b["reasoning_accuracy"] = 18 if t.proof_verified else 9
    else:  # UNKNOWN — correct to assert nothing
        b["reasoning_accuracy"] = 12 if t.answer_confidence == 0.0 else 0

    # Constraint Tracking /15 — every constraint represented AND checked.
    if t.constraints_total == 0:
        b["constraint_tracking"] = 15 if t.classification in ("UNKNOWN",) else 7
    else:
        ratio = t.constraints_checked / t.constraints_total
        b["constraint_tracking"] = round(15 * min(1.0, ratio))

    # Consistency /15 — no verified counter-example contradicting a unique claim.
    contradiction = t.forced_single_answer and t.counter_example_found and t.counter_example_verified
    b["consistency"] = 0 if contradiction else 15
    if contradiction:
        notes.append("asserted a unique answer while a verified counter-example exists")

    # Evidence Usage /10 — facts grounded in source spans.
    total_stmts = t.grounded_facts + t.ungrounded_statements
    if total_stmts == 0:
        b["evidence_usage"] = 10 if t.classification == "UNKNOWN" else 6
    else:
        b["evidence_usage"] = round(10 * (t.grounded_facts / total_stmts))

    # Hallucination Resistance /10 — ungrounded statements were flagged, not admitted.
    if t.ungrounded_statements == 0:
        b["hallucination_resistance"] = 10
    else:
        b["hallucination_resistance"] = round(10 * (t.ungrounded_flagged / t.ungrounded_statements))

    # Decision Quality /10 — refused to force a single answer when multiple; refused UNKNOWN.
    if t.classification in ("MULTIPLE_SOLUTIONS", "UNDERCONSTRAINED"):
        b["decision_quality"] = 0 if t.forced_single_answer else 10
    elif t.classification == "UNKNOWN":
        b["decision_quality"] = 10 if t.answer_confidence == 0.0 else 0
    else:
        b["decision_quality"] = 10

    # Counter Example Search /10 — an invalidation attempt actually ran.
    if t.counter_example_ran:
        b["counter_example_search"] = 10
    else:
        b["counter_example_search"] = 0
        notes.append("no counter-example search ran")

    # Self Verification /5 — candidate independently verified (or N/A for UNSAT/UNKNOWN).
    if t.classification == "SATISFIABLE":
        b["self_verification"] = 5 if t.verifier_ran else 0
    elif t.classification in ("MULTIPLE_SOLUTIONS", "UNDERCONSTRAINED"):
        b["self_verification"] = 5 if t.verifier_ran else 3
    else:
        b["self_verification"] = 5   # nothing to verify; proof/MUS covers it

    # Confidence Calibration /5.
    b["confidence_calibration"] = 5 if _calibrated(t) else 0
    if not _calibrated(t):
        notes.append("confidence outside the calibrated band for the class")

    total = sum(b.get(k, 0) for k in MAX)
    return DecisionScore(breakdown=b, total=total, max_total=sum(MAX.values()), notes=notes)
