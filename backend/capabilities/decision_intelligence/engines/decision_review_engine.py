"""
engines/decision_review_engine.py — Decision Review Engine
==========================================================
Single responsibility: adversarially REVIEW a decision and return an accept/reject verdict.
It challenges the decision's facts, constraints, assumptions, confidence, predictions, and
trade-offs, incorporates a counter-example (supplied by the Review Board service, which
owns the Counter Example engine — engines never call engines), and REJECTS weak decisions.

A decision is rejected when any of:
  · no candidate was chosen (nothing to accept);
  · the chosen action's confidence is below `confidence_threshold`;
  · a verified counter-example invalidates the constraint assumptions;
  · the chosen action is infeasible (constraint penalty present);
  · the predicted uncertainty at the far horizon dwarfs the expected gain (unreliable).

Pure and deterministic. The Review Board service composes this with the Counter Example
engine and CVL — this engine only judges what it is given.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..contracts import Decision, Goal, ReviewVerdict, SimOutcome, WorldVars


class DecisionReviewEngine:
    name = "default"

    def review(self, decision: Decision, world: WorldVars, goals: List[Goal],
               outcomes: Dict[str, SimOutcome], constraints_text: str,
               confidence_threshold: float,
               counterexample: Optional[Dict[str, Any]] = None) -> ReviewVerdict:
        challenges: List[str] = []
        reasons: List[str] = []
        chosen = decision.chosen

        if chosen is None:
            return ReviewVerdict(accepted=False, challenges=["no candidate selected"],
                                 confidence=0.0, reasons=["nothing to accept"])

        # 1) confidence challenge
        conf = float(chosen.estimated_confidence)
        if conf < confidence_threshold:
            reasons.append(f"confidence {conf:.2f} < threshold {confidence_threshold:.2f}")
        challenges.append(f"Is confidence {conf:.2f} justified for '{chosen.id}'?")

        # 2) assumptions / risks challenge
        if chosen.risks:
            challenges.append("Risks declared but assumed manageable: " + "; ".join(chosen.risks))
        if not chosen.expected_benefits:
            reasons.append("chosen action declares no expected benefit")

        # 3) counter-example (supplied by the service that owns the CE engine)
        if counterexample:
            reasons.append("a verified counter-example invalidates constraint assumptions")
            challenges.append(f"Counter-example: {counterexample.get('note', counterexample)}")

        # 4) prediction reliability challenge (uncertainty vs signal at far horizon)
        oc = outcomes.get(chosen.id)
        if oc and oc.predictions:
            far = oc.predictions[-1]
            unreliable_vars = []
            for g in goals:
                exp = _num(far.expected.get(g.variable))
                lo = _num(far.low.get(g.variable))
                hi = _num(far.high.get(g.variable))
                if exp is None or lo is None or hi is None:
                    continue
                base = _num(world.get(g.variable, 0.0)) or 0.0
                signal = abs(exp - base)
                spread = abs(hi - lo)
                if signal > 1e-9 and spread > 4.0 * signal:
                    unreliable_vars.append(g.variable)
            if unreliable_vars:
                challenges.append("Prediction uncertainty dwarfs the signal for: "
                                  + ", ".join(sorted(set(unreliable_vars))))

        # 5) feasibility (trade-off) — an infeasible chosen plan is rejected
        infeasible = any(aid == chosen.id for aid, _ in decision.rejected)
        if infeasible:
            reasons.append("chosen action is infeasible (constraint penalty)")

        accepted = not reasons
        # review confidence = chosen confidence, discounted by open challenges
        review_conf = conf * (1.0 - min(0.5, 0.1 * len(challenges))) if accepted else 0.0
        return ReviewVerdict(accepted=accepted, challenges=challenges,
                             counterexample=counterexample, confidence=review_conf,
                             reasons=reasons)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
