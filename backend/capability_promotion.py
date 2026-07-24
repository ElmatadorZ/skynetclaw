"""
capability_promotion.py — OX-CAPABILITY-1 CAPABILITY PROMOTION ENGINE (read-side)
=================================================================================
FIRST PRINCIPLE: a lesson is knowledge; a capability is reusable behavior.
Repeated SUCCESS should become a capability; repeated FAILURE should become a
WARNING capability. OX-LEARNING-1 synthesized lessons — this engine PROMOTES the
validated, stable ones into capabilities the House can recall and prefer.

Read-only over the Lesson Registry (lesson_synthesis) + the histories the lessons
already encode (Tool Intelligence, Artifact Registry, Mission/Knowledge/Intent).
No redesign of runtime, governance or learning. Owns only capabilities.json.

PROMOTION RULES — a lesson may become a capability only if:
  • confidence       >= CONF_THRESH
  • evidence_count   >= EVIDENCE_THRESH      (observed repeatedly)
  • stable over time  (evidence >= STABLE_EVIDENCE on first sight, OR the
                       capability was already promoted in a prior snapshot)

CAPABILITY SCHEMA:
  {
    "name": "HTML Report Builder",
    "type": "reporting",
    "polarity": "capability" | "warning",
    "confidence": 0.93,
    "evidence_count": 14,
    "derived_from": ["lesson_001", "lesson_008"],
    "recommended_tools": ["read_file", "write_file"],
    "match": ["report", "html"],          # for recall
    "summary": "..."
  }

Capability types: execution, research, reporting, artifact, recovery,
knowledge_acquisition (+ a `warning` polarity on any of them).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_STORE = Path(__file__).parent / "capabilities.json"
_TOK = re.compile(r"[a-zA-Z0-9_]+")

CONF_THRESH = 0.80
EVIDENCE_THRESH = 5         # observed repeatedly
STABLE_EVIDENCE = 10        # first-sight stability bar (else must persist across snapshots)

# artifact types that are documents/reports vs. raw data artifacts
_REPORT_ARTIFACTS = {"report", "markdown", "pdf", "html", "dashboard", "txt"}
# default tool chains per capability type (used when no tool-lesson contributes)
_DEFAULT_TOOLS = {
    "reporting": ["read_file", "write_file"],
    "research": ["web_search", "http_request"],
    "knowledge_acquisition": ["web_search", "http_request"],
    "execution": ["read_file", "write_file"],
    "artifact": ["write_file"],
    "recovery": [],
}


def _tokens(s: str) -> set:
    return {w.lower() for w in _TOK.findall(s or "") if len(w) > 2}


def _tool_captype(task_type: Optional[str]) -> str:
    return {"report": "reporting", "research": "research", "code": "execution",
            "obsidian": "knowledge_acquisition"}.get(task_type or "", "execution")


# ── routing: a promotable lesson → which capability bucket it belongs to ─────
def _route(lesson: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
    """Return (cap_type, name, polarity) for a lesson, or None if it only
    contributes recommended tools (success tool-lessons)."""
    cat = lesson.get("category")
    pol = lesson.get("polarity")
    ctx = lesson.get("context") or {}
    atype = ctx.get("artifact_type")
    tt = ctx.get("task_type")
    tool = ctx.get("tool")

    if cat == "artifact":
        is_report = (atype or "") in _REPORT_ARTIFACTS
        cap_type = "reporting" if is_report else "artifact"
        base = "Report Builder" if is_report else "Artifact Builder"
        name = f"{(atype or 'file').upper()} {base}"
        if pol == "failure":
            return cap_type, name + " (UNSTABLE)", "warning"
        return cap_type, name, "capability"

    if cat == "knowledge":
        if pol == "failure":
            return "knowledge_acquisition", "Knowledge Acquisition (DEGRADED)", "warning"
        return "knowledge_acquisition", "Knowledge Acquisition", "capability"

    if cat == "execution":
        name = f"{(tt or 'General').title()} Execution"
        if pol == "failure":
            return "execution", name + " (UNRELIABLE)", "warning"
        return "execution", name, "capability"

    if cat == "recovery":
        return "recovery", f"{(tt or 'General').title()} Recovery Risk", "warning"

    if cat == "tool":
        if pol == "failure" and tool:
            return "warning", f'"{tool}" (AVOID)', "warning"
        return None      # success tool-lessons only feed recommended_tools

    return None


# ── promotion ─────────────────────────────────────────────────────────────────
def promote(lessons: List[Dict[str, Any]], *, prior_names: Optional[Set[str]] = None,
            conf_thresh: float = CONF_THRESH, evidence_thresh: int = EVIDENCE_THRESH,
            stable_evidence: int = STABLE_EVIDENCE) -> List[Dict[str, Any]]:
    """Promote validated, stable lessons into capabilities. Deterministic."""
    prior_names = prior_names or set()
    # only lessons that clear confidence + evidence may contribute
    promotable = [l for l in (lessons or [])
                  if l.get("confidence", 0) >= conf_thresh
                  and l.get("evidence_count", 0) >= evidence_thresh]

    # pass 1 — collect recommended tools per cap_type from SUCCESS tool-lessons
    tools_by_type: Dict[str, Set[str]] = {}
    for l in promotable:
        if l.get("category") in ("tool", "knowledge") and l.get("polarity") == "success":
            ctx = l.get("context") or {}
            tool = ctx.get("tool")
            if not tool:
                continue
            ct = ("knowledge_acquisition" if l["category"] == "knowledge"
                  else _tool_captype(ctx.get("task_type")))
            tools_by_type.setdefault(ct, set()).add(tool)

    # pass 2 — build capability buckets
    buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for l in promotable:
        routed = _route(l)
        if not routed:
            continue
        cap_type, name, polarity = routed
        key = (cap_type, name)
        b = buckets.setdefault(key, {
            "name": name, "type": cap_type, "polarity": polarity,
            "confidence": 0.0, "evidence_count": 0, "derived_from": [],
            "match": set(),
        })
        b["confidence"] = max(b["confidence"], float(l.get("confidence", 0)))
        b["evidence_count"] = max(b["evidence_count"], int(l.get("evidence_count", 0)))
        if l.get("id"):
            b["derived_from"].append(l["id"])
        ctx = l.get("context") or {}
        for v in (ctx.get("task_type"), ctx.get("artifact_type")):
            if v:
                b["match"].add(v)

    # finalize + apply the stability gate
    caps: List[Dict[str, Any]] = []
    for (cap_type, name), b in buckets.items():
        evid = b["evidence_count"]
        stable = (evid >= stable_evidence) or (name in prior_names)
        if not stable:
            continue                       # repeated but not yet stable → hold
        rec_tools = sorted(set(tools_by_type.get(cap_type, set()))
                           | set(_DEFAULT_TOOLS.get(cap_type, [])))
        caps.append({
            "name": name,
            "type": cap_type,
            "polarity": b["polarity"],
            "confidence": round(b["confidence"], 2),
            "evidence_count": evid,
            "derived_from": sorted(set(b["derived_from"])),
            "recommended_tools": rec_tools,
            "match": sorted(b["match"]),
            "summary": _summary(name, b["polarity"], cap_type, evid),
        })
    caps.sort(key=lambda c: (c["polarity"] == "capability", c["confidence"], c["evidence_count"]),
              reverse=True)
    return caps


def _summary(name: str, polarity: str, cap_type: str, evid: int) -> str:
    if polarity == "warning":
        return f"Repeated failure ({evid} obs) — treat '{name}' as a known risk; prefer an alternative."
    return f"Emerged from {evid} repeated successes — a reusable {cap_type} capability."


# ── Capability Registry (separate persisted store) ───────────────────────────
def load(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or _STORE
    try:
        if p.exists():
            return (json.loads(p.read_text(encoding="utf-8")) or {}).get("capabilities", [])
    except Exception:
        pass
    return []


def refresh(workspace: Optional[str] = None, lessons: Optional[List[Dict[str, Any]]] = None,
            path: Optional[Path] = None, **kw) -> List[Dict[str, Any]]:
    """Promote from the current lessons and PERSIST the Capability Registry.
    Stability uses the PRIOR registry: a capability seen before stays promoted."""
    if lessons is None:
        try:
            import lesson_synthesis as _ls
            lessons = _ls.load()
        except Exception:
            lessons = []
    p = path or _STORE
    prior = {c.get("name") for c in load(p)}
    caps = promote(lessons, prior_names=prior, **kw)
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "generated_at": time.time(),
                                   "capabilities": caps}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[CapabilityPromotion] persist failed: {e}")
    return caps


# ── CAPABILITY RECALL (before planning — preferred over raw lessons) ─────────
def _classify(task: str) -> str:
    try:
        import tool_intelligence as _ti
        return _ti.classify_task(task or "")
    except Exception:
        return "general"


def recall(task: str, capabilities: Optional[List[Dict[str, Any]]] = None,
           limit: int = 5, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Surface the capabilities most relevant to a task (matching type/keywords,
    weighted by confidence × evidence). Returns top `limit`."""
    capabilities = capabilities if capabilities is not None else load(path)
    if not capabilities:
        return []
    tt = _classify(task)
    ttoks = _tokens(task)

    def score(c: Dict[str, Any]) -> float:
        s = c.get("confidence", 0.0) * min(1.0, 0.4 + c.get("evidence_count", 0) / 20.0)
        if tt in (c.get("match") or []):
            s += 0.6
        overlap = ttoks & _tokens(c.get("name", ""))
        s += 0.1 * len(overlap)
        return s

    ranked = sorted(capabilities, key=score, reverse=True)
    out = [c for c in ranked if score(c) >= 0.45 or c.get("confidence", 0) >= 0.85]
    return out[:max(0, limit)]


