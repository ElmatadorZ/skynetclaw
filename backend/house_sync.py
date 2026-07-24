"""
house_sync.py — THE HOUSE Unified State Layer (backend)
========================================================
Backend-mediated shared state between all UI surfaces.
Uses SSE broadcast so every connected UI receives changes instantly.

State fields (UI preferences only — runtime truth lives on the event bus):
  model            str   — active model name
  connection       dict  — {id, name} active API connection

API:
  GET  /api/house/state         — current snapshot
  POST /api/house/state         — update fields; broadcasts to all SSE listeners
  GET  /api/house/state/stream  — SSE stream of state change events
  GET  /house-state-client.js   — serve the client JS library

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import asyncio
import collections
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# ── UI cross-tab shared state ─────────────────────────────────────────────────
# ONLY the operator's model + connection selection live here — these are genuine
# UI preferences that must sync across tabs and have no event-bus equivalent.
#
# Runtime TRUTH (mission state, who is active) lives on the event bus + the
# institutional DB. The former 'mission' and 'active_agents' fields were a SHADOW
# copy round-tripped through this channel; every UI surface now derives those
# from bus events (tool_started / reasoning_* / mission_* / house_*), so they are
# removed here. The client keeps a private local copy for its own rendering — it
# no longer pretends to be shared truth.
# (Removed: 'active_session' (write-only), 'mission' + 'active_agents' (shadow of
#  the event bus — bus is the single source of truth).)
_STATE: Dict[str, Any] = {
    "model": "",
    "connection": {"id": None, "name": ""},
    "_ts": 0.0,
    "_origin": "",
}

# Active SSE subscriber queues (one per connected client)
_SUBSCRIBERS: List[asyncio.Queue] = []

# ── Runtime Event Bus (Phase 1) ───────────────────────────────────────────────
# A SECOND, dedicated channel that carries discrete runtime ACTIVITY events
# (tool started/failed, council started/completed, mission updated, …) — as
# opposed to the _STATE snapshot channel above which carries shared UI state.
# Kept on its own subscriber pool so the existing state/stream consumers are
# never spammed with activity events (zero behavioural change to that channel).
#
# Envelope (the one source-of-truth shape):  {id, timestamp, type, source, payload}
#
# This is NOT new intelligence — it only re-broadcasts events the runtime
# already emits, so any UI can observe real activity regardless of who issued
# the request. The producer is house_sync.publish(); the relay is the tap.
_EVENT_SUBSCRIBERS: List[asyncio.Queue] = []
_EVENT_LOG: "collections.deque" = collections.deque(maxlen=200)  # replay buffer for late joiners
_EVENT_SEQ: int = 0


def _broadcast_event(evt: Dict[str, Any]) -> None:
    """Fan one event out to every events-channel subscriber (mirrors _broadcast)."""
    payload = json.dumps(evt, ensure_ascii=False)
    dead: List[asyncio.Queue] = []
    for q in _EVENT_SUBSCRIBERS:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _EVENT_SUBSCRIBERS.remove(q)
        except ValueError:
            pass


def publish(type: str, payload: Optional[Dict[str, Any]] = None,
            source: str = "runtime") -> Dict[str, Any]:
    """Publish ONE runtime event to the central House event bus.

    Best-effort and never raises — a failure here must never break the runtime
    path that called it. Returns the envelope (useful for tests/logging).
    """
    global _EVENT_SEQ
    _EVENT_SEQ += 1
    evt = {
        "id": f"evt_{int(time.time() * 1000)}_{_EVENT_SEQ}",
        "timestamp": time.time(),
        "type": str(type),
        "source": str(source),
        "payload": payload or {},
    }
    try:
        _EVENT_LOG.append(evt)
        _broadcast_event(evt)
    except Exception:
        pass
    return evt


def _broadcast(event: Dict[str, Any]) -> None:
    """Push an event to every connected SSE subscriber."""
    payload = json.dumps(event, ensure_ascii=False)
    dead: List[asyncio.Queue] = []
    for q in _SUBSCRIBERS:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _SUBSCRIBERS.remove(q)
        except ValueError:
            pass


def _diff(a: Any, b: Any) -> bool:
    """True if a and b differ (JSON-normalised comparison)."""
    try:
        return json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)
    except Exception:
        return a != b


def mount(app: FastAPI) -> None:
    _CLIENT_JS = Path(__file__).resolve().parent.parent / "house-state-client.js"

    @app.get("/house-state-client.js")
    def _serve_client():
        if _CLIENT_JS.exists():
            return FileResponse(
                str(_CLIENT_JS),
                media_type="application/javascript",
                headers={"Cache-Control": "no-cache, no-store"},
            )
        return JSONResponse({"error": "house-state-client.js not found"}, status_code=404)

    @app.get("/api/house/state")
    def _get_state():
        return JSONResponse({
            "ok": True,
            "state": _STATE,
            "subscribers": len(_SUBSCRIBERS),
        })

    @app.post("/api/house/state")
    async def _post_state(body: dict):
        origin = str(body.pop("_origin", ""))
        changed: Dict[str, Any] = {}

        for k, v in body.items():
            if k.startswith("_") or k not in _STATE:
                continue
            if _diff(_STATE[k], v):
                _STATE[k] = v
                changed[k] = v

        if changed:
            _STATE["_ts"] = time.time()
            _STATE["_origin"] = origin
            _broadcast({
                "type": "state_update",
                "changes": changed,
                "origin": origin,
                "ts": _STATE["_ts"],
            })

        return JSONResponse({"ok": True, "changed": list(changed.keys()), "origin": origin})

    @app.get("/api/house/state/stream")
    async def _stream(origin: str = ""):
        q: asyncio.Queue = asyncio.Queue(maxsize=128)
        _SUBSCRIBERS.append(q)

        async def _gen():
            # Immediately sync the new subscriber with current state
            snapshot = json.dumps({
                "type": "state_snapshot",
                "state": _STATE,
                "subscribers": len(_SUBSCRIBERS),
            }, ensure_ascii=False)
            yield f"data: {snapshot}\n\n"

            try:
                while True:
                    try:
                        msg = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield f"data: {msg}\n\n"
                    except asyncio.TimeoutError:
                        yield 'data: {"type":"keepalive"}\n\n'
            finally:
                try:
                    _SUBSCRIBERS.remove(q)
                except ValueError:
                    pass

        return StreamingResponse(
            _gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get("/api/house/events")
    async def _events(origin: str = "", replay: int = 50):
        """SSE channel for the Runtime Event Bus. On connect it replays the most
        recent events (so a late joiner isn't blank), then streams live."""
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        _EVENT_SUBSCRIBERS.append(q)

        async def _gen():
            n = max(0, min(int(replay or 0), _EVENT_LOG.maxlen))
            for evt in list(_EVENT_LOG)[-n:] if n else []:
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            try:
                while True:
                    try:
                        msg = await asyncio.wait_for(q.get(), timeout=15.0)
                        yield f"data: {msg}\n\n"
                    except asyncio.TimeoutError:
                        yield 'data: {"type":"keepalive"}\n\n'
            finally:
                try:
                    _EVENT_SUBSCRIBERS.remove(q)
                except ValueError:
                    pass

        return StreamingResponse(
            _gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get("/api/house/events/recent")
    def _events_recent(limit: int = 50):
        """Non-streaming snapshot of the recent event buffer (debug / polling)."""
        n = max(0, min(int(limit or 0), _EVENT_LOG.maxlen))
        return JSONResponse({
            "ok": True,
            "events": list(_EVENT_LOG)[-n:] if n else [],
            "subscribers": len(_EVENT_SUBSCRIBERS),
        })

    @app.get("/api/house/cognition")
    def _cognition():
        """HOUSE MIND V2 — current cognitive state (read-model over house_state).
        Returns blank fields when the House genuinely knows nothing."""
        try:
            import house_cognition as _hc
            return JSONResponse({"ok": True, "state": _hc.snapshot()})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e), "state": {}}, status_code=200)

    @app.get("/api/house/frame")
    def _frame():
        """OX-1.7 COGNITIVE HOUSE MIND — the reasoning state reframed as the five
        questions: Current Question / Belief / Conflict / Risk / Next Decision.
        Pure re-projection of house_state; blank when the House knows nothing."""
        try:
            import house_cognition as _hc
            return JSONResponse({"ok": True, "frame": _hc.frame()})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e), "frame": {}}, status_code=200)

    @app.get("/api/house/timeline")
    def _timeline(state_id: str = ""):
        """BELIEF EVOLUTION TIMELINE (Phase 4) — Question -> Evidence -> Hypothesis
        -> Challenge -> Revision -> Decision, projected from house_state +
        belief_changes. Missing stages are reported as gaps, never invented."""
        try:
            import belief_timeline as _bt
            return JSONResponse({"ok": True, "timeline": _bt.timeline(state_id or None)})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e), "timeline": {}}, status_code=200)

    @app.get("/api/house/missions")
    def _missions():
        """MISSION COMMAND CENTER (Phase 5) — unified mission view projected from
        house_state (council) + agent_runs (execution). PAUSED is always empty
        (no real pause source); fields with no real source are left blank."""
        try:
            import mission_command as _mc
            return JSONResponse({"ok": True, "missions": _mc.snapshot()})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e), "missions": {}}, status_code=200)

    @app.get("/api/house/learning")
    def _learning():
        """INSTITUTIONAL LEARNING (Phase 6) — lessons / failures / successes /
        behavior changes / repeat errors, projected from graded outcomes only.
        Empty when reality has graded nothing yet."""
        try:
            import learning_engine as _le
            return JSONResponse({"ok": True, "learning": _le.snapshot()})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e), "learning": {}}, status_code=200)

    @app.get("/api/house/os")
    def _house_os():
        """HOUSE OPERATING SYSTEM (Phase P3) — policies + rules with provenance,
        plus the lessons / behavior changes they answer to. Policies are codified
        with real provenance, never fabricated."""
        try:
            import house_os as _os
            return JSONResponse({"ok": True, "os": _os.snapshot()})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e), "os": {}}, status_code=200)

    @app.get("/api/house/discover")
    def _discover(q: str = ""):
        """OX-1 DISCOVERY: Discover → Classify → Route. Investigate the House's own
        records before planning. Returns {category, answer, evidence, confidence,
        needs_clarification, discovery_order}. Read-only; STATE_LOOKUP is answered
        directly (no plan/council)."""
        try:
            import discovery as _disc
            return JSONResponse({"ok": True, "route": _disc.route(q or "")})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e), "route": {}}, status_code=200)

    print(
        "[HouseSync] Unified State Layer mounted · "
        "/api/house/state (GET+POST+SSE) · /house-state-client.js · "
        "/api/house/events (Runtime Event Bus SSE)"
    )
