"""
20_skills_sync.py - boot hook that syncs folder-based skills to skynerclaw.db
"""
from __future__ import annotations
from typing import Any, Dict


def run(app: Any, ctx: Dict[str, Any]) -> None:
    try:
        from skills_loader import sync_skills_to_db
        r = sync_skills_to_db()
        if r.get("ok"):
            print(f"[hook.20_skills_sync] [OK] {r['discovered']} skill(s) synced "
                  f"(new={r['new']} updated={r['updated']})")
        else:
            print(f"[hook.20_skills_sync] sync returned: {r}")
    except Exception as e:
        print(f"[hook.20_skills_sync] error: {type(e).__name__}: {e}")
