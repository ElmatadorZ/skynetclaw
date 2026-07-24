"""
execution_policy.py — OX-EXEC EXECUTION PRIMACY (stateless decision core)
=========================================================================
FIRST PRINCIPLE: the purpose of deliberation is EXECUTION. Information exists to
enable action. UNKNOWN IS NOT BLOCKED — only evidence may block a mission.

This module classifies an operator directive into an execution ROUTE and a RISK
level, deterministically and without a model call, so the House executes first,
reasons second, asks last.

  ROUTE:
    DIRECT_EXECUTE — explicit operator intent / low-risk action → bypass council
    STATE_LOOKUP   — pure information retrieval → discover → answer (no reasoning)
    DELIBERATE     — genuinely novel/complex → council ADVISES (never blocks)

  RISK: low | medium | high  (drives the Unknown-≠-Blocked policy)

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

DIRECT_EXECUTE = "DIRECT_EXECUTE"
STATE_LOOKUP = "STATE_LOOKUP"
DELIBERATE = "DELIBERATE"

# ── ACTION BIAS (OX-EXEC-2): explicit intent → execute, do not deliberate ──
# English + Thai operator confirmations actually used in this House.
_ACTION_BIAS = re.compile(
    r"\b(approve|confirm|continue|resume|proceed|go ahead|do it|just do|make it|"
    r"generate( the)?( report| pdf| html| dashboard| graph)?|create( the)?( html| pdf| report| note| file| dashboard)|"
    r"build( the| it)|write( the)? (file|note|report)|save( the)? (note|file)|export|render|ship it)\b",
    re.I)
_ACTION_BIAS_TH = ("ทำเลย", "ต่อเลย", "ต่อไป", "ลงมือ", "เอาเลย", "จัดไป", "ดำเนินการ", "ทำต่อ", "อนุมัติ", "ยืนยัน")
_CONFIRM_SHORT = re.compile(r"^\s*(yes|y|ok|okay|go|continue|proceed|approve|confirm|do it|ต่อ|ทำ|โอเค|ได้)\s*[.!]*\s*$", re.I)

# ── STATE LOOKUP (OX-EXEC-6): retrieval, not reasoning ──
_STATE_LOOKUP = re.compile(
    r"\b(status|progress|checkpoint|history|learning|memory|mission list|missions?|"
    r"what do we know|where are we|recent runs?|what happened|show me the|list the)\b", re.I)
_STATE_LOOKUP_TH = ("สถานะ", "ความคืบหน้า", "ประวัติ", "รายการ", "ถึงไหน", "สรุปสถานะ")

# ── RISK (OX-EXEC-3): only HIGH risk may gate on uncertainty ──
_HIGH_RISK = re.compile(
    r"\b(delete|remove|destroy|drop|wipe|format|rm -rf|overwrite|deploy|publish|push to|"
    r"force push|send (email|message|payment)|pay|charge|transfer|production|prod\b|"
    r"shutdown|kill|terminate|irreversible|credentials?|secret|api key|sudo)\b", re.I)
_LOW_RISK = re.compile(
    r"\b(read|list|show|view|display|get|fetch|summari[sz]e|report|note|analy[sz]e|"
    r"search|describe|explain|compare|draft|preview|generate|create (html|pdf|report|note|dashboard|graph)|render)\b",
    re.I)


def assess_risk(directive: str) -> str:
    t = directive or ""
    if _HIGH_RISK.search(t):
        return "high"
    if _LOW_RISK.search(t):
        return "low"
    return "medium"


def is_action_bias(directive: str) -> bool:
    t = (directive or "").strip()
    if _CONFIRM_SHORT.match(t):
        return True
    if _ACTION_BIAS.search(t):
        return True
    return any(k in t for k in _ACTION_BIAS_TH)


def is_state_lookup(directive: str) -> bool:
    t = directive or ""
    if _STATE_LOOKUP.search(t):
        return True
    return any(k in t for k in _STATE_LOOKUP_TH)


def classify(directive: str) -> Dict[str, Any]:
    """Route + risk for a directive. Execution-first: explicit/low-risk → execute."""
    t = (directive or "").strip()
    risk = assess_risk(t)
    if is_state_lookup(t) and not is_action_bias(t):
        return {"route": STATE_LOOKUP, "risk": risk, "action_bias": False,
                "reason": "information retrieval — discover and answer, no reasoning loop"}
    if is_action_bias(t):
        return {"route": DIRECT_EXECUTE, "risk": risk, "action_bias": True,
                "reason": "explicit operator intent — execute, bypass council"}
    if risk == "low":
        return {"route": DIRECT_EXECUTE, "risk": risk, "action_bias": False,
                "reason": "low-risk action — execute directly, deliberation not warranted"}
    return {"route": DELIBERATE, "risk": risk, "action_bias": False,
            "reason": "novel/elevated-risk — council may advise (it cannot block)"}


# ── UNKNOWN ≠ BLOCKED (OX-EXEC-3) ──
def gap_policy(risk: str, has_unknowns: bool = True) -> Dict[str, Any]:
    """What to do when the mission has open unknowns. Unknown alone never blocks."""
    if not has_unknowns:
        return {"action": "proceed", "reason": "no open unknowns"}
    if risk == "high":
        return {"action": "ask", "reason": "high-risk + unknown — confirm before acting"}
    if risk == "medium":
        return {"action": "proceed_with_warning", "reason": "unknown noted; proceeding (medium risk)"}
    return {"action": "proceed", "reason": "unknown + low risk — proceed; unknown is not a blocker"}