def render_brief(capabilities: List[Dict[str, Any]]) -> str:
    """The CAPABILITY RECALL prompt block — emerged behaviors the House is good
    at, PREFERRED over raw lessons. Empty when none are relevant."""
    if not capabilities:
        return ""
    caps = [c for c in capabilities if c.get("polarity") == "capability"]
    warns = [c for c in capabilities if c.get("polarity") == "warning"]
    L = ["## CAPABILITIES (emerged from repeated success — PREFER these over raw lessons):"]
    for c in caps[:4]:
        L.append(f"  ★ {c['name']} (conf {c['confidence']}, n={c['evidence_count']}) "
                 f"— tools: {', '.join(c.get('recommended_tools', []) or ['—'])}")
    for c in warns[:4]:
        L.append(f"  ⚠ {c['name']} (conf {c['confidence']}, n={c['evidence_count']}) — known risk; avoid or mitigate.")
    L.append("  → Reach for an emerged capability before improvising; heed the warnings.")
    return "\n".join(L)


def diff_and_emit(publish, workspace: Optional[str] = None,
                  lessons: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    caps = refresh(workspace=workspace, lessons=lessons)
    try:
        publish("capabilities_promoted",
                {"count": len(caps),
                 "capabilities": sum(1 for c in caps if c["polarity"] == "capability"),
                 "warnings": sum(1 for c in caps if c["polarity"] == "warning")},
                source="learning")
    except Exception:
        pass
    return caps
