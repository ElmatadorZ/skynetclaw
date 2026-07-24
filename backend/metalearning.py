"""
metalearning.py — OX-METALEARNING-1 LEARNING HOW TO LEARN PROTOCOL (additive)
=============================================================================
Discover which LEARNING STRATEGIES produce the highest acquisition success — i.e.
for each knowledge gap_type, which SOURCE ORDER actually works — and bias future
acquisition planning toward it.

Builds on the existing read-models: Knowledge Seeking, Acquisition (records),
Attribution, Reinforcement, Compliance. Additive only — no redesign of runtime,
workflow_runs, agent_runs, house_state or governance. No autonomous goals, no
self-modification, no Level-5 features. It learns from recorded episodes and
recommends an ordering; the agent still does the searching.

Learning Episode (derived from one acquisition record):
  {gap_type, sources_tried, sources_successful, acquisition_success,
   execution_success, compliance_score}

Learning Strategy (promoted, persisted):
  {gap_type, recommended_order:[...], confidence, evidence_count,
   success_rate, execution_rate, compliance_rate, status}

Promotion: evidence_count >= MIN_EVIDENCE (5) AND confidence >= CONF_THRESH (0.70).
Reinforcement: confidence is recomputed from ALL accumulated episodes each
refresh — more successes strengthen it, failures weaken it; falling below the
gate demotes the strategy.

Owns only learning_strategies.json. Reads acquisition.load_records().

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE = Path(__file__).parent / "learning_strategies.json"

MIN_EVIDENCE = 5
CONF_THRESH = 0.70


# ── 1. Learning Episodes (projection of acquisition records) ─────────────────
def episode_from_record(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "gap_type": r.get("gap_type") or "?",
        "sources_tried": list(r.get("sources_checked") or []),
        "sources_successful": list(r.get("sources_successful") or []),
        "acquisition_success": bool(r.get("knowledge_found")),
        "execution_success": bool(r.get("execution_used")),
        "compliance_score": r.get("compliance_score"),
    }


def episodes(records: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    if records is None:
        try:
            import acquisition as _aq
            records = _aq.load_records()
        except Exception:
            records = []
    return [episode_from_record(r) for r in (records or [])]


# ── 2+3. Strategy Discovery ──────────────────────────────────────────────────
def _mean(xs: List[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def discover_strategies(eps: List[Dict[str, Any]],
                        min_evidence: int = MIN_EVIDENCE,
                        conf_thresh: float = CONF_THRESH,
                        prior: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Aggregate episodes by gap_type → a Learning Strategy each. recommended_order
    ranks sources by how often they SUCCEEDED for that gap_type (then by success
    rate among tries). Marks promoted/demoted + reinforced/weakened vs prior."""
    prior = prior or {}
    by_gap: Dict[str, List[Dict[str, Any]]] = {}
    for e in eps:
        by_gap.setdefault(e["gap_type"], []).append(e)

    out: Dict[str, Dict[str, Any]] = {}
    for gap_type, group in by_gap.items():
        n = len(group)
        succ = sum(1 for e in group if e["acquisition_success"])
        exe = sum(1 for e in group if e["execution_success"])
        success_rate = round(succ / n, 3)
        execution_rate = round(exe / n, 3)
        compliance_rate = _mean([e["compliance_score"] for e in group])

        # per-source: successes and tries within this gap_type
        s_succ: Dict[str, int] = {}
        s_try: Dict[str, int] = {}
        for e in group:
            for s in e["sources_tried"]:
                s_try[s] = s_try.get(s, 0) + 1
            for s in e["sources_successful"]:
                s_succ[s] = s_succ.get(s, 0) + 1
        # rank: most successes first, then highest success-rate-among-tries
        ranked = sorted(
            s_try.keys(),
            key=lambda s: (s_succ.get(s, 0), s_succ.get(s, 0) / max(s_try.get(s, 1), 1)),
            reverse=True,
        )
        # sources that NEVER succeeded sink to the bottom (keep order, but after
        # any source that did succeed)
        recommended_order = [s for s in ranked if s_succ.get(s, 0) > 0] + \
                            [s for s in ranked if s_succ.get(s, 0) == 0]

        confidence = success_rate
        promoted = (n >= min_evidence) and (confidence >= conf_thresh)
        prev = (prior.get(gap_type) or {}).get("confidence")
        if prev is None:
            status = "promoted" if promoted else "candidate"
        elif confidence >= prev:
            status = "reinforced"
        else:
            status = "weakened"
        if not promoted:
            status = "demoted" if prev is not None else "candidate"

        out[gap_type] = {
            "gap_type": gap_type,
            "recommended_order": recommended_order,
            "confidence": confidence,
            "evidence_count": n,
            "success_rate": success_rate,
            "execution_rate": execution_rate,
            "compliance_rate": compliance_rate,
            "promoted": promoted,
            "status": status,
        }
    return out


