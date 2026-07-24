"""
control_engine.py — OX-CONTROL-1 ADAPTIVE CONTROL ENGINE
========================================================
FIRST PRINCIPLE: a self-improving system needs Measure → Decide → Adjust. The
House could MEASURE (OX-TELEMETRY-1) but stopped there — telemetry was a sensor,
not a controller. This engine closes the Telemetry → Adjustment loop: it consumes
a telemetry scorecard and DECIDES recommended adjustment actions + a structured
policy that the existing recall/promotion paths can apply.

It does NOT redesign telemetry, learning, capability promotion or runtime. It only
produces adjustments within the permitted surface:
  • recommendation weights   • recall priority
  • lesson priority          • capability priority   (incl. promotion threshold)
It may NOT rewrite code, modify runtime, create tools, or change governance.
(Per OX-CONTROL-1: no attribution, no self-initiation here.)

Decision schema:
  {
    "verdict": "regressing",
    "recommended_actions": ["...", "..."],
    "reason": "...",
    "policy": { ...adjustment knobs the recall/promotion paths read... },
    "score": -0.31, "timestamp": 1.0
  }

Policy knobs (all within the permitted surface):
  promotion_conf_delta   float  — added to the capability promotion threshold
  capability_recall_order "warnings_first"|"proven_first"|"default"
  lesson_recall_focus    "recovery"|"validated"|"default"
  reinforce_proven       bool
  hold                   bool   — observe, do not adjust

Owns only control_history.json (verdict/action/timestamp — for FUTURE attribution).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE = Path(__file__).parent / "control_history.json"

# bound the threshold nudge so the controller can never destabilize promotion
_MAX_CONF_DELTA = 0.10


def _neutral_policy() -> Dict[str, Any]:
    return {"promotion_conf_delta": 0.0, "capability_recall_order": "default",
            "lesson_recall_focus": "default", "reinforce_proven": False, "hold": True}


# ── DECIDE: verdict (+ drivers) → recommended actions + policy ────────────────
def decide(scorecard: Dict[str, Any]) -> Dict[str, Any]:
    """Map a telemetry scorecard to corrective/reinforcing actions + a policy."""
    sc = scorecard or {}
    verdict = sc.get("verdict", "insufficient_data")
    score = sc.get("score", 0.0)
    drivers = sc.get("drivers", []) or []
    n = sc.get("n_runs", 0)
    drv = (" drivers: " + ", ".join(drivers)) if drivers else ""

    if verdict == "regressing":
        actions = [
            "increase warning-capability priority",
            "reduce unstable-capability weight",
            "surface recovery lessons earlier",
            "raise confidence threshold for promotion",
        ]
        policy = {"promotion_conf_delta": +0.05, "capability_recall_order": "warnings_first",
                  "lesson_recall_focus": "recovery", "reinforce_proven": False, "hold": False}
        reason = (f"Outcomes are declining (score {score:+g} over {n} runs;{drv}). "
                  "Lead with warnings, surface recovery, and tighten promotion until the trend recovers.")
    elif verdict == "improving":
        actions = [
            "reinforce successful capabilities",
            "prioritize proven execution paths",
            "increase confidence in validated lessons",
        ]
        policy = {"promotion_conf_delta": 0.0, "capability_recall_order": "proven_first",
                  "lesson_recall_focus": "validated", "reinforce_proven": True, "hold": False}
        reason = (f"Outcomes are improving (score {score:+g} over {n} runs;{drv}). "
                  "Reinforce what works — prefer proven capabilities and validated lessons.")
    elif verdict == "flat":
        actions = [
            "maintain current strategy",
            "observe another window before adjusting",
        ]
        policy = _neutral_policy()
        reason = (f"Outcomes are stable (score {score:+g} over {n} runs). "
                  "Hold strategy and observe — do not overreact to noise.")
    else:  # insufficient_data
        actions = ["gather more runs before adjusting"]
        policy = _neutral_policy()
        reason = f"Not enough runs ({n}) to judge a trend. Keep operating; revisit once data accrues."

    return {"verdict": verdict, "recommended_actions": actions, "reason": reason,
            "policy": policy, "score": score, "timestamp": time.time()}


# ── CONTROL HISTORY (verdict / actions / timestamp — for future attribution) ──
def record(decision: Dict[str, Any], path: Optional[Path] = None, keep: int = 200) -> None:
    p = path or _STORE
    try:
        hist = load_history(p)
        hist.append({"timestamp": decision.get("timestamp", time.time()),
                     "verdict": decision.get("verdict"),
                     "score": decision.get("score"),
                     "recommended_actions": decision.get("recommended_actions", []),
                     "reason": decision.get("reason", ""),
                     "policy": decision.get("policy", {})})
        hist = hist[-keep:]
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "history": hist}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[ControlEngine] record failed: {e}")


def load_history(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or _STORE
    try:
        if p.exists():
            return (json.loads(p.read_text(encoding="utf-8")) or {}).get("history", [])
    except Exception:
        pass
    return []


def latest(path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    hist = load_history(path)
    return hist[-1] if hist else None


def latest_policy(path: Optional[Path] = None) -> Dict[str, Any]:
    d = latest(path)
    return (d or {}).get("policy") or _neutral_policy()


def decide_and_record(scorecard: Dict[str, Any], path: Optional[Path] = None) -> Dict[str, Any]:
    d = decide(scorecard)
    record(d, path)
    return d


# ── ADJUST helpers (the permitted control surface) ───────────────────────────
def adjusted_promotion_threshold(base: float, policy: Optional[Dict[str, Any]] = None,
                                 path: Optional[Path] = None) -> float:
    """Apply the policy's promotion-threshold nudge (bounded)."""
    pol = policy if policy is not None else latest_policy(path)
    delta = max(-_MAX_CONF_DELTA, min(_MAX_CONF_DELTA, float(pol.get("promotion_conf_delta", 0.0) or 0.0)))
    return round(max(0.5, min(0.95, base + delta)), 3)


