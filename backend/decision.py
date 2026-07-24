"""
decision.py — OX-DECISION-1 DECISION FRAMEWORK PROTOCOL (read-only)
===================================================================
Synthesize structured RECOMMENDATIONS from the existing epistemic layers — First
Principles, MetaLearning strategies, Belief Revision (drift), and Curiosity
(blind spots). It does not decide for the runtime; it produces a transparent,
scored recommendation with its reasoning, risks and uncertainties.

Builds on First Principles / Belief Revision / Curiosity / MetaLearning.
Read-only — no redesign of Runtime / Control / Acquisition / Exploration /
Reinforcement. No autonomy, no tool-selection change, no behavior change.

Decision:
  {recommendation, confidence, category, pattern,
   supporting_principles:[], known_risks:[], blind_spots:[], reasoning:[]}

Scoring (additive, capped at 1.0):
  principle support   +0.4
  metalearning support +0.3
  no belief drift     +0.2   (drift present → forfeited + surfaced as a risk)
  no blind spot       +0.1   (blind spot present → forfeited + surfaced)

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

W_PRINCIPLE = 0.4
W_METALEARNING = 0.3
W_NO_DRIFT = 0.2
W_NO_BLINDSPOT = 0.1

_LABEL = {
    "github": "Examples (GitHub)", "documentation": "Documentation",
    "existing_code": "Existing Code", "workspace_files": "Workspace Files",
    "web_search": "Web Search", "obsidian": "Vault", "artifact_registry": "Prior Artifacts",
    "lesson_registry": "Lessons", "capability_registry": "Proven Capabilities",
}
_CATEGORY = {
    "Strategy Principle": "Strategy Decision",
    "Execution Principle": "Execution Decision",
    "Knowledge Principle": "Knowledge Decision",
    "Risk Principle": "Risk Decision",
}


def _label(source: str) -> str:
    return f"{_LABEL.get(source, source.replace('_', ' ').title())} First"


def _drift_matches(d: Dict[str, Any], source: str) -> bool:
    s = source.lower()
    return s == str(d.get("pattern", "")).lower() or s in str(d.get("belief", "")).lower()


def _blindspot_matches(b: Dict[str, Any], source: str) -> bool:
    return str(b.get("target", "")).lower() == source.lower() and b.get("severity") is not None


# ── core synthesis ────────────────────────────────────────────────────────────
def decide(principles: Optional[List[Dict[str, Any]]] = None,
           strategies: Optional[Dict[str, Any]] = None,
           drifts: Optional[List[Dict[str, Any]]] = None,
           blind_spots: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Produce scored recommendations per candidate pattern (source). Defaults
    load from the epistemic stores."""
    if principles is None:
        try: import first_principles as _fp; principles = _fp.all_principles()
        except Exception: principles = []
    if strategies is None:
        try: import metalearning as _ml; strategies = _ml.load_strategies()
        except Exception: strategies = {}
    if drifts is None:
        try: import belief_revision as _br; drifts = _br.review().get("belief_drift", [])
        except Exception: drifts = []
    if blind_spots is None:
        try: import curiosity as _cu; blind_spots = _cu.scan()
        except Exception: blind_spots = []

    # candidate patterns = sources named by a principle or a metalearning strategy
    pats: set = {p.get("pattern") for p in principles if p.get("pattern")}
    for st in (strategies or {}).values():
        for s in (st.get("recommended_order") or []):
            pats.add(s)
    pats.discard(None); pats.discard("")

    out: List[Dict[str, Any]] = []
    for source in pats:
        score = 0.0
        reasoning: List[str] = []
        supporting_principles: List[str] = []
        known_risks: List[str] = []
        blinds: List[str] = []
        category = "Knowledge Decision"

        princ = [p for p in principles if p.get("pattern") == source]
        if princ:
            score += W_PRINCIPLE
            supporting_principles = [p.get("principle", "") for p in princ]
            category = _CATEGORY.get(princ[0].get("category", ""), "Knowledge Decision")
            reasoning.append(f"+{W_PRINCIPLE}: backed by {len(princ)} first principle(s)")

        ml_gaps = [gt for gt, st in (strategies or {}).items()
                   if source in (st.get("recommended_order") or [])]
        if ml_gaps:
            score += W_METALEARNING
            reasoning.append(f"+{W_METALEARNING}: proven MetaLearning strategy ({', '.join(ml_gaps[:2])})")

        dmatch = [d for d in (drifts or []) if _drift_matches(d, source)]
        if not dmatch:
            score += W_NO_DRIFT
            reasoning.append(f"+{W_NO_DRIFT}: no belief drift")
        else:
            known_risks = [d.get("belief", "?") for d in dmatch]
            reasoning.append("belief drift present → confidence not credited; risk surfaced")
            if not princ and not ml_gaps:
                category = "Risk Decision"

        bmatch = [b for b in (blind_spots or []) if _blindspot_matches(b, source)]
        if not bmatch:
            score += W_NO_BLINDSPOT
            reasoning.append(f"+{W_NO_BLINDSPOT}: no blind spot")
        else:
            blinds = [b.get("target", source) for b in bmatch]
            reasoning.append("blind spot present → confidence not credited; uncertainty surfaced")

        if not (princ or ml_gaps):
            continue                              # no positive support → not a recommendation

        out.append({
            "recommendation": _label(source),
            "pattern": source,
            "confidence": round(min(1.0, score), 3),
            "category": category,
            "supporting_principles": supporting_principles,
            "known_risks": known_risks,
            "blind_spots": blinds,
            "reasoning": reasoning,
        })
    out.sort(key=lambda d: d["confidence"], reverse=True)
    return out


# ── recall / metrics ─────────────────────────────────────────────────────────
def render_brief(decisions: Optional[List[Dict[str, Any]]] = None, limit: int = 4) -> str:
    decisions = decisions if decisions is not None else decide()
    if not decisions:
        return ""
    L = ["## DECISIONS (recommendations synthesized from the epistemic layers — advisory):"]
    for d in decisions[:limit]:
        line = f"  • {d['recommendation']} [{d['category']}] (confidence {d['confidence']})"
        if d["known_risks"]:
            line += f" · risk: {', '.join(d['known_risks'][:2])}"
        if d["blind_spots"]:
            line += f" · blind spot: {', '.join(d['blind_spots'][:2])}"
        L.append(line)
    return "\n".join(L)


def metrics(decisions: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    decisions = decisions if decisions is not None else decide()
    by_cat: Dict[str, int] = {}
    for d in decisions:
        by_cat[d["category"]] = by_cat.get(d["category"], 0) + 1
    return {
        "decision_count": len(decisions),
        "by_category": by_cat,
        "avg_confidence": round(sum(d["confidence"] for d in decisions) / len(decisions), 3) if decisions else None,
        "with_risks": sum(1 for d in decisions if d["known_risks"]),
        "with_blind_spots": sum(1 for d in decisions if d["blind_spots"]),
        "top": [d["recommendation"] for d in decisions[:5]],
    }