# ── store (promoted strategies only) ─────────────────────────────────────────
def load_strategies(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    p = path or _STORE
    try:
        if p.exists():
            return (json.loads(p.read_text(encoding="utf-8")) or {}).get("strategies", {})
    except Exception:
        pass
    return {}


def refresh(records: Optional[List[Dict[str, Any]]] = None,
            path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Recompute strategies from all episodes and PERSIST the promoted ones.
    Confidence is recomputed each call (reinforcement: strengthen/weaken)."""
    p = path or _STORE
    prior = load_strategies(p)
    allstrat = discover_strategies(episodes(records), prior=prior)
    promoted = {g: s for g, s in allstrat.items() if s.get("promoted")}
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "generated_at": time.time(),
                                   "strategies": promoted}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[metalearning] persist failed: {e}")
    return promoted


# ── 5. Recall — bias acquisition source ordering ─────────────────────────────
def lookup_strategy(gap_type: str, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    return load_strategies(path).get(gap_type)


def bias_order(gap_type: str, candidates: List[str],
               path: Optional[Path] = None) -> List[str]:
    """If a promoted strategy exists for gap_type, reorder the candidate sources
    to follow its recommended_order (intersected with candidates); otherwise
    return candidates unchanged. Adds/removes nothing."""
    strat = lookup_strategy(gap_type, path)
    if not strat:
        return list(candidates or [])
    rec = [s for s in strat.get("recommended_order", []) if s in (candidates or [])]
    rest = [s for s in (candidates or []) if s not in rec]
    return rec + rest


# ── 7. Metrics ────────────────────────────────────────────────────────────────
def metrics(path: Optional[Path] = None,
            records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    strategies = load_strategies(path)
    eps = episodes(records)
    # gap-type frequency + most-effective sources across all episodes
    gap_counts: Dict[str, int] = {}
    src_success: Dict[str, int] = {}
    for e in eps:
        gap_counts[e["gap_type"]] = gap_counts.get(e["gap_type"], 0) + 1
        for s in e["sources_successful"]:
            src_success[s] = src_success.get(s, 0) + 1
    srates = [s.get("success_rate", 0.0) for s in strategies.values()]
    top_gaps = sorted(gap_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_src = sorted(src_success.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "strategy_count": len(strategies),
        "strategy_success_rate": round(sum(srates) / len(srates), 3) if srates else None,
        "top_gap_types": [{"gap_type": g, "episodes": c} for g, c in top_gaps],
        "most_effective_sources": [{"source": s, "successes": c} for s, c in top_src],
        "episodes_total": len(eps),
    }


def render_brief(path: Optional[Path] = None) -> str:
    strategies = load_strategies(path)
    if not strategies:
        return ""
    L = ["## LEARNING STRATEGIES (proven source orders — bias acquisition by these):"]
    for s in sorted(strategies.values(), key=lambda x: x["confidence"], reverse=True)[:5]:
        L.append(f"  • {s['gap_type']}: {' → '.join(s['recommended_order'][:4])} "
                 f"(conf {s['confidence']}, n={s['evidence_count']})")
    return "\n".join(L)
