"""
acquisition.py — OX-ACQUISITION-1 KNOWLEDGE ACQUISITION PROTOCOL (additive)
===========================================================================
Enable THE HOUSE to ACQUIRE missing knowledge before asking the operator. It
distinguishes KNOWN / KNOWABLE / UNKNOWN (via the existing knowledge_seeking
gap detector) and, for KNOWABLE gaps, produces a structured acquisition plan
over a fixed source hierarchy — the House must try ≥1 valid source before
clarification.

Additive layer ONLY. Does not redesign runtime, workflow_runs, house_state,
agent_runs, lessons, capabilities, attribution, reinforcement or compliance. No
autonomous goals, no self-modification, no meta-learning. It plans + records;
the agent's normal tool calls do the actual searching, and this layer observes
which sources were checked.

Source hierarchy (priority order):
  1 existing_code · 2 workspace_files · 3 artifact_registry · 4 lesson_registry
  5 capability_registry · 6 documentation · 7 github · 8 obsidian · 9 web_search
  10 acquisition_attempt (escalation → operator, last resort)

Owns only acquisitions.json (gap + acquisition records).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_STORE = Path(__file__).parent / "acquisitions.json"

# ── source hierarchy (ordered) + the tools that search each ──────────────────
SOURCE_HIERARCHY: List[str] = [
    "existing_code", "workspace_files", "artifact_registry", "lesson_registry",
    "capability_registry", "documentation", "github", "obsidian", "web_search",
    "acquisition_attempt",
]
_HIER_IX = {s: i for i, s in enumerate(SOURCE_HIERARCHY)}
SOURCE_TOOLS: Dict[str, List[str]] = {
    "existing_code": ["grep_search", "find_files", "read_file"],
    "workspace_files": ["list_files", "find_files", "read_file"],
    "artifact_registry": ["read_file"],
    "lesson_registry": ["query_learning", "recall_archive"],
    "capability_registry": ["recall_archive"],
    "documentation": ["web_search", "http_request"],
    "github": ["http_request", "web_search", "shell_command"],
    "obsidian": ["search_obsidian", "read_obsidian_note"],
    "web_search": ["web_search"],
    "acquisition_attempt": ["ask_user_options"],
}
# observed tool → which source it represents (for recording what was checked)
_TOOL_SOURCE: Dict[str, str] = {
    "grep_search": "existing_code", "find_files": "existing_code",
    "read_file": "workspace_files", "list_files": "workspace_files",
    "search_obsidian": "obsidian", "read_obsidian_note": "obsidian",
    "web_search": "web_search", "http_request": "documentation",
    "download_file": "documentation", "shell_command": "github",
    "recall_archive": "lesson_registry", "query_learning": "lesson_registry",
}

# knowledge_seeking gap "need" label → candidate sources (relevant subset)
_NEED_SOURCES: Dict[str, List[str]] = {
    "external system / API knowledge": ["documentation", "github", "web_search"],
    "repository knowledge": ["github", "web_search"],
    "must locate existing code": ["existing_code", "workspace_files"],
    "prior artifact reference": ["artifact_registry", "workspace_files"],
    "captured-knowledge reference": ["obsidian", "lesson_registry"],
    "capability / skill knowledge": ["capability_registry", "lesson_registry"],
    "explicit learning need": ["documentation", "web_search", "github"],
}
_DEFAULT_SOURCES = ["documentation", "web_search"]


def _ordered(sources) -> List[str]:
    return sorted({s for s in sources if s in _HIER_IX}, key=lambda s: _HIER_IX[s])


def _gid(task: str, need: str) -> str:
    return "gap_" + hashlib.sha1(f"{task}:{need}".encode("utf-8")).hexdigest()[:10]


# ── 1. Knowledge Gap detection (KNOWABLE only) ───────────────────────────────
def detect_gaps(task: str, *, available_tools: Optional[List[str]] = None,
                workspace: Optional[str] = None, vault: Optional[str] = None,
                known_facts: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """KNOWABLE gaps as Knowledge Gap Objects. KNOWN tasks → []. Uses the existing
    knowledge_seeking detector; never re-implements classification."""
    try:
        import knowledge_seeking as _ks
        plan = _ks.plan(task or "", available_tools=available_tools,
                        workspace=workspace, vault=vault, known_facts=known_facts)
    except Exception:
        return []
    gaps: List[Dict[str, Any]] = []
    for g in (plan.get("knowable") or []):       # only KNOWABLE (has a source)
        need = g.get("need") or "knowledge"
        cands = _ordered(_NEED_SOURCES.get(need, _DEFAULT_SOURCES))
        gaps.append({
            "gap_id": _gid(task or "", need),
            "task": (task or "")[:300],
            "knowledge_needed": (g.get("match") or need)[:200],
            "gap_type": need,
            "source_candidates": cands,
            "status": "pending",
        })
    return gaps


# ── 2. Acquisition Planner ────────────────────────────────────────────────────
def plan_acquisition(gap: Dict[str, Any]) -> Dict[str, Any]:
    """For a KNOWABLE gap: goal · source_priority · validation_method · success."""
    cands = _ordered(gap.get("source_candidates") or _DEFAULT_SOURCES)
    return {
        "gap_id": gap.get("gap_id"),
        "acquisition_goal": f"Acquire: {gap.get('knowledge_needed','')}",
        "source_priority": cands,
        "tools_by_source": {s: SOURCE_TOOLS.get(s, []) for s in cands},
        "validation_method": "evidence_from_source + execution_reference",
        "success_criteria": "a searched source returns content that execution then uses",
    }


def attempt_order(gap: Dict[str, Any]) -> List[str]:
    return _ordered(gap.get("source_candidates") or _DEFAULT_SOURCES)


# ── 4. Clarification gate — search before ask ────────────────────────────────
def should_clarify(gap: Dict[str, Any], record: Optional[Dict[str, Any]] = None) -> bool:
    """Operator clarification is allowed ONLY after acquisition was attempted and
    failed, OR when no source is reachable at all. Before any attempt, if sources
    exist, the House must search first → False."""
    if record is None:
        # nothing searchable (no candidate sources) → ask is the only move.
        # Use the gap's RAW candidates (not attempt_order, which applies a default).
        return not bool(_ordered(gap.get("source_candidates") or []))
    if record.get("knowledge_found"):
        return False                              # acquired → no need to ask
    # attempted but nothing found → clarification now allowed
    return bool(record.get("sources_checked"))


# ── 3+5. Acquisition Record + validation ─────────────────────────────────────
def map_tools_to_sources(tools_used) -> List[str]:
    out: Set[str] = set()
    for t in (tools_used or []):
        s = _TOOL_SOURCE.get(str(t))
        if s:
            out.add(s)
    return _ordered(out)


def record(gap: Dict[str, Any], sources_checked: List[str],
           sources_successful: Optional[List[str]] = None,
           knowledge_found: bool = False, execution_used: bool = False,
           mission_id: Optional[str] = None, compliance_score: Optional[float] = None,
           path: Optional[Path] = None, keep: int = 500) -> Dict[str, Any]:
    rec = {
        "gap_id": gap.get("gap_id"),
        "mission_id": mission_id,                 # OX-METALEARNING-1: episode join key
        "knowledge_gap": gap.get("knowledge_needed", ""),
        "gap_type": gap.get("gap_type", ""),
        "task": gap.get("task", ""),
        "ts": time.time(),
        "sources_checked": _ordered(sources_checked),
        "sources_successful": _ordered(sources_successful or []),
        "knowledge_found": bool(knowledge_found),
        "execution_used": bool(execution_used),
        "compliance_score": compliance_score,     # OX-METALEARNING-1: episode signal
    }
    p = path or _STORE
    try:
        data = _load(p); data.append(rec); data = data[-keep:]
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "records": data}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[acquisition] record failed: {e}")
    return rec


def validate(record_obj: Dict[str, Any]) -> bool:
    """Acquired ONLY IF: evidence exists (knowledge_found) AND a source is recorded
    (sources_successful) AND execution references it (execution_used)."""
    return bool(record_obj.get("knowledge_found")
                and record_obj.get("sources_successful")
                and record_obj.get("execution_used"))


def _load(path: Path) -> List[Dict[str, Any]]:
    try:
        if path.exists():
            return (json.loads(path.read_text(encoding="utf-8")) or {}).get("records", [])
    except Exception:
        pass
    return []


def load_records(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    return _load(path or _STORE)


# ── 7. Metrics ────────────────────────────────────────────────────────────────
def metrics(records: Optional[List[Dict[str, Any]]] = None,
            path: Optional[Path] = None) -> Dict[str, Any]:
    records = records if records is not None else load_records(path)
    n = len(records)
    attempted = [r for r in records if r.get("sources_checked")]
    succeeded = [r for r in records if r.get("knowledge_found")]
    gap_types: Dict[str, int] = {}
    src_success: Dict[str, int] = {}
    for r in records:
        gap_types[r.get("gap_type", "?")] = gap_types.get(r.get("gap_type", "?"), 0) + 1
        for s in (r.get("sources_successful") or []):
            src_success[s] = src_success.get(s, 0) + 1
    top = sorted(src_success.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "total_gaps": n,
        "acquisition_attempt_rate": round(len(attempted) / n, 3) if n else 0.0,
        "acquisition_success_rate": round(len(succeeded) / len(attempted), 3) if attempted else 0.0,
        "knowledge_gap_types": gap_types,
        "top_successful_sources": [{"source": s, "n": c} for s, c in top[:5]],
    }


# ── prompt rendering — ACQUISITION brief (search before ask) ─────────────────
def render_brief(gaps: List[Dict[str, Any]]) -> str:
    if not gaps:
        return ""
    L = ["## KNOWLEDGE ACQUISITION (acquire KNOWABLE gaps by searching — ask the operator LAST):"]
    for g in gaps[:4]:
        order = attempt_order(g)
        L.append(f"  • need: {g['knowledge_needed']}")
        L.append("     search in order: " + " → ".join(order))
    L.append("  RULE: try at least one source above BEFORE ask_user_options. "
             "Ask only if every candidate source fails.")
    return "\n".join(L)
