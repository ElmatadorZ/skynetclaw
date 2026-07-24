"""
workflow_memory.py — OX-UI-1 WORKFLOW MEMORY (read-model)
=========================================================
Constitutional rule (OX-UI-1): House Mind ≠ Workflow Context.
  House Mind        = current COGNITIVE state (house_cognition.frame()).
  Workflow Memory   = historical EXECUTION artifacts (this module).

Workflow artifacts — TASK AS / DONE_WHEN / PLAN / files / status / rollback —
describe HOW a mission was executed, not what the House believes now. They must
never appear in House Mind. This is a thin, read-only projection over the
EXISTING agent_runs ledger (owned by openclaw_port_tier2): it shapes each run
for the operator, strips machine footers, and marks runs archived once they are
no longer running. Zero new state — mirrors execution_recall / discovery.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# strip the OX-1.5 execution-memory footer that lives inside summary
try:
    from execution_recall import EXEC_MEM_MARK as _MEM_MARK
except Exception:
    _MEM_MARK = "[[EXEC_MEM]]"

_DONE_WHEN_RE = re.compile(r"^\s*\[done_when:\s*(.*?)\]\s*", re.IGNORECASE | re.DOTALL)

# raw ledger status → operator-language status (never show raw)
_STATUS_LABEL = {
    "running": ("thinking", "Executing"),
    "task_complete": ("done", "Complete"),
    "success": ("done", "Complete"),
    "blocked": ("blocked", "Blocked — dead end"),
    "limit": ("failed", "Hit step limit"),
    "stuck": ("failed", "Halted"),
    "error": ("failed", "Error"),
    "cancelled": ("failed", "Cancelled"),
}


def _clean_summary(summary: str) -> Dict[str, str]:
    """Split a stored summary into {done_when, text} and drop the EXEC_MEM footer."""
    s = summary or ""
    i = s.find(_MEM_MARK)
    if i >= 0:
        s = s[:i]
    done_when = ""
    m = _DONE_WHEN_RE.match(s)
    if m:
        done_when = (m.group(1) or "").strip()
        s = s[m.end():]
    return {"done_when": done_when, "text": s.strip()}


def _shape(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = str(row.get("status") or "").lower()
    state, label = _STATUS_LABEL.get(raw, ("failed", raw or "unknown"))
    parts = _clean_summary(str(row.get("summary") or ""))
    return {
        "id": row.get("id", ""),
        "task": (row.get("task") or "")[:300],          # TASK AS
        "done_when": parts["done_when"],                  # DONE_WHEN
        "outcome": parts["text"][:600],                   # closing summary (no machine footer)
        "status": state,                                  # operator-language state
        "status_label": label,
        "archived": raw != "running",                     # completed runs archive out of the live view
        "n_steps": row.get("n_steps") or 0,
        "n_tools": row.get("n_tools") or 0,
        "started_at": row.get("started_at") or 0.0,
        "ended_at": row.get("ended_at") or 0.0,
        "model": row.get("model") or "",
        "trajectory": bool(row.get("trajectory_path")),   # full PLAN/steps available via trajectory
    }


def recent(recent_rows: List[Dict[str, Any]], limit: int = 6) -> List[Dict[str, Any]]:
    """Shape recent agent_runs into operator-facing Workflow Memory entries.
    Newest first; active (running) runs sort to the top."""
    shaped = [_shape(r) for r in (recent_rows or [])]
    shaped.sort(key=lambda e: (0 if not e["archived"] else 1,
                               -(e["started_at"] or 0)))
    return shaped[:max(1, limit)]
