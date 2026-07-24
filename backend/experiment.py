"""
experiment.py — OX-EXPERIMENT-1 EXPERIMENT DESIGN PROTOCOL (read-only)
=====================================================================
Move from CORRELATION ("github_first works, confidence 0.91") to CONTROLLED
VALIDATION ("is github_first actually the CAUSE?"). This layer proposes
controlled experiments — a control ordering vs a test ordering — for beliefs the
House is confident about, prioritising those whose recent evidence is starting
to contradict them.

Builds on MetaLearning (the belief) + Causal Discovery (a mechanism) + Belief
Revision (recent contradiction) + Calibration. Read-only — it produces
RECOMMENDATIONS only. It DOES NOT run experiments, change behavior, schedule, or
create goals.

Experiment Candidate:
  {hypothesis, gap_type, control_strategy, test_strategy, evidence, priority,
   reason, suggested_test, has_causal, has_drift}

Priority:
  HIGH    strong belief (confidence > 0.80) AND recent contradiction (drift)
  MEDIUM  strong belief, no contradiction
  (weak belief → no experiment)

Owns no state. Pure read-model.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

STRONG_CONF = 0.80      # belief must exceed this to be worth an experiment


def _drift_matches(d: Dict[str, Any], gap_type: str, lead: str) -> bool:
    # token-match (not raw substring) so a short gap_type can't spuriously match
    # inside another word (e.g. "b" inside "github").
    toks = set(re.findall(r"[a-z0-9_]+", str(d.get("belief", "")).lower()))
    pat = str(d.get("pattern", "")).lower()
    return (gap_type.lower() in toks or lead.lower() in toks
            or pat in (gap_type.lower(), lead.lower()))


def _causal_for(hypotheses: Dict[str, Any], gap_type: str, lead: str) -> bool:
    for h in (hypotheses or {}).get(gap_type, []) or []:
        fac = str(h.get("factor", "")).lower()
        if lead.lower() in fac or fac.startswith(("uses:", "leads:")):
            return True
    return bool((hypotheses or {}).get(gap_type))


# ── design ────────────────────────────────────────────────────────────────────
def design(strategies: Optional[Dict[str, Any]] = None,
           hypotheses: Optional[Dict[str, Any]] = None,
           drifts: Optional[List[Dict[str, Any]]] = None,
           strong_conf: float = STRONG_CONF) -> List[Dict[str, Any]]:
    """Produce experiment candidates. Defaults load from the stores."""
    if strategies is None:
        try: import metalearning as _ml; strategies = _ml.load_strategies()
        except Exception: strategies = {}
    if hypotheses is None:
        try: import causal as _ca; hypotheses = _ca.load_hypotheses()
        except Exception: hypotheses = {}
    if drifts is None:
        try: import belief_revision as _br; drifts = _br.review().get("belief_drift", [])
        except Exception: drifts = []

    out: List[Dict[str, Any]] = []
    for gap_type, st in (strategies or {}).items():
        conf = float(st.get("confidence", 0) or 0)
        order = list(st.get("recommended_order") or [])
        if conf <= strong_conf:
            continue                       # weak belief → no experiment (validation C)
        if len(order) < 2:
            continue                       # need an alternative to form a controlled test
        lead, second = order[0], order[1]
        has_drift = any(_drift_matches(d, gap_type, lead) for d in (drifts or []))
        has_causal = _causal_for(hypotheses, gap_type, lead)
        priority = "high" if has_drift else "medium"
        reason = ("belief strong but recent evidence declining" if has_drift
                  else "belief strong with no recent contradiction — confirm the cause")
        out.append({
            "hypothesis": f"{lead}_first_is_better",
            "gap_type": gap_type,
            "control_strategy": order,                 # current primary ordering
            "test_strategy": [second, lead] + order[2:],   # the controlled alternative
            "evidence": int(st.get("evidence_count", 0) or 0),
            "confidence": round(conf, 3),
            "priority": priority,
            "reason": reason,
            "suggested_test": f"alternate {lead}_first vs {second}_first",
            "has_causal": has_causal,
            "has_drift": has_drift,
        })
    _rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda e: (_rank.get(e["priority"], 3), -e["evidence"]))
    return out


# ── recall / metrics ─────────────────────────────────────────────────────────
def render_brief(candidates: Optional[List[Dict[str, Any]]] = None, limit: int = 4) -> str:
    candidates = candidates if candidates is not None else design()
    if not candidates:
        return ""
    L = ["## EXPERIMENT CANDIDATES (controlled tests to validate beliefs — recommendation only):"]
    for e in candidates[:limit]:
        L.append(f"  • [{e['priority'].upper()}] {e['hypothesis']} — {e['reason']}; "
                 f"test: {e['suggested_test']}")
    return "\n".join(L)


def metrics(candidates: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    candidates = candidates if candidates is not None else design()
    by_pri: Dict[str, int] = {}
    for e in candidates:
        by_pri[e["priority"]] = by_pri.get(e["priority"], 0) + 1
    return {
        "experiment_count": len(candidates),
        "by_priority": by_pri,
        "high_priority": [e["hypothesis"] for e in candidates if e["priority"] == "high"][:5],
        "top": [e["hypothesis"] for e in candidates[:5]],
    }
