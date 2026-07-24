"""
decision_intelligence/confidence_engine.py — Phase 5: confidence from evidence
==============================================================================
Single responsibility: COMPUTE a confidence in [0,1] from run evidence — never a
heuristic guess. Five components, each in [0,1], combined by a documented weighted sum
and then GATED (a gate can only lower confidence, never raise it):

    verified_constraint_ratio   verifier passed / total
    proof_completeness          1.0 iff search was exhaustive AND the proof re-verifies
    information_completeness     1 - missing / (grounded_facts + missing)
    answer_determinacy           1.0 if no goal-differing counter-example; else 1/#answers
    assumption_integrity         1 - load_bearing_unverified_assumptions / total_constraints

Gates (hard caps):
    class == UNKNOWN                 → confidence 0
    verifier rejected the model      → confidence 0
    a VERIFIED goal-differing CE      → answer confidence collapses to answer_determinacy

Two confidences are reported (the Logic Engine's honest distinction):
    answer_confidence   — confidence in a specific/unique ANSWER
    status_confidence   — confidence in the CLASSIFICATION itself (e.g. "impossible")

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Documented weights for the answer-confidence weighted sum (sum to 1.0).
W = {
    "verified_constraint_ratio": 0.30,
    "proof_completeness":        0.25,
    "information_completeness":  0.15,
    "answer_determinacy":        0.20,
    "assumption_integrity":      0.10,
}


@dataclass
class ConfidenceComponents:
    verified_constraint_ratio: float = 0.0
    proof_completeness: float = 0.0
    information_completeness: float = 1.0
    answer_determinacy: float = 1.0
    assumption_integrity: float = 1.0

    def as_dict(self) -> Dict[str, float]:
        return {k: round(v, 4) for k, v in vars(self).items()}


@dataclass
class ConfidenceReport:
    answer_confidence: float
    status_confidence: float
    components: ConfidenceComponents
    weights: Dict[str, float] = field(default_factory=lambda: dict(W))
    calibration_notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"answer_confidence": round(self.answer_confidence, 4),
                "status_confidence": round(self.status_confidence, 4),
                "components": self.components.as_dict(),
                "weights": self.weights,
                "calibration_notes": self.calibration_notes}


def _clamp(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def assess_confidence(*, classification: str,
                      verification,                       # DecisionVerification | None
                      counter_example,                    # CounterExample | None
                      exhaustive: bool,
                      proof_verified: bool,
                      grounded_facts: int,
                      missing_information: int,
                      distinct_answer_count: int = 1) -> ConfidenceReport:
    notes: List[str] = []
    c = ConfidenceComponents()

    # 1) verified constraint ratio
    if verification is not None and verification.total_constraints > 0:
        c.verified_constraint_ratio = verification.passed / verification.total_constraints
    elif classification == "UNSATISFIABLE":
        c.verified_constraint_ratio = 1.0     # the MUS is re-checked by the engine
    else:
        c.verified_constraint_ratio = 0.0

    # 2) proof completeness
    c.proof_completeness = 1.0 if (exhaustive and proof_verified) else (0.5 if proof_verified else 0.0)
    if not exhaustive:
        notes.append("search was not exhaustive — proof_completeness capped")

    # 3) information completeness
    denom = grounded_facts + missing_information
    c.information_completeness = 1.0 if denom == 0 else _clamp(grounded_facts / denom)
    if missing_information:
        notes.append(f"{missing_information} item(s) of missing information reduce information_completeness")

    # 4) answer determinacy (alternatives)
    if counter_example is not None and counter_example.found and counter_example.verified:
        n = max(distinct_answer_count, 2)
        c.answer_determinacy = 1.0 / n
        notes.append("a verified goal-differing counter-example exists — answer is not unique")
    else:
        c.answer_determinacy = 1.0

    # 5) assumption integrity
    if verification is not None and verification.total_constraints > 0:
        bad = len(set(verification.load_bearing_assumptions) |
                  set(verification.unverified_assumptions))
        c.assumption_integrity = _clamp(1.0 - bad / verification.total_constraints)
        if bad:
            notes.append(f"{bad} load-bearing/unverified assumption(s) reduce assumption_integrity")

    # weighted sum → base answer confidence
    answer = sum(W[k] * getattr(c, k) for k in W)

    # status confidence — how sure we are of the CLASS
    if classification in ("SATISFIABLE", "UNSATISFIABLE"):
        status = 1.0 if exhaustive else 0.6
    elif classification in ("MULTIPLE_SOLUTIONS", "UNDERCONSTRAINED"):
        status = 1.0 if (verification is None or True) and proof_verified else 0.6
    else:  # UNKNOWN
        status = 0.0

    # ── Gates (only ever lower) ──
    if classification == "UNKNOWN":
        answer = 0.0
        notes.append("gate: UNKNOWN ⇒ answer_confidence 0 (refuse to assert)")
    if verification is not None and verification.total_constraints > 0 and not verification.ok:
        answer = 0.0
        notes.append("gate: verifier REJECTED the model ⇒ answer_confidence 0")
    if classification in ("MULTIPLE_SOLUTIONS", "UNDERCONSTRAINED"):
        # we deliberately refuse a unique answer; determinacy dominates
        answer = min(answer, c.answer_determinacy)
        notes.append("gate: non-unique class ⇒ answer_confidence capped at answer_determinacy")

    return ConfidenceReport(answer_confidence=_clamp(answer),
                            status_confidence=_clamp(status),
                            components=c, calibration_notes=notes)
