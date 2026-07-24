"""
mission_identity.py — OX-H1 IDENTITY SEPARATION (stateless)
===========================================================
ARCHITECTURAL LAW (OX-H1): four concepts are permanently distinct and never
interchangeable —

  1. USER DIRECTIVE    what the operator actually requested.
  2. MISSION IDENTITY  the canonical title/objective written to state.
  3. EXECUTION CONTEXT WORKFLOW_CONTEXT / DONE_WHEN / KNOWN_GAPS / ROLLBACK.
  4. MODEL PROMPT      the full LLM briefing (system + context + directive).

Only MISSION IDENTITY may enter house_state.question, agent_runs.task, the
mission ledger, the house frame, or the timeline. EXECUTION CONTEXT and the
MODEL PROMPT may live only in runtime memory / prompt assembly / logs.

This module is the single chokepoint that extracts a clean MISSION IDENTITY
from whatever a caller passes — including a fully-assembled model prompt that
begins with a "WORKFLOW CONTEXT" block. Stateless, deterministic, no DB, no
model call. Used by BOTH the runtime write paths and the repair migration so
they agree byte-for-byte.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Optional

# Sigils that prove a string is an EXECUTION PROMPT, not a mission identity.
PROMPT_SIGILS = (
    "WORKFLOW CONTEXT",
    "YOU UNDERSTAND THE TASK",
    "### YOUR PLAN",
    "MID-EXECUTION CHECKPOINTS",
)

# Markers the executor uses to delimit the real operator request inside a prompt.
_REQUEST_MARKERS = ("USER REQUEST:", "USER DIRECTIVE:", "OPERATOR REQUEST:")

# The comprehension's restatement of the task — a clean objective. Used to
# recover identity from a prompt that was TRUNCATED before the USER REQUEST
# marker (old agent_runs.task rows were capped at 1000 chars).
_UNDERSTAND_MARKER = "YOU UNDERSTAND THE TASK AS:"
_UNDERSTAND_STOP = ("Core intent:", "Complexity:", "###", "Core Intent:")

# A horizontal rule / divider line (═, =, -, ─) — noise around the marker.
_BAR = re.compile(r"^[═=\-─_\s]+$")


def looks_like_prompt(text: Optional[str]) -> bool:
    """True when the text carries execution-prompt sigils (must not be identity)."""
    t = text or ""
    return any(s in t for s in PROMPT_SIGILS)


def _strip_leading_noise(lines):
    out, started = [], False
    for ln in lines:
        if not started and (not ln.strip() or _BAR.match(ln.strip())):
            continue
        started = True
        out.append(ln)
    return "\n".join(out).strip()


def extract_directive(task: Optional[str], directive: Optional[str] = "") -> str:
    """Return the clean USER DIRECTIVE from (task, directive).

    Priority:
      1. an explicit `directive` (the caller already knows the clean request),
      2. the tail after a USER REQUEST: marker inside an assembled prompt,
      3. the task itself when it is NOT a prompt,
      4. a best-effort recovery (last non-heading paragraph) when a prompt has
         no marker — never returns the WORKFLOW CONTEXT block.
    """
    if directive and directive.strip():
        return directive.strip()
    t = (task or "").strip()
    if not t:
        return ""
    # 2. explicit request marker (the executor's augmented_task format)
    for mk in _REQUEST_MARKERS:
        idx = t.rfind(mk)
        if idx >= 0:
            tail = _strip_leading_noise(t[idx + len(mk):].splitlines())
            if tail:
                return tail
    # 3. plain directive — not a prompt
    if not looks_like_prompt(t):
        return t
    # 4. prompt truncated before the request marker — recover the comprehension
    #    restatement ("YOU UNDERSTAND THE TASK AS:  <restated>").
    ui = t.find(_UNDERSTAND_MARKER)
    if ui >= 0:
        for ln in t[ui + len(_UNDERSTAND_MARKER):].splitlines():
            s = ln.strip()
            if not s:
                continue
            if any(s.startswith(stop) for stop in _UNDERSTAND_STOP):
                break
            return s
    # 5. last resort — the last meaningful, non-heading paragraph
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    for p in reversed(paras):
        head = p.lstrip()
        if head.startswith("#"):
            continue
        if any(s in p for s in PROMPT_SIGILS):
            continue
        return p
    return ""   # honest: could not recover a clean directive


def mission_title(identity: Optional[str], maxlen: int = 90) -> str:
    """A short canonical title from a clean identity (first meaningful line)."""
    s = (identity or "").strip()
    if not s:
        return ""
    for ln in s.splitlines():
        ln = ln.strip().lstrip("#").strip()
        if ln:
            return ln[:maxlen]
    return ""


def clean_identity(task: Optional[str], directive: Optional[str] = "") -> str:
    """The value safe to persist as MISSION IDENTITY. Falls back to a truncated
    raw task ONLY if extraction fails AND the task is not a prompt (never lets a
    WORKFLOW CONTEXT block through).

    OX-STABILITY-1 Phase 2: also rejects ERROR/DIAGNOSTIC text — an error message
    ("LLM reflection phase failed", a stack trace, …) must never become a mission
    identity. Returns '' so the caller does not open a garbage mission."""
    d = extract_directive(task, directive)
    if not d:
        t = (task or "").strip()
        d = "" if looks_like_prompt(t) else t
    if not d:
        return ""
    try:
        import runtime_integrity as _ri
        if _ri.is_error_text(d):
            return ""
    except Exception:
        pass
    return d
