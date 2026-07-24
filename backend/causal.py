"""
causal.py — OX-CAUSAL-1 CAUSAL DISCOVERY PROTOCOL (additive)
===========================================================
The House learns the pattern "A → success" but not WHY A works. This layer
contrasts successful vs failed episodes for a gap_type and surfaces the FACTORS
that discriminate them — turning correlation into testable causal hypotheses
with supporting/contradicting evidence.

Builds on the existing records (Acquisition + Compliance + Exploration). Additive
only — no redesign of runtime, workflow, reinforcement or governance. No
autonomous goals, no self-modification, no Level-5 features. It discovers and
flags hypotheses; it never rewrites strategies or weights.

Observation (one per acquisition record):
  {gap_type, strategy, sources_used, compliance, outcome}

Hypothesis:
  {hypothesis, factor, supporting_evidence, contradicting_evidence, confidence,
   promotion_candidate}

A factor is a causal candidate when it is DISCRIMINATING — present far more in
successes than failures (not present everywhere, not random):
  supporting_evidence  = successes exhibiting the factor
  contradicting_evidence = failures exhibiting the factor
  confidence = P(success | factor) = supporting / (supporting + contradicting)
  + requires a contrast (absence cases exist) and P(success|factor) > P(success|¬factor)
Promotion: supporting >= 5 AND confidence >= 0.70 (+ discriminating).

Owns only causal_hypotheses.json. Reads acquisition.load_records().

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE = Path(__file__).parent / "causal_hypotheses.json"

MIN_SUPPORT = 5
CONF_THRESH = 0.70
HIGH_COMPLIANCE = 0.70

# heuristic rationale for WHY a source tends to work (labelled as heuristic)
_SOURCE_RATIONALE = {
    "github": "reference implementations / code examples exist there",
    "documentation": "an authoritative specification exists there",
    "existing_code": "the answer already exists in the local codebase",
    "workspace_files": "the needed artifact already exists on disk",
    "artifact_registry": "a prior deliverable already contains it",
    "web_search": "current external information is available",
    "obsidian": "prior captured knowledge exists in the vault",
    "lesson_registry": "a prior lesson already captured it",
    "capability_registry": "an emerged capability already covers it",
}


def _is_success(o: str) -> bool:
    return str(o).lower() in ("success", "task_complete", "completed", "true", "1")


# ── Observations (projection of acquisition records) ─────────────────────────
def observations(records: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    if records is None:
        try:
            import acquisition as _aq
            records = _aq.load_records()
        except Exception:
            records = []
    obs: List[Dict[str, Any]] = []
    for r in (records or []):
        srcs = list(r.get("sources_checked") or [])
        obs.append({
            "gap_type": r.get("gap_type") or "?",
            "strategy": (srcs[0] + "_first") if srcs else "none",
            "sources_used": srcs,
            "compliance": r.get("compliance_score"),
            "outcome": "success" if r.get("knowledge_found") else "failure",
        })
    return obs


# ── Factor extraction ─────────────────────────────────────────────────────────
def _factors(o: Dict[str, Any]) -> Dict[str, bool]:
    f: Dict[str, bool] = {}
    srcs = o.get("sources_used") or []
    for s in srcs:
        f[f"uses:{s}"] = True
    if srcs:
        f[f"leads:{srcs[0]}"] = True
    c = o.get("compliance")
    if c is not None:
        f["high_compliance"] = (c >= HIGH_COMPLIANCE)
    return f


def _factor_universe(group: List[Dict[str, Any]]) -> List[str]:
    univ: set = set()
    for o in group:
        for k, v in _factors(o).items():
            if v:
                univ.add(k)
    # high_compliance is testable even when False in some obs
    if any(o.get("compliance") is not None for o in group):
        univ.add("high_compliance")
    return sorted(univ)


def _hypothesis_text(gap_type: str, factor: str) -> str:
    if factor.startswith("uses:"):
        s = factor.split(":", 1)[1]
        why = _SOURCE_RATIONALE.get(s, "it provides the needed knowledge")
        return f'"{s}" drives success for {gap_type} — because {why}'
    if factor.startswith("leads:"):
        s = factor.split(":", 1)[1]
        return f'leading with "{s}" drives success for {gap_type}'
    if factor == "high_compliance":
        return f"following the recommended tools (high compliance) drives success for {gap_type}"
    return f"{factor} drives success for {gap_type}"


# ── Discovery model ───────────────────────────────────────────────────────────
def discover(records: Optional[List[Dict[str, Any]]] = None, gap_type: Optional[str] = None,
             min_support: int = MIN_SUPPORT, conf_thresh: float = CONF_THRESH) -> List[Dict[str, Any]]:
    """Contrast successes vs failures per gap_type; emit a hypothesis per factor
    with supporting/contradicting evidence + confidence. Marks promotion_candidate
    only for DISCRIMINATING factors (a contrast exists and it favours success)."""
    obs = observations(records)
    by_gap: Dict[str, List[Dict[str, Any]]] = {}
    for o in obs:
        by_gap.setdefault(o["gap_type"], []).append(o)
    gaps = [gap_type] if gap_type else list(by_gap.keys())

    out: List[Dict[str, Any]] = []
    for gt in gaps:
        group = by_gap.get(gt, [])
        if not group:
            continue
        succ = [o for o in group if o["outcome"] == "success"]
        fail = [o for o in group if o["outcome"] != "success"]
        n_s, n_f = len(succ), len(fail)
        for factor in _factor_universe(group):
            sw = sum(1 for o in succ if _factors(o).get(factor))     # success WITH factor
            fw = sum(1 for o in fail if _factors(o).get(factor))     # fail WITH factor
            swo = n_s - sw                                            # success WITHOUT factor
            fwo = n_f - fw                                           # fail WITHOUT factor
            supporting = sw
            contradicting = fw
            denom = supporting + contradicting
            confidence = round(supporting / denom, 3) if denom else 0.0
            # discriminating: a contrast must exist and the factor must favour success
            p_with = supporting / denom if denom else 0.0
            absent = swo + fwo
            p_without = (swo / absent) if absent else None
            discriminating = (absent >= 1) and (p_without is not None) and (p_with > p_without)
            promote = discriminating and supporting >= min_support and confidence >= conf_thresh
            out.append({
                "gap_type": gt,
                "factor": factor,
                "hypothesis": _hypothesis_text(gt, factor),
                "supporting_evidence": supporting,
                "contradicting_evidence": contradicting,
                "confidence": confidence,
                "discriminating": discriminating,
                "promotion_candidate": promote,
            })
    out.sort(key=lambda h: (h["promotion_candidate"], h["confidence"], h["supporting_evidence"]), reverse=True)
    return out


# ── store (promoted hypotheses only) ─────────────────────────────────────────
def load_hypotheses(path: Optional[Path] = None) -> Dict[str, List[Dict[str, Any]]]:
    p = path or _STORE
    try:
        if p.exists():
            return (json.loads(p.read_text(encoding="utf-8")) or {}).get("hypotheses", {})
    except Exception:
        pass
    return {}


def refresh(records: Optional[List[Dict[str, Any]]] = None,
            path: Optional[Path] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Discover + persist the PROMOTED hypotheses, grouped by gap_type."""
    p = path or _STORE
    promoted: Dict[str, List[Dict[str, Any]]] = {}
    for h in discover(records):
        if h["promotion_candidate"]:
            promoted.setdefault(h["gap_type"], []).append(h)
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "generated_at": time.time(),
                                   "hypotheses": promoted}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[causal] persist failed: {e}")
    return promoted


