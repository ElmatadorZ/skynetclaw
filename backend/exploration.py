"""
exploration.py — OX-EXPLORATION-1 ADAPTIVE EXPLORATION PROTOCOL (additive)
==========================================================================
Discover new, potentially superior learning strategies WITHOUT abandoning proven
ones — balance exploitation (use the proven source order) with exploration (test
alternatives). Builds on Acquisition + MetaLearning + Attribution + Reinforcement
+ Compliance. Additive only — no redesign of runtime, workflow_runs, agent_runs,
house_state, governance, or MetaLearning's strategy discovery. No autonomous
goals, no self-modification, no Level-5 features.

This layer NEVER rewrites strategy rankings. It selects primary-vs-alternative
source orders per run, records outcomes, and FLAGS promotion candidates —
MetaLearning remains the sole owner of final promotion.

Exploration Profile:
  {gap_type, best_strategy, confidence, exploration_rate,
   times_explored, times_improved, last_improvement}

Policy (exploration_rate by confidence):
  conf >= 0.90 → 0.05 · 0.70–0.90 → 0.15 · < 0.70 → 0.30 · no strategy → 1.00

Owns only exploration.json (profiles + selection/outcome records).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_STORE = Path(__file__).parent / "exploration.json"

MAX_ALT_CANDIDATES = 3
IMPROVEMENT_MIN_EVIDENCE = 5


# ── EXPLORATION POLICY ───────────────────────────────────────────────────────
def exploration_rate(confidence: Optional[float]) -> float:
    if confidence is None:
        return 1.00
    if confidence >= 0.90:
        return 0.05
    if confidence >= 0.70:
        return 0.15
    return 0.30


# ── CANDIDATE GENERATION (deterministic, bounded) ────────────────────────────
def candidates(recommended_order: List[str], max_alt: int = MAX_ALT_CANDIDATES):
    """Primary path + up to max_alt DETERMINISTIC alternative orderings.
    Never endless randomization."""
    primary = list(recommended_order or [])
    alts: List[List[str]] = []
    if len(primary) >= 2:
        swap = primary[:]; swap[0], swap[1] = swap[1], swap[0]      # swap first two
        rotate = primary[-1:] + primary[:-1]                          # last → front
        rev = list(reversed(primary))                                 # reverse
        for cand in (swap, rotate, rev):
            if cand != primary and cand not in alts:
                alts.append(cand)
    return primary, alts[:max_alt]


def _path_key(order: List[str]) -> str:
    return "→".join(order or [])


# ── store ─────────────────────────────────────────────────────────────────────
def _load(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _save(data: Dict[str, Any], path: Path) -> None:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        print(f"[exploration] save failed: {e}")


def load_profiles(path: Optional[Path] = None) -> Dict[str, Any]:
    return _load(path or _STORE).get("profiles", {})


def load_records(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    return _load(path or _STORE).get("records", [])


def lookup_exploration_profile(gap_type: str, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    return load_profiles(path).get(gap_type)


# ── PROFILE assembly (from a MetaLearning strategy + stored counters) ────────
def profile_for(gap_type: str, strategy: Optional[Dict[str, Any]] = None,
                path: Optional[Path] = None) -> Dict[str, Any]:
    best = list((strategy or {}).get("recommended_order") or [])
    conf = (strategy or {}).get("confidence") if strategy else None
    stored = lookup_exploration_profile(gap_type, path) or {}
    return {
        "gap_type": gap_type,
        "best_strategy": best,
        "confidence": conf,
        "exploration_rate": exploration_rate(conf),
        "times_explored": int(stored.get("times_explored", 0)),
        "times_improved": int(stored.get("times_improved", 0)),
        "last_improvement": stored.get("last_improvement", 0),
    }


# ── SELECTION (epsilon-greedy: mostly primary, sometimes an alternative) ─────
def select(gap_type: str, strategy: Optional[Dict[str, Any]] = None,
           rng: Optional[Callable[[], float]] = None,
           path: Optional[Path] = None) -> Dict[str, Any]:
    """Choose the source order for this run. With probability=exploration_rate
    sample ONE deterministic alternative; otherwise use the primary strategy.
    `rng` injectable for determinism in tests."""
    rng = rng or random.random
    prof = profile_for(gap_type, strategy, path)
    primary, alts = candidates(prof["best_strategy"])
    if not primary:
        # no learned strategy → full exploration, but no learned order to vary;
        # let acquisition's default hierarchy stand.
        return {"gap_type": gap_type, "selected_strategy": [], "exploration": True,
                "exploration_rate": prof["exploration_rate"], "is_primary": False}
    if alts and rng() < prof["exploration_rate"]:
        idx = prof["times_explored"] % len(alts)          # deterministic rotation
        return {"gap_type": gap_type, "selected_strategy": alts[idx], "exploration": True,
                "exploration_rate": prof["exploration_rate"], "is_primary": False}
    return {"gap_type": gap_type, "selected_strategy": primary, "exploration": False,
            "exploration_rate": prof["exploration_rate"], "is_primary": True}


def reorder(candidates_list: List[str], selected_strategy: List[str]) -> List[str]:
    """Apply a selected order to a gap's candidate sources (selected first, then
    remaining). Adds/removes nothing."""
    sel = [s for s in (selected_strategy or []) if s in (candidates_list or [])]
    rest = [s for s in (candidates_list or []) if s not in sel]
    return sel + rest


# ── RECORD selection outcome ─────────────────────────────────────────────────
def record_outcome(gap_type: str, selected_strategy: List[str], exploration: bool,
                   outcome: str, path: Optional[Path] = None, keep: int = 1000) -> Dict[str, Any]:
    p = path or _STORE
    data = _load(p)
    recs = data.get("records", [])
    rec = {"gap_type": gap_type, "selected_strategy": list(selected_strategy or []),
           "path_key": _path_key(selected_strategy), "exploration": bool(exploration),
           "outcome": "success" if str(outcome).lower() in ("success", "task_complete", "completed") else "failure",
           "ts": time.time()}
    recs.append(rec); recs = recs[-keep:]
    data["records"] = recs
    # bump exploration counter on the profile
    if exploration:
        profs = data.setdefault("profiles", {})
        pf = profs.setdefault(gap_type, {})
        pf["times_explored"] = int(pf.get("times_explored", 0)) + 1
    _save(data, p)
    return rec


# ── IMPROVEMENT DETECTION (flag only — MetaLearning owns promotion) ──────────
def detect_improvements(gap_type: Optional[str] = None,
                        min_evidence: int = IMPROVEMENT_MIN_EVIDENCE,
                        path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """An alternative path is a promotion_candidate when its success_rate exceeds
    the primary's AND it has >= min_evidence runs. Flags only; persists the
    times_improved / last_improvement counters."""
    p = path or _STORE
    data = _load(p)
    recs = data.get("records", [])
    gaps = {gap_type} if gap_type else {r["gap_type"] for r in recs}
    out: List[Dict[str, Any]] = []
    profs = data.setdefault("profiles", {})
    for gt in gaps:
        grp = [r for r in recs if r["gap_type"] == gt]
        prim = [r for r in grp if not r["exploration"]]
        prim_n = len(prim)
        prim_sr = (sum(1 for r in prim if r["outcome"] == "success") / prim_n) if prim_n else 0.0
        # group alternative (exploration) paths
        by_path: Dict[str, List[Dict[str, Any]]] = {}
        for r in grp:
            if r["exploration"]:
                by_path.setdefault(r["path_key"], []).append(r)
        for pk, rows in by_path.items():
            n = len(rows)
            sr = sum(1 for r in rows if r["outcome"] == "success") / n
            is_candidate = (n >= min_evidence) and (sr > prim_sr)
            if is_candidate:
                pf = profs.setdefault(gt, {})
                pf["times_improved"] = int(pf.get("times_improved", 0)) + 1
                pf["last_improvement"] = time.time()
            out.append({
                "gap_type": gt, "alternative": rows[0]["selected_strategy"],
                "alt_success_rate": round(sr, 3), "alt_evidence": n,
                "primary_success_rate": round(prim_sr, 3), "primary_evidence": prim_n,
                "promotion_candidate": is_candidate,
            })
    if out:
        _save(data, p)
    return [o for o in out if o["promotion_candidate"]] if gap_type is None else out


# ── DISCOVERY METRICS ─────────────────────────────────────────────────────────
def metrics(path: Optional[Path] = None) -> Dict[str, Any]:
    data = _load(path or _STORE)
    profiles = data.get("profiles", {})
    recs = data.get("records", [])
    expl = [r for r in recs if r["exploration"]]
    expl_succ = [r for r in expl if r["outcome"] == "success"]
    rates = [exploration_rate((p or {}).get("confidence")) for p in profiles.values() if p]
    gap_counts: Dict[str, int] = {}
    for r in expl:
        gap_counts[r["gap_type"]] = gap_counts.get(r["gap_type"], 0) + 1
    cands = detect_improvements(path=path)  # promotion candidates across all gaps
    return {
        "strategy_count": len(profiles),
        "exploration_rate": round(sum(rates) / len(rates), 3) if rates else None,
        "exploration_success_rate": round(len(expl_succ) / len(expl), 3) if expl else None,
        "improvement_candidates": len(cands),
        "most_discovered_gap_types": sorted(gap_counts.items(), key=lambda kv: kv[1], reverse=True)[:5],
        "total_records": len(recs),
    }
