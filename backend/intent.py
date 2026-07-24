"""
intent.py — OX-INTENT-1 UNIFIED INTENT PROTOCOL (shared interpretation layer)
=============================================================================
FIRST PRINCIPLE: the operator issued ONE request, so the system should interpret
it ONCE. Before this layer, Artifact Registry, Tool Intelligence and Knowledge
Seeking each re-read the raw text independently → intent drift, duplicate
classification, duplicate resume detection, divergent knowledge routing
(see OX-INTEGRATION-AUDIT: DUP-1, DUP-2, M-1, M-2).

This is NOT a new cognitive capability and adds NO learning. It is a thin
interpretation layer that runs the EXISTING detectors exactly once and freezes
the result into a single Intent Object that every consumer reads:

    interpret(task, …) → Intent Object        # the one interpretation
    enrich(intent, recall)                     # Execution Recall may enrich, not redefine

Single source of truth for artifact-resume = Artifact Registry. Tool Intelligence
no longer detects resume; it consumes the Intent Object. Knowledge Seeking no
longer decides "artifact vs knowledge"; it consumes the Intent Object (and the
artifact-source overlap is suppressed when the Registry already resolved one).

Intent schema:
    {
      "intent": "resume_artifact" | "use_recent_artifact" | "acquire_knowledge"
                 | "create_artifact" | "execute",
      "target": "<artifact stem | topic | task slug>",
      "confidence": 0.0-1.0,
      "requires_artifact": bool,            # request hinges on an EXISTING artifact
      "requires_knowledge_search": bool,    # a gap must be discovered before acting
      "requires_clarification": bool,       # operator input needed (last resort)
      # carried sub-results so consumers never recompute:
      "task_type": "<tool_intelligence task-type>",
      "artifact": {resolve_resume result} | None,   # owned by Artifact Registry
      "knowledge_plan": {knowledge_seeking plan} | None,
      "recall": {execution-recall enrichment} | None,
      "raw": "<original task>",
    }

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_CREATE_VERB = re.compile(
    r"\b(generate|create|build|make|write|produce|draft|export|render|compose|design)\b", re.I)
_OUTPUT_NOUN = re.compile(
    r"\b(report|dashboard|pdf|html|file|document|note|chart|graph|csv|json|spreadsheet|deck|page|artifact)s?\b", re.I)
_TOK = re.compile(r"[a-zA-Z0-9_]+")


def _slug(s: str, n: int = 48) -> str:
    s = re.sub(r"[^\w\- ]+", "", (s or "")).strip().lower().replace(" ", "_")
    return s[:n] or "task"


def interpret(task: str, *, available_tools: Optional[List[str]] = None,
              workspace: Optional[str] = None, vault: Optional[str] = None,
              known_facts: Optional[List[str]] = None) -> Dict[str, Any]:
    """Interpret the operator request ONCE. Runs each existing detector a single
    time and returns the canonical Intent Object. Best-effort: any detector
    failure degrades to a safe default — never raises."""
    t = (task or "").strip()
    intent: Dict[str, Any] = {
        "intent": "execute", "target": _slug(t), "confidence": 0.6,
        "requires_artifact": False, "requires_knowledge_search": False,
        "requires_clarification": False, "task_type": "general",
        "artifact": None, "knowledge_plan": None, "recall": None, "raw": t,
    }

    # ── task-type (Tool Intelligence owns the taxonomy) — computed ONCE ──
    try:
        import tool_intelligence as _ti
        intent["task_type"] = _ti.classify_task(t)
    except Exception:
        pass

    # ── 1. ARTIFACT RESUME — Artifact Registry is the SINGLE SOURCE OF TRUTH ──
    artifact_res = None
    try:
        import artifact_registry as _ar
        if t and workspace and _ar.references_artifact(t):
            artifact_res = _ar.resolve_resume(t, workspace)
    except Exception:
        artifact_res = None

    if artifact_res and artifact_res.get("artifact"):
        a = artifact_res["artifact"]
        exists = bool(artifact_res.get("exists"))
        # "recent/latest data" phrasing → use_recent; otherwise a continuation
        is_recent = bool(re.search(r"\b(recent|latest|last)\b", t, re.I)) and \
            not re.search(r"\b(continue|resume|previous|prior)\b", t, re.I)
        explicit = bool(re.search(r"\b(continue|resume|previous|prior|the)\b", t, re.I))
        intent["intent"] = "use_recent_artifact" if is_recent else "resume_artifact"
        intent["target"] = Path(str(a.get("artifact_path") or "")).stem or _slug(t)
        intent["requires_artifact"] = True
        intent["requires_knowledge_search"] = False
        intent["artifact"] = artifact_res
        if exists:
            intent["confidence"] = 0.94 if explicit else 0.85
            intent["requires_clarification"] = False
        else:
            # registered but missing from disk → confirm/recreate (last resort)
            intent["confidence"] = 0.6
            intent["requires_clarification"] = True

    # ── 2. KNOWLEDGE SEEKING — consumes the artifact decision (no overlap) ──
    # Suppress the artifacts source when the Registry already owns the resume,
    # so Knowledge Seeking stops re-routing the same reference (DUP-2).
    try:
        import knowledge_seeking as _ks
        plan = _ks.plan(t, available_tools=available_tools, workspace=workspace,
                        vault=vault, known_facts=known_facts,
                        suppress_artifact_source=intent["requires_artifact"])
        intent["knowledge_plan"] = plan
        if not intent["requires_artifact"]:
            has_gap = bool(plan.get("knowable") or plan.get("unknown"))
            if has_gap:
                intent["intent"] = "acquire_knowledge"
                intent["requires_knowledge_search"] = bool(plan.get("needs_search"))
                intent["requires_clarification"] = _ks.should_clarify(plan, discovered=None)
                intent["confidence"] = 0.8 if plan.get("needs_search") else 0.65
                # topic target = first gap's matched fragment
                gaps = (plan.get("knowable") or []) + (plan.get("unknown") or [])
                if gaps:
                    intent["target"] = (gaps[0].get("match") or gaps[0].get("need") or intent["target"])[:60]
    except Exception:
        pass

    # ── 3. fallthrough: no artifact, no gap → create vs execute ──
    if intent["intent"] == "execute" and not intent["requires_artifact"] \
            and not intent["requires_knowledge_search"]:
        if _CREATE_VERB.search(t) and _OUTPUT_NOUN.search(t):
            intent["intent"] = "create_artifact"
            intent["confidence"] = 0.75
    return intent


def enrich(intent: Dict[str, Any], recall: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Execution Recall MAY enrich the intent (prior unknown tools / dead-ends /
    similar-run count) but MUST NOT redefine it. Mutates and returns intent."""
    if not intent or not recall:
        return intent
    try:
        intent["recall"] = {
            "unknown_tools": list(recall.get("unknown_tools") or [])[:12],
            "prior_dead_ends": len(recall.get("prior_dead_ends") or []),
            "similar_count": int(recall.get("similar_count") or 0),
        }
    except Exception:
        pass
    return intent


def render_brief(intent: Dict[str, Any]) -> str:
    """A compact one-line statement of the single interpretation, injected first
    so every consumer (and the model) shares the same reading of the request."""
    if not intent:
        return ""
    flags = []
    if intent.get("requires_artifact"):
        flags.append("artifact")
    if intent.get("requires_knowledge_search"):
        flags.append("knowledge-search")
    if intent.get("requires_clarification"):
        flags.append("clarify")
    return ("## INTENT (interpreted once — all modules consume this, none re-interpret):\n"
            f"  intent={intent.get('intent')} · target={intent.get('target')} · "
            f"confidence={intent.get('confidence')}"
            + (f" · requires: {', '.join(flags)}" if flags else " · requires: none"))
