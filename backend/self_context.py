"""
self_context.py — PROPRIOCEPTION: the system learning from its own outcomes
===========================================================================
The runtime bridge that Volume VI (Theory of Learning) owes, exactly as the CEE
bridge (warrant_check.py) was the bridge the Theory of Warrant owed.

Vol VI · LT4 (frozen-seat theorem): the local model has frozen weights → it
CANNOT learn in the weights. So the system's learning must live in a persistent
external store that changes future *inputs*. SkynetClaw already keeps the store
(agent_runs, warrant_log) — but a log that never changes a decision is MEMORY,
not learning (Vol VI · Q1). This module turns that memory into learning: it mines
the system's own recorded outcomes into TASK-RELEVANT, CREDIT-ASSIGNED lessons
and feeds them into the next run's prompt, so a failure teaches the run after it.

It closes a real loop between two theory bridges:
  CEE (warrant_check) RECORDS the system's overclaims  →
  self_context FEEDS them back as a caution            →
  the model is warned before it repeats them.

Design discipline (from this system's own evidence):
  * Credit assignment is the differentia of learning (LT1): a lesson is surfaced
    only when it is RELEVANT to the current task (keyword overlap) or RECURRING —
    not a raw aggregate stat (that is reality_context's job).
  * F2 (scaffolding noise degrades output): SILENT when nothing has been learned
    (returns ""), and terse when it has. Never add noise.
  * Aggregation-only: it observes recorded outcomes; it never reasons or invents.

Acceptance test (Vol VI · red-team Attack 7): this is *learning* only if the
lessons demonstrably change future behaviour; if they only display, it is
monitoring. The mining is unit-tested here; behavioural change is the standing
job of the golden-behavior harness.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_STOP = {
    "the", "and", "for", "with", "this", "that", "from", "you", "your", "are", "was",
    "แล้ว", "ให้", "ของ", "และ", "ที่", "เป็น", "จาก", "ใน", "การ", "ผม", "คุณ",
    "task", "run", "please", "then", "into", "โดย", "ตาม",
}


def _tokens(s: str) -> set:
    """Lowercased content tokens (len>=3), stop-words dropped — for task similarity."""
    out = set()
    for t in re.findall(r"[A-Za-z฀-๿][A-Za-z0-9฀-๿]{2,}", (s or "").lower()):
        if t not in _STOP:
            out.add(t)
    return out


def _similarity(a: set, b: set) -> float:
    """Jaccard overlap — the credit map: how relevant a past task is to this one."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── warrant lessons: the system's own recorded C1 (overclaim) failures ───────
def mine_warrant_lessons(warrant_log_path: Optional[str] = None, recent: int = 60) -> Optional[str]:
    """If the system recently claimed reading files that did not exist, surface it.
    Reuses warrant_check's durable log (the CEE bridge output)."""
    try:
        import warrant_check as _wc
        rows = _wc.recent(limit=recent, log_path=warrant_log_path)
    except Exception:
        return None
    if not rows:
        return None
    overs = [r for r in rows if r.get("verdict") == "OVERCLAIM"]
    if not overs:
        return None
    n = len(overs)
    # a few concrete paths it fabricated, for a specific (not vague) caution
    paths: List[str] = []
    for r in overs[-5:]:
        for o in (r.get("overclaims") or [])[:2]:
            p = o.get("path")
            if p and p not in paths:
                paths.append(p)
    ex = (" e.g. " + ", ".join(paths[:3])) if paths else ""
    return (f"- SELF: in {n} recent run(s) you asserted reading files that did NOT exist{ex}. "
            f"VERIFY each file exists (list_files/find_files) before stating its contents.")


# ── run lessons: task-relevant past failures (credit-assigned by similarity) ──
def mine_run_lessons(db_path: str, task: str, recent: int = 40,
                     max_lessons: int = 2, min_sim: float = 0.12) -> List[str]:
    """Recent FAILED runs whose task resembles the current one → targeted cautions.
    Similarity is the credit map (Vol VI): only history relevant to THIS task-class
    is surfaced, so it is a lesson, not a stat."""
    qtok = _tokens(task)
    if not qtok:
        return []
    try:
        con = sqlite3.connect(db_path); c = con.cursor()
        cols = {r[1] for r in c.execute("PRAGMA table_info(agent_runs)")}
        if not {"status", "task"} <= cols:
            con.close(); return []
        tcol = "ended_at" if "ended_at" in cols else ("started_at" if "started_at" in cols else None)
        order = f"ORDER BY {tcol} DESC" if tcol else ""
        rows = c.execute(
            f"SELECT status, task, summary FROM agent_runs "
            f"WHERE status IN ('failed','limit','interrupted','blocked_awaiting_gate') {order} LIMIT ?",
            (recent,)).fetchall()
        con.close()
    except Exception:
        return []
    scored = []
    for st, ptask, summ in rows:
        sim = _similarity(qtok, _tokens(ptask or ""))
        if sim >= min_sim:
            scored.append((sim, st, ptask, summ))
    scored.sort(key=lambda x: -x[0])
    out = []
    seen = set()
    for sim, st, ptask, summ in scored[:max_lessons]:
        key = (str(ptask)[:40])
        if key in seen:
            continue
        seen.add(key)
        why = (summ or "").split("[[EXEC_MEM]]")[0].strip()[:110]
        out.append(f"- SELF: a similar past task ended [{st}]: \"{str(ptask)[:60]}\""
                   + (f" — {why}" if why else "") + ". Don't repeat that failure mode.")
    return out


def build_self_context(db_path: str, task: str,
                       warrant_log_path: Optional[str] = None,
                       recent_runs: int = 40, recent_warrant: int = 60) -> str:
    """Compose the PROPRIOCEPTION block from the system's own outcomes. Returns ''
    when nothing relevant has been learned (silence is correct — do not add noise)."""
    lessons: List[str] = []
    w = mine_warrant_lessons(warrant_log_path, recent=recent_warrant)
    if w:
        lessons.append(w)
    lessons.extend(mine_run_lessons(db_path, task, recent=recent_runs))
    if not lessons:
        return ""
    return (
        "## LESSONS FROM YOUR OWN HISTORY (proprioception — verified from your run log)\n"
        + "\n".join(lessons[:3])
        + "\nThese are your OWN past outcomes on tasks like this one. Apply them now."
    )
