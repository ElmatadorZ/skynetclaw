"""
21_skills_index.py - rebuilds backend/skills_index.json on boot
================================================================
Runs after 20_skills_sync. Ensures the auto-router's trigger index is
fresh, so user messages match the latest folder skills.
"""
from __future__ import annotations
from typing import Any, Dict


def run(app: Any, ctx: Dict[str, Any]) -> None:
    try:
        from skills_auto_router import build_index
        idx = build_index()
        n = len(idx.get("skills", []))
        print(f"[hook.21_skills_index] [OK] skills_index.json rebuilt - {n} skill(s) indexed")
    except Exception as e:
        print(f"[hook.21_skills_index] error: {type(e).__name__}: {e}")
    try:
        from capability_skill_registry import build_index as build_cap_index
        cidx = build_cap_index()
        print(f"[hook.21_skills_index] [OK] capability index rebuilt - "
              f"{len(cidx.get('skills', []))} skill(s) bound")
    except Exception as e:
        print(f"[hook.21_skills_index] capability index error: {type(e).__name__}: {e}")
