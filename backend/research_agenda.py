"""
research_agenda.py — OX-RESEARCH-AGENDA-1 RESEARCH AGENDA PROTOCOL (read-only)
=============================================================================
Decide WHAT THE HOUSE SHOULD INVESTIGATE NEXT — prioritise research topics by
blending how much they matter (impact), how unsure we are (uncertainty), and how
testable they are (leverage). Synthesises Theory, Experiment, Belief Revision and
Calibration into a ranked agenda.

Builds on Theory / Experiment / Belief Revision / Calibration. Read-only — no
autonomy, no scheduling, no behavior change. It RANKS questions; it does not
answer or run them.

Research Priority:
  {topic, pattern, impact, uncertainty, leverage, priority_score,
   supporting_domains, has_experiment, has_drift, drivers}

Score = impact * uncertainty * leverage  (multiplicative — a top priority must
matter AND be uncertain AND be testable). A pattern with no theory and no
experiment is not investigable here and is excluded.

Owns no state. Pure read-model.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_DRIFT_SEVERITY = {"high": 0.9, "medium": 0.6, "low": 0.3}
_BASE_UNCERTAINTY = 0.2


def _toks(s: str) -> set:
    return set(re.findall(r"[a-z0-9_]+", (s or "").lower()))


def _exp_pattern(e: Dict[str, Any]) -> str:
    h = str(e.get("hypothesis", ""))
    return h.split("_first", 1)[0] if "_first" in h else (e.get("pattern") or e.get("gap_type") or "")


def _matches(text_field: str, pattern: str, obj: Dict[str, Any]) -> bool:
    p = pattern.lower()
    # prefer the explicit pattern field (precise); fall back to text tokens only
    # when absent, so a multi-source belief label doesn't match every source.
    if obj.get("pattern"):
        return str(obj["pattern"]).lower() == p
    return p in _toks(obj.get(text_field, ""))


# ── agenda formation ──────────────────────────────────────────────────────────
def form(theories: Optional[List[Dict[str, Any]]] = None,
         experiments: Optional[List[Dict[str, Any]]] = None,
         drifts: Optional[List[Dict[str, Any]]] = None,
         calibration: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Rank research priorities. Defaults load from the stores."""
    if theories is None:
        try: import theory as _th; theories = _th.form()
        except Exception: theories = []
    if experiments is None:
        try: import experiment as _ex; experiments = _ex.design()
        except Exception: experiments = []
    if drifts is None:
        try: import belief_revision as _br; drifts = _br.review().get("belief_drift", [])
        except Exception: drifts = []
    if calibration is None:
        try: import calibration as _cal; calibration = _cal.calibrate()
        except Exception: calibration = []

    theory_by_pat = {t.get("pattern"): t for t in (theories or []) if t.get("pattern")}
    exp_by_pat: Dict[str, List[Dict[str, Any]]] = {}
    for e in (experiments or []):
        exp_by_pat.setdefault(_exp_pattern(e), []).append(e)

    patterns = set(theory_by_pat) | set(exp_by_pat)
    patterns.discard(""); patterns.discard(None)

    out: List[Dict[str, Any]] = []
    for pat in patterns:
        drivers: List[str] = []
        th = theory_by_pat.get(pat)
        exps = exp_by_pat.get(pat, [])

        # IMPACT — breadth/importance (a broad theory matters most)
        if th:
            impact = round(min(1.0, 0.5 + 0.25 * len(th.get("supporting_domains", []))), 3)
            drivers.append(f"theory across {len(th.get('supporting_domains', []))} domains")
        elif exps:
            impact = 0.5
        else:
            impact = 0.3

        # LEVERAGE — is there a clear, prioritised way to test it?
        if any(e.get("priority") == "high" for e in exps):
            leverage = 0.9; drivers.append("high-priority experiment available")
        elif exps:
            leverage = 0.6; drivers.append("experiment available")
        else:
            leverage = 0.3

        # UNCERTAINTY — drift + miscalibration
        d_unc = max((_DRIFT_SEVERITY.get(d.get("severity", ""), 0.3)
                     for d in (drifts or []) if _matches("belief", pat, d)), default=0.0)
        has_drift = d_unc > 0
        if has_drift:
            drivers.append("recent belief drift")
        c_err = max((float(c.get("error", 0) or 0)
                     for c in (calibration or [])
                     if c.get("status") in ("overconfident", "underconfident")
                     and _matches("subject", pat, c)), default=0.0)
        if c_err > _BASE_UNCERTAINTY:
            drivers.append(f"miscalibrated (error {round(c_err,2)})")
        uncertainty = round(max(d_unc, c_err, _BASE_UNCERTAINTY), 3)

        score = round(impact * uncertainty * leverage, 4)
        out.append({
            "topic": (th or {}).get("theory") or f"Is '{pat}' actually causal?",
            "pattern": pat,
            "impact": impact,
            "uncertainty": uncertainty,
            "leverage": leverage,
            "priority_score": score,
            "supporting_domains": (th or {}).get("supporting_domains", []),
            "has_experiment": bool(exps),
            "has_drift": has_drift,
            "drivers": drivers,
        })
    out.sort(key=lambda r: r["priority_score"], reverse=True)
    return out


# ── recall / metrics ─────────────────────────────────────────────────────────
def render_brief(agenda: Optional[List[Dict[str, Any]]] = None, limit: int = 4) -> str:
    agenda = agenda if agenda is not None else form()
    if not agenda:
        return ""
    L = ["## RESEARCH AGENDA (what to investigate next — prioritised, advisory):"]
    for r in agenda[:limit]:
        L.append(f"  • {r['topic']} (priority {r['priority_score']}; "
                 f"impact {r['impact']}, uncertainty {r['uncertainty']}, leverage {r['leverage']})"
                 + (f" — {', '.join(r['drivers'][:2])}" if r["drivers"] else ""))
    return "\n".join(L)


def metrics(agenda: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    agenda = agenda if agenda is not None else form()
    return {
        "agenda_size": len(agenda),
        "top_priority": agenda[0]["topic"] if agenda else None,
        "top_score": agenda[0]["priority_score"] if agenda else None,
        "avg_score": round(sum(r["priority_score"] for r in agenda) / len(agenda), 4) if agenda else None,
        "with_experiment": sum(1 for r in agenda if r["has_experiment"]),
        "with_drift": sum(1 for r in agenda if r["has_drift"]),
    }
