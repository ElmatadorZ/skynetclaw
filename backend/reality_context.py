"""
reality_context.py — inject VERIFIED runtime reality into the model's context
=============================================================================
Root of a real, felt failure: the workspace banner tells the agent WHERE to
write (the folder path) but never WHAT is already there. So with 13 files
mounted the model still asks "which file?" — it is answering from language, not
from the current world.

This module aggregates the CURRENT WORLD (workspace contents + runtime identity)
into one compact, honestly-labelled block. It is aggregation-only: it OBSERVES,
it never reasons or decides. Every fact is a direct filesystem/config read
(high confidence, source-tagged, timestamped for freshness) — nothing inferred.

Kept bounded so it costs little context and never bloats the window.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Optional


def _list_workspace_files(folder: str, max_files: int = 40) -> tuple[List[str], int]:
    """Return (relative paths shown, total count). Recursive, bounded, skips
    dotfiles / node_modules / __pycache__ noise. Direct filesystem read."""
    root = Path(folder)
    out: List[str] = []
    total = 0
    _SKIP = {".git", "node_modules", "__pycache__", ".venv", ".idea"}
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP and not d.startswith(".")]
            for fn in sorted(filenames):
                if fn.startswith("."):
                    continue
                total += 1
                if len(out) < max_files:
                    rel = os.path.relpath(os.path.join(dirpath, fn), root)
                    try:
                        size = os.path.getsize(os.path.join(dirpath, fn))
                        out.append(f"{rel} ({_human(size)})")
                    except Exception:
                        out.append(rel)
    except Exception:
        pass
    return out, total


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def build_operational_summary(db_path: str, recent: int = 4) -> str:
    """Compact, verified summary of the runtime's OWN run history (agent_runs):
    outcome counts + the most recent failures with their cause. Grounds
    self-diagnosis so 'analyze the failures' can't honestly answer UNKNOWN while
    38 failed runs sit in the DB. Direct SQLite read; never inferred."""
    import sqlite3
    try:
        con = sqlite3.connect(db_path); c = con.cursor()
        cols = {r[1] for r in c.execute("PRAGMA table_info(agent_runs)")}
        if not {"status", "task"} <= cols:
            con.close(); return ""
        counts = dict(c.execute(
            "SELECT status, COUNT(*) FROM agent_runs GROUP BY status").fetchall())
        total = sum(counts.values())
        tcol = "ended_at" if "ended_at" in cols else "started_at"
        fails = c.execute(
            f"SELECT status, task, summary, {tcol} FROM agent_runs "
            "WHERE status IN ('failed','limit','interrupted') "
            f"ORDER BY {tcol} DESC LIMIT ?", (recent,)).fetchall()
        con.close()
    except Exception:
        return ""
    if not total:
        return ""
    order = ["TASK_COMPLETE", "failed", "limit", "interrupted", "blocked_awaiting_gate"]
    cparts = [f"{k}={counts[k]}" for k in order if k in counts] + \
             [f"{k}={v}" for k, v in counts.items() if k not in order]
    lines = [f"RECENT OPERATIONS: {total} agent runs · " + ", ".join(cparts)]
    if fails:
        lines.append("LATEST FAILURES (verified from agent_runs):")
        for st, task, summ, t in fails:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) if isinstance(t, (int, float)) and t and t > 1e9 else ""
            why = (summ or "").split("[[EXEC_MEM]]")[0].strip()[:120]
            lines.append(f"  - [{st}] {ts} · {str(task)[:60]} — {why}")
    return "\n".join(lines)


def build_reality(workspace_folder: Optional[str] = None,
                  runtime_label: str = "", model: str = "",
                  operational: str = "",
                  max_files: int = 40) -> str:
    """Compose the REALITY block. Returns '' if there is nothing verifiable to
    report (so callers can inject unconditionally)."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S %z") or time.strftime("%Y-%m-%d %H:%M:%S")
    parts: List[str] = []

    if runtime_label or model:
        rt = " · ".join([x for x in (f"runtime={runtime_label}" if runtime_label else "",
                                     f"model={model}" if model else "") if x])
        parts.append(rt)

    if workspace_folder and os.path.isdir(workspace_folder):
        files, total = _list_workspace_files(workspace_folder, max_files=max_files)
        parts.append(f"WORKSPACE: {workspace_folder}")
        if total == 0:
            parts.append("FILES: (workspace is EMPTY — 0 files)")
        else:
            shown = "\n".join(f"  - {f}" for f in files)
            more = f"\n  … and {total - len(files)} more" if total > len(files) else ""
            parts.append(f"FILES ({total} total):\n{shown}{more}")

    if operational:
        parts.append(operational)

    if not parts:
        return ""

    body = "\n".join(parts)
    return (
        f"## REALITY — verified current world (direct observation @ {ts})\n"
        f"{body}\n"
        "USE THIS: everything above is VERIFIED runtime state right now. Resolve "
        "'the file' / 'this data' against the FILES list (don't ask which file if "
        "one match exists). For any question about failures / errors / system "
        "health, use RECENT OPERATIONS + LATEST FAILURES above as your evidence — "
        "NEVER answer UNKNOWN or 'no data' when these lines are present."
    )
