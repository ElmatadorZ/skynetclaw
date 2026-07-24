"""
first_principles.py — OX-FIRST-PRINCIPLE-1 First Principle Extraction (read-only)
=================================================================================
Extract reusable PRINCIPLES from things multiple learning systems INDEPENDENTLY
agree on — promoted MetaLearning strategies, promoted Causal hypotheses, and
reinforced capabilities. A principle is trustworthy only when corroborated by
>= 2 independent systems (cross-validation), so no single noisy detector can
mint one.

Builds on MetaLearning / Causal Discovery / Reinforcement / Belief Revision.
Read-only — no redesign of Acquisition / Exploration / Control / Runtime. No
automatic promotion, no reinforcement, no behavior change. It only NAMES
principles as candidates; humans / later protocols decide.

Principle:
  {principle, supporting_evidence, confidence, sources:[...], category, status}

Rules — a principle requires:
  support >= 5  AND  confidence >= 0.70  AND  >= 2 independent systems
  (MetaLearning+Causal, Causal+Reinforcement, or MetaLearning+Reinforcement).

Owns no state. Pure read-model over the existing stores.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

MIN_SUPPORT = 5
CONF_THRESH = 0.70
REINFORCED_WEIGHT = 1.10

# tool → source (so reinforced capabilities' recommended_tools map onto sources)
_TOOL_SOURCE = {
    "grep_search": "existing_code", "find_files": "existing_code",
    "read_file": "workspace_files", "list_files": "workspace_files",
    "search_obsidian": "obsidian", "read_obsidian_note": "obsidian",
    "web_search": "web_search", "http_request": "documentation",
    "download_file": "documentation", "shell_command": "github",
    "recall_archive": "lesson_registry", "query_learning": "lesson_registry",
}

# source → first-principle statement + classification
_PRINCIPLE = {
    "github":            ("Executable examples reduce ambiguity", "Knowledge Principle"),
    "documentation":     ("Authoritative specifications resolve uncertainty", "Knowledge Principle"),
    "existing_code":     ("Reuse what already exists before rebuilding", "Strategy Principle"),
    "workspace_files":   ("The needed artifact often already exists on disk", "Strategy Principle"),
    "artifact_registry": ("Prior deliverables are the fastest source of truth", "Strategy Principle"),
    "web_search":        ("Current external information beats stale assumptions", "Knowledge Principle"),
    "obsidian":          ("Captured knowledge compounds — consult the vault first", "Knowledge Principle"),
    "lesson_registry":   ("Past lessons prevent repeated mistakes", "Knowledge Principle"),
    "capability_registry": ("Proven capabilities should be reused", "Strategy Principle"),
}


def _src_from_factor(factor: str) -> Optional[str]:
    if ":" in factor:
        return factor.split(":", 1)[1]
    if factor == "high_compliance":
        return "_compliance"
    return None


# ── gather per-source support from each system ───────────────────────────────
def _ml_support(strategies: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for st in (strategies or {}).values():
        conf = float(st.get("confidence", 0) or 0)
        ev = int(st.get("evidence_count", 0) or 0)
        order = st.get("recommended_order") or []
        for s in order:
            a = out.setdefault(s, {"support": 0, "conf": 0.0, "leads": False})
            a["support"] += ev
            a["conf"] = max(a["conf"], conf)
            if order and order[0] == s:
                a["leads"] = True
    return out


def _causal_support(hypotheses: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for hyps in (hypotheses or {}).values():
        for h in (hyps or []):
            s = _src_from_factor(h.get("factor", ""))
            if not s:
                continue
            a = out.setdefault(s, {"support": 0, "conf": 0.0})
            a["support"] += int(h.get("supporting_evidence", 0) or 0)
            a["conf"] = max(a["conf"], float(h.get("confidence", 0) or 0))
    return out


def _reinf_support(reinforced: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for c in (reinforced or []):
        conf = float(c.get("confidence", 0) or 0)
        ev = int(c.get("evidence_count", 0) or 0)
        for t in (c.get("recommended_tools") or []):
            s = _TOOL_SOURCE.get(t)
            if not s:
                continue
            a = out.setdefault(s, {"support": 0, "conf": 0.0})
            a["support"] += ev
            a["conf"] = max(a["conf"], conf)
    return out


# ── extraction ────────────────────────────────────────────────────────────────
def extract(strategies: Optional[Dict[str, Any]] = None,
            hypotheses: Optional[Dict[str, Any]] = None,
            reinforced: Optional[List[Dict[str, Any]]] = None,
            min_support: int = MIN_SUPPORT, conf_thresh: float = CONF_THRESH) -> List[Dict[str, Any]]:
    """Extract principles corroborated by >= 2 systems. Defaults load from stores."""
    if strategies is None:
        try: import metalearning as _ml; strategies = _ml.load_strategies()
        except Exception: strategies = {}
    if hypotheses is None:
        try: import causal as _ca; hypotheses = _ca.load_hypotheses()
        except Exception: hypotheses = {}
    if reinforced is None:
        reinforced = _load_reinforced()

    ml = _ml_support(strategies)
    ca = _causal_support(hypotheses)
    rf = _reinf_support(reinforced)

    principles: List[Dict[str, Any]] = []
    for source in set(ml) | set(ca) | set(rf):
        per_system: List[tuple] = []   # (system_name, support, conf)
        if source in ml: per_system.append(("MetaLearning", ml[source]["support"], ml[source]["conf"]))
        if source in ca: per_system.append(("Causal", ca[source]["support"], ca[source]["conf"]))
        if source in rf: per_system.append(("Reinforcement", rf[source]["support"], rf[source]["conf"]))
        if len(per_system) < 2:
            continue                                   # single source → reject
        support = sum(p[1] for p in per_system)
        confidence = round(sum(p[2] for p in per_system) / len(per_system), 3)
        if support < min_support or confidence < conf_thresh:
            continue
        text, category = _PRINCIPLE.get(source, (f"'{source}' reliably contributes to success", "Knowledge Principle"))
        # MetaLearning ordering evidence → Strategy Principle
        if source in ml and ml[source].get("leads"):
            category = "Strategy Principle"
        if source == "_compliance":
            text, category = ("Following the recommended tools improves execution", "Execution Principle")
        principles.append({
            "principle": text,
            "pattern": source,
            "supporting_evidence": support,
            "confidence": confidence,
            "sources": sorted(p[0] for p in per_system),
            "category": category,
            "status": "candidate",
        })
    principles.sort(key=lambda p: (p["confidence"], p["supporting_evidence"]), reverse=True)
    return principles


# ── Risk Principles (from Belief Revision drift + originating system) ────────
def extract_risk(drifts: Optional[List[Dict[str, Any]]] = None,
                 min_support: int = MIN_SUPPORT, conf_thresh: float = CONF_THRESH) -> List[Dict[str, Any]]:
    """A drifted belief, corroborated by Belief Revision AND the belief's own
    origin system, yields a Risk Principle (>=2 systems by construction)."""
    if drifts is None:
        try:
            import belief_revision as _br
            drifts = _br.review().get("belief_drift", [])
        except Exception:
            drifts = []
    out: List[Dict[str, Any]] = []
    for d in (drifts or []):
        support = int(d.get("recent_n", 0) or 0)
        conf = round(min(0.99, 0.5 + float(d.get("contradiction", 0) or 0)), 3)
        origin = {"metalearning": "MetaLearning", "causal": "Causal",
                  "capability": "Reinforcement"}.get(d.get("source", ""), "MetaLearning")
        if support < min_support or conf < conf_thresh:
            continue
        out.append({
            "principle": f"'{d.get('belief','?')}' is no longer reliable — recent evidence contradicts it",
            "pattern": d.get("belief", "?"),
            "supporting_evidence": support,
            "confidence": conf,
            "sources": sorted({"BeliefRevision", origin}),
            "category": "Risk Principle",
            "status": "candidate",
        })
    return out


def _load_reinforced() -> List[Dict[str, Any]]:
    """Reinforced capabilities = promoted capabilities whose reinforcement weight
    is at/above the reinforced band."""
    try:
        import capability_promotion as _cp, reinforcement as _rf
        caps = _cp.load()
        caps = list(caps.values()) if isinstance(caps, dict) else (caps or [])
        weights = _rf.load()
        out = []
        for c in caps:
            w = weights.get(c.get("name")) or {}
            if w.get("status") == "reinforced" or float(w.get("weight", 1.0) or 1.0) >= REINFORCED_WEIGHT:
                out.append(c)
        return out
    except Exception:
        return []


# ── recall / metrics ─────────────────────────────────────────────────────────
def all_principles(**kw) -> List[Dict[str, Any]]:
    return extract(**kw) + extract_risk()


def render_brief(principles: Optional[List[Dict[str, Any]]] = None) -> str:
    principles = principles if principles is not None else all_principles()
    if not principles:
        return ""
    L = ["## FIRST PRINCIPLES (cross-validated by >=2 systems — candidates, not rules):"]
    for p in principles[:5]:
        L.append(f"  • [{p['category']}] {p['principle']} "
                 f"(conf {p['confidence']}, support {p['supporting_evidence']}, "
                 f"{'+'.join(p['sources'])})")
    return "\n".join(L)


def metrics(principles: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    principles = principles if principles is not None else all_principles()
    by_cat: Dict[str, int] = {}
    for p in principles:
        by_cat[p["category"]] = by_cat.get(p["category"], 0) + 1
    return {
        "principle_count": len(principles),
        "by_category": by_cat,
        "avg_confidence": round(sum(p["confidence"] for p in principles) / len(principles), 3) if principles else None,
        "top_principles": [p["principle"] for p in principles[:5]],
    }
