"""
belief_revision.py — OX-BELIEF-REVISION-1 BELIEF REVISION PROTOCOL (read-only)
==============================================================================
Detect when accumulated RECENT evidence contradicts a previously PROMOTED belief
— i.e. the House is over-confident relative to how things are now going. Builds
on MetaLearning, Exploration, Causal Discovery and Curiosity.

DETECTION ONLY. No promotion, no demotion, no weight changes, no autonomous
correction. It surfaces drift as recall context; humans / later protocols decide.

Belief sources:
  1. Promoted MetaLearning strategies   (confidence + gap_type)
  2. Promoted Causal hypotheses          (confidence + factor + gap_type)
  3. High-confidence capabilities        (confidence >= HIGH_CONF_CAP)

Belief drift = belief_confidence − recent_success_rate (the contradiction gap).
Severity:
  gap > 0.40 → high · gap >= 0.20 → medium · gap >= 0.10 → low · else stable

  NOTE: the mission brief's table reads ">0.25 → medium", but its Validation B
  (belief 0.80, recent 0.60, gap 0.20 → MEDIUM) requires the medium threshold to
  be 0.20. The two are inconsistent; the concrete validation is treated as
  authoritative, so medium begins at 0.20.

An UNSUPPORTED belief (fewer than MIN_RECENT recent observations) is IGNORED —
drift cannot be assessed without recent evidence.

Owns no state. Pure read-model over the existing record stores.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

HIGH_CONF_CAP = 0.80     # a capability is a "belief" once this confident
RECENT_WINDOW = 20       # how many recent observations count as "recent"
MIN_RECENT = 3           # need at least this many to assess drift (else ignored)


def severity(gap: float) -> Optional[str]:
    if gap > 0.40:
        return "high"
    if gap >= 0.20:
        return "medium"
    if gap >= 0.10:
        return "low"
    return None           # within tolerance → stable


# ── single-belief assessment ─────────────────────────────────────────────────
def assess(belief: str, confidence: float, recent_success: Optional[float],
           recent_n: int, min_recent: int = MIN_RECENT) -> Optional[Dict[str, Any]]:
    """Assess one belief against recent evidence. Returns an insight dict, or
    None when unsupported (too little recent evidence → ignored)."""
    if recent_success is None or recent_n < min_recent:
        return None
    gap = round(float(confidence) - float(recent_success), 3)
    sev = severity(gap)
    return {
        "belief": belief,
        "confidence": round(float(confidence), 3),
        "recent_success": round(float(recent_success), 3),
        "contradiction": gap,
        "recent_n": recent_n,
        "severity": sev,
        "status": "belief_drift" if sev else "stable",
    }


# ── recent-evidence helpers (over the existing record stores) ────────────────
def _recent(records: List[Dict[str, Any]], window: int) -> List[Dict[str, Any]]:
    return list(records or [])[-window:]


def _gap_success(episodes, gap_type, window=RECENT_WINDOW):
    rows = [e for e in (episodes or []) if e.get("gap_type") == gap_type]
    rows = _recent(rows, window)
    n = len(rows)
    if not n:
        return None, 0
    s = sum(1 for e in rows if e.get("knowledge_found"))
    return s / n, n


def _factor_success(episodes, gap_type, factor, window=RECENT_WINDOW):
    want = factor.split(":", 1)[1] if ":" in factor else factor
    rows = [e for e in (episodes or []) if e.get("gap_type") == gap_type
            and want in (e.get("sources_checked") or [])]
    rows = _recent(rows, window)
    n = len(rows)
    if not n:
        return None, 0
    s = sum(1 for e in rows if e.get("knowledge_found"))
    return s / n, n


def _cap_success(attributions, cap_name, window=RECENT_WINDOW):
    rows = [a for a in (attributions or []) if cap_name in (a.get("recalled_capabilities") or [])]
    rows = _recent(rows, window)
    n = len(rows)
    if not n:
        return None, 0
    s = sum(1 for a in rows if a.get("outcome") == "success")
    return s / n, n


# ── full belief review ────────────────────────────────────────────────────────
def review(strategies: Optional[Dict[str, Any]] = None,
           hypotheses: Optional[Dict[str, Any]] = None,
           capabilities: Optional[List[Dict[str, Any]]] = None,
           episodes: Optional[List[Dict[str, Any]]] = None,
           attributions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Assess every promoted belief against recent evidence. Returns
    {strengths, stable, belief_drift}. Unsupported beliefs are ignored."""
    if strategies is None:
        try: import metalearning as _ml; strategies = _ml.load_strategies()
        except Exception: strategies = {}
    if hypotheses is None:
        try: import causal as _ca; hypotheses = _ca.load_hypotheses()
        except Exception: hypotheses = {}
    if capabilities is None:
        try:
            import capability_promotion as _cp
            c = _cp.load(); capabilities = list(c.values()) if isinstance(c, dict) else (c or [])
        except Exception: capabilities = []
    if episodes is None:
        try: import acquisition as _aq; episodes = _aq.load_records()
        except Exception: episodes = []
    if attributions is None:
        try: import attribution as _at; attributions = _at.load_records()
        except Exception: attributions = []

    assessed: List[Dict[str, Any]] = []

    for gap_type, st in (strategies or {}).items():
        label = f"{gap_type}: {'→'.join((st.get('recommended_order') or [])[:2])}"
        rs, n = _gap_success(episodes, gap_type)
        r = assess(label, st.get("confidence", 0.0), rs, n)
        if r: r["source"] = "metalearning"; assessed.append(r)

    for gap_type, hyps in (hypotheses or {}).items():
        for h in (hyps or []):
            rs, n = _factor_success(episodes, gap_type, h.get("factor", ""))
            r = assess(h.get("hypothesis", h.get("factor", "?")), h.get("confidence", 0.0), rs, n)
            if r: r["source"] = "causal"; assessed.append(r)

    for c in (capabilities or []):
        if c.get("polarity") == "warning" or float(c.get("confidence", 0) or 0) < HIGH_CONF_CAP:
            continue
        rs, n = _cap_success(attributions, c.get("name", ""))
        r = assess(c.get("name", "?"), c.get("confidence", 0.0), rs, n)
        if r: r["source"] = "capability"; assessed.append(r)

    drift = [a for a in assessed if a["status"] == "belief_drift"]
    stable = [a for a in assessed if a["status"] == "stable"]
    strengths = [a for a in stable if a["confidence"] >= HIGH_CONF_CAP
                 and a["recent_success"] >= HIGH_CONF_CAP]
    _rank = {"high": 0, "medium": 1, "low": 2}
    drift.sort(key=lambda a: _rank.get(a["severity"], 3))
    return {"strengths": strengths, "stable": stable, "belief_drift": drift}


