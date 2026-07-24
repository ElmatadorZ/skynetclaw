"""
house_cognition.py — HOUSE MIND V2 cognitive-state projection (Phase 3B)
========================================================================
A THIN read-model over house_state (the authoritative source of truth) that
assembles the operator-facing HouseCognitiveState and emits change events on
the existing Runtime Event Bus.

It GENERATES NOTHING. Every field is read verbatim from house_state items that
were themselves populated from real council evidence/reasoning, or from active
execution state (the scheduler). When house_state knows nothing, every field is
blank — the House is honest: "unknown" is better than invented.

Provenance per field (all real, audited in Phase 3A):
  known        ← house_state known_fact  ← analyst.known (evidence)
  unknown      ← unknown_fact + open_question ← analyst.unknown / data_gaps
  hypotheses   ← hypothesis              ← forecaster.scenario
  beliefs      ← belief                  ← aggregate_recommendation (evolution logged)
  confidence   ← house_state.confidence  ← _recompute_confidence (evidence-based)
  next_action  ← scheduler.pending()     ← active execution state (blank if none)
  mission      ← house_state.question / status

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import house_state as _hs

try:
    import scheduler as _sched
    _SCHED = True
except Exception:
    _SCHED = False

# Last emitted snapshot per House state, for change-diffing. Keyed by state_id
# so concurrent missions never share a baseline (Mission A's deltas cannot be
# suppressed or triggered by Mission B). Resets on process restart (a fresh
# process re-emits each state's current snapshot once — correct for new clients).
_LAST: Dict[str, Dict[str, Any]] = {}


def _next_action() -> Dict[str, Any]:
    """Next action from ACTIVE EXECUTION STATE only (scheduler pending jobs).
    Returns {} when nothing is scheduled — never invents an action."""
    if not _SCHED:
        return {}
    try:
        pend = _sched.pending() or []
    except Exception:
        return {}
    if not pend:
        return {}
    soonest = min(pend, key=lambda j: j.get("run_at", 9e18))
    return {"action": soonest.get("kind", ""), "run_at": soonest.get("run_at"),
            "source": "scheduler"}


def snapshot(path: Optional[str] = None) -> Dict[str, Any]:
    """Assemble the House cognitive state from house_state (read-only).
    Empty/blank when the House genuinely knows nothing."""
    empty = {
        "mission": "", "status": "", "state_id": "",
        "known": [], "unknown": [], "hypotheses": [], "beliefs": [],
        "confidence": 0.0, "next_action": _next_action(), "last_update": 0.0,
    }
    try:
        st = _hs.current(path)
    except Exception:
        st = None
    if not st:
        return empty
    try:
        ans = _hs.answer(st["id"], path) or {}
    except Exception:
        return empty
    return {
        "mission": ans.get("question", ""),
        "status": st.get("status", ""),
        "state_id": st["id"],
        "known": list(ans.get("what_we_know", []) or []),
        "unknown": list(ans.get("what_we_dont_know", []) or []),
        "hypotheses": [h.get("hypothesis", "") for h in (ans.get("hypotheses", []) or [])
                       if h.get("hypothesis")],
        "beliefs": [{"belief": b.get("belief", ""), "confidence": b.get("confidence", 0.0)}
                    for b in (ans.get("what_we_believe", []) or []) if b.get("belief")],
        "confidence": float(ans.get("overall_confidence", 0.0) or 0.0),
        "next_action": _next_action(),
        "last_update": st.get("updated_at") or st.get("created_at") or 0.0,
    }


def diff_and_emit(publish: Callable[..., Any], path: Optional[str] = None) -> List[tuple]:
    """Diff the current snapshot against the last-emitted one and publish
    house_* events for GENUINE changes only. `publish(type, payload, source)`.
    Returns the list of (type, payload) emitted. Generates nothing — if a field
    did not change in house_state, no event fires."""
    snap = snapshot(path)
    _key = snap.get("state_id", "")          # per-state baseline — concurrent-safe
    prev = _LAST.get(_key) or {}
    emitted: List[tuple] = []

    def emit(etype: str, payload: Dict[str, Any]) -> None:
        try:
            publish(etype, {**payload, "state_id": snap.get("state_id", "")}, source="house")
        except Exception:
            pass
        emitted.append((etype, payload))

    prev_known = set(prev.get("known", []))
    for k in snap["known"]:
        if k not in prev_known:
            emit("house_known_added", {"item": k})

    prev_unknown = set(prev.get("unknown", []))
    for u in snap["unknown"]:
        if u not in prev_unknown:
            emit("house_unknown_added", {"item": u})

    prev_hyp = set(prev.get("hypotheses", []))
    for hy in snap["hypotheses"]:
        if hy not in prev_hyp:
            emit("house_hypothesis_added", {"item": hy})

    new_belief = snap["beliefs"][0]["belief"] if snap["beliefs"] else ""
    old_beliefs = prev.get("beliefs", [])
    old_belief = old_beliefs[0]["belief"] if old_beliefs else ""
    if new_belief and new_belief != old_belief:
        emit("house_belief_updated",
             {"belief": new_belief, "confidence": snap["beliefs"][0]["confidence"]})

    oc = round(float(prev.get("confidence", 0.0)), 3)
    nc = round(float(snap["confidence"]), 3)
    if nc != oc:
        emit("house_confidence_changed", {"from": oc, "to": nc})

    na_new = (snap.get("next_action") or {}).get("action", "")
    na_old = (prev.get("next_action") or {}).get("action", "")
    if na_new != na_old:
        emit("house_next_action_changed", {"next_action": snap.get("next_action") or {}})

    _LAST[_key] = snap
    return emitted


# ── OX-1.7 COGNITIVE HOUSE MIND ─────────────────────────────────────────────
# Reframe the House Mind from a static evidence dump into the five questions an
# operator actually asks of a reasoning mind RIGHT NOW: what is it deciding,
# what does it currently believe, what conflicts, what is at risk, and what it
# will do next. This is a PURE RE-PROJECTION of house_state.answer() — every
# field is verbatim from real state and blank when unknown. It owns NO new state.
_LAST_FRAME: Dict[str, Dict[str, Any]] = {}


def _confidence_level(c: float) -> str:
    if c >= 0.70: return "high"
    if c >= 0.45: return "medium"
    if c >= 0.25: return "low"
    return "critical"


def frame(path: Optional[str] = None) -> Dict[str, Any]:
    """The House Mind reframed as: Current Question / Current Belief /
    Current Conflict / Current Risk / Next Decision. Read-only; generates
    nothing; blank fields when the House genuinely does not know."""
    base = {
        "state_id": "", "current_question": "", "current_belief": {},
        "current_conflict": "", "current_risk": "", "next_decision": _next_action(),
        "confidence": 0.0, "confidence_level": "", "last_update": 0.0,
        "known_count": 0, "unknown_count": 0,
    }
    try:
        st = _hs.current(path)
    except Exception:
        st = None
    if not st:
        return base
    try:
        ans = _hs.answer(st["id"], path) or {}
    except Exception:
        return base

    beliefs = [b for b in (ans.get("what_we_believe") or []) if b.get("belief")]
    top = max(beliefs, key=lambda b: b.get("confidence", 0.0)) if beliefs else {}
    contradictions = ans.get("contradictions") or []
    minority = ans.get("minority_view") or []
    blind = ans.get("blind_spots") or []
    knowns = ans.get("what_we_know") or []
    unknowns = ans.get("what_we_dont_know") or []
    conf = float(ans.get("overall_confidence", 0.0) or 0.0)

    return {
        "state_id": st["id"],
        # OX-UI-1 L1 operator counts (glanceable; the lists themselves are L2)
        "known_count": len(knowns),
        "unknown_count": len(unknowns),
        # what the House is trying to resolve (fall back to the top open unknown)
        "current_question": ans.get("question", "") or (unknowns[0] if unknowns else ""),
        # the strongest current belief (verbatim) + its confidence
        "current_belief": ({"belief": top.get("belief", ""),
                            "confidence": float(top.get("confidence", 0.0) or 0.0)} if top else {}),
        # a REAL contradiction, else a real minority view, else none
        "current_conflict": (contradictions[0] if contradictions
                             else (minority[0] if minority else "")),
        # a REAL blind spot, else the top open unknown, else none
        "current_risk": (blind[0] if blind else (unknowns[0] if unknowns else "")),
        # what the House will actually do next (scheduler) — blank if nothing
        "next_decision": _next_action(),
        "confidence": conf,
        "confidence_level": _confidence_level(conf),
        "last_update": st.get("updated_at") or st.get("created_at") or 0.0,
    }


def frame_render(fr: Optional[Dict[str, Any]] = None, path: Optional[str] = None) -> str:
    """A CURRENT MIND text block (for prompt/UI). Empty when nothing is known."""
    fr = fr if fr is not None else frame(path)
    q = fr.get("current_question", "")
    b = fr.get("current_belief") or {}
    if not (q or b or fr.get("current_conflict") or fr.get("current_risk")):
        return ""
    L = ["## CURRENT MIND (the House's reasoning state right now):"]
    if q:
        L.append(f"  ❓ Question: {q}")
    if b.get("belief"):
        L.append(f"  💡 Belief:   {b['belief']}  (confidence {round(float(b.get('confidence',0.0)),2)} · {fr.get('confidence_level','')})")
    if fr.get("current_conflict"):
        L.append(f"  ⚡ Conflict: {fr['current_conflict']}")
    if fr.get("current_risk"):
        L.append(f"  ⚠ Risk:     {fr['current_risk']}")
    nd = fr.get("next_decision") or {}
    if nd.get("action"):
        L.append(f"  ➡ Next:     {nd['action']}")
    return "\n".join(L)


def frame_diff_and_emit(publish: Callable[..., Any], path: Optional[str] = None) -> List[tuple]:
    """Emit a `house_frame` event when the cognitive frame changes. Keyed by
    state_id (concurrent-safe). Generates nothing — fires only on real change."""
    fr = frame(path)
    key = fr.get("state_id", "")
    prev = _LAST_FRAME.get(key) or {}
    emitted: List[tuple] = []
    # change = any of the five cognitive fields (or confidence) moved
    sig_fields = ("current_question", "current_belief", "current_conflict",
                  "current_risk", "next_decision", "confidence")
    changed = any(fr.get(f) != prev.get(f) for f in sig_fields)
    if changed and (fr.get("current_question") or fr.get("current_belief")):
        try:
            publish("house_frame", {**fr}, source="house")
        except Exception:
            pass
        emitted.append(("house_frame", fr))
    _LAST_FRAME[key] = fr
    return emitted


def reset() -> None:
    """Clear the diff baseline (test/maintenance hook)."""
    global _LAST, _LAST_FRAME
    _LAST = {}
    _LAST_FRAME = {}
