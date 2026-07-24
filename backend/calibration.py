"""
calibration.py — OX-CONFIDENCE-1 CONFIDENCE CALIBRATION PROTOCOL (read-only)
===========================================================================
Measure whether PREDICTED confidence matches OBSERVED outcomes — across Decision
recommendations, promoted beliefs (MetaLearning strategies / capabilities) and
First Principles. Surfaces over/under-confidence so the House knows where its
self-assessment can be trusted.

Builds on Decision Framework / Belief Revision / MetaLearning / First Principles.
Read-only — no behavior change, no correction, no weight change, no autonomy.

Calibration Record:
  {subject, type, predicted_confidence, observed_success, recent_n,
   error, status, quality}

Rules:
  error = |predicted - observed|
  error > 0.30 → quality "poor" · > 0.15 → "moderate" · else "calibrated"
  status:  error <= 0.15 → "calibrated"
           else predicted > observed → "overconfident"
           else                      → "underconfident"

A subject with too little observed evidence (< MIN_OBS) is ignored.

Owns no state. Pure read-model over the existing stores.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

CALIBRATED_TOL = 0.15
POOR_TOL = 0.30
MIN_OBS = 3
RECENT_WINDOW = 20


# ── single-subject calibration ───────────────────────────────────────────────
def assess(subject: str, predicted: float, observed: Optional[float],
           recent_n: int = MIN_OBS, type_: str = "belief") -> Optional[Dict[str, Any]]:
    """Compare a predicted confidence to an observed success rate. Returns None
    when there is too little observed evidence to judge."""
    if observed is None or recent_n < MIN_OBS:
        return None
    p, o = float(predicted), float(observed)
    error = round(abs(p - o), 3)
    quality = "poor" if error > POOR_TOL else "moderate" if error > CALIBRATED_TOL else "calibrated"
    if error <= CALIBRATED_TOL:
        status = "calibrated"
    elif p > o:
        status = "overconfident"
    else:
        status = "underconfident"
    return {"subject": subject, "type": type_,
            "predicted_confidence": round(p, 3), "observed_success": round(o, 3),
            "recent_n": recent_n, "error": error, "status": status, "quality": quality}


# ── observed-evidence helpers (recent success rate) ──────────────────────────
def _source_success(episodes, source, window=RECENT_WINDOW):
    rows = [e for e in (episodes or []) if source in (e.get("sources_checked") or [])][-window:]
    n = len(rows)
    if not n:
        return None, 0
    return sum(1 for e in rows if e.get("knowledge_found")) / n, n


# ── full calibration over the epistemic layers ───────────────────────────────
def calibrate(subjects: Optional[List[Dict[str, Any]]] = None,
              beliefs: Optional[List[Dict[str, Any]]] = None,
              decisions: Optional[List[Dict[str, Any]]] = None,
              principles: Optional[List[Dict[str, Any]]] = None,
              episodes: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Assess calibration for every subject. `subjects` (pre-built
    {subject,predicted_confidence,observed_success,recent_n,type}) may be passed
    directly; otherwise gathered from beliefs/decisions/principles + episodes."""
    if subjects is not None:
        recs = [assess(s["subject"], s["predicted_confidence"], s.get("observed_success"),
                       s.get("recent_n", MIN_OBS), s.get("type", "belief")) for s in subjects]
        return [r for r in recs if r]

    # default-gather from the live layers
    if beliefs is None:
        try:
            import belief_revision as _br
            rev = _br.review()
            beliefs = rev.get("stable", []) + rev.get("belief_drift", [])
        except Exception:
            beliefs = []
    if episodes is None:
        try: import acquisition as _aq; episodes = _aq.load_records()
        except Exception: episodes = []
    if decisions is None:
        try: import decision as _dec; decisions = _dec.decide()
        except Exception: decisions = []
    if principles is None:
        try: import first_principles as _fp; principles = _fp.all_principles()
        except Exception: principles = []

    out: List[Dict[str, Any]] = []
    seen = set()
    # beliefs already carry predicted (confidence) vs observed (recent_success)
    for b in beliefs:
        r = assess(b.get("belief", "?"), b.get("confidence", 0.0),
                   b.get("recent_success"), int(b.get("recent_n", 0) or 0), "belief")
        if r and (r["type"], r["subject"]) not in seen:
            seen.add((r["type"], r["subject"])); out.append(r)
    # decisions + principles: observed = recent success of the underlying source
    for d in decisions:
        obs, n = _source_success(episodes, d.get("pattern", ""))
        r = assess(d.get("recommendation", d.get("pattern", "?")), d.get("confidence", 0.0), obs, n, "decision")
        if r: out.append(r)
    for p in principles:
        obs, n = _source_success(episodes, p.get("pattern", ""))
        r = assess(p.get("principle", p.get("pattern", "?")), p.get("confidence", 0.0), obs, n, "principle")
        if r: out.append(r)
    out.sort(key=lambda r: r["error"], reverse=True)
    return out


# ── recall / metrics ─────────────────────────────────────────────────────────
def render_brief(records: Optional[List[Dict[str, Any]]] = None) -> str:
    records = records if records is not None else calibrate()
    if not records:
        return ""
    over = [r for r in records if r["status"] == "overconfident"]
    under = [r for r in records if r["status"] == "underconfident"]
    best = sorted([r for r in records if r["status"] == "calibrated"], key=lambda r: r["error"])
    L = ["## CONFIDENCE CALIBRATION (predicted vs observed — awareness only):"]
    for r in over[:3]:
        L.append(f"  ⚠ OVERCONFIDENT: {r['subject']} — predicted {r['predicted_confidence']} "
                 f"but observed {r['observed_success']} (error {r['error']})")
    for r in under[:3]:
        L.append(f"  ↑ UNDERCONFIDENT: {r['subject']} — predicted {r['predicted_confidence']} "
                 f"but observed {r['observed_success']} (error {r['error']})")
    if best:
        L.append("  ✓ WELL CALIBRATED: " + ", ".join(r["subject"] for r in best[:3]))
    return "\n".join(L)


def metrics(records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    records = records if records is not None else calibrate()
    by_status: Dict[str, int] = {}
    by_quality: Dict[str, int] = {}
    for r in records:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_quality[r["quality"]] = by_quality.get(r["quality"], 0) + 1
    n = len(records)
    return {
        "subjects_assessed": n,
        "by_status": by_status,
        "by_quality": by_quality,
        "mean_error": round(sum(r["error"] for r in records) / n, 3) if n else None,
        "overconfident": [r["subject"] for r in records if r["status"] == "overconfident"][:5],
        "underconfident": [r["subject"] for r in records if r["status"] == "underconfident"][:5],
        "best_calibrated": [r["subject"] for r in sorted(records, key=lambda r: r["error"])
                            if r["status"] == "calibrated"][:5],
    }
