"""
paradigm.py — OX-PARADIGM-1 PARADIGM EVOLUTION PROTOCOL (read-only)
==================================================================
Track the House's dominant theoretical FRAMEWORKS and how they evolve (Kuhn-
style): a broad, confident theory with no anomalies is a STABLE PARADIGM; when
anomalies accumulate against a dominant theory (recent drift, overconfident
surprises, unknown-unknowns), it is a PARADIGM SHIFT in progress; an emerging
theory not yet dominant is a PARADIGM CANDIDATE.

Builds on Theory / Belief Revision / Calibration / Unknowns. Read-only — no
autonomy, no scheduling, no behavior change. It observes the structure of the
House's knowledge; it does not change it.

Owns no state. Pure read-model.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

PARADIGM_DOMAINS = 3      # dominant frameworks generalize broadly
PARADIGM_CONF = 0.80      # ...and confidently


def _toks(s: str) -> set:
    return set(re.findall(r"[a-z0-9_]+", (s or "").lower()))


def _matches(pattern: str, obj: Dict[str, Any], text_field: str) -> bool:
    p = pattern.lower()
    if obj.get("pattern"):
        return str(obj["pattern"]).lower() == p
    return p in _toks(obj.get(text_field, ""))


# ── anomaly detection (pressure against a paradigm) ──────────────────────────
def _anomalies(pattern: str, drifts, calibration, uu_items) -> List[str]:
    out: List[str] = []
    if any(_matches(pattern, d, "belief") for d in (drifts or [])):
        out.append("recent belief drift")
    if any(c.get("status") == "overconfident" and _matches(pattern, c, "subject")
           for c in (calibration or [])):
        out.append("overconfident surprise")
    if any(_matches(pattern, u, "item") for u in (uu_items or [])):
        out.append("unknown-unknown surfaced")
    return out


# ── evolution ─────────────────────────────────────────────────────────────────
def evolve(theories: Optional[List[Dict[str, Any]]] = None,
           drifts: Optional[List[Dict[str, Any]]] = None,
           calibration: Optional[List[Dict[str, Any]]] = None,
           unknowns_state: Optional[Dict[str, Any]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Classify theories into stable paradigms / shifts / candidates. Defaults
    load from the stores."""
    if theories is None:
        try: import theory as _th; theories = _th.form()
        except Exception: theories = []
    if drifts is None:
        try: import belief_revision as _br; drifts = _br.review().get("belief_drift", [])
        except Exception: drifts = []
    if calibration is None:
        try: import calibration as _cal; calibration = _cal.calibrate()
        except Exception: calibration = []
    if unknowns_state is None:
        try: import unknowns as _un; unknowns_state = _un.analyze()
        except Exception: unknowns_state = {}
    uu_items = (unknowns_state or {}).get("unknown_unknowns", [])

    stable: List[Dict[str, Any]] = []
    shifts: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []

    for t in (theories or []):
        pat = t.get("pattern", "?")
        breadth = len(t.get("supporting_domains", []))
        conf = float(t.get("confidence", 0) or 0)
        anomalies = _anomalies(pat, drifts, calibration, uu_items)
        dominant = breadth >= PARADIGM_DOMAINS and conf >= PARADIGM_CONF
        rec = {
            "paradigm": t.get("theory", pat),
            "pattern": pat,
            "breadth": breadth,
            "confidence": round(conf, 3),
            "supporting_domains": t.get("supporting_domains", []),
            "anomalies": anomalies,
        }
        if dominant and anomalies:
            rec["status"] = "paradigm_shift"
            shifts.append(rec)
        elif dominant:
            rec["status"] = "stable_paradigm"
            stable.append(rec)
        else:
            rec["status"] = "paradigm_candidate"
            candidates.append(rec)

    stable.sort(key=lambda r: (r["breadth"], r["confidence"]), reverse=True)
    shifts.sort(key=lambda r: (len(r["anomalies"]), r["breadth"]), reverse=True)
    candidates.sort(key=lambda r: (r["breadth"], r["confidence"]), reverse=True)
    return {"stable_paradigms": stable, "paradigm_shifts": shifts,
            "paradigm_candidates": candidates}


# ── recall / metrics ─────────────────────────────────────────────────────────
def render_brief(state: Optional[Dict[str, Any]] = None) -> str:
    state = state if state is not None else evolve()
    stable, shifts, cands = (state["stable_paradigms"], state["paradigm_shifts"],
                             state["paradigm_candidates"])
    if not (stable or shifts or cands):
        return ""
    L = ["## PARADIGMS (dominant frameworks + their evolution — awareness only):"]
    for r in shifts[:3]:
        L.append(f"  ⚠ SHIFTING: {r['paradigm']} — anomalies: {', '.join(r['anomalies'])}")
    for r in stable[:3]:
        L.append(f"  ▣ STABLE: {r['paradigm']} (breadth {r['breadth']}, conf {r['confidence']})")
    for r in cands[:3]:
        L.append(f"  • EMERGING: {r['paradigm']} (breadth {r['breadth']}, conf {r['confidence']})")
    return "\n".join(L)


def metrics(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = state if state is not None else evolve()
    return {
        "stable_paradigms": len(state["stable_paradigms"]),
        "paradigm_shifts": len(state["paradigm_shifts"]),
        "paradigm_candidates": len(state["paradigm_candidates"]),
        "shifting": [r["pattern"] for r in state["paradigm_shifts"]][:5],
        "stable": [r["pattern"] for r in state["stable_paradigms"]][:5],
    }
