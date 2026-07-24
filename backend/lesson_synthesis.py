"""
lesson_synthesis.py — OX-LEARNING-1 LESSON SYNTHESIS ENGINE (read-side)
=======================================================================
FIRST PRINCIPLE: experience is not learning. A log is not a lesson. The House
already RECORDS experience (mission ledger, tool memory, artifact registry,
agent_runs) but has never CONVERTED it into reusable conclusions. Learning
occurs only when REPEATED evidence in a SIMILAR context produces a CONSISTENT
outcome.

This engine reads the EXISTING operational histories (read-only, no redesign of
any system) and synthesizes lessons into a SEPARATE Lesson Registry — synthesized
knowledge, not execution logs. It is distinct from learning_engine.py (which
derives lessons from outcome-caused BELIEF revisions); this one derives lessons
from operational OUTCOMES (tool success rates, artifact delivery, mission
completion, dead-ends).

A lesson requires (the learning model):
  1. multiple observations   (evidence_count >= min_obs)
  2. similar context         (grouped by tool / task-type / artifact-type)
  3. consistent outcome      (success_rate >= success_thresh, or <= failure_thresh)
  4. supporting evidence      (the counts + the source histories)

Capabilities:
  - synthesize()  — convert histories → lessons (success/failure/recovery/tool/
                    knowledge patterns)
  - refresh()     — synthesize + persist the Lesson Registry (lessons.json)
  - recall()      — before planning, surface relevant lessons / similar
                    successes / similar failures for a task
  - render_brief()— the LESSON RECALL prompt block

Read-only inputs (existing systems): tool_intelligence.load_memory(),
artifact_registry (mission ledger + artifact records), agent_runs.recent().
Owns ONLY lessons.json (the synthesized registry).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_STORE = Path(__file__).parent / "lessons.json"
_TOK = re.compile(r"[a-zA-Z0-9_]+")

# learning-model thresholds (a lesson must clear these)
MIN_OBS = 3            # multiple observations
SUCCESS_THRESH = 0.70  # consistent success
FAILURE_THRESH = 0.40  # consistent failure (success_rate at or below this)


def _tokens(s: str) -> set:
    return {w.lower() for w in _TOK.findall(s or "") if len(w) > 2}


def _classify(task: str) -> str:
    try:
        import tool_intelligence as _ti
        return _ti.classify_task(task or "")
    except Exception:
        return "general"


def _lid(category: str, text: str) -> str:
    return hashlib.sha1(f"{category}:{text}".encode("utf-8")).hexdigest()[:12]


def _lesson(text: str, polarity: str, rate: float, n: int, source: List[str],
            category: str, context: Dict[str, Any]) -> Dict[str, Any]:
    conf = rate if polarity == "success" else (1.0 - rate)
    return {
        "id": _lid(category, text),
        "lesson": text,
        "confidence": round(conf, 2),
        "evidence_count": int(n),
        "source": sorted(set(source)),
        "category": category,
        "polarity": polarity,          # success | failure
        "context": context,            # for recall matching
    }


# ── pattern extractors (each: history → lessons) ─────────────────────────────
def _tool_patterns(tool_mem: Dict[str, Any], min_obs: int) -> List[Dict[str, Any]]:
    """TOOL + KNOWLEDGE-acquisition patterns from tool memory."""
    out: List[Dict[str, Any]] = []
    _SEARCH = {"web_search", "http_request", "get_news", "download_file"}
    for tool, st in (tool_mem.get("tools") or {}).items():
        tts = st.get("task_types") or {}
        # prefer task-type-scoped evidence; fall back to the tool's overall record
        scopes = [(tt, d) for tt, d in tts.items() if (d.get("uses") or 0) >= min_obs]
        if not scopes and (st.get("uses") or 0) >= min_obs:
            scopes = [(None, {"uses": st["uses"], "successes": st.get("successes", 0)})]
        for tt, d in scopes:
            n = int(d.get("uses") or 0)
            s = int(d.get("successes") or 0)
            if n < min_obs:
                continue
            rate = s / float(n)
            ctx = {"tool": tool, "task_type": tt}
            where = f" for {tt} tasks" if tt else ""
            knowledge = tool in _SEARCH and (tt in (None, "research"))
            cat = "knowledge" if knowledge else "tool"
            if rate >= SUCCESS_THRESH:
                txt = (f'"{tool}" is reliable{where} ({s}/{n} succeeded)'
                       + (" — use it to acquire knowledge." if knowledge else "."))
                out.append(_lesson(txt, "success", rate, n, ["tool_history"], cat, ctx))
            elif rate <= FAILURE_THRESH:
                txt = f'"{tool}" repeatedly fails{where} ({n-s}/{n} failed) — prefer an alternative.'
                out.append(_lesson(txt, "failure", rate, n, ["tool_history"], cat, ctx))
    return out


def _artifact_patterns(artifacts: List[Dict[str, Any]], min_obs: int) -> List[Dict[str, Any]]:
    """ARTIFACT delivery reliability per type (the PDF-export / HTML examples)."""
    out: List[Dict[str, Any]] = []
    groups: Dict[str, List[bool]] = {}
    for a in artifacts or []:
        groups.setdefault(a.get("artifact_type") or "file", []).append(bool(a.get("exists")))
    for atype, exists in groups.items():
        n = len(exists)
        if n < min_obs:
            continue
        ex = sum(1 for e in exists if e)
        rate = ex / float(n)
        ctx = {"artifact_type": atype}
        if rate >= SUCCESS_THRESH:
            out.append(_lesson(
                f"{atype.upper()} artifacts are reliably delivered ({ex}/{n} exist on disk).",
                "success", rate, n, ["artifact_history"], "artifact", ctx))
        elif rate <= FAILURE_THRESH:
            out.append(_lesson(
                f"{atype.upper()} export is unstable — {n-ex}/{n} produced no artifact on disk.",
                "failure", rate, n, ["artifact_history"], "artifact", ctx))
    return out


def _mission_patterns(missions: List[Dict[str, Any]], min_obs: int) -> List[Dict[str, Any]]:
    """EXECUTION patterns: task-type completion reliability from the ledger."""
    out: List[Dict[str, Any]] = []
    groups: Dict[str, List[bool]] = {}
    for m in missions or []:
        tt = _classify(str(m.get("task") or ""))
        groups.setdefault(tt, []).append(str(m.get("status") or "").upper() == "COMPLETE")
    for tt, oks in groups.items():
        n = len(oks)
        if n < min_obs:
            continue
        c = sum(1 for o in oks if o)
        rate = c / float(n)
        ctx = {"task_type": tt}
        if rate >= SUCCESS_THRESH:
            out.append(_lesson(f"{tt} missions usually complete ({c}/{n}).",
                               "success", rate, n, ["mission_history"], "execution", ctx))
        elif rate <= FAILURE_THRESH:
            out.append(_lesson(
                f"{tt} missions frequently fail to complete ({n-c}/{n}) — scope tighter or verify earlier.",
                "failure", rate, n, ["mission_history"], "execution", ctx))
    return out


def _recovery_patterns(runs: List[Dict[str, Any]], min_obs: int) -> List[Dict[str, Any]]:
    """RECOVERY patterns: repeated dead-ends / blocked exits on similar tasks."""
    out: List[Dict[str, Any]] = []
    try:
        import execution_recall as _er
    except Exception:
        _er = None
    groups: Dict[str, List[bool]] = {}
    for r in runs or []:
        tt = _classify(str(r.get("task") or ""))
        dead = str(r.get("status") or "").upper() in ("PROBLEM", "BLOCKED")
        if not dead and _er is not None:
            try:
                dead = bool(_er.parse_footer(str(r.get("summary") or "")).get("b"))
            except Exception:
                pass
        groups.setdefault(tt, []).append(dead)
    for tt, deads in groups.items():
        n = len(deads)
        if n < min_obs:
            continue
        k = sum(1 for d in deads if d)
        rate = k / float(n)               # dead-end rate
        if rate >= SUCCESS_THRESH:        # consistently dead-ending
            out.append(_lesson(
                f"{tt} tasks repeatedly dead-end ({k}/{n}) — recover earlier or change strategy.",
                "failure", 1.0 - rate, n, ["execution_recall"], "recovery", {"task_type": tt}))
    return out


# ── synthesis ─────────────────────────────────────────────────────────────────
def synthesize(*, tool_mem: Optional[Dict[str, Any]] = None,
               missions: Optional[List[Dict[str, Any]]] = None,
               artifacts: Optional[List[Dict[str, Any]]] = None,
               runs: Optional[List[Dict[str, Any]]] = None,
               workspace: Optional[str] = None,
               min_obs: int = MIN_OBS) -> List[Dict[str, Any]]:
    """Convert operational history into lessons. Any source left None is loaded
    from the existing system (read-only). Deterministic, model-free."""
    # load missing sources from existing systems (read-only)
    if tool_mem is None:
        try:
            import tool_intelligence as _ti
            tool_mem = _ti.load_memory()
        except Exception:
            tool_mem = {"tools": {}}
    if missions is None and workspace:
        try:
            import artifact_registry as _ar
            missions = _ar._load_missions(workspace)
        except Exception:
            missions = []
    if artifacts is None:
        try:
            import artifact_registry as _ar
            artifacts = _ar.registry(workspace, missions=missions)
        except Exception:
            artifacts = []

    # OX-STABILITY-1 Phase 4: corrupted history must not contaminate learning —
    # drop error-generated missions and non-outcome (orphaned/interrupted) runs.
    try:
        import runtime_integrity as _ri
        missions = _ri.filter_valid_missions(missions or [])
        runs = _ri.filter_valid_runs(runs or [])
    except Exception:
        pass

    lessons: List[Dict[str, Any]] = []
    lessons += _tool_patterns(tool_mem or {}, min_obs)
    lessons += _artifact_patterns(artifacts or [], min_obs)
    lessons += _mission_patterns(missions or [], min_obs)
    lessons += _recovery_patterns(runs or [], min_obs)

    # dedupe by id; keep the higher-evidence instance
    by_id: Dict[str, Dict[str, Any]] = {}
    for ln in lessons:
        cur = by_id.get(ln["id"])
        if not cur or ln["evidence_count"] > cur["evidence_count"]:
            by_id[ln["id"]] = ln
    out = list(by_id.values())
    out.sort(key=lambda l: (l["confidence"], l["evidence_count"]), reverse=True)
    return out


# ── Lesson Registry (separate from raw events) ───────────────────────────────
def load(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or _STORE
    try:
        if p.exists():
            return (json.loads(p.read_text(encoding="utf-8")) or {}).get("lessons", [])
    except Exception:
        pass
    return []


def refresh(workspace: Optional[str] = None, runs: Optional[List[Dict[str, Any]]] = None,
            path: Optional[Path] = None, **kw) -> List[Dict[str, Any]]:
    """Synthesize and PERSIST the Lesson Registry. Returns the lessons."""
    lessons = synthesize(workspace=workspace, runs=runs, **kw)
    p = path or _STORE
    try:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "generated_at": time.time(),
                                   "lessons": lessons}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[LessonSynthesis] persist failed: {e}")
    return lessons


# ── LESSON RECALL (before planning) ──────────────────────────────────────────
def recall(task: str, lessons: Optional[List[Dict[str, Any]]] = None,
           limit: int = 6, path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Surface the lessons most relevant to a task: matching task-type, then
    token overlap, weighted by confidence × evidence. Returns top `limit`."""
    lessons = lessons if lessons is not None else load(path)
    if not lessons:
        return []
    tt = _classify(task)
    ttoks = _tokens(task)

    def score(ln: Dict[str, Any]) -> float:
        ctx = ln.get("context") or {}
        s = ln.get("confidence", 0.0) * min(1.0, 0.4 + ln.get("evidence_count", 0) / 20.0)
        if ctx.get("task_type") and ctx["task_type"] == tt:
            s += 0.5
        overlap = ttoks & _tokens(ln.get("lesson", ""))
        s += 0.1 * len(overlap)
        return s

    ranked = sorted(lessons, key=score, reverse=True)
    # keep only lessons with some relevance signal OR globally strong (conf≥.8)
    out = [ln for ln in ranked
           if score(ln) >= 0.45 or ln.get("confidence", 0) >= 0.8]
    return out[:max(0, limit)]


