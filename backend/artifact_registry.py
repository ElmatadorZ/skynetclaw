"""
artifact_registry.py — OX-ARTIFACT-1 ARTIFACT AWARENESS PROTOCOL (read-side)
=============================================================================
FIRST PRINCIPLE: a mission is not the question, the prompt, or the plan — a
mission is the ARTIFACT it produced. If the artifact cannot be found, the mission
cannot be resumed. The House remembered questions, missions, tools and gaps, but
NOT what it created — so "continue previous report" searched house_state.question
instead of the actual generated output.

This module gives the House Artifact Awareness as a pure READ-SIDE capability.
It is NOT a second memory system: it owns NO state and writes nothing. It is a
projection over the EXISTING mission ledger (`_MISSION_LEDGER.json`, owned by
main._ledger_*), whose every signed entry already records {id, ts, files[...]}.
Each ledger file becomes a structured artifact record, with existence/size read
live from disk:

    {mission_id, artifact_path, artifact_type, created_at, size, exists}

Capabilities (exactly the OX-ARTIFACT-1 spec):
  1. REGISTRY            — registry(): project the ledger's files into records.
  2. DISCOVERY           — latest_artifact / recent_artifacts / mission_artifacts /
                           artifact_exists (read-only lookup).
  3. RESUME INTELLIGENCE — resolve_resume(): for "continue previous report", find
                           the matching artifact, verify it exists, recommend
                           resume — NOT search the prompt / make a new plan.
  4. PRIORITY ROUTING    — references_artifact(): when the operator references a
                           prior output, the registry is consulted BEFORE question
                           / mission / knowledge memory.
  5. COMPLETION TRUTH     — verify_delivery(): "Mission Complete" means the artifact
                           EXISTS, not merely that execution finished.

Deterministic, dependency-free, model-free. Mirrors knowledge_frontier /
tool_intelligence (read-models, no shadow store).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_LEDGER_NAME = "_MISSION_LEDGER.json"   # owned by main._ledger_* — we only READ it
_TOK = re.compile(r"[a-zA-Z0-9_]+")

# Extensions the House treats as deliverable artifacts (spec-listed + common).
_ARTIFACT_EXTS = {".md", ".markdown", ".pdf", ".html", ".htm", ".json", ".csv", ".txt"}


# ── artifact typing ──────────────────────────────────────────────────────────
def classify(path: str) -> str:
    """Map a path to an artifact_type. Extension-canonical, with the semantic
    names the spec calls out (report / dashboard) when the filename hints them."""
    name = (path or "").lower()
    ext = Path(name).suffix
    if ext == ".pdf":
        return "pdf"
    if ext in (".html", ".htm"):
        return "dashboard" if "dashboard" in name else "html"
    if ext in (".md", ".markdown"):
        return "report" if "report" in name else "markdown"
    if ext == ".json":
        return "json"
    if ext == ".csv":
        return "csv"
    if ext == ".txt":
        return "txt"
    return (ext.lstrip(".") or "file")


def is_artifact_path(path: str) -> bool:
    return Path((path or "").lower()).suffix in _ARTIFACT_EXTS


# ── existence / record building (read-only, live disk probe) ─────────────────
def _resolve(path: str, workspace: Optional[str]) -> Optional[Path]:
    """Return the first on-disk Path for a (possibly relative) ledger entry."""
    if not path:
        return None
    p = Path(path)
    if p.exists():
        return p
    if workspace:
        wp = Path(workspace) / path
        if wp.exists():
            return wp
    return None


def artifact_exists(path: str, workspace: Optional[str] = None) -> bool:
    """CAPABILITY 2 — does the artifact still physically exist (non-empty)?"""
    rp = _resolve(path, workspace)
    try:
        return bool(rp) and rp.is_file() and rp.stat().st_size > 0
    except Exception:
        return False


def _record(mission_id: str, path: str, mission_ts: float,
            workspace: Optional[str]) -> Dict[str, Any]:
    rp = _resolve(path, workspace)
    exists = False
    size = 0
    created_at = float(mission_ts or 0.0)
    if rp:
        try:
            st = rp.stat()
            exists = rp.is_file() and st.st_size > 0
            size = st.st_size
            # prefer the file's own mtime as created_at when available
            if st.st_mtime:
                created_at = st.st_mtime
        except Exception:
            pass
    return {
        "mission_id": mission_id,
        "artifact_path": str(rp) if rp else path,
        "artifact_type": classify(path),
        "created_at": round(created_at, 3),
        "size": size,
        "exists": exists,
    }


# ── ledger access (READ-ONLY — never writes) ─────────────────────────────────
def _load_missions(workspace: Optional[str]) -> List[Dict[str, Any]]:
    if not workspace:
        return []
    try:
        p = Path(workspace) / _LEDGER_NAME
        if not p.exists():
            return []
        import json
        data = json.loads(p.read_text(encoding="utf-8")) or {}
        return list(data.get("missions") or [])
    except Exception:
        return []


# ── 1. ARTIFACT REGISTRY ──────────────────────────────────────────────────────
def registry(workspace: Optional[str], *, missions: Optional[List[Dict[str, Any]]] = None,
             existing_only: bool = False) -> List[Dict[str, Any]]:
    """Project every ledger file into an artifact record (newest mission first).
    `missions` may be supplied directly (tests); else read from the ledger."""
    rows = missions if missions is not None else _load_missions(workspace)
    out: List[Dict[str, Any]] = []
    seen = set()
    for m in reversed(rows or []):                       # newest mission first
        mid = str(m.get("id") or "")
        ts = m.get("ts") or 0.0
        for f in (m.get("files") or []):
            if not f or not is_artifact_path(str(f)):
                continue
            rec = _record(mid, str(f), ts, workspace)
            key = (rec["mission_id"], rec["artifact_path"])
            if key in seen:
                continue
            seen.add(key)
            if existing_only and not rec["exists"]:
                continue
            out.append(rec)
    # within the whole registry, sort by created_at desc (stable, newest first)
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return out


# ── 2. ARTIFACT DISCOVERY ─────────────────────────────────────────────────────
def recent_artifacts(workspace: Optional[str], limit: int = 10,
                     existing_only: bool = True,
                     missions: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    return registry(workspace, missions=missions, existing_only=existing_only)[:max(0, limit)]


def latest_artifact(workspace: Optional[str], existing_only: bool = True,
                    artifact_types: Optional[set] = None,
                    missions: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    for r in registry(workspace, missions=missions, existing_only=existing_only):
        if artifact_types and r["artifact_type"] not in artifact_types:
            continue
        return r
    return None


def mission_artifacts(mission_id: str, workspace: Optional[str],
                      missions: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    return [r for r in registry(workspace, missions=missions)
            if r["mission_id"] == str(mission_id)]


# ── 4. ARTIFACT PRIORITY ROUTING ──────────────────────────────────────────────
# Operator phrases that mean "I'm talking about something you already produced" —
# when any matches, the Artifact Registry is consulted BEFORE question/mission/
# knowledge memory.
_ARTIFACT_REFERENCE = re.compile(
    r"\b(previous|prior|earlier|last|recent(?:ly)?|latest|the)\s+"
    r"(report|dashboard|pdf|file|output|artifact|deliverable|document|work|task data|data|analysis|note)s?\b"
    r"|\bcontinue\b|\bresume\b|\bgenerated (report|pdf|dashboard|file|html|output)\b"
    r"|\brecent (work|task data|output|file)\b|\blast output\b|\bทำต่อ\b|\bอันเดิม\b|\bที่ค้างไว้\b",
    re.I)

# operator phrase → which artifact_types satisfy it
_TYPE_HINTS: List[tuple] = [
    ({"report"},      {"report", "markdown", "pdf"}),
    ({"pdf"},         {"pdf"}),
    ({"dashboard"},   {"dashboard", "html"}),
    ({"html"},        {"html", "dashboard"}),
    ({"csv", "spreadsheet"}, {"csv"}),
    ({"data", "json"},{"csv", "json"}),
    ({"note"},        {"markdown", "txt"}),
]


def references_artifact(text: str) -> bool:
    """CAPABILITY 4 — does the operator reference a prior output?"""
    return bool(_ARTIFACT_REFERENCE.search(text or ""))


def _type_filter(text: str) -> Optional[set]:
    t = (text or "").lower()
    types: set = set()
    for words, kinds in _TYPE_HINTS:
        if any(w in t for w in words):
            types |= kinds
    return types or None


def _tokens(s: str) -> set:
    return {w.lower() for w in _TOK.findall(s or "") if len(w) > 2}


# ── 3. RESUME INTELLIGENCE ────────────────────────────────────────────────────
def resolve_resume(text: str, workspace: Optional[str],
                   missions: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """For "continue previous report": find the matching artifact, verify it
    exists, return its path and a resume recommendation. Searches the REGISTRY —
    never the prompt/question. Returns None only when the House has produced
    no artifact at all matching the reference."""
    rows = missions if missions is not None else _load_missions(workspace)
    reg = registry(workspace, missions=rows)
    if not reg:
        return None
    type_filter = _type_filter(text)

    # rank candidates: type match first, then topical overlap with the mission
    # task, then recency. Prefer existing files but still surface a deleted one
    # (so the House can report it missing rather than silently recreate).
    task_by_mission = {str(m.get("id") or ""): str(m.get("task") or "") for m in (rows or [])}
    ttoks = _tokens(text)

    def score(r: Dict[str, Any]) -> tuple:
        type_ok = 1 if (not type_filter or r["artifact_type"] in type_filter) else 0
        mtoks = _tokens(task_by_mission.get(r["mission_id"], ""))
        overlap = len(ttoks & mtoks) / float(len(ttoks | mtoks) or 1)
        return (type_ok, 1 if r["exists"] else 0, round(overlap, 3), r["created_at"])

    ranked = sorted(reg, key=score, reverse=True)
    # if a type was requested, drop records that don't match it (unless none match)
    if type_filter:
        typed = [r for r in ranked if r["artifact_type"] in type_filter]
        ranked = typed or ranked
    best = ranked[0]
    exists = artifact_exists(best["artifact_path"], workspace)
    return {
        "artifact": best,
        "exists": exists,
        "recommend_resume": exists,
        "reason": ("artifact found on disk — open and extend it, do not recreate"
                   if exists else
                   "artifact was registered but is MISSING from disk — recreate or confirm with operator"),
    }


# ── 5. MISSION COMPLETION TRUTH ────────────────────────────────────────────────
def verify_delivery(files_touched: List[str], workspace: Optional[str] = None,
                    expected: bool = True) -> Dict[str, Any]:
    """CAPABILITY 5 — "Mission Complete" must mean the artifact EXISTS. Project
    this run's touched files into records and report whether a real artifact was
    delivered. When an artifact was expected but none exists, delivered=False so
    the caller can refuse to report success."""
    recs = []
    for f in (files_touched or []):
        if f and is_artifact_path(str(f)):
            recs.append(_record("", str(f), time.time(), workspace))
    existing = [r for r in recs if r["exists"]]
    return {
        "artifacts": recs,
        "existing": existing,
        "delivered": bool(existing) if expected else True,
        "expected": expected,
        "missing": [r["artifact_path"] for r in recs if not r["exists"]],
    }


# ── prompt rendering ──────────────────────────────────────────────────────────
def _render_resume(res: Optional[Dict[str, Any]]) -> str:
    """Render an ARTIFACT AWARENESS block from an ALREADY-RESOLVED resume result
    (the output of resolve_resume). Shared by render_brief and the intent path."""
    if not res or not res.get("artifact"):
        return ""
    a = res["artifact"]
    L = ["## ARTIFACT AWARENESS (resolve this from what you CREATED, not from the prompt):"]
    if res.get("exists"):
        L.append(f"  ▣ RESUME this artifact (mission {a.get('mission_id') or '—'}):")
        L.append(f"     path: {a.get('artifact_path')}")
        L.append(f"     type: {a.get('artifact_type')} · {a.get('size')} bytes")
        L.append("     → read_file / read_obsidian_note it FIRST, then extend it. "
                 "Do NOT search house_state.question. Do NOT start a new plan.")
    else:
        L.append(f"  ⚠ The referenced artifact is MISSING from disk: {a.get('artifact_path')}")
        L.append("     → it was created before but no longer exists; recreate it or "
                 "confirm with the operator before proceeding.")
    return "\n".join(L)


def render_brief(text: str, workspace: Optional[str],
                 missions: Optional[List[Dict[str, Any]]] = None) -> str:
    """The ARTIFACT AWARENESS prompt block, resolved directly from raw text.
    Kept for direct/standalone use; the run-time path uses the shared Intent
    Object via render_brief_from_intent()."""
    if not references_artifact(text):
        return ""
    return _render_resume(resolve_resume(text, workspace, missions=missions))


def render_brief_from_intent(intent: Dict[str, Any]) -> str:
    """OX-INTENT-1 consumer — render from the Intent Object's PRE-RESOLVED resume
    (intent['artifact'], produced once by interpret()). The Artifact Registry does
    not re-classify the raw text here; it consumes the single interpretation."""
    if not intent or not intent.get("requires_artifact"):
        return ""
    return _render_resume(intent.get("artifact"))
