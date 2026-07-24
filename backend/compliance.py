"""
compliance.py — OX-COMPLIANCE-1 CAPABILITY COMPLIANCE VERIFICATION (read-side)
==============================================================================
The House recalls capabilities (each with recommended_tools) and injects them as
guidance — but nothing verified whether that guidance actually SHAPED execution
(the "soft final mile" / O-B gap from the Level-4 audit). This engine measures
it: per mission, compare the tools a recalled capability RECOMMENDED against the
tools the run ACTUALLY used, and classify FOLLOWED / PARTIAL / IGNORED.

MEASURE ONLY. It does NOT alter runtime decisions, tool selection, or
reinforcement weights — it records a compliance signal and exposes it to
attribution / telemetry as read-only evidence.

Compliance model (per mission):
  expected = ∪ recommended_tools of the recalled (positive) capabilities
  matched  = expected ∩ tools_used
  compliance_score = |matched| / |expected|      (None when expected is empty)
  FOLLOWED  score ≥ 0.7
  PARTIAL   0 < score < 0.7
  IGNORED   score == 0
  NOT_APPLICABLE  no recalled capability recommended any tool

Owns only compliance.json (per-mission records). Additive.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_STORE = Path(__file__).parent / "compliance.json"

FOLLOWED_THRESH = 0.70
FOLLOWED, PARTIAL, IGNORED, NA = "FOLLOWED", "PARTIAL", "IGNORED", "NOT_APPLICABLE"


def _norm(tools) -> Set[str]:
    return {str(t).strip() for t in (tools or []) if str(t).strip()}


# ── scoring ───────────────────────────────────────────────────────────────────
def score(expected_tools, tools_used) -> Dict[str, Any]:
    """Compare expected (recommended) vs actually-used tools → compliance."""
    expected = _norm(expected_tools)
    used = _norm(tools_used)
    if not expected:
        return {"compliance_score": None, "classification": NA,
                "expected_tools": [], "matched_tools": [], "used_tools": sorted(used)}
    matched = expected & used
    s = round(len(matched) / len(expected), 3)
    cls = FOLLOWED if s >= FOLLOWED_THRESH else (IGNORED if s == 0 else PARTIAL)
    return {"compliance_score": s, "classification": cls,
            "expected_tools": sorted(expected), "matched_tools": sorted(matched),
            "used_tools": sorted(used)}


def _expected_from_capabilities(recalled_capabilities: List[str],
                                registry: Optional[List[Dict[str, Any]]] = None) -> Set[str]:
    """Union of recommended_tools across the recalled (positive) capabilities,
    looked up in the capability registry by name."""
    if registry is None:
        try:
            import capability_promotion as _cp
            registry = _cp.load()
            # load() returns {name: rec}? No — capabilities.json stores a list.
            if isinstance(registry, dict):
                registry = list(registry.values())
        except Exception:
            registry = []
    by_name = {c.get("name"): c for c in (registry or []) if isinstance(c, dict)}
    expected: Set[str] = set()
    for name in (recalled_capabilities or []):
        cap = by_name.get(name)
        if cap and cap.get("polarity", "capability") == "capability":
            expected |= _norm(cap.get("recommended_tools"))
    return expected


def evaluate(recalled_capabilities: List[str], tools_used,
             registry: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Full per-mission compliance: recalled capabilities (names) vs tools used."""
    expected = _expected_from_capabilities(recalled_capabilities, registry)
    out = score(expected, tools_used)
    out["recalled_capabilities"] = list(recalled_capabilities or [])
    return out


# ── per-mission record store ─────────────────────────────────────────────────
def _load(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            return (json.loads(path.read_text(encoding="utf-8")) or {}).get("records", [])
    except Exception:
        pass
    return []


def load_records(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    return _load(path or _STORE)


def record(mission_id: str, recalled_capabilities: List[str], tools_used,
           outcome: str = "", registry: Optional[List[Dict[str, Any]]] = None,
           path: Optional[Path] = None, keep: int = 500) -> Dict[str, Any]:
    """Compute + persist a compliance record for a mission."""
    ev = evaluate(recalled_capabilities, tools_used, registry)
    rec = {"mission_id": mission_id, "ts": time.time(), "outcome": outcome, **ev}
    p = path or _STORE
    try:
        data = _load(p); data.append(rec); data = data[-keep:]
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "records": data}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[compliance] record failed: {e}")
    return rec


# ── aggregate metrics (read-only signal for telemetry/attribution) ───────────
def metrics(records: Optional[List[Dict[str, Any]]] = None,
            path: Optional[Path] = None) -> Dict[str, Any]:
    records = records if records is not None else load_records(path)
    scored = [r for r in records if r.get("compliance_score") is not None]
    n = len(scored)
    by_class: Dict[str, int] = {}
    for r in records:
        by_class[r.get("classification", NA)] = by_class.get(r.get("classification", NA), 0) + 1
    avg = round(sum(r["compliance_score"] for r in scored) / n, 3) if n else None
    followed = by_class.get(FOLLOWED, 0)
    return {
        "total": len(records),
        "measurable": n,                       # had expected tools to compare
        "avg_compliance_score": avg,
        "by_classification": by_class,
        "followed_rate": round(followed / n, 3) if n else None,
        "ignored_rate": round(by_class.get(IGNORED, 0) / n, 3) if n else None,
    }


def per_capability(records: Optional[List[Dict[str, Any]]] = None,
                   path: Optional[Path] = None) -> Dict[str, Any]:
    """Compliance broken down by recalled capability — which capabilities are
    actually heeded vs ignored (read-only evidence for attribution)."""
    records = records if records is not None else load_records(path)
    agg: Dict[str, Dict[str, Any]] = {}
    for r in records:
        if r.get("compliance_score") is None:
            continue
        for name in r.get("recalled_capabilities", []) or []:
            a = agg.setdefault(name, {"n": 0, "score_sum": 0.0, "followed": 0})
            a["n"] += 1
            a["score_sum"] += r["compliance_score"]
            if r.get("classification") == FOLLOWED:
                a["followed"] += 1
    return {name: {"recalled_in": a["n"],
                   "avg_compliance": round(a["score_sum"] / a["n"], 3) if a["n"] else 0.0,
                   "followed_rate": round(a["followed"] / a["n"], 3) if a["n"] else 0.0}
            for name, a in agg.items()}