def render_brief(lessons: List[Dict[str, Any]]) -> str:
    """The LESSON RECALL prompt block — what repeatedly works / fails for this
    kind of task. Empty when nothing relevant has been learned yet."""
    if not lessons:
        return ""
    wins = [l for l in lessons if l.get("polarity") == "success"]
    fails = [l for l in lessons if l.get("polarity") == "failure"]
    L = ["## LESSONS (synthesized from prior runs — apply BEFORE planning):"]
    for l in wins[:4]:
        L.append(f"  ✓ {l['lesson']}  (conf {l['confidence']}, n={l['evidence_count']})")
    for l in fails[:4]:
        L.append(f"  ✗ {l['lesson']}  (conf {l['confidence']}, n={l['evidence_count']})")
    L.append("  → Lean on what repeatedly works; avoid what repeatedly fails.")
    return "\n".join(L)


def diff_and_emit(publish: Callable[..., Any], workspace: Optional[str] = None,
                  runs: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Refresh the registry and emit a compact `lessons_synthesized` summary."""
    lessons = refresh(workspace=workspace, runs=runs)
    try:
        publish("lessons_synthesized",
                {"count": len(lessons),
                 "wins": sum(1 for l in lessons if l["polarity"] == "success"),
                 "fails": sum(1 for l in lessons if l["polarity"] == "failure")},
                source="learning")
    except Exception:
        pass
    return lessons