# ── recall / metrics ─────────────────────────────────────────────────────────
def render_brief(rev: Optional[Dict[str, Any]] = None) -> str:
    rev = rev if rev is not None else review()
    drift = rev.get("belief_drift", [])
    strong = rev.get("strengths", [])
    if not drift and not strong:
        return ""
    L = ["## BELIEF REVISION (recent evidence vs promoted beliefs — awareness only):"]
    if strong:
        L.append("  HOLDING UP: " + ", ".join(
            f"{a['belief']}({a['recent_success']})" for a in strong[:4]))
    for a in drift[:5]:
        L.append(f"  ⚠ DRIFT [{a['severity']}]: {a['belief']} — "
                 f"believed {a['confidence']} but recent {a['recent_success']} "
                 f"(gap {a['contradiction']}, n={a['recent_n']})")
    return "\n".join(L)


def metrics(rev: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rev = rev if rev is not None else review()
    by_sev: Dict[str, int] = {}
    for a in rev.get("belief_drift", []):
        by_sev[a["severity"]] = by_sev.get(a["severity"], 0) + 1
    return {
        "beliefs_assessed": len(rev.get("belief_drift", [])) + len(rev.get("stable", [])),
        "drift_count": len(rev.get("belief_drift", [])),
        "drift_by_severity": by_sev,
        "strength_count": len(rev.get("strengths", [])),
    }
