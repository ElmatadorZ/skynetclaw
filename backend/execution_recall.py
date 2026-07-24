"""
execution_recall.py — OX-1.5 EXECUTION MEMORY (read-model + pre-warm)
=====================================================================
OX-1.1/1.3/1.4 built three per-run signals that DIE at run end: the world model
(verified/absent paths, unknown tools), the execution-confidence scalar, and the
BLOCKED dead-end reason. So the next run re-discovers the same absent paths and
can re-enter the same dead end.

This module carries that knowledge FORWARD — with ZERO new state. It is a
read-model over the EXISTING `agent_runs` ledger:

  * WRITE  — at terminal time the loop appends a compact, machine-readable
             footer (`[[EXEC_MEM]]{json}`) onto the run's existing `summary`
             column. No schema change, no new table, no Memory/Learning edit.
  * READ   — at run START, recall() reads recent `agent_runs`, parses those
             footers, and returns what is SAFE to carry forward:
               - unknown tools      → task-INDEPENDENT hard fact (a tool that
                                       does not exist never exists) → seed world
               - absent paths       → task-similar HINT only (a file may have
                                       been created since) → prompt, never gated
               - prior dead-ends    → task-similar cautionary note

Ownership: owns NO state. Reads agent_runs (owned by openclaw_port_tier2),
seeds the per-run world_model (owned by world_model). Mirrors discovery.py:
read-only, deterministic, no model call.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

EXEC_MEM_MARK = "[[EXEC_MEM]]"
_TOK = re.compile(r"[a-zA-Z0-9_]+")


# ── footer write/parse (lives inside the existing summary column) ───────────
def encode_footer(world_snapshot: Optional[Dict[str, Any]],
                  exec_conf_value: Optional[float],
                  blocked: bool, halt: str, final_status: str,
                  max_paths: int = 12) -> str:
    """Build the ` [[EXEC_MEM]]{json}` footer appended to a run's summary."""
    snap = world_snapshot or {}
    payload = {
        "u": sorted(set(snap.get("absent_tools", []) or [])),            # unknown tools
        "a": list(snap.get("absent", []) or [])[:max_paths],             # absent paths
        "c": exec_conf_value,                                            # final exec confidence
        "b": bool(blocked),                                              # dead end?
        "h": (halt or "")[:120],                                         # halt reason
        "s": final_status or "",                                         # canonical terminal status
    }
    return " " + EXEC_MEM_MARK + json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def parse_footer(summary: str) -> Dict[str, Any]:
    """Extract the EXEC_MEM payload from a run summary (or {} if none)."""
    s = summary or ""
    i = s.rfind(EXEC_MEM_MARK)
    if i < 0:
        return {}
    try:
        return json.loads(s[i + len(EXEC_MEM_MARK):].strip()) or {}
    except Exception:
        return {}


def _tokens(s: str) -> set:
    return {t.lower() for t in _TOK.findall(s or "") if len(t) > 2}


def _similar(task_toks: set, other: str, threshold: float = 0.34) -> bool:
    o = _tokens(other)
    if not task_toks or not o:
        return False
    overlap = len(task_toks & o) / float(len(task_toks | o))
    return overlap >= threshold


# ── recall ──────────────────────────────────────────────────────────────────
def recall(task: str, recent_rows: List[Dict[str, Any]],
           max_runs: int = 30) -> Dict[str, Any]:
    """Aggregate carry-forward knowledge from recent agent_runs.

    recent_rows: list of dicts from AgentRunsDB.recent() (must include 'task'
    and 'summary'). Unknown tools are task-independent (carried from ALL runs);
    absent paths + dead-ends are carried only from TASK-SIMILAR runs.
    """
    task_toks = _tokens(task)
    unknown_tools: set = set()
    absent_paths: set = set()
    prior_dead_ends: List[Dict[str, str]] = []
    similar_count = 0

    for r in (recent_rows or [])[:max_runs]:
        mem = parse_footer(str(r.get("summary") or ""))
        if not mem:
            continue
        # unknown tools — always safe to carry (tool set is task-independent)
        for t in mem.get("u", []) or []:
            unknown_tools.add(t)
        # the rest is only meaningful for a SIMILAR task
        if _similar(task_toks, str(r.get("task") or "")):
            similar_count += 1
            for p in mem.get("a", []) or []:
                absent_paths.add(p)
            if mem.get("b"):
                prior_dead_ends.append({
                    "task": str(r.get("task") or "")[:120],
                    "halt": str(mem.get("h") or "")[:120],
                })

    return {
        "unknown_tools": sorted(unknown_tools),
        "absent_paths_hint": sorted(absent_paths),
        "prior_dead_ends": prior_dead_ends[:3],
        "similar_count": similar_count,
    }


# ── pre-warm + prompt injection ─────────────────────────────────────────────
def seed_world(world: Any, rec: Dict[str, Any]) -> int:
    """Seed ONLY the safe hard facts (unknown tools) into the per-run world
    model. Returns how many were seeded. Absent paths are NOT seeded — a file
    may have been created since; they surface as a HINT only (see render)."""
    if world is None or not rec:
        return 0
    n = 0
    try:
        import world_model as _W
        for name in rec.get("unknown_tools", []) or []:
            world.observe("tool:" + name, _W.ABSENT, kind="tool", source="execution_recall")
            n += 1
    except Exception:
        return n
    return n


def render(rec: Dict[str, Any]) -> str:
    """An EXECUTION MEMORY prompt block (empty when nothing to recall)."""
    if not rec:
        return ""
    ut = rec.get("unknown_tools") or []
    ap = rec.get("absent_paths_hint") or []
    de = rec.get("prior_dead_ends") or []
    if not (ut or ap or de):
        return ""
    L = ["## EXECUTION MEMORY (learned in prior runs — apply, do not re-discover):"]
    if ut:
        L.append("  NO SUCH TOOL (never call): " + ", ".join(ut))
    if ap:
        L.append("  PREVIOUSLY ABSENT (verify first — may have changed): " + ", ".join(ap[:12]))
    for d in de:
        L.append(f"  ⚠ PRIOR DEAD-END on a similar task: {d.get('halt','')}")
    return "\n".join(L)
