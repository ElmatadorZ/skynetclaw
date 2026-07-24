"""
observability.py — OX-OBSERVABILITY-1 (read-only aggregator)
============================================================
Make the House observable: one fresh, truthful snapshot an operator UI can bind
to so it can explain exactly what the House is doing, why it stopped, and what it
currently believes — without reading logs or databases.

Creates NO new intelligence or learning. Pure read-only aggregation over the
EXISTING stores: workflow_runs, house_state, agent_runs, decision, theory,
research_agenda, unknowns, paradigm.

Design notes:
  F. Always reads LIVE from the stores (never the discovery `_cached` values) so
     the UI can never show a value older than the DB.
  G. Every section is independently guarded — a missing/empty source degrades to
     a blank section, never an error.

Panels (all fed by snapshot()):
  A/B/D  Workflow Timeline + active workflow_id + trace (reached/failed phase,
         termination reason) — from workflow_runs (+ agent_runs)
  C      house_state metadata (state_id, updated_at, source)
  E      Cognitive Stack (decision / theory / research agenda / unknowns /
         paradigm) with confidence + a generated_at timestamp

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

# canonical workflow phases → display labels (mirrors workflow_runs.PHASE_ORDER)
_PHASES = [("dispatch", "DISPATCHED"), ("comprehend", "COMPREHEND"), ("plan", "PLAN"),
           ("council", "COUNCIL"), ("execute", "EXECUTE"), ("reflect", "REFLECT"),
           ("complete", "COMPLETE")]
_PHASE_IX = {p: i for i, (p, _) in enumerate(_PHASES)}
_TERMINAL_BAD = ("failed", "interrupted", "timeout", "error")


# ── A/B/D — workflow timeline + trace (pure) ─────────────────────────────────
def build_workflow_view(wf_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Workflow Timeline + active workflow_id + trace from a workflow_runs row."""
    if not wf_row:
        return {"workflow_id": None, "timeline": [], "current_phase": None,
                "status": None, "termination_reason": None, "reached_phase": None,
                "failed_phase": None, "house_state_id": None, "agent_run_id": None,
                "dispatched_at": None, "updated_at": None}
    phase = (wf_row.get("phase") or "dispatch")
    cur_ix = _PHASE_IX.get(phase, 0)
    status = wf_row.get("status")
    is_bad = str(status or "").lower() in _TERMINAL_BAD
    timeline = [{"phase": label, "key": key, "reached": i <= cur_ix}
                for i, (key, label) in enumerate(_PHASES)]
    reached_label = dict(_PHASES).get(phase, phase)
    return {
        "workflow_id": wf_row.get("workflow_id"),
        "directive": (wf_row.get("directive") or "")[:160],
        "timeline": timeline,
        "current_phase": reached_label,
        "status": status,
        "termination_reason": wf_row.get("termination_reason") or None,
        "reached_phase": reached_label,
        "failed_phase": reached_label if is_bad else None,
        "house_state_id": wf_row.get("house_state_id"),
        "agent_run_id": wf_row.get("agent_run_id"),
        "dispatched_at": wf_row.get("created_at"),
        "updated_at": wf_row.get("updated_at"),
    }


def build_house_state_view(st: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """C — house_state metadata: state_id, updated_at, source."""
    if not st:
        return {"state_id": None, "updated_at": None, "source": None,
                "status": None, "question": None, "confidence": None}
    return {
        "state_id": st.get("id"),
        "updated_at": st.get("updated_at"),
        "source": st.get("session_id") or st.get("source") or "house_state",
        "status": st.get("status"),
        "question": (st.get("question") or "")[:160],
        "confidence": st.get("confidence"),
    }


def build_cognitive_stack(decisions: Optional[List[Dict[str, Any]]] = None,
                          theories: Optional[List[Dict[str, Any]]] = None,
                          agenda: Optional[List[Dict[str, Any]]] = None,
                          unknowns_metrics: Optional[Dict[str, Any]] = None,
                          paradigm_metrics: Optional[Dict[str, Any]] = None,
                          generated_at: Optional[float] = None) -> Dict[str, Any]:
    """E — the cognitive stack with confidence + a generated_at timestamp."""
    ts = generated_at if generated_at is not None else time.time()
    decisions = decisions or []
    theories = theories or []
    agenda = agenda or []

    def _top(lst, label_key, conf_key):
        return ({"label": lst[0].get(label_key), "confidence": lst[0].get(conf_key)}
                if lst else {"label": None, "confidence": None})

    return {
        "generated_at": ts,
        "decision": {**_top(decisions, "recommendation", "confidence"), "count": len(decisions)},
        "theory": {**_top(theories, "theory", "confidence"), "count": len(theories)},
        "research_agenda": {"label": (agenda[0].get("topic") if agenda else None),
                            "priority_score": (agenda[0].get("priority_score") if agenda else None),
                            "count": len(agenda)},
        "unknowns": unknowns_metrics or {},
        "paradigm": paradigm_metrics or {},
    }


# ── live snapshot (reads fresh — never cached; every part guarded) ───────────
def _active_workflow(wf_rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for r in wf_rows:                       # recent() is newest-first
        if str(r.get("status") or "").lower() in ("created", "active"):
            return r
    return wf_rows[0] if wf_rows else None


def snapshot(workflow_id: str = "") -> Dict[str, Any]:
    """Assemble the full observability snapshot, live from the stores."""
    out: Dict[str, Any] = {"generated_at": time.time()}

    # A/B/D — workflow
    try:
        import workflow_runs as _wf
        db = _wf.WorkflowRunsDB()
        if workflow_id:
            wf_row = db.get(workflow_id)
        else:
            wf_row = _active_workflow(db.recent(limit=20))
        out["workflow"] = build_workflow_view(wf_row)
        out["recent_workflows"] = [
            {"workflow_id": r.get("workflow_id"), "status": r.get("status"),
             "phase": r.get("phase"), "directive": (r.get("directive") or "")[:80]}
            for r in db.recent(limit=10)]
    except Exception as e:
        out["workflow"] = build_workflow_view(None); out["recent_workflows"] = []
        out["workflow_error"] = str(e)

    # C — house_state (LIVE, not cached)
    try:
        import house_state as _hs
        out["house_state"] = build_house_state_view(_hs.current())
    except Exception as e:
        out["house_state"] = build_house_state_view(None); out["house_state_error"] = str(e)

    # E — cognitive stack
    try:
        import decision as _dec
        decisions = _dec.decide()
    except Exception:
        decisions = []
    try:
        import theory as _th
        theories = _th.form()
    except Exception:
        theories = []
    try:
        import research_agenda as _ra
        agenda = _ra.form()
    except Exception:
        agenda = []
    try:
        import unknowns as _un
        un_m = _un.metrics()
    except Exception:
        un_m = {}
    try:
        import paradigm as _pg
        pg_m = _pg.metrics()
    except Exception:
        pg_m = {}
    out["cognitive_stack"] = build_cognitive_stack(decisions, theories, agenda, un_m, pg_m,
                                                   generated_at=out["generated_at"])
    return out
