"""
makruk_api.py — HTTP surface for the Thai Chess (Makruk) feature
================================================================
Follows the repo's mount(app) convention. Exposes a small REST API over the
deterministic makruk engine and serves the play page at /makruk.

Endpoints (all JSON):
    POST /api/makruk/new       {level?}                 → {game_id, state}
    GET  /api/makruk/state     ?game_id=                → {state}
    POST /api/makruk/move      {game_id, from, to}      → {state}
    POST /api/makruk/ai-move   {game_id, level?}        → {state, ai:{move,score,pv,reason,nodes}}
    POST /api/makruk/hint      {game_id, level?}        → {hint:{...}}   (does not mutate)

Games are held in-memory (local single-operator app). No coupling to main.py.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import Body
from fastapi.responses import FileResponse, JSONResponse

from makruk.game import Game
from makruk.ai import best_move, win_prob, LEVELS, LEVEL_BUDGET, DEFAULT_BUDGET, LEVEL_TIME

_GAMES: Dict[str, Game] = {}
_PROJ_ROOT = Path(__file__).resolve().parent.parent


def _level_depth(level: Optional[str]) -> int:
    return LEVELS.get((level or "hard").lower(), 3)


def _level_budget(level: Optional[str]) -> int:
    return LEVEL_BUDGET.get((level or "hard").lower(), DEFAULT_BUDGET)


def _level_time(level: Optional[str]):
    return LEVEL_TIME.get((level or "hard").lower())


def _alg(s: int) -> str:
    from makruk.board import alg
    return alg(s)


def mount(app) -> None:
    # ── the play page ──
    @app.get("/makruk")
    @app.get("/makruk.html")
    @app.get("/thaichess")
    def _makruk_page():
        f = _PROJ_ROOT / "makruk.html"
        if f.exists():
            return FileResponse(str(f), media_type="text/html",
                                headers={"Cache-Control": "no-cache, must-revalidate"})
        return JSONResponse({"error": "makruk.html not found"}, status_code=404)

    # ── new game ──
    @app.post("/api/makruk/new")
    def _new(payload: dict = Body(default={})):
        gid = uuid.uuid4().hex[:12]
        _GAMES[gid] = Game()
        return {"game_id": gid, "state": _GAMES[gid].to_state(),
                "level": (payload or {}).get("level", "hard")}

    # ── read state ──
    @app.get("/api/makruk/state")
    def _state(game_id: str):
        g = _GAMES.get(game_id)
        if not g:
            return JSONResponse({"error": "unknown game_id"}, status_code=404)
        return {"state": g.to_state()}

    # ── human move ──
    @app.post("/api/makruk/move")
    def _move(payload: dict = Body(...)):
        g = _GAMES.get(payload.get("game_id", ""))
        if not g:
            return JSONResponse({"error": "unknown game_id"}, status_code=404)
        if g.is_over():
            return JSONResponse({"error": "game is over", "state": g.to_state()}, status_code=409)
        try:
            g.push_algebraic(payload["from"], payload["to"])
        except (ValueError, KeyError) as e:
            return JSONResponse({"error": f"illegal move: {e}", "state": g.to_state()},
                                status_code=400)
        return {"state": g.to_state()}

    # ── engine move ──
    @app.post("/api/makruk/ai-move")
    def _ai_move(payload: dict = Body(default={})):
        g = _GAMES.get((payload or {}).get("game_id", ""))
        if not g:
            return JSONResponse({"error": "unknown game_id"}, status_code=404)
        if g.is_over():
            return JSONResponse({"error": "game is over", "state": g.to_state()}, status_code=409)
        level = (payload or {}).get("level")
        res = best_move(g, depth=_level_depth(level), node_budget=_level_budget(level), time_limit=_level_time(level))
        ai = _ai_payload_from_result(g, res)
        if res.move is not None:
            g.push(res.move)
        return {"state": g.to_state(), "ai": ai}

    # ── hint (does not mutate the game) ──
    @app.post("/api/makruk/hint")
    def _hint(payload: dict = Body(default={})):
        g = _GAMES.get((payload or {}).get("game_id", ""))
        if not g:
            return JSONResponse({"error": "unknown game_id"}, status_code=404)
        level = (payload or {}).get("level")
        res = best_move(g, depth=_level_depth(level), node_budget=_level_budget(level), time_limit=_level_time(level))
        return {"hint": _ai_payload_from_result(g, res)}

    # ── learned state: the engine's current (possibly self-tuned) weights ──
    @app.get("/api/makruk/weights")
    def _weights():
        from makruk import ai
        active, default = ai.ACTIVE_WEIGHTS.as_dict(), ai.DEFAULT_WEIGHTS.as_dict()
        delta = {k: round(active[k] - default[k], 4) for k in default if active[k] != default[k]}
        return {"active": active, "default": default, "tuned": bool(delta), "delta": delta,
                "note": "train with: python -m makruk.learn --generations N (writes weights.json), "
                        "then POST /api/makruk/reload-weights"}

    # ── hot-reload weights.json produced by a training run (no restart needed) ──
    @app.post("/api/makruk/reload-weights")
    def _reload_weights():
        from makruk import ai
        ai.ACTIVE_WEIGHTS = ai.load_weights()
        return {"reloaded": True, "active": ai.ACTIVE_WEIGHTS.as_dict()}

    print("[Makruk] Thai Chess mounted at http://localhost:8766/makruk")


def _ai_payload_from_result(game: Game, res) -> dict:
    return {
        "move": None if not res.move else
                {"from": _alg(res.move.frm), "to": _alg(res.move.to), "promo": res.move.promo},
        "score": round(res.score, 3),
        "win_prob": win_prob(res.score),        # engine's win-expectancy from the eval
        "pv": res.pv,
        "reason": res.reason,
        "nodes": res.nodes,
        "depth": res.depth,
    }
