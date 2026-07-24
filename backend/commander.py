"""
commander.py — OX-EXEC ELITE COMMANDER AUTHORITY (stateless decision)
=====================================================================
ARCHITECTURE LAW:  Council ADVISES.  Commander DECIDES.  Executor ACTS.

The Council may advise, challenge, and estimate risk — it may NOT block
execution. Only the Elite Commander issues a terminal verdict, and ONLY EVIDENCE
may block a mission (not logical doubt, not unknowns, not generated "gaps").

  verdict ∈ { EXECUTE_NOW, HOLD, ABORT }
    EXECUTE_NOW — route to Executor immediately (the default; deliberation's job
                  is to enable action, not prevent it)
    HOLD        — pause and ask the operator (only on high-risk + real evidence,
                  or an explicit operator hold)
    ABORT       — stop (only on evidence the goal is impossible/forbidden)

The Commander AUTOMATICALLY OVERRIDES the council (OX-EXEC-7) when it detects a
planning loop, repeated gaps/clarification, an explicit operator confirmation,
or a low-risk action. A council "REBUILD"/"FRAGILE" verdict is downgraded to
ADVICE — it never halts.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, Optional

EXECUTE_NOW = "EXECUTE_NOW"
HOLD = "HOLD"
ABORT = "ABORT"


def _council_objection(council_verdict: Optional[Dict[str, Any]]) -> str:
    """The council's skeptic verdict (advice only): CONSISTENT|FRAGILE|REBUILD."""
    if not council_verdict:
        return ""
    sk = council_verdict.get("skeptic") or {}
    return str(sk.get("verdict", "") or "").upper()


def decide(policy: Dict[str, Any],
           council_verdict: Optional[Dict[str, Any]] = None,
           plan_cycles: int = 0,
           evidence_block: bool = False,
           operator_hold: bool = False) -> Dict[str, Any]:
    """The terminal verdict. `policy` is execution_policy.classify() output.

    evidence_block — True ONLY when there is real EVIDENCE the action must not
                     proceed (e.g. a verified contradiction / a hard gate), never
                     a mere logical doubt. This is the ONLY thing that can block.
    operator_hold  — the operator explicitly asked to stop/hold.
    """
    risk = (policy or {}).get("risk", "medium")
    route = (policy or {}).get("route", "DELIBERATE")
    action_bias = bool((policy or {}).get("action_bias"))
    objection = _council_objection(council_verdict)
    overrode = False
    reasons = []

    # 1. operator explicitly halts → HOLD (operator authority)
    if operator_hold:
        return {"verdict": HOLD, "reason": "operator requested hold", "overrode_council": False}

    # 1.5 CONSTITUTION (M3): a REJECTED verdict is an institutional decision,
    # not advice — the Constitution enforces, it does not advise. The Commander
    # may act against it ONLY on explicit operator intent, and that act is an
    # override on the record (overrode_council=True), never silent.
    _gov = (council_verdict or {}).get("governance") or {}
    if str(_gov.get("decision", "")).upper() == "REJECTED":
        _rules = ", ".join(sorted({v.get("rule", "?") for v in _gov.get("violations", [])
                                   if str(v.get("severity", "")).lower() == "reject"})) or "R?"
        if action_bias:
            return {"verdict": EXECUTE_NOW,
                    "reason": f"constitution rejected ({_rules}) but operator intent is explicit — overriding on the record",
                    "overrode_council": True}
        return {"verdict": HOLD,
                "reason": f"constitution rejected the verdict ({_rules}) — fix before acting",
                "overrode_council": False}

    # 2. EVIDENCE is the only blocker. High-risk + real evidence → HOLD to confirm.
    if evidence_block:
        if risk == "high":
            return {"verdict": HOLD, "reason": "evidence + high risk — confirm before acting",
                    "overrode_council": objection in ("FRAGILE", "REBUILD")}
        reasons.append("evidence noted but risk not high — proceeding with care")

    # 3. AUTO-OVERRIDE (OX-EXEC-7): explicit intent / low-risk / loop → execute now
    if action_bias:
        overrode = objection in ("FRAGILE", "REBUILD")
        return {"verdict": EXECUTE_NOW, "reason": "explicit operator intent — execute now",
                "overrode_council": overrode}
    if route == "DIRECT_EXECUTE" or risk == "low":
        overrode = objection in ("FRAGILE", "REBUILD")
        return {"verdict": EXECUTE_NOW, "reason": "low-risk / direct action — execute now",
                "overrode_council": overrode}
    if plan_cycles >= 1:
        # OX-EXEC-4: no second planning cycle — Commander forces a terminal choice
        if risk == "high" and evidence_block:
            return {"verdict": ABORT, "reason": "planning loop + high-risk evidence — abort",
                    "overrode_council": True}
        return {"verdict": EXECUTE_NOW,
                "reason": "planning loop detected — no third plan; execute now",
                "overrode_council": objection in ("FRAGILE", "REBUILD")}

    # 4. DELIBERATE path: council advised. Its doubt is ADVICE, not a veto.
    if objection == "REBUILD":
        # downgraded to advice — proceed unless high-risk evidence (handled above)
        return {"verdict": EXECUTE_NOW,
                "reason": "council advises REBUILD (advisory only) — proceeding to execute",
                "overrode_council": True}

    # 5. default — execution primacy
    return {"verdict": EXECUTE_NOW, "reason": "deliberation complete — execute",
            "overrode_council": False}


def render(verdict: Dict[str, Any]) -> str:
    v = (verdict or {}).get("verdict", EXECUTE_NOW)
    icon = {"EXECUTE_NOW": "▶", "HOLD": "⏸", "ABORT": "⛔"}.get(v, "▶")
    ov = "  (council overridden)" if verdict.get("overrode_council") else ""
    return f"{icon} ELITE COMMANDER: {v} — {verdict.get('reason','')}{ov}"
