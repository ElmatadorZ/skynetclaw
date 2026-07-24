"""
continental_relay.py — express lane between Continental UI <-> SkynetClaw chat
==============================================================================
Mirrors directives + responses to chat_history.db (audit transparency)
and emits CBP envelopes (bridge log) at every key event.

Mounted at /api/continental/*
"""
from __future__ import annotations
import asyncio, hashlib, json, sqlite3, time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

try:
    from bridge_protocol import emit as _cbp, T as _CT
    _CBP = True
except Exception:
    _CBP = False
    class _CT:
        DIRECTIVE=ACK=STREAM_START=PHASE=OPERATIVE_ON=OPERATIVE_OFF=""
        SKILL_FIRE=TOOL_CALL=TOOL_RESULT=TEXT_DELTA=VERDICT=COMPLETE=ERROR=""
    def _cbp(*a, **k): return None

# NOTE: this relay used to re-publish runtime events to the House bus (Phase 1b).
# That tap was removed — runtime events are now published at the SOURCE
# (main.py via house_sync.publish), which is the single source of truth and
# avoids duplicate bus events. The relay only proxies the SSE stream + writes
# the CBP audit log.

_BASE  = Path(__file__).parent.resolve()
AUDIT  = _BASE / "continental_audit.jsonl"
CHATDB = _BASE / "chat_history.db"


