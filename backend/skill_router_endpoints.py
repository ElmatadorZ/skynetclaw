"""
skill_router_endpoints.py — preview + force-rebuild endpoints for the auto-router
==================================================================================
Mounted at /api/skills/*

Endpoints
---------
GET  /api/skills/index          — show current trigger index (skills + tokens)
POST /api/skills/match          — preview which skills WOULD fire for given text
                                  body: {"text": "...", "top_k": 2, "min_score": 1.0}
POST /api/skills/rebuild        — force-rebuild skills_index.json (after adding skills)
GET  /api/skills/status         — quick health check
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from pydantic import BaseModel

from skills_auto_router import (
    build_index, load_index, match, auto_skill_messages, fetch_system_prompt,
)


class MatchReq(BaseModel):
    text: str
    top_k: int = 2
    min_score: float = 1.0


def mount(app: FastAPI) -> None:
    """Call from main.py after `app = FastAPI(...)`."""

    @app.get("/api/skills/index")
    def _index() -> Dict[str, Any]:
        idx = load_index()
        return {
            "built_at": idx.get("built_at"),
            "count":    len(idx.get("skills", [])),
            "skills":   [
                {
                    "id":           s["id"],
                    "name":         s["name"],
                    "role":         s.get("role", ""),
                    "version":      s.get("version", ""),
                    "n_triggers":   len(s.get("trigger_phrases", [])),
                    "n_tokens":     len(s.get("trigger_tokens",  [])),
                    "description":  s.get("description", "")[:200],
                }
                for s in idx.get("skills", [])
            ],
        }

    @app.post("/api/skills/match")
    def _match(req: MatchReq) -> Dict[str, Any]:
        matches = match(req.text, top_k=req.top_k, min_score=req.min_score)
        msgs = auto_skill_messages(req.text, top_k=req.top_k, min_score=req.min_score)
        return {
            "ok":          True,
            "text":        req.text,
            "n_matches":   len(matches),
            "matches":     matches,
            "would_inject_chars": sum(len(m["content"]) for m in msgs),
        }

    @app.post("/api/skills/rebuild")
    def _rebuild() -> Dict[str, Any]:
        idx = build_index()
        try:
            import capability_skill_registry as _csr
            _csr.build_index()
        except Exception:
            pass
        return {
            "ok":     True,
            "count":  len(idx.get("skills", [])),
            "skills": [s["name"] for s in idx.get("skills", [])],
        }

    # ── Capability-Skill Architecture (CSA v1) ────────────────────────────
    @app.get("/api/skills/architecture")
    def _architecture() -> Dict[str, Any]:
        """Capability -> skills tree (drives the Skills page architecture view)."""
        try:
            import capability_skill_registry as _csr
            return {"ok": True, **_csr.architecture()}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @app.post("/api/skills/resolve")
    def _resolve(req: MatchReq) -> Dict[str, Any]:
        """Preview: which capabilities + skills WOULD activate for this task."""
        try:
            import capability_skill_registry as _csr
            caps = _csr.resolve(req.text)
            msgs = _csr.activate_for_task(req.text, top_k=req.top_k)
            return {
                "ok": True, "text": req.text,
                "capabilities": caps,
                "skills": [m["skill_meta"] for m in msgs],
                "would_inject_chars": sum(len(m["content"]) for m in msgs),
            }
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @app.post("/api/skills/find")
    def _find(req: MatchReq) -> Dict[str, Any]:
        """Runtime find_skill, exposed for the UI search box."""
        try:
            import capability_skill_registry as _csr
            hits = _csr.find_skills(req.text, top_k=max(req.top_k, 5))
            return {"ok": True, "query": req.text, "skills": hits}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    @app.get("/api/skills/status")
    def _status() -> Dict[str, Any]:
        try:
            idx = load_index()
            n = len(idx.get("skills", []))
            return {
                "ok":              True,
                "skills_indexed":  n,
                "auto_router":     "armed",
                "all_phrases":     sum(len(s.get("trigger_phrases", [])) for s in idx.get("skills", [])),
            }
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
