"""
theory.py — OX-THEORY-1 THEORY FORMATION PROTOCOL (read-only)
=============================================================
A principle that holds in ONE domain is local; a principle that holds across
MANY domains is a THEORY. This layer forms theory candidates by finding patterns
that generalize — corroborated by Causal hypotheses in >= 2 domains (gap_types)
and supported by First Principles / Decisions.

Builds on Causal Discovery / First Principles / Decision Framework. Read-only —
no autonomy, no runtime modification, no behavior change. Theory candidates are
named, not enacted.

Theory:
  {theory, pattern, supporting_domains:[...], confidence, evidence,
   sources:[...], status:"candidate"}

Rules — a theory requires:
  generalizes across >= MIN_DOMAINS (2) distinct domains  AND  confidence >= 0.70

Owns no state. Pure read-model.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

MIN_DOMAINS = 2
CONF_THRESH = 0.70

# source/pattern → generalized theory statement
_THEORY_TEXT = {
    "github": "Executable examples reduce ambiguity across domains",
    "documentation": "Authoritative specifications resolve uncertainty across domains",
    "existing_code": "Reusing what already exists outperforms rebuilding, across domains",
    "workspace_files": "The needed artifact usually already exists locally, across domains",
    "web_search": "Current external information beats stale assumptions, across domains",
    "obsidian": "Captured knowledge compounds across domains",
    "_compliance": "Following proven tools improves outcomes across domains",
}


def _factor_source(factor: str) -> Optional[str]:
    if ":" in factor:
        return factor.split(":", 1)[1]
    if factor == "high_compliance":
        return "_compliance"
    return None


def _theory_text(pattern: str) -> str:
    return _THEORY_TEXT.get(pattern, f"'{pattern}' is a reliable factor across domains")


# ── theory formation ──────────────────────────────────────────────────────────
def form(causal: Optional[Dict[str, Any]] = None,
         principles: Optional[List[Dict[str, Any]]] = None,
         decisions: Optional[List[Dict[str, Any]]] = None,
         min_domains: int = MIN_DOMAINS, conf_thresh: float = CONF_THRESH) -> List[Dict[str, Any]]:
    """Form theory candidates. Defaults load from the stores."""
    if causal is None:
        try: import causal as _ca; causal = _ca.load_hypotheses()
        except Exception: causal = {}
    if principles is None:
        try: import first_principles as _fp; principles = _fp.all_principles()
        except Exception: principles = []
    if decisions is None:
        try: import decision as _dec; decisions = _dec.decide()
        except Exception: decisions = []

    # per-pattern: which DOMAINS (gap_types) the causal evidence spans + confidences
    agg: Dict[str, Dict[str, Any]] = {}
    for gap_type, hyps in (causal or {}).items():
        for h in (hyps or []):
            s = _factor_source(h.get("factor", ""))
            if not s:
                continue
            a = agg.setdefault(s, {"domains": set(), "confs": [], "evidence": 0, "sources": set()})
            a["domains"].add(gap_type)
            a["confs"].append(float(h.get("confidence", 0) or 0))
            a["evidence"] += int(h.get("supporting_evidence", 0) or 0)
            a["sources"].add("causal")

    for p in (principles or []):
        s = p.get("pattern")
        if s in agg:
            agg[s]["confs"].append(float(p.get("confidence", 0) or 0))
            agg[s]["sources"].add("first_principles")
    for d in (decisions or []):
        s = d.get("pattern")
        if s in agg:
            agg[s]["confs"].append(float(d.get("confidence", 0) or 0))
            agg[s]["sources"].add("decision")

    out: List[Dict[str, Any]] = []
    for pattern, a in agg.items():
        domains = sorted(a["domains"])
        if len(domains) < min_domains:
            continue                                  # holds in one domain → not a theory
        confidence = round(sum(a["confs"]) / len(a["confs"]), 3) if a["confs"] else 0.0
        if confidence < conf_thresh:
            continue
        out.append({
            "theory": _theory_text(pattern),
            "pattern": pattern,
            "supporting_domains": domains,
            "confidence": confidence,
            "evidence": a["evidence"],
            "sources": sorted(a["sources"]),
            "status": "candidate",
        })
    out.sort(key=lambda t: (len(t["supporting_domains"]), t["confidence"], t["evidence"]), reverse=True)
    return out


# ── recall / metrics ─────────────────────────────────────────────────────────
def render_brief(theories: Optional[List[Dict[str, Any]]] = None, limit: int = 4) -> str:
    theories = theories if theories is not None else form()
    if not theories:
        return ""
    L = ["## THEORIES (patterns that generalize across domains — candidates, not laws):"]
    for t in theories[:limit]:
        L.append(f"  • {t['theory']} (confidence {t['confidence']}, "
                 f"domains: {', '.join(t['supporting_domains'][:3])})")
    return "\n".join(L)


def metrics(theories: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    theories = theories if theories is not None else form()
    return {
        "theory_count": len(theories),
        "avg_confidence": round(sum(t["confidence"] for t in theories) / len(theories), 3) if theories else None,
        "max_domains": max((len(t["supporting_domains"]) for t in theories), default=0),
        "top_theories": [t["theory"] for t in theories[:5]],
    }