def _ensure_chat_db():
    with sqlite3.connect(CHATDB, check_same_thread=False) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT, role TEXT, content TEXT,
            source TEXT, operator TEXT, ts REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS continental_conversations (
            id TEXT PRIMARY KEY, started_at REAL, last_at REAL,
            directive_preview TEXT, operative_routed TEXT,
            tools_invoked INTEGER DEFAULT 0, status TEXT)""")


def mirror_directive_to_chat(conv_id: str, directive: str, operator: str = "ELMATADORZ"):
    _ensure_chat_db()
    now = time.time()
    with sqlite3.connect(CHATDB, check_same_thread=False) as c:
        c.execute("INSERT INTO chat_messages(conversation_id,role,content,source,operator,ts) VALUES (?,?,?,?,?,?)",
                  (conv_id, "user", directive, "continental", operator, now))
        existing = c.execute("SELECT id FROM continental_conversations WHERE id=?", (conv_id,)).fetchone()
        if existing:
            c.execute("UPDATE continental_conversations SET last_at=?, directive_preview=? WHERE id=?",
                      (now, directive[:120], conv_id))
        else:
            c.execute("INSERT INTO continental_conversations(id,started_at,last_at,directive_preview,operative_routed,tools_invoked,status) VALUES (?,?,?,?,?,?,?)",
                      (conv_id, now, now, directive[:120], "", 0, "DISPATCHED"))


def mirror_response_to_chat(conv_id: str, content: str, tools: int = 0):
    _ensure_chat_db()
    with sqlite3.connect(CHATDB, check_same_thread=False) as c:
        c.execute("INSERT INTO chat_messages(conversation_id,role,content,source,operator,ts) VALUES (?,?,?,?,?,?)",
                  (conv_id, "assistant", content, "agent", "skynetclaw", time.time()))
        c.execute("UPDATE continental_conversations SET tools_invoked=?, status=? WHERE id=?",
                  (tools, "COMPLETE", conv_id))


def _last_audit_hash() -> str:
    if not AUDIT.exists(): return "GENESIS"
    try:
        with AUDIT.open("rb") as f:
            f.seek(0, 2); size = f.tell()
            f.seek(max(0, size - 4096))
            tail = f.read().decode("utf-8", errors="ignore").splitlines()
            for line in reversed(tail):
                try: return json.loads(line).get("hash", "GENESIS")
                except Exception: continue
    except Exception: pass
    return "GENESIS"


def audit_log(operator: str, conv_id: str, directive: str,
              response_hash: str, operative: str = "", tools: int = 0):
    prev = _last_audit_hash()
    entry = {
        "ts": time.time(), "operator": operator, "conv_id": conv_id,
        "directive": directive[:300], "response_hash": response_hash,
        "operative_routed": operative, "tools_invoked": tools, "prev_hash": prev,
    }
    block = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    entry["hash"] = hashlib.sha256((prev + block).encode("utf-8")).hexdigest()[:16]
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class DispatchReq(BaseModel):
    directive: str
    model: Optional[str] = None
    operator: Optional[str] = "ELMATADORZ"
    mode: Optional[str] = "agent"
    workspace_folder: Optional[str] = None   # where the agent writes files


def mount(app: FastAPI, base_url: str = "http://127.0.0.1:8766") -> None:
    _ensure_chat_db()
    # OX-WORKFLOW-1: additive workflow lifecycle store (separate from chat/house/runs)
    try:
        import workflow_runs as _wfmod
        _WF = _wfmod.WorkflowRunsDB()
    except Exception as _wfe:
        _WF = None
        print(f"[ContinentalRelay] workflow_runs unavailable: {_wfe}")

    @app.post("/api/continental/dispatch")
    async def _dispatch(req: DispatchReq):
        conv_id = "CD-" + hashlib.sha1(
            f"{req.directive[:80]}:{time.time()}".encode()
        ).hexdigest()[:10]
        mirror_directive_to_chat(conv_id, req.directive, req.operator or "ELMATADORZ")
        # OX-WORKFLOW-1: durable record the instant the dispatch is issued — before
        # COMPREHEND, so no dispatch can ever vanish (closes the attempt gap).
        if _WF:
            try: _WF.start(conv_id, req.directive)
            except Exception: pass
        if _CBP:
            _cbp(_CT.DIRECTIVE, {"text": req.directive}, src="operator", dst="house", conv_id=conv_id)

        async def stream():
            yield f"data: {json.dumps({'type':'continental_open','conv_id':conv_id})}\n\n"
            if _CBP:
                _cbp(_CT.STREAM_START, {"mode": req.mode}, conv_id=conv_id)
                _cbp(_CT.ACK, {"conv_id": conv_id}, conv_id=conv_id)

            # ── OX-EXEC-2 ACTION BIAS ── explicit operator intent or a low-risk
            # action bypasses council deliberation and Discovery lookup. The
            # Commander routes it straight to the Executor.
            _exec_mode = req.mode
            _reason_context = None      # House records to reason over (analytical status Q)
            try:
                import execution_policy as _ep
                _pol = _ep.classify(req.directive or "")
                # A genuine DELIBERATION ("ตัดสินใจ… ชั่งน้ำหนัก… แนะนำ", "should we…",
                # weigh/compare/trade-off) must reach the council even though the
                # action-bias heuristic flags it as "explicit operator intent".
                # Action-bias is for imperative do-this-now tasks, not decisions —
                # the operator picked council mode ON PURPOSE. (Found live: a clear
                # decision question was bypassed straight to the executor.)
                _is_deliberation = False
                try:
                    import agent_council as _acq
                    _is_deliberation = _acq.looks_like_deliberation_task(req.directive or "")
                except Exception:
                    _is_deliberation = False
                if req.mode == "council" and _pol["route"] == _ep.DIRECT_EXECUTE and not _is_deliberation:
                    _exec_mode = "agent"
                    yield f"data: {json.dumps({'type':'commander','verdict':'EXECUTE_NOW','text':'▶ ELITE COMMANDER: EXECUTE NOW — ' + _pol['reason'] + ' · council bypassed','risk':_pol['risk']}, ensure_ascii=False)}\n\n"
            except Exception as _epe:
                print(f"[ExecPolicy] action-bias check skipped: {_epe}")

            # ── OX-1 DISCOVER FIRST ── investigate the House's own records before
            # planning. A pure STATE_LOOKUP is answered directly from records — no
            # comprehend, no plan, no council, no model call. Best-effort: any
            # failure falls through to the normal reasoning path below.
            try:
                import discovery as _discovery
                _r = _discovery.route(req.directive or "")
                # small talk → the conversational model, not the 4-phase workflow
                # (a greeting was answered with a House Mind dump before this)
                if _r.get("category") == "CHAT":
                    _exec_mode = "chat"
                    # an ANALYTICAL status question carries the House records as
                    # context so the model reasons over them and actually answers
                    if _r.get("reason_over_records") and _r.get("context"):
                        _reason_context = _r["context"]
                if _exec_mode != "agent" and _r.get("category") == "STATE_LOOKUP" and _r.get("answer") and not _r.get("needs_clarification"):
                    _ans = _r["answer"]
                    yield f"data: {json.dumps({'type':'phase','phase':'discover'})}\n\n"
                    yield f"data: {json.dumps({'type':'text','text':_ans}, ensure_ascii=False)}\n\n"
                    mirror_response_to_chat(conv_id, _ans, 0)
                    _rh = hashlib.sha256(_ans.encode('utf-8')).hexdigest()[:16]
                    audit_log(req.operator or "ELMATADORZ", conv_id, req.directive, _rh, "DISCOVERY", 0)
                    if _WF:
                        try: _WF.complete(conv_id, "completed", "state_lookup")
                        except Exception: pass
                    # outcome travels WITH the close — a STATE_LOOKUP answered from
                    # records is a COMPLETED mission, not "channel closed, no event"
                    yield f"data: {json.dumps({'type':'continental_close','conv_id':conv_id,'response_hash':_rh,'tools':0,'route':'STATE_LOOKUP','outcome':'completed'})}\n\n"
                    return
            except Exception as _dre:
                print(f"[Discovery] preflight skipped: {_dre}")

            if _exec_mode == "council":
                # 4-phase Genesis workflow — real division of labour:
                # comprehend → plan → council(6 specialists) → execute → reflect
                url = base_url + "/api/workflow/run"
                payload = {"task": req.directive, "model": req.model,
                           "workspace_folder": req.workspace_folder}
            elif _exec_mode == "agent":
                url = base_url + "/api/agent/run"
                payload = {"task": req.directive, "model": req.model,
                           "workspace_folder": req.workspace_folder}
            else:
                url = base_url + "/api/chat"
                _msgs = []
                if _reason_context:
                    _msgs.append({"role": "system", "content":
                        "You are answering a question about THE HOUSE's own status. "
                        "Reason over these live records and give a specific, technical "
                        "answer to what the operator asked — do not just restate the "
                        "numbers. Records:\n" + _reason_context})
                _msgs.append({"role": "user", "content": req.directive})
                payload = {"messages": _msgs,
                           "model": req.model, "use_tools": False, "agent_mode": False,
                           "workspace_folder": req.workspace_folder}

            text_accum: List[str] = []
            tool_count = 0
            operative_routed = ""
            _mission_state_id = None      # House-Mind state to close when the mission ends
            try:
                async with httpx.AsyncClient(timeout=None) as cx:
                    async with cx.stream("POST", url, json=payload) as r:
                        aiter = r.aiter_lines()
                        _pending = None
                        while True:
                            # LIVENESS WATCHDOG — emit keepalive while upstream is silent,
                            # WITHOUT cancelling the pending read. (asyncio.wait_for would
                            # CANCEL __anext__ on timeout and corrupt the iterator — that
                            # bug silently severed every stream that stayed quiet >10s,
                            # e.g. local-model prompt eval, sealing "(no text response)".)
                            if _pending is None:
                                _pending = asyncio.ensure_future(aiter.__anext__())
                            _done, _ = await asyncio.wait({_pending}, timeout=10.0)
                            if not _done:
                                yield f"data: {json.dumps({'type':'keepalive','src':'relay'})}\n\n"
                                continue  # same read stays pending — nothing lost
                            _task = _done.pop(); _pending = None
                            try:
                                line = _task.result()
                            except StopAsyncIteration:
                                break
                            if not line: continue
                            if line.startswith("data: "):
                                p = line[6:].strip()
                                if not p: continue
                                try: ev = json.loads(p)
                                except Exception:
                                    yield f"data: {p}\n\n"; continue
                                etype = ev.get("type", "")
                                # ── OX-WORKFLOW-1: drive the workflow lifecycle from the
                                # events the relay already proxies (no runtime change).
                                if _WF:
                                    try:
                                        if etype == "workflow_phase_start" and ev.get("phase"):
                                            _WF.set_phase(conv_id, ev["phase"])
                                        elif etype == "agent_start":
                                            _WF.set_phase(conv_id, "execute")
                                            if ev.get("run_id"):
                                                _WF.link(conv_id, agent_run_id=ev["run_id"])
                                        elif etype == "house_mind" and ev.get("state_id"):
                                            _WF.link(conv_id, house_state_id=ev["state_id"])
                                    except Exception: pass
                                # remember the mission's House-Mind state so we can
                                # CLOSE it when the mission ends — else it lingers as
                                # 'active' forever and every later brief input
                                # "Resuming '<old mission>'…" (the stale-state bug).
                                if etype == "house_mind" and ev.get("state_id"):
                                    _mission_state_id = ev["state_id"]
                                # NOTE: runtime events are published to the House bus at the
                                # SOURCE (main.py via house_sync.publish). The relay no longer
                                # re-publishes them — see commit "publish at the SOURCE".
                                # ── text-accumulation + CBP handling ──
                                if etype == "text" and ev.get("text"):
                                    text_accum.append(ev["text"])
                                    if _CBP: _cbp(_CT.TEXT_DELTA, {"text": ev["text"][:300]}, conv_id=conv_id)
                                elif etype == "agent_think" and ev.get("text") and not ev.get("is_think"):
                                    # agent mode streams visible text as agent_think(is_think=False)
                                    text_accum.append(ev["text"])
                                elif etype == "agent_complete":
                                    _s = (ev.get("summary") or "").strip()
                                    if _s: text_accum.append(("\n\n" if text_accum else "") + _s)
                                elif etype == "agent_tool_call":
                                    tool_count += 1
                                    if _CBP:
                                        _ah = hashlib.sha256(str(ev.get("args", "")).encode()).hexdigest()[:8]
                                        _cbp(_CT.TOOL_CALL, {"name": ev.get("name", "tool"), "args_hash": _ah}, conv_id=conv_id)
                                elif etype == "__tool_calls__":
                                    tool_count += len(ev.get("calls", []))
                                    if _CBP:
                                        for _c in ev.get("calls", []):
                                            _name = (_c.get("function", {}) or {}).get("name") or _c.get("name", "tool")
                                            _args = (_c.get("function", {}) or {}).get("arguments", "")
                                            _ah = hashlib.sha256(str(_args).encode()).hexdigest()[:8]
                                            _cbp(_CT.TOOL_CALL, {"name": _name, "args_hash": _ah}, conv_id=conv_id)
                                elif etype == "phase":
                                    if _CBP: _cbp(_CT.PHASE, {"phase": ev.get("phase", "")}, conv_id=conv_id)
                                elif etype in ("reflect", "reflection"):
                                    if _CBP: _cbp(_CT.VERDICT, {"verdict": ev.get("verdict", "CONSISTENT")}, conv_id=conv_id)
                                yield f"data: {p}\n\n"

                full_response = "".join(text_accum).strip() or "(no text response)"
                mirror_response_to_chat(conv_id, full_response, tool_count)
                rh = hashlib.sha256(full_response.encode("utf-8")).hexdigest()[:16]
                audit_log(req.operator or "ELMATADORZ", conv_id, req.directive, rh, operative_routed, tool_count)
                if _CBP: _cbp(_CT.COMPLETE, {"response_hash": rh, "tools": tool_count}, conv_id=conv_id)
                # OX-WORKFLOW-1: stream ended cleanly. "completed" if it produced a
                # real result; "failed" if the workflow yielded nothing (no-output).
                if _WF:
                    try:
                        if full_response == "(no text response)":
                            _WF.complete_if_open(conv_id, "failed", "no output produced")
                        else:
                            _WF.complete(conv_id, "completed", "")
                    except Exception: pass
                # the relay already judged the outcome for the workflow record —
                # the SAME judgement must reach the UI (chat/lookup modes have no
                # agent_complete, so without this every clean close rendered as
                # "channel closed — NO completion event")
                _outcome = "no_output" if full_response == "(no text response)" else "completed"
                # CLOSE the mission's House-Mind state so it stops being 'active'
                # and can never be silently resumed by a later brief input.
                if _mission_state_id:
                    try:
                        import house_state as _hs
                        _hs.close_state(_mission_state_id, summary=full_response[:200])
                    except Exception as _cse:
                        print(f"[Continental] house_state close skipped: {_cse}")
                yield f"data: {json.dumps({'type':'continental_close','conv_id':conv_id,'response_hash':rh,'tools':tool_count,'outcome':_outcome})}\n\n"
            except Exception as e:
                if _CBP: _cbp(_CT.ERROR, {"message": str(e)}, conv_id=conv_id)
                if _WF:
                    try: _WF.complete_if_open(conv_id, "failed", str(e)[:200])
                    except Exception: pass
                yield f"data: {json.dumps({'type':'continental_error','error':str(e)})}\n\n"
            finally:
                # OX-WORKFLOW-1 GUARANTEE: any path that left the workflow non-terminal
                # (client disconnect, GeneratorExit, cancellation) is closed here.
                if _WF:
                    try: _WF.complete_if_open(conv_id, "interrupted", "stream ended before terminal status")
                    except Exception: pass

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/continental/audit")
    def _audit(limit: int = 50):
        if not AUDIT.exists(): return {"ok": True, "entries": []}
        rows: List[Dict[str, Any]] = []
        with AUDIT.open("r", encoding="utf-8") as f:
            for line in f:
                try: rows.append(json.loads(line))
                except Exception: pass
        return {"ok": True, "count": len(rows), "entries": rows[-limit:]}

    @app.get("/api/continental/conversations")
    def _convs(limit: int = 30):
        _ensure_chat_db()
        with sqlite3.connect(CHATDB, check_same_thread=False) as c:
            rows = c.execute(
                "SELECT id, started_at, last_at, directive_preview, operative_routed, tools_invoked, status "
                "FROM continental_conversations ORDER BY last_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return {"ok": True, "conversations": [
            {"id": r[0], "started_at": r[1], "last_at": r[2],
             "directive": r[3], "operative": r[4], "tools": r[5], "status": r[6]}
            for r in rows
        ]}

    @app.post("/api/continental/reset")
    def _reset():
        """Clear stale House-Mind state on demand — closes every 'active' mission
        so the theatre starts fresh (fixes 'it doesn't clear old data'). The
        durable archive/ledger is untouched; only the live open states close."""
        closed = 0
        try:
            import house_state as _hs
            for _ in range(100):
                cur = _hs.current()
                if not cur or not cur.get("id"):
                    break
                _hs.close_state(cur["id"], summary="reset by operator")
                closed += 1
        except Exception as e:
            return {"ok": False, "error": str(e)[:200], "closed": closed}
        return {"ok": True, "closed": closed, "message": "House Mind cleared — fresh start"}

    print("[ContinentalRelay] mounted at /api/continental/* (dispatch + audit + conversations + reset)")