def reorder_capabilities(caps: List[Dict[str, Any]],
                         policy: Optional[Dict[str, Any]] = None,
                         path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Apply capability recall PRIORITY from the policy (does not add/remove —
    only reorders what recall already surfaced)."""
    pol = policy if policy is not None else latest_policy(path)
    order = pol.get("capability_recall_order", "default")
    if order == "warnings_first":
        return sorted(caps, key=lambda c: c.get("polarity") != "warning")
    if order == "proven_first":
        return sorted(caps, key=lambda c: c.get("polarity") != "capability")
    return caps


# ── prompt rendering — the CONTROL DIRECTIVE injected at run-start ───────────
def render_brief(decision: Dict[str, Any]) -> str:
    """A trend-based directive telling the agent how to WEIGH recalled knowledge.
    Empty for insufficient_data (nothing to direct yet)."""
    if not decision:
        return ""
    v = decision.get("verdict")
    if v == "insufficient_data":
        return ""
    head = {"regressing": "verdict REGRESSING — correct course",
            "improving": "verdict IMPROVING — reinforce",
            "flat": "verdict FLAT — hold & observe"}.get(v, v)
    L = [f"## ADAPTIVE CONTROL ({head}):"]
    if v == "regressing":
        L += ["  • Lead with WARNING capabilities; treat unstable capabilities as cautions.",
              "  • Surface RECOVERY lessons before others; recover earlier.",
              "  • Hold a higher bar before trusting newly-promoted capabilities."]
    elif v == "improving":
        L += ["  • Reinforce PROVEN capabilities and execution paths.",
              "  • Trust validated lessons — keep doing what works."]
    elif v == "flat":
        L += ["  • Maintain the current strategy; observe another window.",
              "  • Do not overreact to noise."]
    return "\n".join(L)
