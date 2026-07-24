"""
engines/learning_engine.py — Learning Engine
============================================
Single responsibility: after missions, turn a decision/outcome HISTORY into structured
lessons. Deterministic aggregation over the history list (no model, no RNG) — the same
history yields the same LearningReport (replayable learning).

History item shape (produced by the Learning service):
    {"action_id", "chosen": bool, "predicted": float, "actual": float,
     "goals": [goal_id...], "accepted": bool, "policy": str, "confidence": float}

Outputs:
  · successful_patterns  — actions whose actual met/beat prediction and were accepted
  · failed_patterns      — actions rejected, or whose actual fell short of prediction
  · tradeoff_analysis    — where high confidence still under-delivered (calibration gaps)
  · policy_improvements   — concrete, evidence-backed suggestions
  · decision lessons      — one Lesson per notable finding

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..contracts import Lesson, LearningReport

_SHORTFALL = 0.1     # relative shortfall threshold that counts as "failed to deliver"


class LearningEngine:
    name = "default"

    def learn(self, history: List[Dict[str, Any]]) -> LearningReport:
        successful: List[str] = []
        failed: List[str] = []
        tradeoffs: List[str] = []
        policy: List[str] = []
        lessons: List[Lesson] = []

        calib_gap = 0
        n_conf = 0
        by_policy: Dict[str, List[bool]] = {}

        for h in sorted(history, key=lambda x: str(x.get("action_id", ""))):
            aid = str(h.get("action_id", "?"))
            predicted = _num(h.get("predicted"))
            actual = _num(h.get("actual"))
            accepted = bool(h.get("accepted", True))
            conf = _num(h.get("confidence")) or 0.0
            pol = str(h.get("policy", "unknown"))

            delivered = None
            if predicted is not None and actual is not None:
                denom = abs(predicted) + 1e-9
                delivered = actual >= predicted - _SHORTFALL * denom

            if not accepted:
                failed.append(aid)
                lessons.append(Lesson("failed_pattern", f"'{aid}' was rejected in review",
                                      {"reason": "review-rejected"}))
            elif delivered is False:
                failed.append(aid)
                lessons.append(Lesson("failed_pattern",
                                      f"'{aid}' under-delivered (predicted {predicted}, actual {actual})",
                                      {"predicted": predicted, "actual": actual}))
                if conf >= 0.7:
                    calib_gap += 1
                    tradeoffs.append(f"'{aid}': high confidence {conf:.2f} but under-delivered")
            elif delivered is True:
                successful.append(aid)
                lessons.append(Lesson("successful_pattern",
                                      f"'{aid}' met/beat prediction (predicted {predicted}, actual {actual})",
                                      {"predicted": predicted, "actual": actual}))

            if conf:
                n_conf += 1
            by_policy.setdefault(pol, []).append(bool(delivered))

        # policy improvements — evidence-backed
        for pol, results in sorted(by_policy.items()):
            hit = sum(1 for r in results if r)
            if results and hit / len(results) < 0.5:
                policy.append(f"policy '{pol}' delivered on {hit}/{len(results)} decisions — "
                              f"consider an alternative policy or tighter confidence gating")
        if n_conf and calib_gap / max(n_conf, 1) > 0.25:
            policy.append("confidence is over-optimistic on >25% of high-confidence actions — "
                          "recalibrate estimated_confidence or raise confidence_threshold")

        return LearningReport(
            lessons=lessons,
            successful_patterns=sorted(set(successful)),
            failed_patterns=sorted(set(failed)),
            tradeoff_analysis=tradeoffs,
            policy_improvements=policy)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
