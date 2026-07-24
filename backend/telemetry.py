"""
telemetry.py — OX-TELEMETRY-1 IMPROVEMENT TELEMETRY (read-side)
===============================================================
Measure whether THE HOUSE is actually IMPROVING — not just busy.

FIRST PRINCIPLE: a log is not improvement. Activity is not progress. Improvement
is a POSITIVE TREND in outcomes over time. So this engine does not count events;
it compares a RECENT window of runs against a PRIOR window and reports the
direction and size of the change, with the evidence.

Read-only over existing systems (no redesign of runtime/governance/learning):
  - agent_runs (the time series: started_at, status, n_steps, n_tools, n_blocks,
    + EXEC_MEM footer for dead-ends / execution confidence)
  - mission ledger / Artifact Registry (artifact delivery)
  - Lesson + Capability registries (knowledge accrual)

Outputs an improvement SCORECARD:
  {
    "verdict": "improving | flat | regressing | insufficient_data",
    "score": 0.18,
    "windows": {"prior": {...}, "recent": {...}},
    "deltas": {"completion_rate": +0.30, "block_rate": -0.12, ...},
    "drivers": ["completion_rate +0.30", "dead_end_rate -0.20"],
    "learning": {"lessons": 12, "capabilities": 4},
    "n_runs": 40
  }

Metrics are oriented so the scorecard answers the only question that matters:
"Is the House getting better at finishing missions, delivering artifacts,
avoiding dead-ends, and acting with confidence — over time?"

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from statistics import mean
from typing import Any, Callable, Dict, List, Optional

# metric orientation: +1 = higher is better, -1 = lower is better
_ORIENT = {
    "completion_rate": +1,
    "exec_confidence": +1,
    "block_rate": -1,
    "dead_end_rate": -1,
    "avg_steps": -1,        # efficiency (low weight)
}
_WEIGHT = {
    "completion_rate": 1.0,
    "exec_confidence": 0.5,
    "block_rate": 0.6,
    "dead_end_rate": 0.8,
    "avg_steps": 0.2,
}
_VERDICT_EPS = 0.05
_MIN_WINDOW = 2            # each window needs at least this many runs

_DEAD_STATUSES = {"blocked", "problem", "limit", "error", "stuck", "incomplete", "cancelled"}


def _is_success(status: str) -> bool:
    return (status or "").strip().lower() in ("task_complete", "complete", "completed")


def _footer(summary: str) -> Dict[str, Any]:
    try:
        import execution_recall as _er
        return _er.parse_footer(summary or "") or {}
    except Exception:
        return {}


# ── per-window metrics ────────────────────────────────────────────────────────
def _win_metrics(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(runs)
    if not n:
        return {"n": 0}
    succ = sum(1 for r in runs if _is_success(str(r.get("status"))))
    blocked = 0
    dead = 0
    confs: List[float] = []
    steps: List[float] = []
    tools: List[float] = []
    for r in runs:
        nb = int(r.get("n_blocks") or 0)
        if nb > 0:
            blocked += 1
        st = str(r.get("status") or "").lower()
        f = _footer(str(r.get("summary") or ""))
        is_dead = (st in _DEAD_STATUSES) or bool(f.get("b")) or (not _is_success(st) and st not in ("",))
        if is_dead and not _is_success(st):
            dead += 1
        if f.get("c") is not None:
            try: confs.append(float(f["c"]))
            except Exception: pass
        steps.append(float(r.get("n_steps") or 0))
        tools.append(float(r.get("n_tools") or 0))
    return {
        "n": n,
        "completion_rate": round(succ / n, 3),
        "block_rate": round(blocked / n, 3),
        "dead_end_rate": round(dead / n, 3),
        "avg_steps": round(mean(steps), 2) if steps else 0.0,
        "avg_tools": round(mean(tools), 2) if tools else 0.0,
        "exec_confidence": round(mean(confs), 3) if confs else None,
    }


def _split(runs: List[Dict[str, Any]], window: Optional[int]) -> tuple:
    """Sort runs oldest→newest and split into (prior, recent) windows."""
    ordered = sorted(runs or [], key=lambda r: r.get("started_at") or 0)
    if window:
        recent = ordered[-window:]
        prior = ordered[-2 * window:-window]
    else:
        mid = len(ordered) // 2
        prior, recent = ordered[:mid], ordered[mid:]
    return prior, recent


# ── scorecard ─────────────────────────────────────────────────────────────────
def scorecard(*, runs: Optional[List[Dict[str, Any]]] = None,
              workspace: Optional[str] = None, window: Optional[int] = None,
              lessons: Optional[List] = None, caps: Optional[List] = None) -> Dict[str, Any]:
    """Compute the improvement scorecard. Any source left None is loaded from the
    existing system (read-only)."""
    if runs is None:
        try:
            import main as _m
            runs = _m._AGENT_RUNS_DB.recent(limit=200) or []
        except Exception:
            runs = []
    # OX-STABILITY-1 Phase 4: only valid concluded history may be measured —
    # orphaned 'running'/'interrupted'/'cancelled' runs and error-generated tasks
    # are non-outcomes and must not skew the improvement trend.
    try:
        import runtime_integrity as _ri
        runs = _ri.filter_valid_runs(runs)
    except Exception:
        pass
    # knowledge accrual (context, not part of the trend score)
    if lessons is None:
        try:
            import lesson_synthesis as _ls
            lessons = _ls.load()
        except Exception:
            lessons = []
    if caps is None:
        try:
            import capability_promotion as _cp
            caps = _cp.load()
        except Exception:
            caps = []
    learning = {"lessons": len(lessons or []), "capabilities": len(caps or [])}

    prior, recent = _split(runs or [], window)
    if len(prior) < _MIN_WINDOW or len(recent) < _MIN_WINDOW:
        return {"verdict": "insufficient_data", "score": 0.0,
                "windows": {"prior": _win_metrics(prior), "recent": _win_metrics(recent)},
                "deltas": {}, "drivers": [], "learning": learning,
                "n_runs": len(runs or [])}

    mp, mr = _win_metrics(prior), _win_metrics(recent)
    deltas: Dict[str, float] = {}
    score = 0.0
    drivers: List[tuple] = []
    for k, orient in _ORIENT.items():
        a, b = mp.get(k), mr.get(k)
        if a is None or b is None:
            continue
        if k == "avg_steps":                       # normalize step delta
            d = (b - a) / max(a, 1.0)
        else:
            d = b - a
        deltas[k] = round(b - a, 3)
        contrib = orient * d * _WEIGHT[k]          # +contrib = improvement
        score += contrib
        drivers.append((k, deltas[k], contrib))

    score = round(score, 3)
    verdict = ("improving" if score >= _VERDICT_EPS else
               "regressing" if score <= -_VERDICT_EPS else "flat")
    drivers.sort(key=lambda x: abs(x[2]), reverse=True)
    driver_str = [f"{k} {d:+g}" for k, d, _c in drivers if abs(_c) > 0.001][:4]
    return {
        "verdict": verdict, "score": score,
        "windows": {"prior": mp, "recent": mr},
        "deltas": deltas, "drivers": driver_str,
        "learning": learning, "n_runs": len(runs or []),
    }


# ── rendering / emission ──────────────────────────────────────────────────────
def render(sc: Dict[str, Any]) -> str:
    """A human answer to 'Is the House improving?'"""
    v = sc.get("verdict")
    if v == "insufficient_data":
        return (f"## IMPROVEMENT TELEMETRY: insufficient data "
                f"({sc.get('n_runs', 0)} runs — need at least {_MIN_WINDOW * 2}).")
    arrow = {"improving": "▲ IMPROVING", "regressing": "▼ REGRESSING", "flat": "▬ FLAT"}[v]
    mp = sc["windows"]["prior"]; mr = sc["windows"]["recent"]
    L = [f"## IMPROVEMENT TELEMETRY: {arrow}  (score {sc['score']:+}, {sc['n_runs']} runs)",
         f"  completion {mp['completion_rate']:.0%} → {mr['completion_rate']:.0%}   "
         f"dead-ends {mp['dead_end_rate']:.0%} → {mr['dead_end_rate']:.0%}   "
         f"blocks {mp['block_rate']:.0%} → {mr['block_rate']:.0%}"]
    if sc.get("drivers"):
        L.append("  drivers: " + ", ".join(sc["drivers"]))
    L.append(f"  knowledge: {sc['learning']['lessons']} lessons, "
             f"{sc['learning']['capabilities']} capabilities.")
    return "\n".join(L)


def diff_and_emit(publish: Callable[..., Any], runs: Optional[List[Dict[str, Any]]] = None,
                  workspace: Optional[str] = None) -> Dict[str, Any]:
    """Compute + publish a compact telemetry event (call at mission completion)."""
    sc = scorecard(runs=runs, workspace=workspace)
    try:
        publish("telemetry", {"verdict": sc["verdict"], "score": sc["score"],
                              "drivers": sc.get("drivers", []),
                              "learning": sc.get("learning", {})}, source="learning")
    except Exception:
        pass
    return sc
