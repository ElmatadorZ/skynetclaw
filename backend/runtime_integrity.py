"""
runtime_integrity.py — OX-STABILITY-1 RUNTIME INTEGRITY PROTOCOL (shared boundary)
==================================================================================
FIRST PRINCIPLE: a cognitive system cannot learn correctly from corrupted
operational history. Truthful state comes before self-improvement. This module is
the single chokepoint for two integrity guarantees that the rest of the House
imports:

  PHASE 2 — ERROR/IDENTITY BOUNDARY: error messages and diagnostic strings must
            NEVER become missions, objectives, capabilities, lessons or artifacts.
            is_error_text() / sanitize_identity() enforce the boundary.

  PHASE 4 — LEARNING INPUT INTEGRITY: only valid, concluded operational history
            may enter learning. Orphaned ('running') / reconciled ('interrupted')
            / cancelled runs and error-generated tasks are non-outcomes and must
            not contaminate Lesson Synthesis, Telemetry, Attribution, etc.
            valid_for_learning() / filter_valid_runs() enforce it.

Stateless, deterministic, dependency-free. Does NOT redesign any cognitive
system — it is a filter the cognitive systems apply at their inputs.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ── PHASE 2 — error / diagnostic sentinels (lowercased substring match) ──────
# A string containing any of these is DIAGNOSTIC, not an objective. Kept tight:
# real operator directives don't contain these phrases.
ERROR_SENTINELS = (
    "reflection phase failed",
    "no learnings extracted",
    "json parse failed", "failed to parse json", "json decode",
    "tool execution failed",
    "llm call failed", "llm reflection",
    "self-call failed",
    "traceback (most recent call",
    "phase failed", "phase_error", "workflow_error",
    "no learnings", "unhandled exception",
    "stack trace",
)
# strong structural markers of a stack trace / exception dump
_TRACE_RX = re.compile(r'File ".*", line \d+|Traceback \(most recent call|^\s*at [\w.$]+\(', re.M)


def is_error_text(text: Optional[str]) -> bool:
    """True when a string is an error/diagnostic message, not real content."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if any(s in t for s in ERROR_SENTINELS):
        return True
    if _TRACE_RX.search(text or ""):
        return True
    return False


def sanitize_identity(text: Optional[str]) -> str:
    """Return the text only if it is a legitimate objective; '' if it is error
    text. Used as the last guard before anything is persisted as a MISSION
    IDENTITY / objective."""
    return "" if is_error_text(text) else (text or "").strip()


# A title with no word characters at all (letters/digits in any script, incl.
# Thai) is punctuation-only — "...", ".....", "—", "···" — never a real mission.
_WORDCHAR_RX = re.compile(r"[^\W_]", re.UNICODE)


def is_punctuation_only(text: Optional[str]) -> bool:
    t = (text or "").strip()
    return bool(t) and not _WORDCHAR_RX.search(t)


def is_displayable_objective(text: Optional[str]) -> bool:
    """OX-HOUSE-GUARD-1: a string fit to surface as a House Mind objective —
    non-empty, not error/diagnostic text, not punctuation-only."""
    t = (text or "").strip()
    if not t:
        return False
    if is_error_text(t):
        return False
    if is_punctuation_only(t):
        return False
    return True


def valid_mission_row(question: Optional[str], confidence: Any, n_items: Any) -> bool:
    """READ-SIDE guard for an OPEN house_state row: surfaces only a high-quality
    mission. Rejects error-generated / punctuation-only / zero-information
    (confidence 0 AND no cognitive content) objectives — even if they remain in
    the DB for audit. Does not mutate anything."""
    if not is_displayable_objective(question):
        return False
    try:
        conf = float(confidence or 0.0)
    except Exception:
        conf = 0.0
    try:
        n = int(n_items or 0)
    except Exception:
        n = 0
    if conf == 0.0 and n == 0:        # zero-information mission
        return False
    return True


def clean_outputs(items: Optional[List[str]]) -> List[str]:
    """Drop error/diagnostic strings from a list destined for lessons /
    capabilities / artifacts (a failed phase contributes NOTHING, not a fake
    'lesson')."""
    return [x for x in (items or []) if isinstance(x, str) and x.strip()
            and not is_error_text(x)]


# ── PHASE 4 — learning input integrity ───────────────────────────────────────
# Non-outcomes: the run did not actually conclude with a real mission result, so
# it is not evidence of anything. (A genuine 'failed'/'limit'/'stuck' IS a real
# outcome and stays — failure is valid learning; absence of conclusion is not.)
NON_OUTCOME_STATUSES = ("running", "interrupted", "cancelled")


def valid_for_learning(row: Dict[str, Any]) -> bool:
    """True when an agent_runs row is valid history for learning systems:
    a concluded (non-orphan) run whose task is not an error-generated mission."""
    if not isinstance(row, dict):
        return False
    status = str(row.get("status") or "").strip().lower()
    if status in NON_OUTCOME_STATUSES or status == "":
        return False
    if is_error_text(row.get("task")):
        return False
    return True


def filter_valid_runs(rows: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Keep only rows that are valid operational history for learning."""
    return [r for r in (rows or []) if valid_for_learning(r)]


def filter_valid_missions(missions: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Ledger missions whose task/objective is an error string are error-generated
    and must not feed learning."""
    return [m for m in (missions or []) if not is_error_text(str(m.get("task") or ""))]
