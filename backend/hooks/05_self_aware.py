"""
05_self_aware.py — boot hook that refreshes SELF.md
====================================================
Runs on every FastAPI startup. Calls self_awareness.write_self_state(app)
which scans:
  - capabilities (tools, integrations, skills, models, modules)
  - Obsidian vault (notes, topics, recent activity)
  - Genome state
  - constraints (what we CAN'T do)
  - recent agent_runs

Output: backend/SELF.md — read by compose_genesis_prompt() at agent_run time.

Hook order: 05_ runs after the default boot hook (which has no number prefix
and effectively runs first or last alphabetically, depending on filenames).
"""
from __future__ import annotations

from typing import Any, Dict


def run(app: Any, ctx: Dict[str, Any]) -> None:
    """Refresh SELF.md so every session boots with current self-awareness."""
    try:
        from self_awareness import write_self_state, compose_brief
    except Exception as e:
        print(f"[hook.05_self_aware] self_awareness import failed: {e}")
        return

    try:
        path = write_self_state(app=app)
        size = path.stat().st_size if path and path.exists() else 0
        print(f"[hook.05_self_aware] SELF.md refreshed → {path} ({size:,} bytes)")
        # Also print a one-line brief so the operator can sanity-check at boot
        brief = compose_brief()
        if brief:
            # Truncate for console
            print(f"[hook.05_self_aware] brief: {brief[:240]}...")
    except Exception as e:
        print(f"[hook.05_self_aware] refresh failed: {e}")
