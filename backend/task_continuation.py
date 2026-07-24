"""
task_continuation.py — ephemeral working memory for multi-round tasks
=====================================================================
When a task needs more processing than the model window holds (e.g. ~60k tokens
of work vs a ~15k context), one agent run cannot finish it: the loop compresses
in-place (mission_snapshot) and then stops at MAX_STEPS with an INCOMPLETE
ledger. There is no automatic hand-off to a fresh round.

This module provides the hand-off: a compact, ephemeral **TaskMemory** that lives
ONLY for the duration of one big-task orchestration (never persisted), carrying
the objective + accumulated findings forward so each new round continues instead
of restarting. The heavy state that CAN be durable already is — files persist in
the workspace, and _MISSION_LEDGER records completed steps — so TaskMemory only
carries the *reasoning residue* needed to continue, kept small enough to always
fit the next round's window (that is the whole point).

Pure + deterministic; the orchestrator (main.py /api/agent/run_big) drives it.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import List, Optional


# Terminal statuses emitted by /api/agent/run's `done` event.
_SUCCESS = "SUCCESS"   # TASK_COMPLETE reached — the whole objective is done
_LIMIT   = "LIMIT"     # ran out of steps without finishing — MORE to do
_FAILED  = "FAILED"    # halted (stuck / stream error) — a fresh round MAY recover
_BLOCKED = "BLOCKED"   # dead-end detected — a fresh round is unlikely to help


def should_continue(final_status: str, tools_used: int, had_summary: bool) -> bool:
    """Decide whether to start another round given how the last round ended.

    - SUCCESS  → stop (done).
    - LIMIT    → continue (step budget hit; the objective is unfinished, not stuck).
    - FAILED   → continue ONLY if the round made progress (a fresh, compressed
                 context often clears a context-overload halt); stop if it did
                 nothing, to avoid spinning on a genuine failure.
    - BLOCKED  → stop (a dead-end the loop already proved; re-running wastes budget).
    """
    s = (final_status or "").upper()
    if s == _SUCCESS:
        return False
    if s == _LIMIT:
        return True
    if s == _FAILED:
        return bool(tools_used > 0 or had_summary)
    return False  # BLOCKED / unknown


class TaskMemory:
    """Ephemeral per-task working memory. Bounded so it always fits the window."""

    def __init__(self, objective: str, max_findings: int = 24,
                 max_finding_len: int = 220):
        self.objective = (objective or "").strip()
        self.round = 0
        self.tools_total = 0
        self.done = False
        self.findings: List[str] = []          # accumulated, deduped, bounded
        self._seen = set()
        self._max_findings = max_findings
        self._max_finding_len = max_finding_len

    def _add(self, text: Optional[str]) -> None:
        t = (text or "").strip()
        if not t:
            return
        t = t[:self._max_finding_len]
        key = t.lower()[:120]
        if key in self._seen:
            return
        self._seen.add(key)
        self.findings.append(t)
        # keep only the most recent N (older residue is already reflected in the
        # workspace files / ledger; the seed must stay small)
        if len(self.findings) > self._max_findings:
            drop = self.findings.pop(0)
            self._seen.discard(drop.lower()[:120])

    def absorb(self, summary: Optional[str], tools_used: int = 0,
               findings: Optional[List[str]] = None) -> None:
        """Fold a completed round's result into the working memory."""
        self.round += 1
        self.tools_total += max(0, int(tools_used or 0))
        self._add(summary)
        for f in (findings or []):
            self._add(f)

    def render(self) -> str:
        """Human/agent-readable accumulated state."""
        if not self.findings:
            return "(no findings recorded yet)"
        return "\n".join(f"- {f}" for f in self.findings)

    def seed_task(self, original_task: Optional[str] = None) -> str:
        """The task text for the NEXT round: objective + bounded progress + a
        continue-don't-restart instruction. Kept compact on purpose."""
        obj = (original_task or self.objective).strip()
        return (
            f"[CONTINUATION · round {self.round + 1} of a large task — "
            f"{self.tools_total} tool calls so far]\n\n"
            "## OBJECTIVE (the whole task)\n"
            f"{obj}\n\n"
            "## PROGRESS SO FAR — already done, do NOT repeat\n"
            f"{self.render()}\n\n"
            "## WORKSPACE\n"
            "Files already written are present in the workspace, and the mission "
            "ledger records completed steps. Read them if needed; never redo "
            "finished work.\n\n"
            "## YOUR JOB THIS ROUND\n"
            "Continue the OBJECTIVE from exactly where it left off — do the NEXT "
            "unfinished part. When the ENTIRE objective is complete, end with "
            "TASK_COMPLETE. If not yet complete, do as much as fits, then stop; "
            "the next round will continue."
        )
