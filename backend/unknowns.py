"""
unknowns.py — OX-UNKNOWNS-1 STRATEGIC UNKNOWN MAPPING (read-only)
=================================================================
Map the House's epistemic state into the strategic-unknowns matrix:

  KNOWN KNOWNS     things we know AND know we know — well-calibrated, strong
  KNOWN UNKNOWNS   things we know we don't know — surfaced gaps, open questions,
                   contradicted beliefs
  UNKNOWN UNKNOWNS the dangerous ones — zero-evidence blind spots (only surfaced
                   via the reference vocabulary) and OVERCONFIDENT surprises
                   (reality contradicted a strong belief → we didn't know we
                   didn't know)

Builds on Curiosity / Research Agenda / Calibration / Belief Revision. Read-only
— no autonomy, no scheduling, no behavior change.

Owns no state. Pure read-model.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _dedup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for it in items:
        k = str(it.get("item", ""))
        if k and k not in seen:
            seen.add(k)
            out.append(it)
    return out


# ── mapping ────────────────────────────────────────────────────────────────--
def analyze(curiosity_insights: Optional[List[Dict[str, Any]]] = None,
            strengths: Optional[List[Dict[str, Any]]] = None,
            agenda: Optional[List[Dict[str, Any]]] = None,
            calibration: Optional[List[Dict[str, Any]]] = None,
            drifts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Classify the epistemic state into known-knowns / known-unknowns /
    unknown-unknowns. Defaults load from the stores."""
    if curiosity_insights is None or strengths is None:
        try:
            import curiosity as _cu
            if curiosity_insights is None: curiosity_insights = _cu.scan()
            if strengths is None: strengths = _cu.strengths()
        except Exception:
            curiosity_insights = curiosity_insights or []; strengths = strengths or []
    if agenda is None:
        try: import research_agenda as _ra; agenda = _ra.form()
        except Exception: agenda = []
    if calibration is None:
        try: import calibration as _cal; calibration = _cal.calibrate()
        except Exception: calibration = []
    if drifts is None:
        try: import belief_revision as _br; drifts = _br.review().get("belief_drift", [])
        except Exception: drifts = []

    kk: List[Dict[str, Any]] = []
    ku: List[Dict[str, Any]] = []
    uu: List[Dict[str, Any]] = []

    # calibration: matched prediction = known known; surprise = unknown unknown;
    # underconfidence = a known uncertainty
    for c in (calibration or []):
        st = c.get("status")
        subj = c.get("subject", "?")
        if st == "calibrated":
            kk.append({"item": subj, "source": "calibration",
                       "reason": "prediction matches observation", "error": c.get("error")})
        elif st == "overconfident":
            uu.append({"item": subj, "source": "calibration",
                       "reason": "confidently wrong — reality contradicted a strong belief",
                       "error": c.get("error")})
        elif st == "underconfident":
            ku.append({"item": subj, "source": "calibration",
                       "reason": "we underrate this — a known uncertainty", "error": c.get("error")})

    # curiosity: zero-evidence high-severity = unknown unknown; thin = known unknown
    for i in (curiosity_insights or []):
        tgt = i.get("target", "?")
        if i.get("severity") == "high" and int(i.get("evidence_count", 0) or 0) == 0:
            uu.append({"item": tgt, "source": "curiosity",
                       "reason": i.get("reason", "no evidence — never explored"), "severity": "high"})
        else:
            ku.append({"item": tgt, "source": "curiosity",
                       "reason": i.get("reason", "underexplored"), "severity": i.get("severity")})

    # curiosity strengths = known knowns
    for s in (strengths or []):
        kk.append({"item": s.get("target", "?"), "source": "curiosity",
                   "reason": "well-explored, strong evidence", "evidence": s.get("evidence_count")})

    # research agenda = explicit open questions (known unknowns)
    for r in (agenda or []):
        ku.append({"item": r.get("topic", "?"), "source": "research_agenda",
                   "reason": "prioritised open question", "priority": r.get("priority_score")})

    # belief drift = a belief we now know is contradicted (known unknown)
    for d in (drifts or []):
        ku.append({"item": d.get("belief", "?"), "source": "belief_revision",
                   "reason": "belief contradicted by recent evidence", "severity": d.get("severity")})

    return {"known_knowns": _dedup(kk), "known_unknowns": _dedup(ku),
            "unknown_unknowns": _dedup(uu)}


# ── recall / metrics ─────────────────────────────────────────────────────────
def render_brief(state: Optional[Dict[str, Any]] = None) -> str:
    state = state if state is not None else analyze()
    kk, ku, uu = state["known_knowns"], state["known_unknowns"], state["unknown_unknowns"]
    if not (kk or ku or uu):
        return ""
    L = ["## STRATEGIC UNKNOWNS (epistemic self-map — awareness only):"]
    if kk:
        L.append("  KNOWN KNOWNS: " + ", ".join(i["item"] for i in kk[:4]))
    if ku:
        L.append("  KNOWN UNKNOWNS: " + ", ".join(i["item"] for i in ku[:4]))
    if uu:
        L.append("  ⚠ UNKNOWN UNKNOWNS (watch these): " + ", ".join(i["item"] for i in uu[:4]))
    return "\n".join(L)


def metrics(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = state if state is not None else analyze()
    kk, ku, uu = len(state["known_knowns"]), len(state["known_unknowns"]), len(state["unknown_unknowns"])
    total = kk + ku + uu
    return {
        "known_knowns": kk,
        "known_unknowns": ku,
        "unknown_unknowns": uu,
        "total": total,
        "known_ratio": round(kk / total, 3) if total else None,
    }
