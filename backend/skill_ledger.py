"""
skill_ledger.py — OX-SKILL-2 SKILL REPUTATION (the return arc for skills)
=========================================================================
FIRST PRINCIPLE (operator, 2026-07-10): a skill is not a thing you merely
invoke — like a human skill it must DEVELOP: be used, be graded by outcomes,
gain or lose trust, and surface for refinement when it keeps failing.

Before this module the House had the forward arc only: the auto-router picked
skills by trigger match and never learned whether a skill had ever carried a
mission to success. Every skill was trusted equally forever — invocation
without development.

The loop this closes (mirrors agent_reputation for council members):
  activation  — agent_run records WHICH skills were auto-activated per run
                (append-only skills_usage.jsonl; the only state this owns)
  grading     — reputation() joins activations against the agent_runs ledger
                (status TASK_COMPLETE/success = win; limit/stuck/error = loss;
                 still running = open, excluded)
  trust       — Laplace-smoothed (wins+1)/(wins+losses+2): prior 0.5, moves
                only with evidence, never reaches 0 or 1
  routing     — skills_auto_router multiplies match scores by trust_factor()
                (bounded 0.6..1.4 — a failing skill is DEPRIORITIZED, never
                 silenced: exploration is how a skill earns its way back)
  refinement  — refine_candidates() surfaces skills that keep failing, with
                the failing run ids as evidence; the FIX is human-gated via
                the existing skills API (same discipline as skill_evolution)

Deterministic, model-free. Stdlib only.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_BASE = Path(__file__).parent
LEDGER = _BASE / "skills_usage.jsonl"

_WIN_STATUSES = ("task_complete", "success", "complete", "done")
# ATTRIBUTION (first principle: blame requires causal relevance) — a run the
# OPERATOR interrupted or that sits at a human gate says nothing about the
# skill's technique. Measured 2026-07-10: 82/200 recent runs were
# 'interrupted' — counting those as losses would punish every skill for the
# operator's context switches. Neutral = excluded from grading.
_NEUTRAL_STATUSES = ("running", "", "interrupted", "blocked_awaiting_gate",
                     "cancelled", "hold")

# trust_factor bounds: never zero (a skill must be able to earn its way back)
_FACTOR_FLOOR = 0.6
_FACTOR_CEIL = 1.4
# RELATIVE grading (measured base rate was 0.14): a skill is good or bad
# COMPARED TO THE HOUSE'S OWN BASE RATE, not an absolute 50% bar — otherwise
# on a hard substrate every skill drifts down together and the comparison
# carries no information. factor = 0.6 + 0.4*lift, lift = trust/base_trust
# (lift 1.0 = average skill = neutral 1.0).
_REHAB_SECONDS = 30 * 86400   # unused for 30 days → factor floats back to ≥1.0
                              # (rich-get-richer breaker: a demoted skill that
                              #  stopped being selected gets a fresh chance)


def record_activation(run_id: str, skill_names: List[str],
                      path: Optional[Path] = None) -> bool:
    """Append one activation event. Never raises (best-effort ledger)."""
    if not run_id or not skill_names:
        return False
    try:
        p = Path(path) if path else LEDGER
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "run_id": run_id,
                                "skills": list(skill_names)}, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def _read_ledger(path: Optional[Path] = None, max_events: int = 5000) -> List[Dict[str, Any]]:
    p = Path(path) if path else LEDGER
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out[-max_events:]


def _classify(status: str) -> str:
    s = (status or "").strip().lower()
    if s in _NEUTRAL_STATUSES:
        return "open"
    if any(w in s for w in _WIN_STATUSES):
        return "win"
    return "loss"


def base_trust(runs: List[Dict[str, Any]]) -> float:
    """The House's own Laplace-smoothed base success rate over graded runs —
    the yardstick every skill is measured against (relative, not absolute)."""
    wins = losses = 0
    for r in runs or []:
        v = _classify(str(r.get("status") or ""))
        if v == "win":
            wins += 1
        elif v == "loss":
            losses += 1
    return (wins + 1) / (wins + losses + 2)


def reputation(runs: List[Dict[str, Any]],
               path: Optional[Path] = None,
               now: Optional[float] = None) -> Dict[str, Dict[str, Any]]:
    """Per-skill track record, computed LIVE by joining the activation ledger
    against the agent_runs rows (`runs`: dicts with at least id + status).

    Returns {skill: {uses, wins, losses, open, rate, trust, lift, factor,
    last_used}} where lift = trust / base_trust (1.0 = average for this House)
    and factor is the router weight. A skill unused for _REHAB_SECONDS gets
    factor >= 1.0 back (rehabilitation)."""
    status_by_run = {str(r.get("id")): str(r.get("status") or "") for r in (runs or [])}
    rep: Dict[str, Dict[str, Any]] = {}
    for evt in _read_ledger(path):
        rid = str(evt.get("run_id") or "")
        verdict = _classify(status_by_run.get(rid, ""))
        for name in evt.get("skills") or []:
            r = rep.setdefault(name, {"uses": 0, "wins": 0, "losses": 0, "open": 0,
                                      "last_used": 0.0, "failing_runs": []})
            r["uses"] += 1
            r["last_used"] = max(r["last_used"], float(evt.get("ts") or 0.0))
            if verdict == "win":
                r["wins"] += 1
            elif verdict == "loss":
                r["losses"] += 1
                r["failing_runs"].append(rid)
            else:
                r["open"] += 1
    bt = base_trust(runs)
    ts_now = now if now is not None else time.time()
    for name, r in rep.items():
        graded = r["wins"] + r["losses"]
        r["rate"] = round(r["wins"] / graded, 4) if graded else None
        r["trust"] = round((r["wins"] + 1) / (graded + 2), 4)      # Laplace, prior 0.5
        r["lift"] = round(r["trust"] / bt, 4) if bt > 0 else 1.0
        factor = max(_FACTOR_FLOOR, min(_FACTOR_CEIL, 0.6 + 0.4 * r["lift"]))
        if ts_now - r["last_used"] > _REHAB_SECONDS:
            factor = max(factor, 1.0)                              # fresh chance
        r["factor"] = round(factor, 4)
        r["failing_runs"] = r["failing_runs"][-10:]
    return rep


def trust_factors(runs: List[Dict[str, Any]],
                  path: Optional[Path] = None) -> Dict[str, float]:
    """{skill_name: factor} for the router. Unknown skill → 1.0 (neutral prior
    handled by the caller's .get(name, 1.0))."""
    return {name: r["factor"] for name, r in reputation(runs, path=path).items()}


def refine_candidates(runs: List[Dict[str, Any]], path: Optional[Path] = None,
                      min_uses: int = 3) -> List[Dict[str, Any]]:
    """Skills underperforming THE HOUSE'S OWN BASE RATE → surfaced for
    refinement (human-gated fix via the existing skills API).

    Relative, not absolute: with a measured base rate of 0.14, an absolute
    50% bar would flag skills performing 3x better than average. A skill is a
    refine candidate only when its lift < 1.0 with enough graded evidence.
    Evidence carries the failing runs' SUMMARIES — the concrete material a
    refiner needs to adjust the technique, not just ids."""
    summary_by_run = {str(r.get("id")): str(r.get("summary") or "")[:200]
                      for r in (runs or [])}
    out: List[Dict[str, Any]] = []
    for name, r in reputation(runs, path=path).items():
        graded = r["wins"] + r["losses"]
        if graded >= min_uses and r["lift"] < 1.0:
            out.append({"skill": name, "uses": r["uses"], "wins": r["wins"],
                        "losses": r["losses"], "rate": r["rate"],
                        "trust": r["trust"], "lift": r["lift"],
                        "evidence": [{"run_id": rid,
                                      "summary": summary_by_run.get(rid, "")}
                                     for rid in r["failing_runs"]],
                        "proposal": ("refine: skill underperforms the House's base "
                                     "rate when auto-activated — read the failing "
                                     "summaries, then patch its SKILL.md prompt or "
                                     "narrow its triggers")})
    out.sort(key=lambda c: (c["lift"], -c["losses"]))
    return out


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "ledger.jsonl"
    record_activation("r1", ["frontend-design"], path=tmp)
    record_activation("r2", ["frontend-design"], path=tmp)
    record_activation("r3", ["frontend-design", "pdf"], path=tmp)
    runs = [{"id": "r1", "status": "TASK_COMPLETE"},
            {"id": "r2", "status": "error"},
            {"id": "r3", "status": "limit"}]
    print(json.dumps(reputation(runs, path=tmp), ensure_ascii=False, indent=1))
    print(json.dumps(refine_candidates(runs, path=tmp, min_uses=2), ensure_ascii=False, indent=1))
