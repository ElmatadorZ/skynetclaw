"""
attribution.py — OX-ATTRIBUTION-1 OUTCOME ATTRIBUTION ENGINE
============================================================
FIRST PRINCIPLE: correlation is not causation. A recalled lesson is not valuable
merely because success followed it. The House could learn, promote, measure and
adjust — but it could not tell WHICH recalled knowledge actually contributed to
an outcome. This engine connects the evidence:

    recalled lesson / capability / control policy  →  mission outcome

It does NOT redesign telemetry, control or runtime, and does NOT self-initiate.
Two layers:

  1. PER-MISSION RECORD — for each mission, what was recalled, what the control
     verdict was, the outcome, and a signed per-mission attribution_score
     (a correlation-aware observation — positive when recall preceded success,
     negative when recall failed to prevent failure, ~0 when nothing was recalled).

  2. CROSS-MISSION ATTRIBUTION — the causal-ish signal: for each capability /
     lesson / control verdict, compare the success rate of missions where it was
     recalled against the BASELINE success rate. Lift over baseline (with enough
     evidence) is what credits or blames an item — answering which capabilities
     actually help, which lessons improve outcomes, which control actions work,
     and which should be demoted.

Owns only attribution.json (the per-mission records). Read-only over everything
else. (Identifies demotion candidates; does NOT itself demote — that would be
acting on the analysis, out of scope here.)

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE = Path(__file__).parent / "attribution.json"

SUCCESS = "success"
FAILURE = "failure"
_MIN_EVIDENCE = 3        # min missions before a lift is trusted (causation needs repetition)
_LIFT_EPS = 0.10         # |lift| above this = a real contribution signal


def _is_success(outcome: str) -> bool:
    return (outcome or "").strip().lower() in (SUCCESS, "task_complete", "complete", "completed")


# ── PER-MISSION attribution_score (correlation-aware observation) ────────────
def mission_score(outcome: str, n_recalled: int) -> float:
    """Signed per-mission credit/blame to the recalled knowledge:
      success + recall   → positive (more recall, more credit, capped)
      success, no recall → ~0   (recall cannot be credited)
      failure + recall   → negative (recall present, didn't prevent failure)
      failure, no recall → 0    (recall not implicated)"""
    had = n_recalled > 0
    mag = round(min(1.0, 0.6 + 0.1 * min(n_recalled, 4)), 2)
    if _is_success(outcome):
        return mag if had else 0.05
    return -mag if had else 0.0


# ── record / store ────────────────────────────────────────────────────────────
def record(mission_id: str, *, capabilities: Optional[List[str]] = None,
           lessons: Optional[List[str]] = None, control_verdict: Optional[str] = None,
           control_policy: Optional[Dict[str, Any]] = None, outcome: str = FAILURE,
           compliance_score: Optional[float] = None, compliance_class: Optional[str] = None,
           path: Optional[Path] = None, keep: int = 500) -> Dict[str, Any]:
    """Record one mission's attribution: what was recalled vs the outcome.

    OX-COMPLIANCE-1 (additive): optionally carries the per-mission compliance
    signal (did the recalled capabilities actually shape execution). Stored as
    read-only evidence; the attribution_score computation is UNCHANGED."""
    caps = [c for c in (capabilities or []) if c]
    less = [l for l in (lessons or []) if l]
    rec = {
        "mission_id": mission_id,
        "ts": time.time(),
        "recalled_capabilities": caps,
        "recalled_lessons": less,
        "control_policy": control_verdict or (control_policy or {}).get("verdict"),
        "outcome": SUCCESS if _is_success(outcome) else FAILURE,
        "attribution_score": mission_score(outcome, len(caps) + len(less)),
        "compliance_score": compliance_score,
        "compliance_class": compliance_class,
    }
    p = path or _STORE
    try:
        data = _load(p)
        data.append(rec)
        data = data[-keep:]
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "records": data}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[Attribution] record failed: {e}")
    return rec


def _load(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            return (json.loads(path.read_text(encoding="utf-8")) or {}).get("records", [])
    except Exception:
        pass
    return []


def load_records(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    return _load(path or _STORE)


# ── CROSS-MISSION attribution (lift over baseline = the causal signal) ───────
def _item_stats(records: List[Dict[str, Any]], field: str, name: str,
                baseline: float) -> Dict[str, Any]:
    rows = [r for r in records if name in (r.get(field) or [])]
    n = len(rows)
    s = sum(1 for r in rows if r.get("outcome") == SUCCESS)
    sr = (s / n) if n else 0.0
    lift = round(sr - baseline, 3)
    if n < _MIN_EVIDENCE:
        rec = "insufficient_evidence"
    elif lift >= _LIFT_EPS:
        rec = "reinforce"
    elif lift <= -_LIFT_EPS:
        rec = "demote"
    else:
        rec = "neutral"
    return {"recalled_in": n, "success_rate": round(sr, 3), "lift": lift,
            "score": lift, "recommendation": rec}


def attribute(records: Optional[List[Dict[str, Any]]] = None,
              path: Optional[Path] = None) -> Dict[str, Any]:
    """Aggregate per-item attribution. Lift = success-rate-when-recalled minus
    the baseline success rate. Items with enough evidence and clear lift are
    flagged reinforce / demote."""
    records = records if records is not None else load_records(path)
    n = len(records)
    if not n:
        return {"baseline": 0.0, "n_missions": 0, "capabilities": {}, "lessons": {},
                "control": {}, "demote": [], "reinforce": []}
    baseline = sum(1 for r in records if r.get("outcome") == SUCCESS) / n

    cap_names = {c for r in records for c in (r.get("recalled_capabilities") or [])}
    les_ids = {l for r in records for l in (r.get("recalled_lessons") or [])}
    capabilities = {nm: _item_stats(records, "recalled_capabilities", nm, baseline) for nm in cap_names}
    lessons = {lid: _item_stats(records, "recalled_lessons", lid, baseline) for lid in les_ids}

    # control verdicts: success rate when each verdict's policy was active
    control: Dict[str, Any] = {}
    verdicts = {r.get("control_policy") for r in records if r.get("control_policy")}
    for v in verdicts:
        rows = [r for r in records if r.get("control_policy") == v]
        s = sum(1 for r in rows if r.get("outcome") == SUCCESS)
        control[v] = {"active_in": len(rows), "success_rate": round(s / len(rows), 3),
                      "lift": round(s / len(rows) - baseline, 3)}

    demote = sorted([{"type": "capability", "name": nm, **st} for nm, st in capabilities.items()
                     if st["recommendation"] == "demote"]
                    + [{"type": "lesson", "name": lid, **st} for lid, st in lessons.items()
                       if st["recommendation"] == "demote"],
                    key=lambda d: d["lift"])
    reinforce = sorted([{"type": "capability", "name": nm, **st} for nm, st in capabilities.items()
                        if st["recommendation"] == "reinforce"]
                       + [{"type": "lesson", "name": lid, **st} for lid, st in lessons.items()
                          if st["recommendation"] == "reinforce"],
                       key=lambda d: d["lift"], reverse=True)
    return {"baseline": round(baseline, 3), "n_missions": n,
            "capabilities": capabilities, "lessons": lessons, "control": control,
            "demote": demote, "reinforce": reinforce}


def summary(report: Optional[Dict[str, Any]] = None, path: Optional[Path] = None) -> str:
    """A human answer to the four attribution questions."""
    rep = report if report is not None else attribute(path=path)
    if not rep.get("n_missions"):
        return "## ATTRIBUTION: no missions recorded yet."
    L = [f"## ATTRIBUTION ({rep['n_missions']} missions, baseline success {rep['baseline']:.0%}):"]
    if rep["reinforce"]:
        L.append("  HELPS (reinforce): " + ", ".join(
            f"{d['name']} (lift {d['lift']:+}, n={d['recalled_in']})" for d in rep["reinforce"][:4]))
    if rep["demote"]:
        L.append("  HURTS (demote candidates): " + ", ".join(
            f"{d['name']} (lift {d['lift']:+}, n={d['recalled_in']})" for d in rep["demote"][:4]))
    if rep["control"]:
        best = max(rep["control"].items(), key=lambda kv: kv[1]["success_rate"], default=None)
        if best:
            L.append(f"  CONTROL: '{best[0]}' verdict ran at {best[1]['success_rate']:.0%} success.")
    if not (rep["reinforce"] or rep["demote"]):
        L.append("  (No item has enough evidence yet to credit or blame — keep accruing.)")
    return "\n".join(L)
