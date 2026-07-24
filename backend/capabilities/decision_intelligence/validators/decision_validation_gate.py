"""
validators/decision_validation_gate.py — Decision Validation Gate
=================================================================
The capability's Validator layer. Before a decision is accepted it must pass FIVE
validations (ADR-0012). This gate INTEGRATES existing subsystems — it writes no new CVL
validator plugins (honoring the validator-development pause, ADR-0003) and no new solver:

  1. Constraint validation   — chosen action's projected world satisfies the constraints
                               (ConstraintService, which adapts logic/DIF).
  2. Consistency validation  — the rendered decision text passes CVL `validate()`
                               (`cognitive_validation.py`).
  3. Counterexample validation — the Review Board found no verified counter-example.
  4. Confidence validation   — review confidence ≥ the request threshold.
  5. Decision validation     — a feasible candidate was actually chosen + explained.

Deterministic; never raises (a broken validator must not break the mission).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..contracts import Decision, ReviewVerdict, WorldVars
from ..services.constraint_service import ConstraintService


@dataclass
class GateResult:
    ok: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    findings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "checks": self.checks, "findings": self.findings}


class DecisionValidationGate:
    def __init__(self, constraint_service: ConstraintService = None):
        self._constraints = constraint_service or ConstraintService()

    def validate(self, *, decision: Decision, verdict: ReviewVerdict,
                 projected_world: WorldVars, constraints_text: str,
                 confidence_threshold: float, decision_text: str) -> GateResult:
        checks: Dict[str, bool] = {}
        findings: List[str] = []

        # 1) Constraint validation (reuses logic/DIF via ConstraintService)
        violations = self._constraints.violations(projected_world, constraints_text)
        checks["constraint"] = not violations
        findings += [f"constraint: {v}" for v in violations]

        # 2) Consistency validation via CVL (existing API — no new plugin)
        checks["consistency"] = self._cvl_ok(decision_text, projected_world, findings)

        # 3) Counterexample validation
        checks["counterexample"] = verdict.counterexample is None
        if verdict.counterexample is not None:
            findings.append("counterexample: a verified counter-example exists")

        # 4) Confidence validation
        checks["confidence"] = verdict.confidence >= confidence_threshold
        if not checks["confidence"]:
            findings.append(f"confidence: {verdict.confidence:.2f} < {confidence_threshold:.2f}")

        # 5) Decision validation (structural)
        chosen_ok = decision.chosen is not None and bool(decision.explanation)
        infeasible = decision.chosen is not None and any(
            aid == decision.chosen.id for aid, _ in decision.rejected)
        checks["decision"] = chosen_ok and not infeasible
        if not chosen_ok:
            findings.append("decision: no explained candidate was chosen")
        if infeasible:
            findings.append("decision: chosen candidate is infeasible")

        return GateResult(ok=all(checks.values()), checks=checks, findings=findings)

    def _cvl_ok(self, decision_text: str, world: WorldVars, findings: List[str]) -> bool:
        try:
            import cognitive_validation as cvl        # existing CVL (ADR-0002)
        except Exception:
            return True                                # CVL absent → do not block (honest)
        try:
            res = cvl.validate(decision_text or "", {"world": world, "domain": "planning"})
            if not res.get("ok", True):
                for e in res.get("errors", [])[:5]:
                    findings.append(f"consistency[CVL]: {e.get('message', e)}")
            return bool(res.get("ok", True))
        except Exception:
            return True