def lookup(gap_type: str, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    return load_hypotheses(path).get(gap_type, [])


# ── Recall — likely reasons a strategy works ─────────────────────────────────
def render_brief(gap_type: str, path: Optional[Path] = None) -> str:
    hyps = lookup(gap_type, path)
    if not hyps:
        return ""
    L = [f"## CAUSAL INSIGHT (likely reasons strategies work for {gap_type}):"]
    for h in sorted(hyps, key=lambda x: x["confidence"], reverse=True)[:4]:
        L.append(f"  • {h['hypothesis']}  (conf {h['confidence']}, "
                 f"support {h['supporting_evidence']}/-{h['contradicting_evidence']})")
    return "\n".join(L)


# ── Metrics ────────────────────────────────────────────────────────────────--
def metrics(records: Optional[List[Dict[str, Any]]] = None,
            path: Optional[Path] = None) -> Dict[str, Any]:
    promoted = load_hypotheses(path)
    all_h = discover(records)
    confs = [h["confidence"] for grp in promoted.values() for h in grp]
    return {
        "hypotheses_evaluated": len(all_h),
        "promoted_count": sum(len(v) for v in promoted.values()),
        "gap_types_covered": len(promoted),
        "avg_confidence": round(sum(confs) / len(confs), 3) if confs else None,
        "top_hypotheses": [h["hypothesis"] for grp in promoted.values()
                           for h in sorted(grp, key=lambda x: x["confidence"], reverse=True)][:5],
    }
