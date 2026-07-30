"""SkynetClaw Backend v5  —  http://localhost:8765"""
from fastapi import FastAPI, HTTPException, Request, WebSocket, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json, httpx, os, subprocess, sys, time, sqlite3, hashlib, math
import tempfile, uuid, re, shutil, asyncio, contextvars
from pathlib import Path

# ── UTF-8-safe stdout/stderr ── On Windows, stdout defaults to cp1252 (esp. when
# redirected to a file), so any print() containing a non-latin1 glyph (→, ✓, Thai)
# raises UnicodeEncodeError. Several module-load blocks print such glyphs INSIDE
# their import try/except, so a logging failure would flip their availability flag
# to False and silently disable the subsystem (observed: the 4-phase workflow /
# council mode returning 500 "not loaded"). Make console output lossless so a
# print can never disable a feature.
for _stream in (sys.stdout, sys.stderr):
    try: _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
from skynetclaw_router import register_router, resolve_model

# ── Path security & active workspace — extracted to path_security.py (God-Object
# decomposition, strangler-fig slice 1). Re-exported here so every call site is
# unchanged (main.ACTIVE_WORKSPACE / main._resolve_path / main._path_is_sensitive). ─
from path_security import (  # noqa: E402
    ACTIVE_WORKSPACE, _SENSITIVE_PATH_PATTERNS, _path_is_sensitive, _resolve_path,
)

def _truncate_tool_result(name: str, result: str, max_chars: int = 4000) -> str:
    """
    Auto-truncate large tool outputs before injecting back into the LLM context.

    Why this exists: when a tool returns 130KB of raw file content (e.g. read_file
    on SELF.md, or search_obsidian dumping multiple notes), the model context
    overflows and the agent ends up echoing raw JSON in its reply instead of
    summarizing. This keeps the context lean.

    For text under max_chars → return unchanged.
    For text over max_chars → keep head + tail + a structured summary note.
    """
    if not result:
        return result or ""
    n = len(result)
    if n <= max_chars:
        return result
    head_chars = int(max_chars * 0.55)
    tail_chars = int(max_chars * 0.20)
    head = result[:head_chars]
    tail = result[-tail_chars:] if tail_chars > 0 else ""
    # Count meaningful structure markers to give the model context
    line_count = result.count("\n")
    return (
        f"[⚠ TOOL RESULT TRUNCATED — original {n:,} chars, ~{line_count:,} lines]\n"
        f"[Tool: {name} · showing first {head_chars:,} + last {tail_chars:,} chars]\n"
        f"[INSTRUCTION: SUMMARIZE the key facts in markdown — do NOT echo this raw blob in your reply.]\n"
        f"─── HEAD ───\n"
        f"{head}\n"
        f"─── ... [{n - head_chars - tail_chars:,} chars omitted] ...\n"
        f"─── TAIL ───\n"
        f"{tail}\n"
        f"─── END ───"
    )


# (sensitive-path deny-list + _path_is_sensitive + _resolve_path now live in
#  path_security.py — imported above.)


# ── CONTEXT FIT (borrowed from Claude Code: never send an over-budget request) ─
# The recurring crash was an over-budget request to the 16k model → Adapter
# ReadError → the whole mission FAILED. Retrying re-sent the SAME over-budget
# payload, so it failed again. Fix: before every model call, guarantee the
# assembled messages fit the window with headroom for the reply — trim oldest
# tool results / drop the middle rather than overflow. Deterministic, model-free.
# Context budget now lives in the Cognitive Kernel Context service (SPEC §3,
# migration step 3a). main delegates so every call site is unchanged; the kernel
# owns the 16k ceiling. Strangler-fig: kernel_context is the single source of truth.
import kernel_context as _kctx


def _est_tokens(messages, tools=None) -> int:
    return _kctx.estimate(messages, tools)


def _fit_context(messages, window: int, tools=None, aggressive: bool = False):
    return _kctx.fit(messages, window, tools, aggressive)


# ── ALWAYS-VERIFY COMPLETION (Claude Code borrow: check the observable result) ─
# SkynetClaw only verified TASK_COMPLETE when a DONE_WHEN was pre-declared; most
# tasks have none, so a self-asserted "done" was accepted blind. Derive a
# verifiable criterion from the task itself (any output file it names) so
# completion is ALWAYS checked against reality.
_OUTPUT_FILE_RE = re.compile(
    r"\b([\w\-]{2,}\.(?:md|txt|py|js|ts|tsx|json|html|css|csv|ya?ml|sh|xlsx|docx|pdf|sql|toml|ini))\b",
    re.I)


def _baseline_done_when(task: str) -> str:
    """A verifiable DONE_WHEN derived from the task when none was declared —
    names the output file(s) the task asks for, so completion_evidence can
    check they actually exist."""
    names = list(dict.fromkeys(_OUTPUT_FILE_RE.findall(task or "")))
    return ("output file(s) exist: " + ", ".join(names)) if names else ""


# ── Vault self-knowledge — extracted to vault_awareness.py (God-Object
# decomposition, slice 3). Re-exported so main._vault_root / main._vault_awareness_banner
# are unchanged (used by agent_run, chat, eval_suite, and path_security). ─
from vault_awareness import _vault_root, _vault_awareness_banner  # noqa: E402,F401


def _default_workspace() -> str:
    """Per-user sandbox used when confine_workspace safe-mode is on but no
    workspace is chosen. Created lazily."""
    d = Path.home() / "SkynetClaw" / "workspace"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return str(d)

_client: httpx.AsyncClient = None

# ── Telegram Bot State ────────────────────────────────────────────────────────
_tg_tasks: dict = {}          # bot_token -> asyncio.Task
_tg_sessions: dict = {}       # chat_id   -> [messages]  (in-memory history)
_tg_status: dict = {}         # bot_token -> {running, bot_name, errors, msg_count}

@asynccontextmanager
async def lifespan(app):
    global _client
    _client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=180.0, write=10.0, pool=5.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    # Auto-start Telegram bots that were previously running
    asyncio.create_task(_autostart_telegram_bots())
    # OPENCLAW PORT T2: run boot hooks (backend/hooks/*.py) — best-effort
    try:
        _ctx = {
            "db_path": str(Path(__file__).parent / "skynerclaw.db"),
            "settings_path": str(Path(__file__).parent / "settings.json"),
            "started_at": time.time(),
        }
        _hook_results = _ocp_boot_hooks(app, _ctx)
        for _name, _status in _hook_results:
            print(f"[boot.hook] {_name}: {_status}")
    except Exception as _e:
        print(f"[boot.hooks] failed: {_e}")
    # OX-STABILITY-1 STARTUP RECONCILIATION — no run may stay 'running' after a
    # process restart, and no open state may live forever. Flip orphaned runs to
    # 'interrupted' and age out stale open states so the active count is truthful
    # and learning never reads abandoned state.
    try:
        _n = _AGENT_RUNS_DB.reconcile_stale_runs(max_age_seconds=1800.0)
        print(f"[startup.reconcile] orphaned runs reconciled: {_n}")
    except Exception as _re:
        print(f"[startup.reconcile] run reconcile failed: {_re}")
    try:
        import house_state as _hs_boot
        _na = _hs_boot.archive_stale(max_age_seconds=7 * 86400.0)
        print(f"[startup.reconcile] stale open states archived: {_na}")
    except Exception as _ae:
        print(f"[startup.reconcile] state archive failed: {_ae}")
    # OX-WORKFLOW-1: recover orphaned workflow_runs (stale active → interrupted)
    try:
        import workflow_runs as _wf_boot
        _nw = _wf_boot.WorkflowRunsDB().reconcile_stale(max_age_seconds=1800.0)
        print(f"[startup.reconcile] orphaned workflows reconciled: {_nw}")
    except Exception as _we:
        print(f"[startup.reconcile] workflow reconcile failed: {_we}")
    yield
    # Stop all Telegram polling tasks on shutdown
    for task in list(_tg_tasks.values()):
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
    await _client.aclose()

async def _autostart_telegram_bots():
    """Auto-start all Telegram integrations with tg_auto_start=1 on server boot."""
    await asyncio.sleep(2)  # Wait for server to be fully ready
    try:
        conn2 = sqlite3.connect(DB_PATH); c2 = conn2.cursor()
        c2.execute("SELECT id, credentials FROM integrations WHERE service='telegram' AND tg_auto_start=1 AND enabled=1")
        rows = c2.fetchall(); conn2.close()
        for iid, creds_raw in rows:
            try:
                creds = json.loads(creds_raw)
                token = creds.get("bot_token","")
                if not token: continue
                # Verify token
                async with httpx.AsyncClient(timeout=10) as c3:
                    r = await c3.get(f"https://api.telegram.org/bot{token}/getMe")
                d = r.json()
                if not d.get("ok"): continue
                bot_name = d["result"].get("username","bot")
                task = asyncio.create_task(tg_polling_loop(token, bot_name))
                _tg_tasks[token] = task
                print(f"[TelegramBot] Auto-started @{bot_name}")
            except Exception as e:
                print(f"[TelegramBot] Auto-start failed for {iid}: {e}")
    except Exception as e:
        print(f"[TelegramBot] Auto-start init error: {e}")

app = FastAPI(title="SkynetClaw", version="5.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── SEC C1/C2: drive-by / CSRF guard ─────────────────────────────────────────
# The SPA is opened from file:// (Origin: null) or localhost, so we allow those
# but reject requests carrying a real foreign website Origin (e.g. https://evil.com).
# This stops a malicious page the user visits from POSTing to 127.0.0.1:8766 or
# reading /api/connections cross-origin. Combined with the 127.0.0.1 bind (see
# __main__), this removes the network + drive-by attack surface without breaking
# the local file:// SPA.
@app.middleware("http")
async def _csrf_origin_guard(request, call_next):
    origin = request.headers.get("origin")
    if origin and origin.lower() != "null":
        try:
            from urllib.parse import urlparse
            host = (urlparse(origin).hostname or "").lower()
        except Exception:
            host = ""
        if host not in ("localhost", "127.0.0.1", "::1", ""):
            from starlette.responses import JSONResponse
            return JSONResponse({"detail": "cross-origin request blocked"}, status_code=403)
    return await call_next(request)

# === SKILLS AUTO-ROUTER ENDPOINTS ===
try:
    import skill_router_endpoints
    skill_router_endpoints.mount(app)
    # RFC-0001 Observatory — the learning loop's single observation surface
    import learning_loop_endpoints
    learning_loop_endpoints.mount(app)
    print("[SkillsRouter] endpoints mounted at /api/skills/*")
except Exception as _sre_e:
    print(f"[SkillsRouter] endpoints mount failed: {_sre_e}")

# === HOUSE SYNC — Unified State Layer (shared state across all UI surfaces) ===
try:
    import house_sync
    house_sync.mount(app)
except Exception as _hs_e:
    print(f"[HouseSync] mount failed: {_hs_e}")

# === PORTRAITS — static assets for THE CONTINENTAL DIVISION agent cards ===
_PORTRAITS_DIR = Path(__file__).resolve().parent.parent / "portraits"
if _PORTRAITS_DIR.is_dir():
    app.mount("/portraits", StaticFiles(directory=str(_PORTRAITS_DIR)), name="portraits")
    print(f"[Portraits] serving {_PORTRAITS_DIR} at /portraits")
else:
    print("[Portraits] directory not found — agent portraits will not load")

# === CONTINENTAL RELAY (Continental UI ↔ SkynetClaw chat audit bridge) ===
try:
    import continental_relay
    continental_relay.mount(app, base_url="http://127.0.0.1:8766")
    print("[ContinentalRelay] mounted at /api/continental/*")
except Exception as _cr_e:
    print(f"[ContinentalRelay] mount failed: {_cr_e}")

# === HEALTH CHECK ENDPOINT (every subsystem · /api/system/health) ===
try:
    import health_check
    health_check.mount(app)
except Exception as _hc_e:
    print(f"[Health] mount failed: {_hc_e}")

# === ECOSYSTEM MANIFEST (single source of truth — kills filesystem-search confusion) ===
# Auto-generates SELF.md describing ALL apps/operatives/subsystems/endpoints
# so SkynetClaw chat KNOWS THE_CONTINENTAL_DIVISION.html is its sister UI
# without searching the filesystem.
try:
    import ecosystem_manifest
    ecosystem_manifest.mount(app)
except Exception as _em_e:
    print(f"[Ecosystem] mount failed: {_em_e}")

# === CBP BRIDGE PROTOCOL + FEEDBACK ENGINE ===
try:
    import bridge_protocol
    bridge_protocol.mount(app)
except Exception as _bp_e:
    print(f"[BridgeProtocol] mount failed: {_bp_e}")
try:
    import feedback_engine
    feedback_engine.mount(app)
except Exception as _fe_e:
    print(f"[FeedbackEngine] mount failed: {_fe_e}")

# === BRIDGE CONSOLE PAGE ===
try:
    from fastapi.responses import FileResponse as _FRb
    from pathlib import Path as _Pb
    _PROJ_ROOT_B = _Pb(__file__).resolve().parent.parent
    @app.get("/bridge")
    @app.get("/bridge-console")
    @app.get("/bridge.html")
    def _bridge_console():
        f = _PROJ_ROOT_B / "bridge_console.html"
        if not f.exists():
            return {"error": f"bridge_console.html not found at {f}"}
        return _FRb(str(f), media_type="text/html")
    print("[BridgeConsole] mounted at http://localhost:8766/bridge")
except Exception as _bc_e:
    print(f"[BridgeConsole] mount failed: {_bc_e}")

# === OBSIDIAN TOOLS (assigned to THE SCOUT) ===
try:
    from obsidian_tools import OBSIDIAN_TOOL_DEFS, dispatch_obsidian, get_vault
    _OBSIDIAN_AVAILABLE = True
    _v = get_vault()
    print(f"[Obsidian] vault = {_v if _v else '(not configured — set obsidian_vault in settings.json)'}")
    print(f"[Obsidian] {len(OBSIDIAN_TOOL_DEFS)} tools registered for THE SCOUT")
except Exception as _ob_e:
    print(f"[Obsidian] tools unavailable: {_ob_e}")
    OBSIDIAN_TOOL_DEFS = []
    _OBSIDIAN_AVAILABLE = False
    def dispatch_obsidian(name, args): return {"ok": False, "error": "obsidian module not loaded"}

# === DIVISION X AGENT ROOM ===
try:
    from fastapi.responses import FileResponse as _FR
    from pathlib import Path as _PathX
    _PROJ_ROOT = _PathX(__file__).resolve().parent.parent

    @app.get("/agent-room")
    @app.get("/agent_room")
    @app.get("/agent-room.html")
    @app.get("/THE_CONTINENTAL_DIVISION.html")
    @app.get("/continental")
    @app.get("/division")
    def _agent_room():
        # try every known naming variant — user may rename freely
        candidates = [
            "THE CONTINENTAL DIVISION.html",   # with spaces (current)
            "THE_CONTINENTAL_DIVISION.html",   # with underscores
            "agent_room.html",                 # legacy
            "the_continental_division.html",   # lowercase
        ]
        for fname in candidates:
            f = _PROJ_ROOT / fname
            if f.exists():
                # no-cache: a stale cached UI kept showing bugs that were already
                # fixed on disk (the operator saw the old close-event handling)
                return _FR(str(f), media_type="text/html",
                           headers={"Cache-Control": "no-cache, must-revalidate"})
        return {"error": f"Continental UI not found · tried: {candidates}"}

    print("[AgentRoom] mounted at http://localhost:8766/agent-room")

    # Serve the main UI at the root so the operator opens http://localhost:8766
    # instead of finding index.html on disk. no-cache so UI edits always land —
    # closes the "had to Ctrl+Shift+R to see the fix" problem for good.
    @app.get("/")
    @app.get("/index.html")
    def _home():
        f = _PROJ_ROOT / "index.html"
        if f.exists():
            return _FR(str(f), media_type="text/html",
                       headers={"Cache-Control": "no-cache, must-revalidate"})
        return {"error": "index.html not found"}

    @app.get("/logo.svg")
    def _logo():
        f = _PROJ_ROOT / "logo.svg"
        return _FR(str(f), media_type="image/svg+xml") if f.exists() else {"error": "no logo"}

    print("[UI] SkynetClaw served at http://localhost:8766/")
except Exception as _ar_e:
    print(f"[AgentRoom] mount failed: {_ar_e}")

# === THAI CHESS (MAKRUK) — logic testbed ===
try:
    import makruk_api
    makruk_api.mount(app)
except Exception as _mk_e:
    print(f"[Makruk] mount failed: {_mk_e}")

# === MASTERPIECE WIRE-UP — START ===
try:
    from skynet_genesis_masterpiece import register_masterpiece
    from skynetclaw_router import register_router, resolve_model as _mp_resolve_model
    from skynetclaw_meta import (
        shadow_gate as _mp_shadow_gate,
        current_datetime_banner as _mp_datetime_banner,
        live_data_directive as _mp_live_data_directive,
    )
    _MASTERPIECE_AVAILABLE = True
except Exception as _e:
    print(f"[Masterpiece] modules not loaded: {_e}")
    _MASTERPIECE_AVAILABLE = False
    def _mp_resolve_model(model, text=""): return model or ""
    def _mp_shadow_gate(*a, **k):
        class _V: action = "PROCEED"; verdict = "CONSISTENT"; reason = ""
        return _V()
    def _mp_datetime_banner(tz="Asia/Bangkok"): return ""
    def _mp_live_data_directive(): return ""

# OPENCLAW PORT (Tier 1 #2-5): trajectory + diary + workspace-git + approvals
try:
    from openclaw_port import (
        write_daily_diary as _ocp_diary,
        TrajectoryWriter as _OCPTrajectory,
        workspace_git_commit as _ocp_git,
        ExecApprovals as _OCPApprovals,
    )
    _OPENCLAW_PORT = True
    print("[OpenClawPort] trajectory + diary + workspace-git + approvals loaded")
except Exception as _e:
    print(f"[OpenClawPort] not loaded: {_e}")
    _OPENCLAW_PORT = False
    def _ocp_diary(**kw): return None
    def _ocp_git(workspace_path, message, **kw): return {"ok": False, "action": "disabled"}
    class _OCPTrajectory:
        def __init__(self, *a, **k): self.path = None
        def step_begin(self, *a, **k): pass
        def plan_captured(self, *a, **k): pass
        def tool_call(self, *a, **k): pass
        def tool_result(self, *a, **k): pass
        def gate_block(self, *a, **k): pass
        def user_ask(self, *a, **k): pass
        def complete(self, *a, **k): pass
        def close(self): pass
    class _OCPApprovals:
        def __init__(self, *a, **k): pass
        def check(self, *a, **k): return None
        def record(self, *a, **k): return {}

# OPENCLAW PORT TIER 2 (#6-9): settings backup chain + agent runs DB + cost + boot hooks
try:
    from openclaw_port_tier2 import (
        SettingsBackupChain as _OCPBackupChain,
        AgentRunsDB as _OCPAgentRunsDB,
        ModelCostOverlay as _OCPModelCost,
    )
    _OPENCLAW_T2 = True
    print("[OpenClawPort.T2] backup chain + agent runs DB + model cost loaded")
except Exception as _e:
    print(f"[OpenClawPort.T2] not loaded: {_e}")
    _OPENCLAW_T2 = False
    class _OCPBackupChain:
        def __init__(self, p): self.path = p
        def safe_save(self, data): self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"); return True
        def safe_load(self, default=None):
            try: return json.loads(self.path.read_text(encoding="utf-8"))
            except: return dict(default or {})
    class _OCPAgentRunsDB:
        def __init__(self, *a, **k): pass
        def start_run(self, *a, **k): return False
        def end_run(self, *a, **k): return False
        def recent(self, **k): return []
        def get(self, *a): return None
        def stats(self, **k): return {"by_status": {}}
    class _OCPModelCost:
        def __init__(self, *a, **k): pass
        def cost(self, m): return {"input": 0.0, "output": 0.0, "local": True}
        def cheapest(self, cands, **k): return cands[0] if cands else None
        def list_all(self): return {}

try:
    from hooks import run_boot_hooks as _ocp_boot_hooks
    _OPENCLAW_BOOT = True
except Exception as _e:
    print(f"[OpenClawPort.Boot] hooks not available: {_e}")
    _OPENCLAW_BOOT = False
    def _ocp_boot_hooks(app, ctx=None): return []

# OPENCLAW PORT: Volition Engine (programmatic L1 extraction)
try:
    from volition_engine import extract as _vol_extract, format_volition_directive as _vol_directive
    _VOLITION_AVAILABLE = True
    print("[VolitionEngine] L1 drive/tone/urgency extractor loaded")
except Exception as _e:
    print(f"[VolitionEngine] not loaded: {_e}")
    _VOLITION_AVAILABLE = False
    def _vol_extract(text):
        class _V:
            surface=text; drive="explore"; emotional_tone="neutral"
            urgency="medium"; gap_detected=False; gap_note=""; recommendation=""
            drive_score={}; tone_score={}
            def to_dict(self): return {"drive":"explore","tone":"neutral","urgency":"medium","gap":False}
        return _V()
    def _vol_directive(v): return ""

# UNIVERSAL LLM ADAPTER — cloud providers via OpenAI-compatible dialect
try:
    from llm_adapter import (
        stream_openai_chat as _ad_stream_openai,
        list_openai_models as _ad_list_models,
        is_cloud as _ad_is_cloud,
        fallback_models as _ad_fallback_models,
        PROVIDER_PRESETS as _AD_PRESETS,
    )
    _LLM_ADAPTER = True
    print("[LLMAdapter] universal cloud adapter loaded (OpenAI/Anthropic/Gemini/Groq/OpenRouter/DeepSeek/xAI/Mistral/Together/custom)")
except Exception as _e:
    print(f"[LLMAdapter] not loaded — local Ollama only: {_e}")
    _LLM_ADAPTER = False
    def _ad_is_cloud(t): return False
    def _ad_fallback_models(t): return []
    _AD_PRESETS = {}

def _llm_stream(payload: dict, base_url: str, api_key: str = "", api_type: str = None):
    """Single dispatch point: route by api_type. When api_type is given (e.g. the
    EXECUTION runtime's connection), route by it; otherwise fall back to the ACTIVE
    connection's api_type. Event contract is identical either way, so every
    consumer works unchanged."""
    try:
        _at = api_type if api_type is not None else get_active_conn().get("api_type")
        if _LLM_ADAPTER and _ad_is_cloud(_at):
            return _ad_stream_openai(payload, base_url, api_key)
    except Exception as _re:
        print(f"[LLMAdapter] route check failed → ollama: {_re}")
    return stream_ollama_chat(payload, base_url, api_key)


def _kernel_enabled() -> bool:
    """OX-KERNEL-ACTIVATION-1 feature flag. Default False → legacy path is byte-for-
    byte unchanged. True → the EXECUTION path routes through the Runtime Kernel."""
    try:
        return bool(load_settings().get("runtime_kernel_enabled", False))
    except Exception:
        return False


async def _kernel_exec_stream(messages, tools=None, options=None):
    """Activation bridge: the EXECUTION path via the Runtime Kernel, emitting the
    SAME event contract as _llm_stream (__tool_calls__/text/done/error). The agent
    never learns runtime/model/endpoint/api/provider — the kernel negotiates by
    capability. The kernel's blocking driver runs in a worker thread so the async
    event loop stays free; the agent's own 8s keepalive covers quiet periods."""
    import asyncio, threading
    import runtime_kernel as _rk, runtime_metrics as _rm
    loop = asyncio.get_event_loop()
    out: asyncio.Queue = asyncio.Queue()

    def _pump():
        try:
            k = _rk.get_kernel(extra_probes=_runtime_extra_probes(), rediscover=True)
            for ev in k.infer(required={"role": "Execution", "tool_calling": bool(tools)},
                              messages=messages, tools=tools, stream=True,
                              options=options or {"temperature": 0.1},
                              metrics=_rm.load_metrics()):
                loop.call_soon_threadsafe(out.put_nowait, ev)
        except Exception as e:
            loop.call_soon_threadsafe(out.put_nowait,
                                      json.dumps({"type": "error", "msg": f"kernel: {str(e)[:160]}"}))
        finally:
            loop.call_soon_threadsafe(out.put_nowait, None)

    threading.Thread(target=_pump, daemon=True).start()
    while True:
        ev = await out.get()
        if ev is None:
            break
        yield ev

# GENESIS GOVERNANCE OS — GPS-2 permission gate (deny-by-default) + GOS-0 declarations
try:
    from governance import GPS2Gate as _GovGate, mount_governance as _gov_mount
    _GOV = _GovGate()
    _gov_mount(app, _GOV)
    print("[Governance] GPS-2 gate armed — deny-by-default · human gate on irreversible tools")
except Exception as _e:
    print(f"[Governance] not loaded (gate OFF): {_e}")
    _GOV = None

# COGNITIVE KERNEL step 5 — the act boundary becomes the PRE_ACT policy hook.
# main INJECTS the concrete gates (GPS-2, shadow) into the kernel; the kernel never
# imports main. Per-run state (approvals, run allow-list) rides on the act ctx.
# The kernel is now the single authority at the act boundary and is FAIL-CLOSED.
try:
    import kernel_policy as _kpol
    import kernel_execution as _kexec
    _kpol.install_act_policies(gate=_GOV, shadow=_mp_shadow_gate)
    # Report policies under the hook each one actually runs on. Printing the flat
    # list under "PRE_ACT" claimed the fabrication and warrant guards fire before
    # the action; they fire before the commit. The boot log is read as the
    # authority on where the gates are, so it has to be the truth.
    for _hook, _ids in _kpol.registered_by_hook().items():
        print(f"[Kernel] {_hook} armed — {', '.join(_ids)}")
except Exception as _ke_e:
    _kexec = None
    print(f"[Kernel] policy hooks NOT armed ({_ke_e}) — legacy gate chain still applies")


# COGNITIVE KERNEL — authenticated operator role (the SAFE alternative to a backdoor).
# Elevation only ever downgrades ESCALATE (the human gate) to an AUDITED allow; DENY
# and deny-by-default are untouched, and every attempt is on the audit spine.
@app.get("/api/operator/status")
async def api_operator_status(request: Request):
    """Read-only: is an operator token configured, and is THIS caller elevated?
    Never reveals the token. Elevation is checked from the X-Operator-Token header."""
    try:
        import kernel_operator as _kop
        tok = request.headers.get("X-Operator-Token")
        return {"ok": True, "configured": _kop.is_configured(),
                "elevated": _kop.verify(tok) if tok else False}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/operator/setup")
async def api_operator_setup(request: Request, force: bool = False):
    """Generate the operator token ONCE (shown a single time). LOCALHOST-ONLY — a
    remotely reachable token generator would itself be a weakness. Rotating needs
    force=true."""
    try:
        from starlette.responses import JSONResponse
        host = (request.client.host if request and request.client else "")
        if host not in ("127.0.0.1", "::1", "localhost"):
            return JSONResponse({"ok": False, "error": "operator setup is localhost-only"}, status_code=403)
        import kernel_operator as _kop
        r = _kop.setup(force=force)
        try:
            import kernel_events as _ke
            _ke.emit("auth.setup", {"rotated": bool(force), "ok": r.get("ok")}, source="operator",
                     severity="warn")
        except Exception:
            pass
        return r
    except Exception as e:
        return {"ok": False, "error": str(e)}

# METACOGNITION + SELF-DEBUG + FIRST PRINCIPLE CODEX (the meta layer)
try:
    import metacognition as _meta_cog
    import self_debug    as _self_dbg
    import skynetclaw_codex as _fp_codex
    _META_LAYER = True
    print("[MetaLayer] metacognition + self_debug + codex loaded")
except Exception as _e:
    print(f"[MetaLayer] not loaded: {_e}")
    _META_LAYER = False
    _meta_cog = None; _self_dbg = None; _fp_codex = None

# AGENTIC WORKFLOW (4-phase comprehension-first orchestrator)
try:
    import agentic_workflow as _workflow
    _WORKFLOW_AVAILABLE = True
    print("[Workflow] 4-phase comprehend→plan→execute→reflect loaded")
except Exception as _e:
    print(f"[Workflow] not loaded: {_e}")
    _WORKFLOW_AVAILABLE = False
    _workflow = None

# AGENT COUNCIL (Skynet blueprint L5 — six specialists)
try:
    import agent_council as _council
    _COUNCIL_AVAILABLE = True
    print("[Council] L5 six specialists loaded (Analyst/Strategist/Skeptic/Forecaster/Executor/Storyteller)")
except Exception as _e:
    print(f"[Council] not loaded: {_e}")
    _COUNCIL_AVAILABLE = False
    _council = None

# COMPOUND MIND (Skynet blueprint L3 + L6 — compound decomposition / cosmic plan)  [wired into agent_run]
# Wires the protocol into the LIVE agent_run loop: a prompt is tokenized and split
# into dependency-tracked work groups up front, replacing linear 1-2-3 stepping.
try:
    import compound_mind as _compound
    _COMPOUND_AVAILABLE = True
    print("[CompoundMind] L3 decomposition + L6 cosmic loaded (compound, not linear)")
except Exception as _e:
    print(f"[CompoundMind] not loaded: {_e}")
    _COMPOUND_AVAILABLE = False
    _compound = None

if _MASTERPIECE_AVAILABLE:
    try:
        register_router(app)
        register_masterpiece(app)
        print("[Masterpiece] /api/router/* and /api/masterpiece/* endpoints registered")
    except Exception as _e:
        print(f"[Masterpiece] register failed: {_e}")
# === MASTERPIECE WIRE-UP — END ===

# === INSTITUTIONAL MEMORY — THE HOUSE remembers, evaluates, improves ===
# Council Intelligence API (/api/council/*) + dashboard (/api/council/dashboard).
try:
    import council_intelligence_api as _council_intel
    _council_intel.register(app)
    import house_constitution as _house_constitution
    _CONSTITUTION_TEXT = _house_constitution.load_constitution()
    import deliberation_briefing as _deliberation_briefing
    import house_state as _house_state
    _INSTITUTIONAL_MEMORY = True
    print("[InstitutionalMemory] Council Intelligence API + Constitution + Briefing + House Mind loaded")
except Exception as _e:
    print(f"[InstitutionalMemory] not loaded: {_e}")
    _INSTITUTIONAL_MEMORY = False
    _CONSTITUTION_TEXT = ""
# === INSTITUTIONAL MEMORY — END ===

DB_PATH       = Path(__file__).parent / "skynerclaw.db"
SETTINGS_PATH = Path(__file__).parent / "settings.json"

# Where the local model runtime lives. "localhost" is right on a workstation and
# wrong inside a container, where the runtime is a sibling service — so the
# deployment gets to say. docker-compose sets OLLAMA_BASE_URL=http://ollama:11434.
OLLAMA_DEFAULT_URL = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")

# RELIABILITY: put the datastore in WAL once at startup (persistent property) so
# readers never block the writer under concurrency. Verified by chaos_test EXP-3/EXP-5.
try:
    import db_reliability as _db_rel
    _db_rel.ensure_wal(DB_PATH)
except Exception as _e:
    print(f"[db] WAL enable skipped: {_e}")

# OPENCLAW PORT T2 — singletons (created once per process)
_SETTINGS_CHAIN = _OCPBackupChain(SETTINGS_PATH)
_AGENT_RUNS_DB  = _OCPAgentRunsDB(DB_PATH)
_COST_OVERLAY   = _OCPModelCost()

# ── DB ───────────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS skills(
        id TEXT PRIMARY KEY, name TEXT, description TEXT,
        system_prompt TEXT, tools TEXT DEFAULT '[]', created_at REAL, updated_at REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS custom_tools(
        id TEXT PRIMARY KEY, name TEXT, description TEXT,
        code TEXT, schema_json TEXT, created_at REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS embeddings(
        id TEXT PRIMARY KEY, path TEXT, content TEXT,
        embedding TEXT, vault_path TEXT, updated_at REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS connections(
        id TEXT PRIMARY KEY, name TEXT, base_url TEXT,
        api_key TEXT DEFAULT '', api_type TEXT DEFAULT 'ollama',
        is_active INTEGER DEFAULT 0, created_at REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS integrations(
        id TEXT PRIMARY KEY, service TEXT, name TEXT,
        credentials TEXT, enabled INTEGER DEFAULT 1,
        tg_auto_start INTEGER DEFAULT 0, created_at REAL)""")
    # Migration: add tg_auto_start column if it doesn't exist yet
    try:
        c.execute("ALTER TABLE integrations ADD COLUMN tg_auto_start INTEGER DEFAULT 0")
    except Exception:
        pass
    # telegram_sessions must ALWAYS be created — independent of connections data
    c.execute("""CREATE TABLE IF NOT EXISTS telegram_sessions(
        chat_id TEXT PRIMARY KEY, bot_token TEXT, username TEXT,
        history TEXT DEFAULT '[]', created_at REAL, updated_at REAL)""")
    # Seed default local Ollama connection if no connections exist yet
    c.execute("SELECT COUNT(*) FROM connections")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO connections VALUES(?,?,?,?,?,?,?)",
                  ("local","Local Ollama",OLLAMA_DEFAULT_URL,"","ollama",1,time.time()))
    conn.commit(); conn.close()
init_db()

# ── Settings ─────────────────────────────────────────────────────────────────
_DEFAULT_SETTINGS = {"vault_path":"","default_model":"","obs_model":"","embed_model":"nomic-embed-text"}

def load_settings():
    # OPENCLAW PORT T2: backup chain auto-recovers from corruption
    try:
        return _SETTINGS_CHAIN.safe_load(default=_DEFAULT_SETTINGS)
    except Exception:
        if SETTINGS_PATH.exists():
            try: return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            except: pass
        return dict(_DEFAULT_SETTINGS)

def save_settings(data: dict):
    s = load_settings(); s.update(data)
    # OPENCLAW PORT T2: rotates .bak / .bak.1-3 / .last-good before write
    try:
        _SETTINGS_CHAIN.safe_save(s)
    except Exception:
        SETTINGS_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

def get_active_base_url():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT base_url FROM connections WHERE is_active=1 LIMIT 1")
    row = c.fetchone(); conn.close()
    return (row[0] if row else OLLAMA_DEFAULT_URL).rstrip("/")

def get_active_api_key():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT api_key FROM connections WHERE is_active=1 LIMIT 1")
    row = c.fetchone(); conn.close()
    return (row[0] if row else "") or ""

def get_active_conn():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT id,name,base_url,api_key,api_type FROM connections WHERE is_active=1 LIMIT 1")
    row = c.fetchone(); conn.close()
    if row: return {"id":row[0],"name":row[1],"base_url":row[2],"api_key":row[3],"api_type":row[4]}
    return {"id":"local","name":"Local","base_url":OLLAMA_DEFAULT_URL,"api_key":"","api_type":"ollama"}

def get_conn_by_name(name: str):
    """OX-EXECUTION-RECOVERY-FINAL: look up a connection row by id OR name (used to
    route the EXECUTION path to a dedicated runtime, e.g. the llama.cpp GPU server,
    independent of the globally-active reasoning/council connection)."""
    if not name:
        return None
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT id,name,base_url,api_key,api_type FROM connections WHERE id=? OR name=? LIMIT 1",
              (name, name))
    row = c.fetchone(); conn.close()
    if row:
        return {"id":row[0],"name":row[1],"base_url":row[2],"api_key":row[3],"api_type":row[4]}
    return None

def get_integration(service: str) -> dict:
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT credentials FROM integrations WHERE service=? AND enabled=1 LIMIT 1",(service,))
    row = c.fetchone(); conn.close()
    return json.loads(row[0]) if row else {}

# ── Pydantic Models ───────────────────────────────────────────────────────────
class ChatMsg(BaseModel):
    role: str; content: str

class ChatReq(BaseModel):
    model: str; messages: List[ChatMsg]
    system_prompt: Optional[str] = None; use_tools: bool = True
    workspace_folder: Optional[str] = None   # absolute path for relative-path resolution
    agent_mode: bool = False                  # only inject "execute next" directives in agent mode

class FileWriteReq(BaseModel):
    path: str; content: str

class ShellReq(BaseModel):
    command: str; cwd: Optional[str] = None

class CodeReq(BaseModel):
    code: str; language: str = "python"

class EmbedReq(BaseModel):
    vault_path: str; embed_model: str = "nomic-embed-text"

class ObsSearchReq(BaseModel):
    vault_path: str; query: str; top_k: int = 5; mode: str = "auto"

class ObsChatReq(BaseModel):
    model: str; vault_path: str
    messages: Optional[List[ChatMsg]] = None
    history: Optional[List[ChatMsg]] = None
    query: Optional[str] = None
    top_k: int = 5; stream: bool = True

class FolderCtxReq(BaseModel):
    path: str
    extensions: List[str] = [".md",".txt",".py",".js",".ts",".json",".csv",".yaml",".toml",".html",".css",".rs",".go",".java",".cpp",".c"]
    max_files: int = 60; max_chars_per_file: int = 3000; recursive: bool = False

class SkillReq(BaseModel):
    name: str; description: Optional[str] = ""
    system_prompt: str; tools: Optional[List[str]] = []
    triggers: Optional[List[str]] = []

class SkillInstallReq(BaseModel):
    repo_url: str                       # github.com/owner/repo  or  owner/repo
    skill: Optional[str] = None         # skill name within the repo
    ref: Optional[str] = None           # branch/tag (default: try main, master)
    confirm: bool = False               # False = review preview; True = install

class BigTaskReq(BaseModel):
    task: str
    model: Optional[str] = None
    workspace_folder: Optional[str] = None
    max_rounds: int = 5                 # hard cap on continuation rounds
    max_steps_per_round: Optional[int] = None

class ToolReq(BaseModel):
    # protected_namespaces=() silences Pydantic v2 warning about `schema_*` field
    # names. We keep the field as-is to preserve the SQL column name and frontend API.
    model_config = {"protected_namespaces": ()}
    name: str; description: str; code: str; schema_json: Optional[Dict] = {}

class SettingsReq(BaseModel):
    vault_path: Optional[str] = None; default_model: Optional[str] = None
    obs_model: Optional[str] = None; embed_model: Optional[str] = None
    model: Optional[str] = None; active_model: Optional[str] = None

class ConnReq(BaseModel):
    name: str; base_url: str; api_key: str = ""; api_type: str = "ollama"

class SnippetReq(BaseModel):
    code: str; language: str = "python"

class AgentRunReq(BaseModel):
    task: str
    max_steps: int = 25
    model: Optional[str] = None
    workspace_folder: Optional[str] = None   # absolute path agent should write into
    # SECURITY: when set, ONLY these tool names may be offered AND executed this
    # run. Enforced both in the schema (model can't see other tools) and at the
    # execution choke point (a hallucinated call to an unlisted tool is refused).
    # Used by the Telegram bot to grant a safe subset regardless of the global
    # SKYNET_ENABLE_EXEC setting.
    tool_allow: Optional[List[str]] = None
    # OX-H1 IDENTITY SEPARATION: the clean USER DIRECTIVE. When the workflow
    # self-calls with an assembled prompt in `task`, it passes the operator's
    # real request here so MISSION IDENTITY never stores the model prompt.
    directive: Optional[str] = ""

class IntegrationReq(BaseModel):
    service: str; name: str; credentials: Dict

class SaveMemoryReq(BaseModel):
    vault_path: str; content: str; title: str = ""

class PackageReq(BaseModel):
    package: str; manager: str = "pip"  # pip | npm | winget | choco | cargo

class DownloadReq(BaseModel):
    url: str; destination: str = ""

class HttpReq(BaseModel):
    url: str; method: str = "GET"
    headers: Optional[Dict] = None
    body: Optional[Any] = None
    params: Optional[Dict] = None

# ── TOOL CATEGORY MAP — extracted to tool_registry.py (God-Object decomposition,
# slice 2). Re-exported so main.TOOL_CATEGORY / main.get_tool_cat / main._PARALLEL_SAFE
# (used by main + eval_suite + system_graph) are unchanged. ──
from tool_registry import TOOL_CATEGORY, get_tool_cat, _PARALLEL_SAFE  # noqa: E402,F401

# ── BUILTIN TOOLS — the base schemas extracted to builtin_tools.py (God-Object
# decomposition, slice 4). Imported here, then extended in-place (obsidian) and
# rebound (stealth) below, so main.BUILTIN_TOOLS is unchanged for every reader. ─
from builtin_tools import BUILTIN_TOOLS  # noqa: E402

# ── EXTEND with OBSIDIAN tools assigned to THE SCOUT ──────────────────────────
try:
    BUILTIN_TOOLS.extend(OBSIDIAN_TOOL_DEFS)
    print(f"[BUILTIN_TOOLS] extended with {len(OBSIDIAN_TOOL_DEFS)} obsidian tools (total {len(BUILTIN_TOOLS)})")
except Exception as _ext_e:
    print(f"[BUILTIN_TOOLS] obsidian extension skipped: {_ext_e}")

# ── MISSION-SCOPED TOOLS ──────────────────────────────────────────────────────
# Prompt-eval dominates local-model latency: sending all ~44 tool schemas costs
# 30-80s of silent eval PER STEP on 9B models (measured TTFT p95 = 83s). Send the
# core set + groups the mission plausibly needs. Kill-switch: settings.full_toolset.
_TOOL_CORE = {
    "read_file", "read_document", "write_file", "edit_file", "list_files", "find_files",
    "grep_search", "file_info", "create_folder", "get_current_datetime",
    "ask_user_options", "calculator",
    # CSA: runtime skill discovery is ALWAYS available — novel tasks pull
    # their own playbook instead of hoping pre-injection guessed right.
    "find_skill", "use_skill",
}
_TOOL_GROUPS = [
    ({"web", "http", "ข่าว", "news", "ค้น", "search", "ราคา", "price", "ทอง", "gold",
      "crypto", "btc", "eth", "หุ้น", "stock", "forex", "ดอลลา", "usd", "thb", "อัตรา",
      "exchange", "วิจัย", "research", "ข้อมูล", "data", "excel", "csv", "สรุป", "summar",
      "บทความ", "article", "report", "รายงาน", "วิเคราะห์", "analy"},
     {"web_search", "http_request", "get_news", "build_news_report", "get_gold_price", "get_crypto_price",
      "get_forex_rate", "download_file"}),
    ({"code", "โค้ด", "python", "run", "รัน", "script", "โปรแกรม", "build", "เว็บ",
      "web app", "html", "css", "js", "server", "npm", "node", "install", "ติดตั้ง",
      "shell", "cmd", "dev", "แอป", "app", "test", "ทดสอบ", "fix", "แก้", "debug",
      "deploy", "สร้างระบบ", "excel", "xlsx", "csv"},
     {"shell_command", "run_python", "dev_server", "install_package"}),
    ({"obsidian", "vault", "note", "โน้ต", "บันทึก", "สมุด", "second brain", "ความรู้"},
     {"obsidian_list_notes", "obsidian_read_note", "obsidian_write_note", "obsidian_search",
      "search_obsidian", "read_obsidian_note", "write_obsidian_note"}),
    ({"ไฟล์", "โฟลเดอร์", "folder", "ย้าย", "move", "copy", "ลบ", "delete",
      "จัดระเบียบ", "organize", "rename", "clean"},
     {"move_file", "copy_file", "delete_file"}),
    ({"system", "ระบบ", "process", "cpu", "memory", "disk", "screenshot", "หน้าจอ",
      "clipboard", "เปิดเว็บ", "browser", "เปิด url"},
     {"get_system_info", "list_processes", "kill_process", "take_screenshot",
      "open_browser", "clipboard_read", "clipboard_write", "analyze_image"}),
    ({"image", "รูป", "ภาพ", "photo", "picture", "screenshot", "สกรีนช็อต", "diagram",
      "chart", "กราฟ", "ocr", "อ่านรูป", "ดูรูป", "ในภาพ", "แผนภาพ", "icon", "โลโก้", "logo"},
     {"analyze_image", "take_screenshot"}),
    ({"telegram", "discord", "line", "facebook", "โพสต์", "ส่งข้อความ", "แจ้งเตือน",
      "notify", "social", "post"},
     {"telegram_send", "discord_send", "line_notify", "facebook_post", "call_integration"}),
]

# ── STEALTH BROWSER (external, isolated) ─────────────────────────────────────
# An undetectable real-Chrome automation surface (Cloudflare/antibot-capable) is
# provided by a separate process in its own Python 3.13 venv, reached over a
# localhost REST shim. The heavy deps (nodriver/fastmcp/Chrome) never enter the
# House env; this only registers curated tool SCHEMAS + a keyword group so the
# agent can reach them when a page blocks normal fetching. Safe if the bridge
# module or the shim is absent (schemas simply won't be offered / will error).
try:
    import stealth_bridge as _stealth
    BUILTIN_TOOLS = BUILTIN_TOOLS + list(_stealth.TOOLS)
    _TOOL_GROUPS.append((
        {"cloudflare", "antibot", "anti-bot", "stealth", "scrape", "ขูด", "ขูดข้อมูล",
         "bypass", "captcha", "undetect", "บล็อก", "เว็บบล็อก", "โดนบล็อก", "real browser",
         "instagram", "linkedin", "twitter", "โซเชียล", "ดึงหน้าเว็บ", "หน้าเว็บที่บล็อก"},
        set(_stealth.TOOL_NAMES),
    ))
    print(f"[stealth] registered {len(_stealth.TOOLS)} browser tools (bridge: external :8781)")
except Exception as _se:
    print(f"[stealth] not registered ({_se}) — House unaffected")

def _select_tools_for_task(task: str) -> list:
    try:
        if load_settings().get("full_toolset"):
            return BUILTIN_TOOLS
    except Exception:
        pass
    t = (task or "").lower()
    wanted = set(_TOOL_CORE)
    for keys, tools in _TOOL_GROUPS:
        if any(k in t for k in keys):
            wanted |= tools
    sel = [td for td in BUILTIN_TOOLS if td.get("function", {}).get("name") in wanted]
    if len(sel) < 8:   # safety floor — something went wrong, ship everything
        return BUILTIN_TOOLS
    return sel

# ── MISSION LEDGER — Commander-signed status of work in a workspace ──────────
# Prevents redundant reruns: every AGENT_RUN signs off COMPLETE / INCOMPLETE /
# PROBLEM with the files it touched; the next run reads the digest and knows
# what is already done. (Signing lives in the ledger, never inside work files.)
_LEDGER_NAME = "_MISSION_LEDGER.json"

def _ledger_load(ws: str) -> dict:
    try:
        p = Path(ws) / _LEDGER_NAME
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"version": 1, "missions": []}

def _ledger_sign(ws: str, entry: dict) -> None:
    try:
        data = _ledger_load(ws)
        data["missions"].append(entry)
        data["missions"] = data["missions"][-100:]
        p = Path(ws) / _LEDGER_NAME
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[MissionLedger] sign failed: {e}")

def _ledger_digest(ws: str, limit: int = 6) -> str:
    try:
        ms = _ledger_load(ws).get("missions", [])[-limit:]
        if not ms:
            return ""
        lines = []
        for m in reversed(ms):
            mark = {"COMPLETE": "✓", "INCOMPLETE": "◐", "PROBLEM": "✗"}.get(m.get("status"), "?")
            line = f"{mark} {m.get('status','?')}: {str(m.get('task',''))[:120]}"
            if m.get("files"):
                line += f" → files: {', '.join(str(f) for f in m['files'][:4])}"
            if m.get("problem"):
                line += f" [issue: {str(m['problem'])[:80]}]"
            lines.append(line)
        return "\n".join(lines)
    except Exception:
        return ""

# ── Background dev-server registry (web-work verification loop) ──────────────
_DEV_SERVERS: dict = {}

def _dev_server_kill(entry) -> str:
    """Kill a tracked background process and its children (npm spawns node etc.)."""
    proc = entry.get("proc")
    if proc is None or proc.poll() is not None:
        return "already exited"
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill()
        return "stopped"
    except Exception as e:
        return f"kill failed: {e}"

def _dev_server_tail(entry, lines: int = 60) -> str:
    try:
        txt = Path(entry["log"]).read_text(encoding="utf-8", errors="replace")
        return "\n".join(txt.splitlines()[-max(lines, 1):]) or "(no output yet)"
    except Exception as e:
        return f"(log unreadable: {e})"

# ── Write-verification (Cowork principle: a bad write must FAIL LOUDLY) ──────
def _syntax_verify(p) -> str:
    """Auto syntax-check a just-written code file; result is appended to the tool
    output so the model sees breakage IMMEDIATELY and self-corrects in the same run."""
    try:
        suf = p.suffix.lower()
        if suf == ".py":
            import ast as _ast
            _ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            return " · ✓ python syntax OK"
        if suf == ".json":
            json.loads(p.read_text(encoding="utf-8", errors="replace"))
            return " · ✓ JSON valid"
        if suf in (".js", ".mjs", ".cjs"):
            node = shutil.which("node")
            if not node:
                return ""
            r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True,
                               timeout=15, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                return " · ✓ JS syntax OK"
            return f"\n⚠ JS SYNTAX ERROR — fix immediately with edit_file:\n{(r.stderr or '')[:800]}"
        if suf in (".html", ".htm"):
            txt = p.read_text(encoding="utf-8", errors="replace")
            issues = [f"unbalanced <{t}> tags" for t in ("script", "style")
                      if txt.count("<" + t) != txt.count("</" + t + ">")]
            return ("\n⚠ HTML CHECK: " + "; ".join(issues) + " — fix immediately") if issues else " · ✓ HTML tags balanced"
    except SyntaxError as se:
        return f"\n⚠ PYTHON SYNTAX ERROR (line {se.lineno}): {se.msg} — fix immediately with edit_file"
    except json.JSONDecodeError as je:
        return f"\n⚠ JSON INVALID (line {je.lineno}): {je.msg} — fix immediately with edit_file"
    except Exception:
        return ""
    return ""

# ── SSRF / confused-deputy guard for http_request ────────────────────────────
# Security audit P0: the model must not use http_request (an ALLOW deputy) to reach
# loopback services — above all the stealth bridge on :8781, whose /call executes
# ungated browser tools (arbitrary JS). Deny loopback, link-local (cloud metadata),
# the unspecified address, and the bridge port. Conserves authority at the boundary:
# http_request may not become a path to a higher-authority executor.
def _http_target_blocked(url: str) -> Optional[str]:
    try:
        from urllib.parse import urlparse
        import socket, ipaddress
        u = urlparse(url if "://" in (url or "") else "http://" + (url or ""))
        host = (u.hostname or "").strip()
        port = u.port
        _BRIDGE_PORT = int(os.getenv("STEALTH_BRIDGE_PORT", "8781"))
        if not host:
            return None
        if host.lower() in ("localhost", "ip6-localhost", "ip6-loopback"):
            return f"{host} (loopback name)"
        # resolve every address the host maps to; block if ANY is loopback/link-local/reserved
        addrs = set()
        try:
            for fam, _, _, _, sa in socket.getaddrinfo(host, port or 80):
                addrs.add(sa[0])
        except Exception:
            addrs.add(host)  # host was likely a literal IP
        for a in addrs:
            try:
                ip = ipaddress.ip_address(a)
            except ValueError:
                continue
            if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                return f"{host}->{a} (loopback/link-local/unspecified)"
        if port == _BRIDGE_PORT:
            return f"{host}:{port} (stealth bridge port)"
    except Exception:
        return None
    return None

# ── Failure detection (drives the failure-adaptation loop) ───────────────────
def _tool_result_failed(name: str, result: str) -> bool:
    """Heuristic: did this tool call FAIL? A failed action must change the next
    action — the loops count consecutive failures and force a replan."""
    r = (result or "").lstrip()
    if r.startswith("[exit "):
        # formats: "[exit 255]" / "[exit 1 · cwd=...]" — judge purely by exit code
        try:
            return int(r[6:r.index("]")].split()[0]) != 0
        except Exception:
            return False
    head = r[:500]
    low = head.lower()
    if "traceback (most recent call last)" in low: return True
    if "syntax error" in low or "syntaxerror" in low or "json invalid" in low: return True
    if head.startswith("❌") or head.startswith("⛔"): return True
    if head.startswith("[") and ("not found" in low or "error" in low or "unknown" in low): return True
    return False

# External tool sources reach the House through the Tool Provider Layer
# (tool_providers/), the way runtimes reach it through drivers. Adding a source
# means dropping a module in that package — not editing this file or exec_tool.
#
# The registry only contributes schemas from providers that are genuinely
# reachable, and REFUSES to load one whose tool names would shadow a native tool
# and inherit its trust. Unavailable providers are reported, never simulated.
try:
    from tool_providers import registry as _tools
    _provided = _tools.tools()
    if _provided:
        BUILTIN_TOOLS = BUILTIN_TOOLS + _provided
    _TOOL_GROUPS.extend(_tools.tool_groups())
    for _p in _tools.status()["providers"]:
        if _p["available"]:
            print(f"[tools] {_p['name']}: {_p['tools']} tools — {_p['description']}")
        else:
            print(f"[tools] {_p['name']}: unavailable — {_p['reason']}")
    for _r in _tools.rejected():
        print(f"[tools] REJECTED {_r['provider']}: {_r['reason']}")
except Exception as _te:
    _tools = None
    print(f"[tools] provider layer not loaded ({_te}) — native tools unaffected")

def _select_tools_for_task(task: str) -> list:
    try:
        if load_settings().get("full_toolset"):
            return BUILTIN_TOOLS
    except Exception:
        pass
    t = (task or "").lower()
    wanted = set(_TOOL_CORE)
    for keys, tools in _TOOL_GROUPS:
        if any(k in t for k in keys):
            wanted |= tools
    sel = [td for td in BUILTIN_TOOLS if td.get("function", {}).get("name") in wanted]
    if len(sel) < 8:   # safety floor — something went wrong, ship everything
        return BUILTIN_TOOLS
    return sel

# ── MISSION LEDGER — Commander-signed status of work in a workspace ──────────
# Prevents redundant reruns: every AGENT_RUN signs off COMPLETE / INCOMPLETE /
# PROBLEM with the files it touched; the next run reads the digest and knows
# what is already done. (Signing lives in the ledger, never inside work files.)
_LEDGER_NAME = "_MISSION_LEDGER.json"

def _ledger_load(ws: str) -> dict:
    try:
        p = Path(ws) / _LEDGER_NAME
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"version": 1, "missions": []}

def _ledger_sign(ws: str, entry: dict) -> None:
    try:
        data = _ledger_load(ws)
        data["missions"].append(entry)
        data["missions"] = data["missions"][-100:]
        p = Path(ws) / _LEDGER_NAME
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[MissionLedger] sign failed: {e}")

def _ledger_digest(ws: str, limit: int = 6) -> str:
    try:
        ms = _ledger_load(ws).get("missions", [])[-limit:]
        if not ms:
            return ""
        lines = []
        for m in reversed(ms):
            mark = {"COMPLETE": "✓", "INCOMPLETE": "◐", "PROBLEM": "✗"}.get(m.get("status"), "?")
            line = f"{mark} {m.get('status','?')}: {str(m.get('task',''))[:120]}"
            if m.get("files"):
                line += f" → files: {', '.join(str(f) for f in m['files'][:4])}"
            if m.get("problem"):
                line += f" [issue: {str(m['problem'])[:80]}]"
            lines.append(line)
        return "\n".join(lines)
    except Exception:
        return ""

# ── Background dev-server registry (web-work verification loop) ──────────────
_DEV_SERVERS: dict = {}

def _dev_server_kill(entry) -> str:
    """Kill a tracked background process and its children (npm spawns node etc.)."""
    proc = entry.get("proc")
    if proc is None or proc.poll() is not None:
        return "already exited"
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill()
        return "stopped"
    except Exception as e:
        return f"kill failed: {e}"

def _dev_server_tail(entry, lines: int = 60) -> str:
    try:
        txt = Path(entry["log"]).read_text(encoding="utf-8", errors="replace")
        return "\n".join(txt.splitlines()[-max(lines, 1):]) or "(no output yet)"
    except Exception as e:
        return f"(log unreadable: {e})"

# ── Write-verification (Cowork principle: a bad write must FAIL LOUDLY) ──────
def _syntax_verify(p) -> str:
    """Auto syntax-check a just-written code file; result is appended to the tool
    output so the model sees breakage IMMEDIATELY and self-corrects in the same run."""
    try:
        suf = p.suffix.lower()
        if suf == ".py":
            import ast as _ast
            _ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            return " · ✓ python syntax OK"
        if suf == ".json":
            json.loads(p.read_text(encoding="utf-8", errors="replace"))
            return " · ✓ JSON valid"
        if suf in (".js", ".mjs", ".cjs"):
            node = shutil.which("node")
            if not node:
                return ""
            r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True,
                               timeout=15, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                return " · ✓ JS syntax OK"
            return f"\n⚠ JS SYNTAX ERROR — fix immediately with edit_file:\n{(r.stderr or '')[:800]}"
        if suf in (".html", ".htm"):
            txt = p.read_text(encoding="utf-8", errors="replace")
            issues = [f"unbalanced <{t}> tags" for t in ("script", "style")
                      if txt.count("<" + t) != txt.count("</" + t + ">")]
            return ("\n⚠ HTML CHECK: " + "; ".join(issues) + " — fix immediately") if issues else " · ✓ HTML tags balanced"
    except SyntaxError as se:
        return f"\n⚠ PYTHON SYNTAX ERROR (line {se.lineno}): {se.msg} — fix immediately with edit_file"
    except json.JSONDecodeError as je:
        return f"\n⚠ JSON INVALID (line {je.lineno}): {je.msg} — fix immediately with edit_file"
    except Exception:
        return ""
    return ""

# ── SSRF / confused-deputy guard for http_request ────────────────────────────
# Security audit P0: the model must not use http_request (an ALLOW deputy) to reach
# loopback services — above all the stealth bridge on :8781, whose /call executes
# ungated browser tools (arbitrary JS). Deny loopback, link-local (cloud metadata),
# the unspecified address, and the bridge port. Conserves authority at the boundary:
# http_request may not become a path to a higher-authority executor.
def _http_target_blocked(url: str) -> Optional[str]:
    try:
        from urllib.parse import urlparse
        import socket, ipaddress
        u = urlparse(url if "://" in (url or "") else "http://" + (url or ""))
        host = (u.hostname or "").strip()
        port = u.port
        _BRIDGE_PORT = int(os.getenv("STEALTH_BRIDGE_PORT", "8781"))
        if not host:
            return None
        if host.lower() in ("localhost", "ip6-localhost", "ip6-loopback"):
            return f"{host} (loopback name)"
        # resolve every address the host maps to; block if ANY is loopback/link-local/reserved
        addrs = set()
        try:
            for fam, _, _, _, sa in socket.getaddrinfo(host, port or 80):
                addrs.add(sa[0])
        except Exception:
            addrs.add(host)  # host was likely a literal IP
        for a in addrs:
            try:
                ip = ipaddress.ip_address(a)
            except ValueError:
                continue
            if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
                return f"{host}->{a} (loopback/link-local/unspecified)"
        if port == _BRIDGE_PORT:
            return f"{host}:{port} (stealth bridge port)"
    except Exception:
        return None
    return None

# ── Failure detection (drives the failure-adaptation loop) ───────────────────
def _tool_result_failed(name: str, result: str) -> bool:
    """Heuristic: did this tool call FAIL? A failed action must change the next
    action — the loops count consecutive failures and force a replan."""
    r = (result or "").lstrip()
    if r.startswith("[exit "):
        # formats: "[exit 255]" / "[exit 1 · cwd=...]" — judge purely by exit code
        try:
            return int(r[6:r.index("]")].split()[0]) != 0
        except Exception:
            return False
    head = r[:500]
    low = head.lower()
    if "traceback (most recent call last)" in low: return True
    if "syntax error" in low or "syntaxerror" in low or "json invalid" in low: return True
    if head.startswith("❌") or head.startswith("⛔"): return True
    if head.startswith("[") and ("not found" in low or "error" in low or "unknown" in low): return True
    return False

# ── Tool Executor ─────────────────────────────────────────────────────────────
async def exec_tool(name: str, args: dict) -> str:
    try:
        # ── PROVIDED TOOLS (Tool Provider Layer) ──────────────────────────
        # MCP servers, the stealth browser, and anything else in
        # tool_providers/. Consulted first: a provider can only own a name the
        # registry has already verified does NOT collide with a native tool, so
        # this cannot intercept the House's own tools. Returns None when no
        # provider owns the name, and the native dispatcher below handles it.
        if _tools is not None:
            _provided_result = await _tools.dispatch(name, args)
            if _provided_result is not None:
                return _provided_result

        # ── OBSIDIAN (SCOUT) — vault read/write/search ─────────────────────
        # accept common aliases so the model doesn't loop on wrong names
        _OBSIDIAN_ALIASES = {
            "search_obsidian":      "obsidian_search",
            "obsidian_search_notes":"obsidian_search",
            "read_obsidian_note":   "obsidian_read_note",
            "obsidian_read":        "obsidian_read_note",
            "list_obsidian_notes":  "obsidian_list_notes",
            "obsidian_list":        "obsidian_list_notes",
            "write_obsidian_note":  "obsidian_write_note",
            "obsidian_write":       "obsidian_write_note",
            "obsidian_create_note": "obsidian_write_note",
        }
        _resolved = _OBSIDIAN_ALIASES.get(name, name)
        if _resolved in ("obsidian_list_notes", "obsidian_read_note",
                          "obsidian_write_note", "obsidian_search"):
            try:
                result = dispatch_obsidian(_resolved, args)
                import json as _j
                return _j.dumps(result, ensure_ascii=False)[:8000]
            except Exception as _oe:
                return f"[obsidian tool error: {_oe}]"

        if name in ("prove_it", "self_audit", "pending_judgments"):
            try:
                import epistemic_dossier as _ed, json as _j
                if name == "pending_judgments":
                    import judgment_queue as _jq
                    return _j.dumps(_jq.queue(limit=int(args.get("limit", 20) or 20)),
                                    ensure_ascii=False)[:8000]
                if name == "self_audit":
                    return _j.dumps(_ed.self_audit(), ensure_ascii=False)[:8000]
                r = _ed.dossier(args.get("claim", "") or "",
                                limit=int(args.get("limit", 6) or 6))
                return _j.dumps(r, ensure_ascii=False)[:8000]
            except Exception as _pe:
                return f"[prove_it error] {type(_pe).__name__}: {_pe}"

        # ── DISCOVERY (OX-1) — read-only queries over the House's own registries ──
        # Investigate first: the loop can look at Mission Center / House Mind /
        # Timeline / Learning / Archive BEFORE assuming or planning. Read-only.
        if name in ("query_missions", "read_house_mind", "query_timeline",
                    "query_learning", "recall_archive", "house_discover"):
            try:
                import discovery as _disc, json as _j
                if name == "query_missions":   r = _disc.query_missions()
                elif name == "read_house_mind":r = _disc.read_house_mind()
                elif name == "query_timeline": r = _disc.query_timeline()
                elif name == "query_learning": r = _disc.query_learning()
                elif name == "recall_archive": r = _disc.recall_archive(args.get("query", "") or "")
                else:                          r = _disc.route(args.get("request", "") or "")
                return _j.dumps(r, ensure_ascii=False)[:8000]
            except Exception as _de:
                return f"[discovery error: {name}] {_de}"

        # ── SKILL DISCOVERY (CSA) — the agent pulls playbooks at runtime ──────
        if name in ("find_skill", "use_skill"):
            try:
                import capability_skill_registry as _csr, json as _j
                if name == "find_skill":
                    hits = _csr.find_skills(args.get("query", "") or "",
                                            top_k=int(args.get("top_k", 5) or 5))
                    if not hits:
                        return ("[find_skill: no local skill matches. Proceed with "
                                "general capability, or use the external discovery "
                                "pipeline (agent-find-skill / npx skills find) if the "
                                "task truly needs a specialist playbook.]")
                    return _j.dumps({"skills": hits,
                                     "next": "call use_skill(name) to load one"},
                                    ensure_ascii=False)[:4000]
                body = _csr.skill_body(args.get("name", "") or "")
                if not body:
                    known = [s["name"] for s in _csr.load_index().get("skills", [])]
                    return f"[use_skill: unknown skill — known: {', '.join(known)}]"
                return (f"=== SKILL LOADED: {args.get('name')} — follow this playbook "
                        f"for the current task ===\n\n{body}")
            except Exception as _cse:
                return f"[skill discovery error: {_cse}]"

        # ── STEALTH BROWSER (external, isolated) ──────────────────────────────
        # Proxy stealth_* tools to the localhost shim (separate 3.13 venv). The
        # bridge auto-manages the browser instance so the model just calls
        # stealth_navigate {url} and reads with stealth_get_content.
        if name.startswith("stealth_"):
            try:
                import stealth_bridge as _sb
                return await asyncio.to_thread(_sb.dispatch, name, args)
            except Exception as _steo:
                return f"[stealth bridge error: {_steo}]"

        # ── SECURITY (audit P1): deny file tools on sensitive paths ───────────
        if name in ("read_file", "read_document", "write_file", "edit_file",
                    "delete_file", "file_info", "move_file", "copy_file"):
            _pp = args.get("path") or args.get("source") or args.get("destination") or ""
            if _pp and _path_is_sensitive(_pp):
                return (f"[denied: '{Path(str(_pp)).name}' is a protected/sensitive file "
                        "(secret/credential/policy) — blocked by security policy]")

        # ── File System ──────────────────────────────────────────────────────
        if name == "read_file":
            p = _resolve_path(args["path"])
            if not p.exists(): return f"[File not found: {p}]"
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            total = len(lines)
            offset = max(int(args.get("offset", 1) or 1), 1)
            limit = int(args.get("limit", 0) or 0)
            _MAXL = 1500  # auto-truncate guard — protects num_ctx on local models
            if limit <= 0:
                limit = total if total <= _MAXL else _MAXL
            chunk = lines[offset - 1: offset - 1 + limit]
            if args.get("line_numbers"):
                body = "\n".join(f"{i}|{ln}" for i, ln in enumerate(chunk, offset))
            else:
                body = "\n".join(chunk)
            if offset == 1 and (offset - 1 + limit) >= total:
                return body  # whole file — same shape as before
            end = min(offset - 1 + limit, total)
            return (f"[read_file: showing lines {offset}-{end} of {total} — "
                    f"call again with offset/limit for more, or grep_search to locate]\n" + body)

        elif name == "write_file":
            p = _resolve_path(args["path"]); p.parent.mkdir(parents=True, exist_ok=True)
            content = args["content"]
            # Same mis-escape guard as run_python: multi-\n literals + zero real newlines
            if content.count("\\n") >= 2 and "\n" not in content:
                content = content.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
            p.write_text(content, encoding="utf-8")
            return f"Written: {p} ({len(content)} chars)" + _syntax_verify(p)

        elif name == "edit_file":
            # FIX (Bug 5): replace_all flag (default False = first occurrence only)
            # FIX (Bug 6): better diagnostics when old_text not found — show nearest match
            p = _resolve_path(args["path"])
            if not p.exists(): return f"[File not found: {p}]"
            content = p.read_text(encoding="utf-8", errors="replace")
            old, new = args["old_text"], args["new_text"]
            replace_all = bool(args.get("replace_all", False))

            if old not in content:
                # Whitespace-normalized search to suggest the likely target
                norm_old = re.sub(r"\s+", " ", old).strip()
                lines = content.splitlines()
                hit_line = None
                for i, ln in enumerate(lines, 1):
                    if norm_old and norm_old in re.sub(r"\s+", " ", ln).strip():
                        hit_line = i; break
                msg = f"[edit_file: old_text NOT found in {p}"
                if hit_line:
                    msg += f"\n  ⚠ But a whitespace-normalized match was found on line {hit_line}:\n"
                    msg += f"     |  {lines[hit_line-1][:200]}\n"
                    msg += f"  → Re-read the file and use the EXACT text including indentation/newlines."
                else:
                    # Show first occurrence of first 30 chars of old to help locate
                    head = old[:30].strip()
                    if head and head in content:
                        idx = content.find(head)
                        ctx_line = content[:idx].count("\n") + 1
                        msg += f"\n  ⚠ First 30 chars of old_text DO appear (around line {ctx_line}) — "
                        msg += f"the rest of your old_text diverges. Re-read the file."
                    else:
                        msg += f"\n  Old_text preview: '{old[:120]}'"
                        msg += f"\n  File preview (first 200 chars): {content[:200]}"
                return msg + "]"

            count = content.count(old)
            if replace_all:
                updated = content.replace(old, new)
                n_replaced = count
            else:
                updated = content.replace(old, new, 1)
                n_replaced = 1
            p.write_text(updated, encoding="utf-8")
            note = f"Edited {p}: replaced {n_replaced} of {count} occurrence(s)"
            if count > 1 and not replace_all:
                note += f"  ⚠ {count-1} more match(es) NOT replaced — pass replace_all=true if you wanted all."
            return note + _syntax_verify(p)

        elif name == "delete_file":
            p = _resolve_path(args["path"])
            if not p.exists(): return f"[Not found: {p}]"
            if p.is_dir():
                if args.get("recursive", False): shutil.rmtree(p)
                else: p.rmdir()
            else: p.unlink()
            return f"Deleted: {p}"

        elif name == "move_file":
            src = _resolve_path(args["source"]); dst = _resolve_path(args["destination"])
            shutil.move(str(src), str(dst))
            return f"Moved: {src} → {dst}"

        elif name == "copy_file":
            src, dst = _resolve_path(args["source"]), _resolve_path(args["destination"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir(): shutil.copytree(src, dst)
            else: shutil.copy2(src, dst)
            return f"Copied: {src} → {dst}"

        elif name == "create_folder":
            p = _resolve_path(args["path"])
            p.mkdir(parents=True, exist_ok=True)
            return f"Created: {p}"

        elif name == "list_files":
            p = _resolve_path(args["path"])
            if not p.exists(): return f"[Not found: {p}]"
            show_hidden = args.get("show_hidden", False)
            items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            result = []
            for i in items:
                if not show_hidden and i.name.startswith("."): continue
                try:
                    stat = i.stat()
                    result.append({"name":i.name,"type":"dir" if i.is_dir() else "file",
                                   "size":stat.st_size if i.is_file() else 0,
                                   "modified":time.strftime("%Y-%m-%d %H:%M",time.localtime(stat.st_mtime))})
                except: pass
            return json.dumps(result, ensure_ascii=False)

        elif name == "find_files":
            root = _resolve_path(args.get("path","."))
            pattern = args.get("pattern","*")
            recursive = args.get("recursive", True)
            files = list(root.rglob(pattern) if recursive else root.glob(pattern))
            return json.dumps([str(f) for f in sorted(files)[:100]])

        elif name == "grep_search":
            root = _resolve_path(args.get("path", ".") or ".")
            if not root.exists(): return f"[Not found: {root}]"
            try:
                rx = re.compile(args["pattern"])
            except re.error:
                rx = re.compile(re.escape(args["pattern"]))
            globpat = args.get("glob", "*") or "*"
            maxr = min(int(args.get("max_results", 50) or 50), 200)
            ctx = min(max(int(args.get("context", 0) or 0), 0), 5)
            _SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv",
                     "dist", "build", ".next", ".parcel-cache", "backups"}
            out, hits, scanned = [], 0, 0
            files = [root] if root.is_file() else sorted(root.rglob(globpat))
            for f in files:
                if hits >= maxr: break
                if not f.is_file(): continue
                if any(part in _SKIP for part in f.parts): continue
                try:
                    if f.stat().st_size > 2_000_000: continue
                    flines = f.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    continue
                scanned += 1
                for i, ln in enumerate(flines, 1):
                    if rx.search(ln):
                        hits += 1
                        if ctx:
                            s_, e_ = max(0, i - 1 - ctx), min(len(flines), i + ctx)
                            blk = "\n".join(f"  {j}|{flines[j-1][:200]}" for j in range(s_ + 1, e_ + 1))
                            out.append(f"{f}:{i}\n{blk}")
                        else:
                            out.append(f"{f}:{i}: {ln.strip()[:200]}")
                        if hits >= maxr: break
            if not out:
                return f"[grep_search: no matches for '{args['pattern']}' in {root} (glob={globpat}, {scanned} files scanned)]"
            return f"[{hits} match(es) in {scanned} file(s) scanned]\n" + "\n".join(out)[:12000]

        elif name == "file_info":
            p = _resolve_path(args["path"])
            if not p.exists(): return f"[Not found: {p}]"
            s = p.stat()
            return json.dumps({"path":str(p.resolve()),"size_bytes":s.st_size,
                               "size_human":f"{s.st_size/1024:.1f}KB" if s.st_size<1e6 else f"{s.st_size/1e6:.1f}MB",
                               "is_dir":p.is_dir(),"is_file":p.is_file(),
                               "created":time.strftime("%Y-%m-%d %H:%M",time.localtime(s.st_ctime)),
                               "modified":time.strftime("%Y-%m-%d %H:%M",time.localtime(s.st_mtime))})

        # ── Shell & Code ─────────────────────────────────────────────────────
        elif name == "system_diagnostics":
            # Read-only OS diagnosis — the agent's eyes on the machine. Safe
            # (allowlisted, verb-checked), so it runs without the shell gate.
            import system_doctor as _sd
            import json as _sdj
            _res = _sd.diagnose(problem=str(args.get("problem", "")),
                                checks=args.get("checks") or None)
            return _sdj.dumps(_res, ensure_ascii=False)[:7000]

        elif name == "system_repair":
            # Curated named repair. list=true is read-only (the menu); running a
            # repair is a STATE CHANGE reached only past the ESCALATE gate.
            import system_doctor as _sd
            import json as _sdj
            if args.get("list") or not args.get("repair"):
                return _sdj.dumps({"repairs": _sd.available_repairs(),
                                   "note": "propose ONE by name; the operator approves before it runs"},
                                  ensure_ascii=False)
            return _sdj.dumps(_sd.run_repair(str(args.get("repair", ""))), ensure_ascii=False)[:7000]

        elif name == "shell_command":
            # FIX (Bug 3): explicit utf-8 encoding so Thai / emoji output doesn't garble on Windows
            timeout = min(int(args.get("timeout",30)), 120)
            cwd = args.get("cwd")
            if cwd:
                cwd = str(_resolve_path(cwd))
            else:
                ws = ACTIVE_WORKSPACE.get()
                if ws: cwd = ws
            cmd = args["command"]
            # AUTO-ROUTE: models constantly mix PowerShell cmdlets into cmd.exe pipes
            # (Select-String / Select-First / $_ ...) which fail with 'not recognized'.
            # Detect PowerShell-only syntax and run it in PowerShell instead of failing.
            _PS_MARKERS = ("select-string", "select-first", "select-object", "foreach-object",
                           "where-object", "measure-object", "sort-object", "out-file",
                           "get-childitem", "get-content", "invoke-webrequest", "invoke-restmethod",
                           "start-process", "$_", "$env:", "-pattern ")
            _use_ps = os.name == "nt" and any(m in cmd.lower() for m in _PS_MARKERS)
            if _use_ps:
                r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                                   capture_output=True, text=True, cwd=cwd, timeout=timeout,
                                   encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, cwd=cwd, timeout=timeout,
                                   encoding="utf-8", errors="replace")
            out = f"[exit {r.returncode}]"
            if _use_ps: out += " [auto-routed to PowerShell]"
            if cwd: out += f" [cwd={cwd}]"
            out += f"\n{r.stdout or ''}"
            if r.stderr: out += f"\nSTDERR:\n{r.stderr}"
            return out.strip()

        elif name == "run_python":
            # FIX (Bug 1): use ACTIVE_WORKSPACE as cwd so Python scripts can read/write workspace files
            # FIX (Bug 2): explicit utf-8 encoding so prints don't garble on Windows non-UTF8 locale
            # Inject PYTHONIOENCODING=utf-8 into child env so the script's stdout is UTF-8 too.
            timeout = min(int(args.get("timeout", 60) or 60), 300)
            code = args["code"]
            # Models sometimes double-escape newlines — code with \n literals but ZERO
            # real newlines is certainly mis-escaped and would be a 1-line SyntaxError.
            if "\\n" in code and "\n" not in code:
                code = code.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
                f.write(code); tmp = f.name
            cwd_py = ACTIVE_WORKSPACE.get() or None
            env_py = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            try:
                r = subprocess.run(
                    [sys.executable, tmp],
                    capture_output=True, text=True, timeout=timeout,
                    encoding="utf-8", errors="replace",
                    cwd=cwd_py, env=env_py,
                )
                header = f"[exit {r.returncode}"
                if cwd_py: header += f" · cwd={cwd_py}"
                header += "]"
                out = f"{header}\nSTDOUT:\n{r.stdout or ''}"
                if r.stderr: out += f"\nSTDERR:\n{r.stderr}"
                return out.strip()
            except subprocess.TimeoutExpired:
                return f"❌ run_python TIMEOUT after {timeout}s (max 300). Code may be infinite loop or blocking IO."
            finally:
                try: os.unlink(tmp)
                except Exception: pass

        elif name == "dev_server":
            action = (args.get("action") or "start").lower()
            if action == "start":
                cmd = (args.get("command") or "").strip()
                if not cmd: return "[dev_server: 'command' is required for action=start]"
                cwd = str(_resolve_path(args["cwd"])) if args.get("cwd") else (ACTIVE_WORKSPACE.get() or None)
                sid = "srv_" + hashlib.sha1(f"{cmd}:{time.time()}".encode()).hexdigest()[:8]
                logf = Path(tempfile.gettempdir()) / f"skynetclaw_{sid}.log"
                fh = open(logf, "w", encoding="utf-8", errors="replace")
                proc = subprocess.Popen(
                    cmd, shell=True, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
                )
                _DEV_SERVERS[sid] = {"proc": proc, "cmd": cmd, "cwd": cwd or "",
                                     "log": str(logf), "fh": fh, "ts": time.time()}
                await asyncio.sleep(2.5)  # boot window — catches instant crashes
                alive = proc.poll() is None
                tail = _dev_server_tail(_DEV_SERVERS[sid], 30)
                if alive:
                    return (f"[dev_server {sid} RUNNING] cmd={cmd} cwd={cwd or '(none)'}\n"
                            f"--- first output ---\n{tail}\n--- \n"
                            f"Next: verify with http_request on the local URL; "
                            f"dev_server action=logs id={sid} to monitor; action=stop id={sid} when done.")
                return (f"[dev_server {sid} EXITED immediately rc={proc.returncode}] cmd={cmd}\n"
                        f"--- output ---\n{tail}\n"
                        f"The process died — read the error above, fix the code/command, then start again.")
            elif action == "logs":
                sid = args.get("id", "")
                e = _DEV_SERVERS.get(sid)
                if not e: return f"[dev_server: unknown id '{sid}' — action=list to see running servers]"
                alive = e["proc"].poll() is None
                status = "RUNNING" if alive else f"EXITED rc={e['proc'].returncode}"
                return f"[dev_server {sid} {status}]\n" + _dev_server_tail(e, int(args.get("lines", 60) or 60))
            elif action == "stop":
                sid = args.get("id", "")
                e = _DEV_SERVERS.get(sid)
                if not e: return f"[dev_server: unknown id '{sid}']"
                res = _dev_server_kill(e)
                try: e["fh"].close()
                except Exception: pass
                _DEV_SERVERS.pop(sid, None)
                return f"[dev_server {sid} {res}] cmd={e['cmd']}"
            elif action == "list":
                if not _DEV_SERVERS: return "[dev_server: none running]"
                rows = []
                for sid, e in _DEV_SERVERS.items():
                    alive = e["proc"].poll() is None
                    rows.append({"id": sid, "cmd": e["cmd"][:80], "cwd": e["cwd"],
                                 "status": "RUNNING" if alive else f"EXITED rc={e['proc'].returncode}",
                                 "uptime_s": round(time.time() - e["ts"], 1)})
                return json.dumps(rows, ensure_ascii=False)
            return f"[dev_server: unknown action '{action}' — use start|logs|stop|list]"

        elif name == "install_package":
            # FIX (Bug 4): explicit utf-8 encoding so pip output stays readable on Windows
            pkg = args["package"]; mgr = args.get("manager","pip")
            cmds = {
                "pip":    [sys.executable,"-m","pip","install","--upgrade",pkg],
                "npm":    ["npm","install","-g",pkg],
                "winget": ["winget","install","--silent","--accept-source-agreements",pkg],
                "choco":  ["choco","install",pkg,"-y","--no-progress"],
                "cargo":  ["cargo","install",pkg],
            }
            cmd = cmds.get(mgr)
            if not cmd: return f"Unknown manager: {mgr}"
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                                   encoding="utf-8", errors="replace")
                return f"[{mgr}] exit {r.returncode}\n{(r.stdout or '')[-2000:]}\n{(r.stderr or '')[-500:]}".strip()
            except subprocess.TimeoutExpired:
                return f"❌ install_package({mgr}) TIMEOUT after 180s — large package or slow network"
            except FileNotFoundError:
                return f"❌ {mgr} not found in PATH — install {mgr} first, or pick a different manager"

        # ── System ───────────────────────────────────────────────────────────
        elif name == "get_system_info":
            import platform
            disk = shutil.disk_usage(os.getcwd())
            info = {
                "os": platform.system(), "platform": platform.platform(),
                "python": sys.version.split()[0], "cwd": os.getcwd(),
                "disk_total_gb": round(disk.total/1e9,1),
                "disk_free_gb":  round(disk.free/1e9,1),
                "disk_used_pct": round((disk.used/disk.total)*100,1),
            }
            try:
                import psutil
                vm = psutil.virtual_memory()
                info.update({"cpu_percent":psutil.cpu_percent(interval=0.5),
                             "cpu_cores":psutil.cpu_count(),
                             "ram_total_gb":round(vm.total/1e9,1),
                             "ram_used_pct":vm.percent,
                             "ram_free_gb":round(vm.available/1e9,1)})
            except: pass
            return json.dumps(info, ensure_ascii=False)

        elif name == "list_processes":
            filt = args.get("filter","").lower()
            try:
                import psutil
                procs = []
                for p in psutil.process_iter(['pid','name','status','cpu_percent','memory_percent']):
                    try:
                        if not filt or filt in p.info['name'].lower():
                            procs.append({k:v for k,v in p.info.items()})
                    except: pass
                return json.dumps(sorted(procs,key=lambda x:x.get('cpu_percent',0),reverse=True)[:30])
            except:
                cmd = "tasklist /FO CSV /NH" if os.name=="nt" else "ps aux --no-header"
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                lines = [l for l in r.stdout.splitlines() if not filt or filt.lower() in l.lower()]
                return "\n".join(lines[:30])

        elif name == "kill_process":
            pid = args.get("pid"); pname = args.get("name","")
            if pid:
                if os.name=="nt": subprocess.run(f"taskkill /PID {pid} /F",shell=True)
                else: subprocess.run(f"kill -9 {pid}",shell=True)
                return f"Killed PID {pid}"
            elif pname:
                if os.name=="nt": subprocess.run(f"taskkill /IM {pname} /F",shell=True)
                else: subprocess.run(f"pkill -f {pname}",shell=True)
                return f"Killed process: {pname}"
            return "Provide pid or name"

        elif name == "take_screenshot":
            dest = args.get("path","")
            if not dest:
                shots = Path.home()/"Screenshots"; shots.mkdir(exist_ok=True)
                dest = str(shots/f"screenshot_{int(time.time())}.png")
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab(); img.save(dest)
            except:
                ps = (f'Add-Type -AssemblyName System.Windows.Forms,System.Drawing;'
                      f'$b=New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,'
                      f'[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height);'
                      f'$g=[System.Drawing.Graphics]::FromImage($b);'
                      f'$g.CopyFromScreen(0,0,0,0,$b.Size);$b.Save("{dest}")')
                subprocess.run(["powershell","-Command",ps], timeout=15)
            return f"Screenshot saved: {dest}"

        elif name == "open_browser":
            import webbrowser; webbrowser.open(args["url"])
            return f"Opened: {args['url']}"

        elif name == "clipboard_read":
            try:
                r = subprocess.run(["powershell","-Command","Get-Clipboard"],capture_output=True,text=True,timeout=5)
                return r.stdout.strip() or "(empty)"
            except: return "Clipboard read not supported"

        elif name == "clipboard_write":
            txt = args["text"].replace("'","\\'")
            try:
                subprocess.run(["powershell","-Command",f"Set-Clipboard -Value '{txt}'"],timeout=5)
                return "Clipboard updated"
            except: return "Clipboard write not supported"

        # ── Math ─────────────────────────────────────────────────────────────
        elif name == "calculator":
            import safe_math
            expr = str(args.get("expression", "")).strip()
            try:
                val = safe_math.evaluate(expr)
                return f"🧮 {expr} = {safe_math.fmt(val)}"
            except safe_math.MathError as _me:
                return f"❌ calculator: {_me}. Allowed: + - * / // % **, ( ), and sqrt/abs/round/floor/ceil/exp/log/sin/cos/tan/min/max/pow/factorial/gcd/hypot with pi,e,tau."

        # ── Vision ───────────────────────────────────────────────────────────
        elif name == "analyze_image":
            import vision_analyze
            p = _resolve_path(args.get("path", ""))
            if not os.path.exists(p):
                return f"❌ analyze_image: file not found: {args.get('path')}"
            q = (args.get("question") or "Describe this image in detail.").strip()
            r = vision_analyze.analyze(p, q)
            if r.get("ok"):
                return f"🖼 [{r['model']}] {r['text']}"
            return (f"❌ analyze_image: no local vision model could read it "
                    f"({r.get('error', '')}). Ensure Ollama is running with a vision model.")

        # ── Real-time Data Tools ─────────────────────────────────────────────
        elif name == "get_current_datetime":
            import datetime, zoneinfo
            tz_name = args.get("timezone", "Asia/Bangkok")
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
                now = datetime.datetime.now(tz)
            except Exception:
                now = datetime.datetime.now(datetime.timezone.utc)
                tz_name = "UTC"
            thai_days = ["จันทร์","อังคาร","พุธ","พฤหัสบดี","ศุกร์","เสาร์","อาทิตย์"]
            thai_months = ["","มกราคม","กุมภาพันธ์","มีนาคม","เมษายน","พฤษภาคม","มิถุนายน",
                           "กรกฎาคม","สิงหาคม","กันยายน","ตุลาคม","พฤศจิกายน","ธันวาคม"]
            day_th = thai_days[now.weekday()]
            month_th = thai_months[now.month]
            year_be = now.year + 543
            return (
                f"📅 วันที่ปัจจุบัน (Real-time จากเซิร์ฟเวอร์):\n"
                f"  วัน{day_th}ที่ {now.day} {month_th} พ.ศ. {year_be} (ค.ศ. {now.year})\n"
                f"  เวลา: {now.strftime('%H:%M:%S')} น. ({tz_name})\n"
                f"  ISO: {now.isoformat()}\n"
                f"  UTC: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )

        elif name == "get_crypto_price":
            # ──────────────────────────────────────────────────────────────────
            # MULTI-SOURCE CRYPTO PRICE — primary CoinGecko, fallback to
            # Binance + Coinbase. If all fail → explicit error (no fabrication).
            # ──────────────────────────────────────────────────────────────────
            import urllib.parse, urllib.request as ureq, json as _json
            raw = args.get("symbols","bitcoin").strip()
            vs  = args.get("vs_currency","usd").lower()

            # Map common symbols to CoinGecko IDs + Binance/Coinbase tickers
            cg_map = {
                "btc":"bitcoin","eth":"ethereum","bnb":"binancecoin","sol":"solana",
                "xrp":"ripple","ada":"cardano","doge":"dogecoin","usdt":"tether",
                "usdc":"usd-coin","dot":"polkadot","avax":"avalanche-2","matic":"matic-network",
                "link":"chainlink","ltc":"litecoin","atom":"cosmos","uni":"uniswap",
                "ftm":"fantom","near":"near","algo":"algorand","vet":"vechain",
            }
            # Reverse: cg_id → uppercase ticker (for Binance/Coinbase fallback)
            cg_to_ticker = {
                "bitcoin":"BTC","ethereum":"ETH","binancecoin":"BNB","solana":"SOL",
                "ripple":"XRP","cardano":"ADA","dogecoin":"DOGE","tether":"USDT",
                "usd-coin":"USDC","polkadot":"DOT","avalanche-2":"AVAX",
                "matic-network":"MATIC","chainlink":"LINK","litecoin":"LTC",
                "cosmos":"ATOM","uniswap":"UNI","fantom":"FTM","near":"NEAR",
                "algorand":"ALGO","vechain":"VET",
            }
            ids = []
            for s in [x.strip().lower() for x in raw.replace(","," ").split()]:
                ids.append(cg_map.get(s, s))
            ids = ids[:10]
            ids_str = ",".join(ids)
            now_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
            errors = []
            data = {}        # {coin_id: {price, change_24h, mcap, source}}

            UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

            # ── Source 1: CoinGecko ──────────────────────────────────────────
            try:
                url = (f"https://api.coingecko.com/api/v3/simple/price"
                       f"?ids={urllib.parse.quote(ids_str)}"
                       f"&vs_currencies={vs}&include_24hr_change=true&include_market_cap=true")
                req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
                with ureq.urlopen(req, timeout=10) as r:
                    cg = _json.loads(r.read().decode())
                if isinstance(cg, dict) and cg:
                    for cid, prices in cg.items():
                        p = prices.get(vs)
                        if p is None: continue
                        data[cid] = {
                            "price": float(p),
                            "change_24h": float(prices.get(f"{vs}_24h_change", 0) or 0),
                            "mcap": float(prices.get(f"{vs}_market_cap", 0) or 0),
                            "source": "CoinGecko",
                        }
            except Exception as e:
                errors.append(f"CoinGecko: {type(e).__name__}: {str(e)[:80]}")

            # ── Source 2: Binance fallback (USDT pair, free, no key) ─────────
            # Only fill in coins that CoinGecko didn't return AND vs_currency=usd
            if vs in ("usd","usdt") and len(data) < len(ids):
                missing = [cid for cid in ids if cid not in data]
                for cid in missing:
                    tick = cg_to_ticker.get(cid)
                    if not tick: continue
                    try:
                        url_b = f"https://api.binance.com/api/v3/ticker/24hr?symbol={tick}USDT"
                        req_b = ureq.Request(url_b, headers={"User-Agent": UA})
                        with ureq.urlopen(req_b, timeout=8) as rb:
                            bd = _json.loads(rb.read().decode())
                        p = float(bd.get("lastPrice", 0) or 0)
                        if p > 0:
                            data[cid] = {
                                "price": p,
                                "change_24h": float(bd.get("priceChangePercent", 0) or 0),
                                "mcap": 0,
                                "source": "Binance",
                            }
                    except Exception as e:
                        errors.append(f"Binance {tick}: {type(e).__name__}: {str(e)[:60]}")

            # ── Source 3: Coinbase fallback (USD spot, free) ─────────────────
            if vs == "usd" and len(data) < len(ids):
                missing = [cid for cid in ids if cid not in data]
                for cid in missing:
                    tick = cg_to_ticker.get(cid)
                    if not tick: continue
                    try:
                        url_c = f"https://api.coinbase.com/v2/prices/{tick}-USD/spot"
                        req_c = ureq.Request(url_c, headers={"User-Agent": UA, "Accept": "application/json"})
                        with ureq.urlopen(req_c, timeout=8) as rc:
                            cd = _json.loads(rc.read().decode())
                        amt = (cd.get("data") or {}).get("amount")
                        if amt:
                            data[cid] = {
                                "price": float(amt),
                                "change_24h": 0,
                                "mcap": 0,
                                "source": "Coinbase",
                            }
                    except Exception as e:
                        errors.append(f"Coinbase {tick}: {type(e).__name__}: {str(e)[:60]}")

            if not data:
                return (
                    f"❌ GET_CRYPTO_PRICE FAILED — ดึงราคา crypto ไม่ได้จากทุกแหล่ง "
                    f"({len(errors)} sources tried, 0 succeeded)\n"
                    f"Errors: {'; '.join(errors)[:500]}\n\n"
                    f"⚠️ AI INSTRUCTION: DO NOT fabricate prices. Tell the user verbatim: "
                    f"'ขณะนี้ระบบดึงราคา crypto ไม่ได้จากทุกแหล่ง — กรุณาตรวจที่ "
                    f"https://www.coingecko.com หรือ https://www.binance.com โดยตรง' and STOP."
                )

            sources_used = sorted({v["source"] for v in data.values()})
            lines = [f"💰 ราคา Crypto Real-time ({len(data)} coins | "
                     f"แหล่ง: {', '.join(sources_used)} | {now_str})\n"]
            for cid, info in data.items():
                price = info["price"]; change = info["change_24h"]; mcap = info["mcap"]
                arrow = "▲" if change >= 0 else "▼"
                tag = "🟢" if change >= 0 else "🔴"
                sym = cg_to_ticker.get(cid, cid.upper())
                if vs == "thb":
                    pf = f"฿{price:,.2f}"
                else:
                    pf = f"${price:,.4f}" if price < 1 else f"${price:,.2f}"
                mcap_fmt = ""
                if mcap > 1e9:   mcap_fmt = f" | MCap ${mcap/1e9:.2f}B"
                elif mcap > 1e6: mcap_fmt = f" | MCap ${mcap/1e6:.1f}M"
                src_tag = f" [{info['source']}]" if info['source'] != "CoinGecko" else ""
                ch_str = f" 24h {arrow}{abs(change):.2f}%" if change else ""
                lines.append(f"  {tag} **{sym}**: {pf}{ch_str}{mcap_fmt}{src_tag}")

            if errors:
                lines.append(f"\n⚠️ แหล่งที่ล้มเหลวบางส่วน: {'; '.join(errors[:3])[:200]}")
            lines.append(f"\n✅ ดึงสด ณ {now_str} — ใช้ตัวเลขเหล่านี้โดยตรง ห้ามใช้ training data")
            return "\n".join(lines)

        elif name == "get_gold_price":
            # ──────────────────────────────────────────────────────────────────
            # MULTI-SOURCE GOLD PRICE — rewritten 2026-05-06
            # Spot (USD/oz) sources tried IN PARALLEL of intent:
            #   1. CoinGecko PAXG token (1 PAXG ≈ 1 troy oz, no key)
            #   2. GoldPrice.org public XRate
            #   3. Stooq XAUUSD CSV
            #   4. Yahoo Finance (often 401 — last resort)
            # Median consensus when ≥2 sources respond. >5% spread → flag.
            #
            # Thai gold sources:
            #   A. chnwt.dev/thai-gold-api (community wrapper of GTA)
            #   B. goldtraders.or.th HTML scrape (FIXED regex — accepts any 5-6 digit)
            #
            # If ALL sources fail → returns explicit ERROR. NEVER fabricates.
            # ──────────────────────────────────────────────────────────────────
            import urllib.request as ureq, json as _json, re as _re
            now_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

            spot_quotes = []         # [(source_name, usd_per_oz), ...]
            silver_quotes = []       # [(source_name, usd_per_oz), ...]
            fx_thb = 0.0
            fx_source = ""
            thai_bar_buy = thai_bar_sell = 0
            thai_orn_buy = thai_orn_sell = 0
            thai_orn_buy_old = thai_orn_buy
            thai_source = ""
            errors = []

            UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            BASE_HDR = {"User-Agent": UA, "Accept": "application/json, text/html, */*",
                        "Accept-Language": "en-US,en;q=0.9,th;q=0.8"}

            def _get(url, timeout=10, extra_headers=None):
                hdr = {**BASE_HDR, **(extra_headers or {})}
                req = ureq.Request(url, headers=hdr)
                with ureq.urlopen(req, timeout=timeout) as r:
                    return r.read().decode("utf-8", "replace")

            # ── Spot Source 1: CoinGecko PAXG (Paxos Gold) ────────────────────
            try:
                body = _get("https://api.coingecko.com/api/v3/simple/price"
                            "?ids=pax-gold&vs_currencies=usd", timeout=8)
                d = _json.loads(body)
                p = float((d.get("pax-gold") or {}).get("usd", 0))
                if 1500 < p < 20000:
                    spot_quotes.append(("CoinGecko PAXG", p))
            except Exception as e:
                errors.append(f"CoinGecko PAXG: {type(e).__name__}: {str(e)[:80]}")

            # ── Spot Source 2: GoldPrice.org public XRate ─────────────────────
            try:
                body = _get("https://data-asg.goldprice.org/dbXRates/USD", timeout=8,
                            extra_headers={"Origin": "https://goldprice.org",
                                           "Referer": "https://goldprice.org/"})
                d = _json.loads(body)
                items = d.get("items") or []
                for it in items:
                    if str(it.get("curr","")).upper() == "USD":
                        p = float(it.get("xauPrice") or 0)
                        ag = float(it.get("xagPrice") or 0)
                        if 1500 < p < 20000:
                            spot_quotes.append(("GoldPrice.org", p))
                        if 5 < ag < 200:
                            silver_quotes.append(("GoldPrice.org", ag))
                        break
            except Exception as e:
                errors.append(f"GoldPrice.org: {type(e).__name__}: {str(e)[:80]}")

            # ── Spot Source 3: Stooq XAUUSD CSV ───────────────────────────────
            try:
                body = _get("https://stooq.com/q/l/?s=xauusd&f=sd2t2ohlcv&h&e=csv", timeout=8)
                rows = body.strip().splitlines()
                if len(rows) >= 2:
                    cols = rows[1].split(",")
                    if len(cols) >= 7:
                        try:
                            p = float(cols[6])  # close
                            if 1500 < p < 20000:
                                spot_quotes.append(("Stooq XAUUSD", p))
                        except ValueError:
                            pass
            except Exception as e:
                errors.append(f"Stooq: {type(e).__name__}: {str(e)[:80]}")

            # ── Spot Source 4: Yahoo Finance (last resort) ────────────────────
            try:
                body = _get("https://query1.finance.yahoo.com/v7/finance/quote"
                            "?symbols=GC%3DF%2CSI%3DF", timeout=8)
                d = _json.loads(body)
                for item in d.get("quoteResponse", {}).get("result", []):
                    sym = item.get("symbol", "")
                    p = item.get("regularMarketPrice") or item.get("ask") or 0
                    p = float(p)
                    if sym == "GC=F" and 1500 < p < 20000:
                        spot_quotes.append(("Yahoo GC=F", p))
                    elif sym == "SI=F" and 5 < p < 200:
                        silver_quotes.append(("Yahoo SI=F", p))
            except Exception as e:
                errors.append(f"Yahoo: {type(e).__name__}: {str(e)[:80]}")

            # ── FX: USD→THB (try several) ─────────────────────────────────────
            for src_url, src_name, key in [
                ("https://open.er-api.com/v6/latest/USD",      "open.er-api",     "rates.THB"),
                ("https://api.frankfurter.app/latest?from=USD&to=THB", "frankfurter", "rates.THB"),
                ("https://api.exchangerate-api.com/v4/latest/USD", "exchangerate-api", "rates.THB"),
            ]:
                if fx_thb: break
                try:
                    d = _json.loads(_get(src_url, timeout=8))
                    cur = d
                    for part in key.split("."):
                        cur = cur.get(part, {}) if isinstance(cur, dict) else {}
                    v = float(cur or 0)
                    if 25 < v < 50:
                        fx_thb = v
                        fx_source = src_name
                except Exception as e:
                    errors.append(f"{src_name}: {type(e).__name__}: {str(e)[:60]}")

            # ── Thai gold A: chnwt.dev community Thai-Gold-API wraps GTA ──────
            try:
                body = _get("https://api.chnwt.dev/thai-gold-api/latest", timeout=10)
                d = _json.loads(body)
                # Defensive: try several response shapes the API has used
                resp = d.get("response", d)
                price = resp.get("price", resp)

                def _to_int(x):
                    if x is None: return 0
                    s = str(x).replace(",", "").strip()
                    try: return int(float(s))
                    except: return 0

                bar = price.get("gold_bar") or price.get("bar") or {}
                orn = price.get("gold")     or price.get("ornament") or {}
                bb = _to_int(bar.get("buy"));  bs = _to_int(bar.get("sell"))
                ob = _to_int(orn.get("buy"));  os_ = _to_int(orn.get("sell"))
                if 30000 < bs < 200000:
                    thai_bar_buy, thai_bar_sell = bb, bs
                    thai_orn_buy, thai_orn_sell = ob, os_
                    thai_source = "chnwt.dev (Thai-Gold-API → GTA)"
            except Exception as e:
                errors.append(f"chnwt.dev: {type(e).__name__}: {str(e)[:80]}")

            # ── Thai gold B: goldtraders.or.th HTML (FIXED regex) ─────────────
            if not thai_bar_sell:
                try:
                    html = _get("https://www.goldtraders.or.th/", timeout=12,
                                extra_headers={
                                    "Accept": "text/html,application/xhtml+xml",
                                    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
                                    "Referer": "https://www.google.com/",
                                })
                    # FIXED — accept ANY 5-6 digit number with comma, then filter by sane range
                    cands = _re.findall(r"\b(\d{2,3},\d{3}(?:\.\d+)?|\d{5,6}(?:\.\d+)?)\b", html)
                    nums_in_range = []
                    seen = set()
                    for c in cands:
                        try:
                            v = int(float(c.replace(",", "")))
                        except:
                            continue
                        if 30000 < v < 200000 and v not in seen:
                            seen.add(v)
                            nums_in_range.append(v)
                    # Heuristic: typical GTA page lists 4 prices in order:
                    # bar_sell, bar_buy, orn_sell, orn_buy — sell > buy by ~100-300 baht
                    if len(nums_in_range) >= 2:
                        thai_bar_sell = nums_in_range[0]
                        thai_bar_buy  = nums_in_range[1]
                        if thai_bar_buy > thai_bar_sell:
                            thai_bar_buy, thai_bar_sell = thai_bar_sell, thai_bar_buy
                    if len(nums_in_range) >= 4:
                        thai_orn_sell = nums_in_range[2]
                        thai_orn_buy  = nums_in_range[3]
                        if thai_orn_buy > thai_orn_sell:
                            thai_orn_buy, thai_orn_sell = thai_orn_sell, thai_orn_buy
                    if thai_bar_sell:
                        thai_source = "goldtraders.or.th (scraped)"
                except Exception as e:
                    errors.append(f"goldtraders.or.th: {type(e).__name__}: {str(e)[:80]}")

            # ── Build consensus spot ──────────────────────────────────────────
            spot_used = 0.0
            spread_pct = 0.0
            if spot_quotes:
                prices = sorted(p for _, p in spot_quotes)
                n = len(prices)
                spot_used = prices[n // 2] if n % 2 == 1 else (prices[n//2-1] + prices[n//2]) / 2
                if n >= 2 and spot_used:
                    spread_pct = (max(prices) - min(prices)) / spot_used * 100

            silver_used = 0.0
            if silver_quotes:
                ag_prices = sorted(p for _, p in silver_quotes)
                m = len(ag_prices)
                silver_used = ag_prices[m // 2] if m % 2 == 1 else (ag_prices[m//2-1] + ag_prices[m//2]) / 2

            # ── Hard fail if NOTHING works ────────────────────────────────────
            if not spot_used and not thai_bar_sell:
                return (
                    f"❌ GET_GOLD_PRICE FAILED — ดึงราคาทองไม่ได้จากทุกแหล่ง "
                    f"({len(errors)} sources tried, 0 succeeded)\n"
                    f"Errors: {'; '.join(errors)[:600]}\n\n"
                    f"⚠️ AI INSTRUCTION (mandatory): "
                    f"DO NOT fabricate or estimate. Tell the user verbatim: "
                    f"'ขณะนี้ระบบดึงราคาทองไม่ได้จากทุกแหล่ง — กรุณาตรวจสอบโดยตรงที่ "
                    f"https://www.goldtraders.or.th หรือ https://goldprice.org' "
                    f"and STOP. Do not invent values."
                )

            # ── Format response ───────────────────────────────────────────────
            lines = [f"🥇 ราคาทองคำ REAL-TIME ({len(spot_quotes)} spot src + Thai | {now_str})"]
            lines.append("=" * 60)

            if spot_used:
                lines.append("")
                lines.append(f"📊 SPOT GOLD (consensus median จาก {len(spot_quotes)} แหล่ง):")
                lines.append(f"   XAU/USD              : ${spot_used:,.2f} / troy oz")
                for src, p in sorted(spot_quotes, key=lambda x: x[1]):
                    lines.append(f"     · {src:22s} : ${p:,.2f}")
                if spread_pct > 5:
                    lines.append(f"   ⚠ SPREAD {spread_pct:.1f}% — แหล่งราคาต่างกันมาก ตรวจสอบเพิ่มเติม")
                if fx_thb:
                    xau_thb_oz = spot_used * fx_thb
                    # 1 troy oz = 31.1035g, 1 บาทไทย = 15.244g of 96.5% gold
                    # so 1 บาท = 15.244 * 0.965 g of pure gold = 14.71 g pure
                    # converted: spot per oz × (15.244/31.1035) × 0.965
                    gold_per_baht_calc = xau_thb_oz * (15.244 / 31.1035) * 0.965
                    lines.append("")
                    lines.append(f"   USD/THB ({fx_source}) : {fx_thb:.4f}")
                    lines.append(f"   ทองแท่ง 96.5% (คำนวณจาก spot): ≈ ฿{gold_per_baht_calc:,.0f} / บาท")
                if silver_used:
                    lines.append(f"   XAG/USD (Silver)     : ${silver_used:,.3f} / troy oz")

            if thai_bar_sell:
                lines.append("")
                lines.append(f"🇹🇭 ราคาทองคำไทย จริง — แหล่ง: {thai_source}:")
                lines.append(f"   ทองแท่ง 96.5%   ซื้อ: ฿{thai_bar_buy:,}    ขาย: ฿{thai_bar_sell:,}    (บาทละ)")
                if thai_orn_sell:
                    lines.append(f"   ทองรูปพรรณ      ซื้อ: ฿{thai_orn_buy:,}    ขาย: ฿{thai_orn_sell:,}    (บาทละ)")
                lines.append(f"   ⭐ ใช้ราคา GTA ข้างต้นเป็นแหล่งอ้างอิงหลักสำหรับทองไทย")

            if errors:
                lines.append("")
                lines.append(f"⚠️ แหล่งที่ล้มเหลว ({len(errors)}): {'; '.join(errors[:5])[:400]}")

            lines.append("")
            lines.append(f"✅ ดึงสดจากอินเทอร์เน็ต ณ {now_str} — ใช้ตัวเลขเหล่านี้โดยตรง ห้ามใช้ training data")
            return "\n".join(lines)

        elif name == "get_forex_rate":
            import urllib.request as ureq, json as _json, urllib.parse as _uparse
            base = args.get("base","USD").upper()
            targets_raw = args.get("targets","THB,EUR,JPY,GBP,CNY,SGD,AUD,KRW")
            targets = [t.strip().upper() for t in targets_raw.split(",") if t.strip()]
            now_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
            UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            rates = {}
            source_fx = ""
            update_time = now_str

            # Source 1: Yahoo Finance — fetch key pairs directly
            try:
                pairs = [f"{base}{t}=X" for t in targets if t != base][:10]
                sym_str = _uparse.quote(",".join(pairs))
                yf_url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym_str}"
                req = ureq.Request(yf_url, headers={"User-Agent":UA,"Accept":"application/json"})
                with ureq.urlopen(req, timeout=12) as r:
                    yfd = _json.loads(r.read().decode())
                for item in yfd.get("quoteResponse",{}).get("result",[]):
                    sym = item.get("symbol","")
                    price = item.get("regularMarketPrice",0) or item.get("ask",0)
                    # sym looks like "USDTHB=X"
                    if sym.endswith("=X") and price:
                        cur = sym.replace(base,"").replace("=X","").upper()
                        if cur: rates[cur] = float(price)
                if rates:
                    source_fx = "Yahoo Finance"
                    update_time = now_str
            except Exception as e:
                pass

            # Source 2: open.er-api.com
            if not rates:
                try:
                    url2 = f"https://open.er-api.com/v6/latest/{base}"
                    req2 = ureq.Request(url2, headers={"User-Agent":UA,"Accept":"application/json"})
                    with ureq.urlopen(req2, timeout=10) as r2:
                        d2 = _json.loads(r2.read().decode())
                    if d2.get("result") == "success":
                        all_rates = d2.get("rates",{})
                        rates = {k:v for k,v in all_rates.items() if k in targets}
                        source_fx = "open.er-api.com"
                        update_time = d2.get("time_last_update_utc", now_str)
                except: pass

            # Source 3: frankfurter.app
            if not rates:
                try:
                    t_str = _uparse.quote(",".join(targets[:10]))
                    url3 = f"https://api.frankfurter.app/latest?from={base}&to={t_str}"
                    req3 = ureq.Request(url3, headers={"User-Agent":UA})
                    with ureq.urlopen(req3, timeout=10) as r3:
                        d3 = _json.loads(r3.read().decode())
                    rates = d3.get("rates",{})
                    source_fx = "frankfurter.app"
                    update_time = d3.get("date", now_str)
                except: pass

            if not rates:
                return (f"❌ GET_FOREX_RATE FAILED — ดึงอัตราแลกเปลี่ยนไม่ได้\n"
                        f"⚠️ AI INSTRUCTION: ห้ามเดาอัตราแลกเปลี่ยน — แจ้งผู้ใช้ว่า 'ขณะนี้ระบบดึงข้อมูล forex ไม่ได้ กรุณาตรวจสอบที่ xe.com หรือ bot.mof.go.th'")

            priority = ["THB","EUR","JPY","GBP","CNY","SGD","AUD","KRW","HKD","INR"]
            lines = [f"💱 อัตราแลกเปลี่ยน REAL-TIME (Base: {base} | แหล่ง: {source_fx})",
                     f"   อัปเดต: {update_time}", ""]
            shown = set()
            for cur in (targets + [c for c in priority if c not in targets]):
                if cur == base or cur in shown or cur not in rates: continue
                rate = rates[cur]
                shown.add(cur)
                flag = {"THB":"🇹🇭","USD":"🇺🇸","EUR":"🇪🇺","JPY":"🇯🇵","GBP":"🇬🇧",
                        "CNY":"🇨🇳","SGD":"🇸🇬","AUD":"🇦🇺","KRW":"🇰🇷","HKD":"🇭🇰"}.get(cur,"")
                fmt = f"{rate:,.2f}" if rate > 10 else f"{rate:.4f}"
                lines.append(f"   {flag} {base}/{cur}: {fmt}")
                if len(shown) >= 10: break
            lines.append(f"\n✅ ข้อมูลสด ณ {now_str} — ใช้ตัวเลขนี้ตอบโดยตรง ห้ามใช้ training data")
            return "\n".join(lines)

        elif name == "get_news":
            import urllib.parse, urllib.request as ureq, re as _re
            import xml.etree.ElementTree as _ET
            topic = (args.get("topic","") or "").strip()
            n_want = min(int(args.get("max_results",6) or 6), 12)
            # language: Thai by default; "en" forces English/global sources
            lang = (args.get("lang","") or "").lower()
            now_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
            if not topic:
                return "[⚠ get_news: empty topic]"
            results = []; src_used = ""; errs = []
            _ua = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
            # ── 1) Google News RSS — real ranked headlines from major outlets,
            #        recency-sorted, Thai-aware, no API key. (Primary source.)
            try:
                q = urllib.parse.quote(topic)
                ceid = "US:en" if lang.startswith("en") else "TH:th"
                hl, gl = ("en", "US") if lang.startswith("en") else ("th", "TH")
                rss = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
                with ureq.urlopen(ureq.Request(rss, headers=_ua), timeout=14) as r:
                    root = _ET.fromstring(r.read().decode("utf-8","replace"))
                for it in root.iter("item"):
                    title = (it.findtext("title") or "").strip()
                    link  = (it.findtext("link") or "").strip()
                    pub   = (it.findtext("pubDate") or "").strip()
                    src_el = it.find("source")
                    source = (src_el.text.strip() if src_el is not None and src_el.text else "")
                    desc = _re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip()
                    if not title: continue
                    line = f"  {len(results)+1}. **{title}**"
                    if source or pub: line += f"\n     🏷 {source} · {pub[:25]}"
                    line += f"\n     🔗 {link[:140]}"
                    if desc: line += f"\n     {desc[:180]}"
                    results.append(line)
                    if len(results) >= n_want: break
                if results: src_used = "Google News"
            except Exception as e:
                errs.append(f"gnews:{str(e)[:60]}")
            # ── 2) Fallback: DuckDuckGo lite scrape (only if RSS returned nothing)
            if not results:
                try:
                    q_enc = urllib.parse.quote(f"{topic} ข่าว {time.strftime('%Y-%m-%d')}")
                    url = f"https://lite.duckduckgo.com/lite/?q={q_enc}&kl=th-th"
                    with ureq.urlopen(ureq.Request(url, headers=_ua), timeout=12) as r:
                        html = r.read().decode("utf-8","replace")
                    links = _re.findall(r'<a[^>]+class="result-link"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, _re.DOTALL)
                    for i,(href,title) in enumerate(links[:n_want]):
                        t = _re.sub(r'<[^>]+>','',title).strip()
                        if t: results.append(f"  {i+1}. **{t}**\n     🔗 {href[:120]}")
                    if results: src_used = "DuckDuckGo"
                except Exception as e:
                    errs.append(f"ddg:{str(e)[:60]}")
            if not results:
                return (f"❌ ไม่พบข่าวสำหรับ: {topic} ({'; '.join(errs)})\n"
                        f"ลอง get_news ด้วยคำที่กว้างขึ้น หรือ web_search(\"{topic}\")")
            header = f"📰 ข่าวล่าสุด: \"{topic}\" | {now_str} | แหล่ง: {src_used} ({len(results)} ข่าว)\n"
            return header + "\n\n".join(results)

        elif name == "read_document":
            # OX-DOC-UPLOAD-1 — turn an uploaded PDF/DOCX/XLSX/HTML/image into text
            import doc_reader as _dr
            p = _resolve_path(args["path"])
            if not p.exists():
                return f"[File not found: {p}]"
            r = _dr.extract_text(str(p))
            if not r.get("ok"):
                return f"❌ read_document: {r.get('error')}"
            return (f"📄 {p.name} [{r['kind']}, {r['chars']} chars"
                    f"{' · truncated' if r.get('truncated') else ''}]\n\n{r['text']}")

        elif name == "build_news_report":
            # OX-NEWS-REPORT-1 — deterministic: gather real ranked news + render the
            # HTML in CODE (not model freestyle). One call → quality report file.
            import news_report as _nr
            topics = args.get("topics") or []
            if isinstance(topics, str):
                topics = [t.strip() for t in re.split(r"[,\n;|]", topics) if t.strip()]
            title = args.get("title") or "สรุปข่าวสำคัญ"
            fname = (args.get("filename") or "news_report.html").strip()
            if not fname.lower().endswith(".html"):
                fname += ".html"
            try:
                p = _resolve_path(fname)
                r = _nr.make_report(topics, title=title, lang=args.get("lang", "th"),
                                    per_topic=int(args.get("per_topic", 6) or 6),
                                    out_path=str(p))
                lines = [f"✅ สร้างรายงานข่าวแล้ว: {p}",
                         f"   {r['count']} ข่าว · {len(r['topics'])} หัวข้อ · จัดอันดับตามความสำคัญ+ความใหม่"]
                for s in r["sections"]:
                    top = s["top"][0]["title"][:50] if s["top"] else "—"
                    lines.append(f"   • {s['topic']}: {s['n']} ข่าว (เด่น: {top})")
                lines.append("DONE — รายงานพร้อมเปิดดูในเบราว์เซอร์ ไม่ต้องเขียน HTML เพิ่ม")
                return "\n".join(lines)
            except Exception as e:
                return f"❌ build_news_report error: {e}"

        # ── Network ──────────────────────────────────────────────────────────
        elif name == "web_search":
            # ─────────────────────────────────────────────────────────────────
            # MULTI-SOURCE WEB SEARCH — the External Provider Layer lives in
            # search_providers.py (ADR-0013 pattern: search is a swappable
            # Capability Provider, like a Model Adapter). Keyed APIs
            # (Brave/Tavily/Serper) are tried FIRST when their env key is set;
            # the free providers keep their exact prior order, so with NO key
            # the behaviour is byte-identical to before.
            #
            # Change class (Commander ruling 2026-07-21): Operational
            # Infrastructure Maintenance — public interface + semantics of
            # web_search UNCHANGED; only the provider layer is factored out.
            # Still refuses to fabricate on total failure.
            # ─────────────────────────────────────────────────────────────────
            query  = (args.get("query","") or "").strip()
            n_want = min(int(args.get("max_results",6) or 6), 10)
            now_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
            if not query:
                return "[⚠ web_search: empty query]"
            try:
                import search_providers as _sp
                results, source_used, errors = _sp.search(query, n_want)
            except Exception as _spe:
                results, source_used, errors = [], "", [
                    f"provider-layer: {type(_spe).__name__}: {str(_spe)[:80]}"]

            # ── Build response (format preserved exactly) ─────────────────────
            header = f"[🔍 Web Search · \"{query}\" · {now_str}]\n"
            if not results:
                return (
                    header
                    + f"\n❌ All {len(errors)} sources failed:\n"
                    + "\n".join(f"   • {e}" for e in errors[:6])
                    + "\n\n⚠ AI INSTRUCTION: tell the user the search system is down. "
                      "Do NOT fabricate search results. Suggest user check directly via browser."
                )
            footer = f"\n\n[✅ Source: {source_used} · {len(results)} results]"
            if errors:
                footer += f"\n[⚠ skipped {len(errors)} dead source(s): {', '.join(e.split(':')[0] for e in errors[:4])}]"
            return header + "\n\n".join(results) + footer

        elif name == "http_request":
            url = args["url"]; method = args.get("method","GET").upper()
            _blk = _http_target_blocked(url)
            if _blk:
                return (f"[blocked: http_request to {_blk} is denied — loopback/internal "
                        f"targets (incl. the stealth bridge) are not reachable via http_request]")
            headers = args.get("headers") or {}
            body = args.get("body"); params = args.get("params")
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.request(method, url, headers=headers,
                                    json=body, params=params)
            try: rj = r.json(); text = json.dumps(rj, ensure_ascii=False, indent=2)[:4000]
            except: text = r.text[:4000]
            return f"[{r.status_code}]\n{text}"

        elif name == "download_file":
            url = args["url"]
            dest = args.get("destination","") or str(Path.home()/"Downloads"/url.split("/")[-1].split("?")[0] or "download.bin")
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            async with httpx.AsyncClient(timeout=120,follow_redirects=True) as c:
                async with c.stream("GET", url) as r:
                    total = 0
                    with open(dest,"wb") as f:
                        async for chunk in r.aiter_bytes(8192):
                            f.write(chunk); total+=len(chunk)
            return f"Downloaded {total/1024:.1f}KB → {dest}"

        # ── Obsidian ─────────────────────────────────────────────────────────
        elif name == "search_obsidian":
            vault = load_settings().get("vault_path","")
            # Fallback: if no vault configured but workspace is set, use workspace
            if not vault:
                ws_fb = ACTIVE_WORKSPACE.get()
                if ws_fb and Path(ws_fb).exists():
                    vault = ws_fb
                else:
                    return ("[No Obsidian vault configured AND no workspace folder mounted.]\n"
                            "→ Solution: ask the user to set vault path via Obsidian tab, "
                            "OR use list_files(path) on a known folder, "
                            "OR use find_files(path, '*.md') to discover markdown notes.")
            results = keyword_search_notes(vault, args.get("query",""), args.get("top_k",5))
            if not results:
                return f"[Searched vault {vault} for '{args.get('query','')}' — no matches. Try list_files or different keyword.]"
            return json.dumps([{"name":r["name"],"snippet":r["snippet"][:300],"score":r["score"]} for r in results])

        elif name == "read_obsidian_note":
            vault = load_settings().get("vault_path","")
            if not vault:
                ws_fb = ACTIVE_WORKSPACE.get()
                if ws_fb and Path(ws_fb).exists():
                    vault = ws_fb
                else:
                    return ("[No vault and no workspace.] → Use read_file(absolute_path_to_md) instead.")
            nm = args.get("name",""); vault_p = Path(vault)
            for md in vault_p.rglob(f"{nm}.md"):
                return md.read_text(encoding="utf-8",errors="replace")[:5000]
            for md in vault_p.rglob("*.md"):
                if nm.lower() in md.stem.lower():
                    return md.read_text(encoding="utf-8",errors="replace")[:5000]
            return f"[Note '{nm}' not found in {vault}. Try find_files('{vault}', '*{nm}*') or list_files to discover.]"

        elif name == "write_obsidian_note":
            vault = load_settings().get("vault_path","")
            if not vault:
                ws_fb = ACTIVE_WORKSPACE.get()
                if ws_fb and Path(ws_fb).exists():
                    vault = ws_fb
                else:
                    return ("[No vault and no workspace.] → Use write_file(absolute_path, content) instead.")
            folder = args.get("folder",""); nm = args.get("name","") + ".md"
            vp = Path(vault)/(folder or ""); vp.mkdir(parents=True, exist_ok=True)
            fpath = vp/nm; fpath.write_text(args.get("content",""), encoding="utf-8")
            return f"Written: {fpath}"

        # ── Social / Integrations ────────────────────────────────────────────
        elif name == "telegram_send":
            creds = get_integration("telegram")
            if not creds: return "Telegram not configured. Add in Connections → Integrations."
            token = creds.get("bot_token",""); chat_id = args.get("chat_id","") or creds.get("chat_id","")
            if not token or not chat_id: return "Set bot_token and chat_id in Telegram integration."
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                 json={"chat_id":chat_id,"text":args["message"],"parse_mode":"Markdown"})
            d = r.json(); return f"Telegram: {'sent ✓' if d.get('ok') else d.get('description','error')}"

        elif name == "discord_send":
            creds = get_integration("discord")
            if not creds: return "Discord not configured."
            webhook = creds.get("webhook_url",""); token = creds.get("bot_token","")
            msg = args["message"]
            if webhook:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.post(webhook, json={"content":msg})
                return f"Discord webhook: {r.status_code}"
            elif token:
                channel = args.get("channel","") or creds.get("channel_id","")
                async with httpx.AsyncClient(timeout=15,headers={"Authorization":f"Bot {token}"}) as c:
                    r = await c.post(f"https://discord.com/api/channels/{channel}/messages",json={"content":msg})
                return f"Discord bot: {r.status_code}"
            return "Set webhook_url or bot_token in Discord integration."

        elif name == "line_notify":
            creds = get_integration("line")
            if not creds: return "Line not configured."
            token = creds.get("notify_token","")
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post("https://notify-api.line.me/api/notify",
                                 headers={"Authorization":f"Bearer {token}"},
                                 data={"message":args["message"]})
            return f"Line Notify: {r.json().get('message','sent')}"

        elif name == "facebook_post":
            creds = get_integration("facebook")
            if not creds: return "Facebook not configured."
            token = creds.get("access_token",""); page_id = args.get("page_id","") or creds.get("page_id","me")
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"https://graph.facebook.com/v19.0/{page_id}/feed",
                                 params={"message":args["message"],"access_token":token})
            return f"Facebook [{r.status_code}]: {r.text[:300]}"

        elif name == "call_integration":
            svc_name = args.get("integration_name","")
            conn2 = sqlite3.connect(DB_PATH); cur = conn2.cursor()
            cur.execute("SELECT credentials FROM integrations WHERE name=? AND enabled=1 LIMIT 1",(svc_name,))
            row = cur.fetchone(); conn2.close()
            if not row: return f"Integration '{svc_name}' not found."
            creds = json.loads(row[0]); base = creds.get("base_url","")
            if not base: return "Integration has no base_url."
            endpoint = args.get("endpoint",""); method = args.get("method","GET")
            api_key  = creds.get("api_key","")
            headers  = {"Authorization":f"Bearer {api_key}"} if api_key else {}
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.request(method, base.rstrip("/")+"/"+endpoint.lstrip("/"),
                                    headers=headers, json=args.get("body"))
            try: return json.dumps(r.json(), ensure_ascii=False, indent=2)[:3000]
            except: return r.text[:3000]

        return f"[Unknown tool: {name}]"
    except Exception as e:
        return f"[Tool error: {name}] {type(e).__name__}: {e}"

# ── Think-tag parser ──────────────────────────────────────────────────────────
def parse_think_stream(raw: str, state: dict) -> list:
    events = []; buf = state.get("buf","") + raw; mode = state.get("mode","text")
    while buf:
        if mode == "text":
            idx = buf.find("<think>")
            if idx == -1:
                partial_start = max(0,len(buf)-7); partial = buf[partial_start:]
                if "<think>"[:len(partial)] == partial and len(partial)<7:
                    events.append(("text",buf[:partial_start])); buf=partial; break
                else: events.append(("text",buf)); buf=""; break
            else:
                if idx>0: events.append(("text",buf[:idx]))
                buf=buf[idx+7:]; mode="think"; events.append(("think_start",""))
        else:
            idx = buf.find("</think>")
            if idx == -1:
                partial_start=max(0,len(buf)-8); partial=buf[partial_start:]
                if "</think>"[:len(partial)]==partial and len(partial)<8:
                    if buf[:partial_start]: events.append(("think",buf[:partial_start]))
                    buf=partial; break
                else: events.append(("think",buf)); buf=""; break
            else:
                if idx>0: events.append(("think",buf[:idx]))
                buf=buf[idx+8:]; mode="text"; events.append(("think_end",""))
    state["buf"]=buf; state["mode"]=mode
    return events

# ── Dedicated streaming client (separate from shared _client pool) ────────────
# Adaptive timeouts:
#   FIRST chunk gets generous timeout (cold-start of big models can take 60-150s
#   for prompt processing before first token).
#   AFTER first chunk, model is warm — any stall is real, fail fast.
STREAM_READ_TIMEOUT_S = 420.0          # absolute max per HTTP read — extended for big prompts on local 33B
FIRST_CHUNK_TIMEOUT_S = 360.0          # 6min cold-start — covers large prompt eval on nemotron3:33b
NEXT_CHUNK_TIMEOUT_S  = 90.0           # warm model — slightly more generous for slow GPUs

def _make_stream_client():
    return httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=STREAM_READ_TIMEOUT_S, write=30.0, pool=10.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )

# ── Streaming helper ──────────────────────────────────────────────────────────
async def stream_ollama_chat(payload: dict, base_url: str, api_key: str = ""):
    headers = {}
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    think_state = {"mode":"text","buf":""}; think_start_time = None
    last_keepalive = time.time()
    first_token_received = False   # toggles when we get any actual content

    try:
        async with _make_stream_client() as sc:
            async with sc.stream("POST", f"{base_url}/api/chat", json=payload,
                                 headers=headers) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    yield json.dumps({"type":"error","msg":f"Ollama {resp.status_code}: {body[:300].decode()}"})
                    yield json.dumps({"type":"done"})
                    return

                # Heartbeat to client so the watchdog stays awake during cold-start
                yield json.dumps({"type":"keepalive","note":"warming"})

                aiter = resp.aiter_lines()
                _pending = None
                _wait_started = time.time()
                while True:
                    # Choose timeout based on warm/cold state
                    line_timeout = NEXT_CHUNK_TIMEOUT_S if first_token_received else FIRST_CHUNK_TIMEOUT_S
                    # TASK-KEEPING WATCHDOG (same proven pattern as the relay fix):
                    # heartbeat every 8s WITHOUT cancelling the pending read — local-model
                    # prompt eval can be silent 30-80s+ per step and the client must know
                    # the channel is alive whether it talks to us directly or via relay.
                    if _pending is None:
                        _pending = asyncio.ensure_future(aiter.__anext__())
                        _wait_started = time.time()
                    try:
                        _done, _ = await asyncio.wait({_pending}, timeout=8.0)
                    except (GeneratorExit, asyncio.CancelledError):
                        try: _pending.cancel()
                        except Exception: pass
                        return
                    if not _done:
                        if time.time() - _wait_started > line_timeout:
                            try: _pending.cancel()
                            except Exception: pass
                            phase = "หลังเริ่ม stream" if first_token_received else "ก่อน first token (cold start)"
                            yield json.dumps({"type":"error","msg":f"⏳ Model timeout {int(line_timeout)}s ({phase}) — ตัดการเชื่อมต่อ. ลองคำถามสั้นลง / restart Ollama / เปลี่ยน model"})
                            yield json.dumps({"type":"done"})
                            return
                        yield json.dumps({"type":"keepalive","note":"eval"})
                        last_keepalive = time.time()
                        continue
                    _task = _pending; _pending = None
                    try:
                        line = _task.result()
                    except StopAsyncIteration:
                        break
                    except (GeneratorExit, asyncio.CancelledError):
                        return
                    if not line: continue
                    try:
                        data = json.loads(line); msg = data.get("message",{})
                        raw = msg.get("content","")
                        thinking = msg.get("thinking", "")
                        if thinking:
                            first_token_received = True
                            yield json.dumps({"type":"think","text":thinking})
                        if raw:
                            first_token_received = True
                            for etype, etext in parse_think_stream(raw, think_state):
                                if etype=="think_start": think_start_time=time.time(); yield json.dumps({"type":"think_start"})
                                elif etype=="think" and etext: yield json.dumps({"type":"think","text":etext})
                                elif etype=="think_end":
                                    elapsed=round(time.time()-(think_start_time or time.time()),1)
                                    yield json.dumps({"type":"think_end","elapsed":elapsed})
                                elif etype=="text" and etext: yield json.dumps({"type":"text","text":etext})

                        if msg.get("tool_calls"):
                            first_token_received = True
                            yield json.dumps({"type":"__tool_calls__","calls":msg["tool_calls"]})

                        if data.get("done"):
                            # Flush any remaining buffer
                            if think_state["buf"]:
                                rest = think_state["buf"]
                                if think_state["mode"]=="text" and rest: yield json.dumps({"type":"text","text":rest})
                                elif think_state["mode"]=="think" and rest: yield json.dumps({"type":"think","text":rest})
                            yield json.dumps({"type":"done"})
                            return

                        # Keepalive ping every 8s during long generations
                        now = time.time()
                        if now - last_keepalive > 8:
                            yield json.dumps({"type":"keepalive"})
                            last_keepalive = now

                    except (GeneratorExit, asyncio.CancelledError):
                        return
                    except Exception as e:
                        yield json.dumps({"type":"error","msg":str(e)})

                # Stream ended without explicit done — still emit done so client knows
                yield json.dumps({"type":"done"})

    except (GeneratorExit, asyncio.CancelledError):
        return
    except httpx.ReadTimeout:
        yield json.dumps({"type":"error","msg":f"⏳ Ollama stream timeout (>{int(STREAM_READ_TIMEOUT_S)}s) — ลองคำถามสั้นกว่านี้"})
        yield json.dumps({"type":"done"})
    except httpx.ConnectError as e:
        yield json.dumps({"type":"error","msg":f"❌ ต่อ Ollama ไม่ได้: {e}"})
        yield json.dumps({"type":"done"})
    except Exception as e:
        yield json.dumps({"type":"error","msg":f"Stream error [{type(e).__name__}]: {e}"})
        yield json.dumps({"type":"done"})

# ── Health / Models ───────────────────────────────────────────────────────────
# P1 perf: listing the active runtime's models is a live network call (~2.3s when
# the runtime is down). /api/health is polled frequently by the SPA, so we serve
# the model list + reachability from a short TTL cache refreshed in the background.
# Health returns instantly and never blocks the event loop on a dead runtime; only
# the very first call per process (cold cache) warms synchronously.
_HEALTH_TTL = 8.0
_HEALTH_CACHE = {"ts": 0.0, "ok": False, "models": []}
_health_refreshing = False

async def _probe_active_models():
    ci = get_active_conn()
    if _LLM_ADAPTER and _ad_is_cloud(ci.get("api_type")):
        try:
            return True, await _ad_list_models(ci["base_url"], ci["api_key"])
        except Exception:
            return False, _ad_fallback_models(ci.get("api_type"))
    base, key = ci["base_url"], ci["api_key"]
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        r = await _client.get(f"{base}/api/tags", timeout=3, headers=headers)
        ok = r.status_code == 200
        return ok, ([m["name"] for m in r.json().get("models", [])] if ok else [])
    except Exception:
        return False, []

async def _refresh_health_cache():
    global _health_refreshing
    if _health_refreshing:
        return
    _health_refreshing = True
    try:
        ok, models = await _probe_active_models()
        _HEALTH_CACHE.update({"ts": time.time(), "ok": ok, "models": models})
    finally:
        _health_refreshing = False

async def _health_cache(force_warm: bool = False):
    """(ok, models) from cache: warm synchronously once when cold, else refresh in
    the background when stale so the request never blocks on the runtime."""
    if _HEALTH_CACHE["ts"] == 0.0 and force_warm:
        await _refresh_health_cache()
    elif time.time() - _HEALTH_CACHE["ts"] > _HEALTH_TTL and not _health_refreshing:
        asyncio.create_task(_refresh_health_cache())
    return _HEALTH_CACHE["ok"], _HEALTH_CACHE["models"]

def _invalidate_health_cache():
    _HEALTH_CACHE["ts"] = 0.0   # next call re-warms (e.g. after switching connection)

@app.get("/api/health")
async def health():
    ok, models = await _health_cache(force_warm=True)
    return {"status":"ok","ollama":ok,"models":models,
            "settings":load_settings(),"active_connection":get_active_conn()}

@app.get("/api/models")
async def get_models():
    ok, models = await _health_cache(force_warm=True)
    if not models and _LLM_ADAPTER:
        models = _ad_fallback_models(get_active_conn().get("api_type"))
    return {"models": models}

class _InstallModelReq(BaseModel):
    base: Optional[str] = None

@app.get("/api/models/scan")
async def api_scan_models():
    """Find every usable local model, no config needed (Ollama + OpenAI-compatible
    servers + loose GGUF files). Backported from AtlasZClaw."""
    try:
        import model_manager as _mm
        return _mm.scan_local_models()
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

@app.post("/api/models/install-elmatadorz")
async def api_install_elmatadorz(req: _InstallModelReq):
    """Install/refresh the ElmatadorZ house model (Ollama Modelfile over a base)."""
    try:
        import model_manager as _mm
        return await asyncio.to_thread(_mm.install_elmatadorz, req.base or _mm.DEFAULT_BASE)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

@app.get("/api/providers")
async def list_providers():
    """Provider presets for one-click cloud API setup in the UI."""
    return {"providers": [
        {"api_type": k, "label": v["label"], "base_url": v["base_url"],
         "fallback_models": v["fallback_models"]}
        for k, v in _AD_PRESETS.items()
    ]}

@app.post("/api/warmup")
async def warmup(model: str=""):
    if not model: model=load_settings().get("default_model","")
    if not model: return {"ok":False}
    base=get_active_base_url(); key=get_active_api_key()
    headers={"Authorization":f"Bearer {key}"} if key else {}
    try:
        r=await _client.post(f"{base}/api/generate",
            json={"model":model,"prompt":"hi","stream":False,"options":{"num_predict":1}},
            timeout=30,headers=headers)
        return {"ok":r.status_code==200,"model":model}
    except Exception as e: return {"ok":False,"error":str(e)}

@app.get("/api/settings")
async def get_settings(): return load_settings()

@app.post("/api/settings")
async def post_settings(req: SettingsReq):
    save_settings(req.model_dump(exclude_none=True))
    _invalidate_health_cache()   # P1: model/connection change → re-warm next health
    return {"success":True,"settings":load_settings()}

# ── Connections CRUD ──────────────────────────────────────────────────────────
@app.get("/api/connections")
async def list_connections():
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT id,name,base_url,api_key,api_type,is_active,created_at FROM connections ORDER BY created_at")
    rows=c.fetchall(); conn.close()
    def _mask_key(k):  # SEC C2: never return full secrets to the client
        if not k: return ""
        return (k[:3]+"…"+k[-4:]) if len(k) > 8 else "***"
    return {"connections":[{"id":r[0],"name":r[1],"base_url":r[2],"api_key":_mask_key(r[3]),
                             "has_key":bool(r[3]),
                             "api_type":r[4],"is_active":bool(r[5]),"created_at":r[6]} for r in rows]}

@app.post("/api/connections")
async def add_connection(req: ConnReq):
    cid=str(uuid.uuid4())
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO connections VALUES(?,?,?,?,?,?,?)",
                 (cid,req.name,req.base_url.rstrip("/"),req.api_key,req.api_type,0,time.time()))
    conn.commit(); conn.close(); return {"id":cid}

@app.post("/api/connections/{cid}/activate")
async def activate_connection(cid: str):
    conn=sqlite3.connect(DB_PATH)
    conn.execute("UPDATE connections SET is_active=0")
    conn.execute("UPDATE connections SET is_active=1 WHERE id=?",(cid,))
    conn.commit(); conn.close()
    _invalidate_health_cache()   # P1: reflect the new runtime's models immediately
    return {"success":True}

@app.delete("/api/connections/{cid}")
async def delete_connection(cid: str):
    if cid=="local": raise HTTPException(400,"Cannot delete default")
    conn=sqlite3.connect(DB_PATH); conn.execute("DELETE FROM connections WHERE id=?",(cid,))
    conn.commit(); conn.close(); return {"success":True}

@app.post("/api/connections/{cid}/models")
async def connection_models(cid: str):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT base_url,api_key FROM connections WHERE id=?",(cid,))
    row=c.fetchone(); conn.close()
    if not row: raise HTTPException(404,"Not found")
    base,key=row[0].rstrip("/"),row[1]
    headers={"Authorization":f"Bearer {key}"} if key else {}
    try:
        r=await _client.get(f"{base}/api/tags",timeout=5,headers=headers)
        return {"models":[m["name"] for m in r.json().get("models",[])],"ok":True}
    except Exception as e: return {"models":[],"ok":False,"error":str(e)}

@app.get("/api/connections/{cid}/ping")
async def ping_connection(cid: str):
    """Proxy ping — browser calls this, backend checks the actual Ollama endpoint.
    Avoids browser CORS / localhost network issues."""
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT base_url,api_key FROM connections WHERE id=?",(cid,))
    row=c.fetchone(); conn.close()
    if not row: return {"ok":False,"latencyMs":0,"models":[],"error":"not found"}
    base,key=row[0].rstrip("/"),row[1]
    headers={"Authorization":f"Bearer {key}"} if key else {}
    t0=time.time()
    try:
        r=await _client.get(f"{base}/api/tags",timeout=httpx.Timeout(5),headers=headers)
        latencyMs=int((time.time()-t0)*1000)
        if not r.is_success: return {"ok":False,"latencyMs":latencyMs,"models":[]}
        models=[m["name"] for m in r.json().get("models",[])]
        return {"ok":True,"latencyMs":latencyMs,"models":models}
    except httpx.TimeoutException: return {"ok":False,"latencyMs":int((time.time()-t0)*1000),"models":[],"error":"timeout"}
    except Exception as e: return {"ok":False,"latencyMs":int((time.time()-t0)*1000),"models":[],"error":str(e)}

# ── Integrations CRUD (social / external services) ────────────────────────────
INTEGRATION_SERVICES = {
    "telegram":  {"name":"Telegram Bot","fields":["bot_token","chat_id"],"icon":"✈️"},
    "discord":   {"name":"Discord","fields":["webhook_url","bot_token","channel_id"],"icon":"🎮"},
    "line":      {"name":"Line Notify","fields":["notify_token"],"icon":"💬"},
    "facebook":  {"name":"Facebook","fields":["access_token","page_id"],"icon":"📘"},
    "github":    {"name":"GitHub","fields":["token","username"],"icon":"🐙"},
    "slack":     {"name":"Slack","fields":["webhook_url","bot_token","channel"],"icon":"💼"},
    "custom":    {"name":"Custom API","fields":["base_url","api_key"],"icon":"🔌"},
}

@app.get("/api/integrations/services")
async def list_services(): return {"services":INTEGRATION_SERVICES}

@app.get("/api/integrations")
async def list_integrations():
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT id,service,name,credentials,enabled,created_at FROM integrations ORDER BY created_at")
    rows=c.fetchall(); conn.close()
    result=[]
    for r in rows:
        creds=json.loads(r[3])
        # Mask secrets
        masked={k:("***"+v[-4:] if v and k in ("token","api_key","bot_token","access_token","notify_token","webhook_url") else v)
                for k,v in creds.items()}
        result.append({"id":r[0],"service":r[1],"name":r[2],"credentials_masked":masked,
                        "enabled":bool(r[4]),"created_at":r[5]})
    return {"integrations":result,"services":INTEGRATION_SERVICES}

@app.post("/api/integrations")
async def add_integration(req: IntegrationReq):
    iid=str(uuid.uuid4())
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO integrations VALUES(?,?,?,?,?,?)",
                 (iid,req.service,req.name,json.dumps(req.credentials),1,time.time()))
    conn.commit(); conn.close(); return {"id":iid}

@app.put("/api/integrations/{iid}")
async def update_integration(iid: str, req: IntegrationReq):
    conn=sqlite3.connect(DB_PATH)
    conn.execute("UPDATE integrations SET service=?,name=?,credentials=? WHERE id=?",
                 (req.service,req.name,json.dumps(req.credentials),iid))
    conn.commit(); conn.close(); return {"success":True}

@app.delete("/api/integrations/{iid}")
async def delete_integration(iid: str):
    conn=sqlite3.connect(DB_PATH); conn.execute("DELETE FROM integrations WHERE id=?",(iid,))
    conn.commit(); conn.close(); return {"success":True}

@app.post("/api/integrations/{iid}/toggle")
async def toggle_integration(iid: str):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT enabled FROM integrations WHERE id=?",(iid,))
    row=c.fetchone()
    if row: conn.execute("UPDATE integrations SET enabled=? WHERE id=?",
                         (0 if row[0] else 1,iid))
    conn.commit(); conn.close(); return {"success":True}

# ── Telegram Bot Engine ───────────────────────────────────────────────────────
TG_API = "https://api.telegram.org/bot{token}/{method}"

async def tg_call(token: str, method: str, **kwargs) -> dict:
    url = TG_API.format(token=token, method=method)
    # Dynamic timeout: Telegram long-poll 'timeout' param needs extra buffer on httpx side
    tg_timeout = kwargs.get("timeout", 0)
    http_timeout = httpx.Timeout(
        connect=10.0,
        read=float(tg_timeout + 15) if tg_timeout else 15.0,
        write=10.0,
        pool=5.0
    )
    async with httpx.AsyncClient(timeout=http_timeout) as c:
        r = await c.post(url, json=kwargs)
    return r.json()

async def tg_send(token: str, chat_id, text: str, parse_mode: str = "",
                  thread_id=None, reply_to=None):
    """
    Send message to Telegram.
    - thread_id: message_thread_id for Forum/Topics groups — MUST be set to reply in correct topic
    - reply_to:  reply_to_message_id to quote the original message
    - parse_mode: '' = plain text (safe default), 'Markdown', or 'HTML'
    """
    if not text:
        text = "..."
    kw: dict = {"chat_id": chat_id, "text": text[:4096]}
    if parse_mode:                      # empty string is invalid — don't include it
        kw["parse_mode"] = parse_mode
    if thread_id:                       # forum topic thread — keep reply in same topic
        kw["message_thread_id"] = thread_id
    if reply_to:                        # quote the message being replied to
        kw["reply_to_message_id"] = reply_to
        kw["allow_sending_without_reply"] = True  # don't fail if original was deleted

    result = await tg_call(token, "sendMessage", **kw)

    # Fallback: if parse failed, retry as plain text
    if not result.get("ok") and parse_mode:
        kw2 = {k: v for k, v in kw.items() if k != "parse_mode"}
        result = await tg_call(token, "sendMessage", **kw2)

    if not result.get("ok"):
        print(f"[TelegramBot] sendMessage failed: {result.get('description','?')} | kw={list(kw.keys())}")
    return result

# ── Obsidian Bridge ──────────────────────────────────────────────────────────

def get_obs_bridge() -> dict | None:
    """Return obsidian_bridge credentials or None."""
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT credentials FROM integrations WHERE service='obsidian_bridge' AND enabled=1 LIMIT 1")
    row = c.fetchone(); conn.close()
    if not row: return None
    return json.loads(row[0])

def obs_check_path(path: str, approved: list[str]) -> bool:
    """Return True if path is under an approved folder."""
    if not approved: return True  # no restriction configured
    path_clean = path.lstrip("/")
    return any(path_clean.startswith(p.strip("/") + "/") or path_clean == p.strip("/")
               for p in approved if p.strip())

async def obs_api(method: str, path: str, body: str = None, cfg: dict = None) -> dict:
    """
    Call Obsidian Local REST API via tunnel.
    Returns {"ok": bool, "data": str|dict, "status": int}
    """
    if cfg is None: cfg = get_obs_bridge()
    if not cfg: return {"ok": False, "data": "❌ ยังไม่ได้ตั้งค่า Obsidian Bridge", "status": 0}

    tunnel = cfg.get("tunnel_url","").rstrip("/")
    api_key = cfg.get("api_key","")
    if not tunnel: return {"ok": False, "data": "❌ tunnel_url ว่างเปล่า", "status": 0}

    url = f"{tunnel}/vault/{path.lstrip('/')}" if path else f"{tunnel}/vault/"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "text/markdown"}

    try:
        async with httpx.AsyncClient(timeout=20) as cx:
            if method == "GET":
                r = await cx.get(url, headers=headers)
            elif method == "PUT":
                r = await cx.put(url, content=(body or "").encode(), headers=headers)
            elif method == "POST":
                r = await cx.post(url, content=(body or "").encode(), headers=headers)
            elif method == "DELETE":
                r = await cx.delete(url, headers=headers)
            elif method == "SEARCH":
                r = await cx.post(f"{tunnel}/search/simple/",
                                  json={"query": path, "contextLength": 200},
                                  headers={"Authorization": f"Bearer {api_key}"})
            else:
                return {"ok": False, "data": f"Unknown method: {method}", "status": 0}

        if r.status_code in (200, 201, 204):
            try:
                data = r.json()
            except Exception:
                data = r.text
            return {"ok": True, "data": data, "status": r.status_code}
        else:
            return {"ok": False, "data": f"HTTP {r.status_code}: {r.text[:200]}", "status": r.status_code}

    except httpx.ConnectError:
        return {"ok": False, "data": "❌ เชื่อมต่อ Tunnel ไม่ได้ — ตรวจสอบว่า Ngrok/Cloudflare กำลังรันอยู่", "status": 0}
    except httpx.TimeoutException:
        return {"ok": False, "data": "❌ Timeout — Obsidian หรือ Tunnel ไม่ตอบสนอง", "status": 0}
    except Exception as e:
        return {"ok": False, "data": f"❌ Error: {repr(e)}", "status": 0}

async def tg_handle_obs_command(token, chat_id, text, username, thread_id, msg_id) -> bool:
    """
    Handle Obsidian Bridge commands. Returns True if command was handled.
    Commands: /note /search /write /append /ls /mkdir /del /vault
    """
    cfg = get_obs_bridge()
    approved = [p.strip() for p in cfg.get("approved_paths","").split(",") if p.strip()] if cfg else []

    async def reply(msg):
        await tg_send(token, chat_id, msg, thread_id=thread_id, reply_to=msg_id)

    # ── /vault — show vault status ──────────────────────────────────────────
    if text == "/vault":
        if not cfg:
            await reply("❌ ยังไม่ได้ตั้งค่า Obsidian Bridge\nไปที่ Connections → Integrations → Add Obsidian Bridge")
            return True
        r = await obs_api("GET", "", cfg=cfg)
        if r["ok"]:
            files = r["data"]
            if isinstance(files, dict): files = files.get("files", [])
            count = len(files) if isinstance(files, list) else "?"
            paths_str = "\n".join(f"  • {p}" for p in approved) if approved else "  ทั้งหมด (ไม่จำกัด)"
            await reply(f"🗄️ Obsidian Vault เชื่อมต่อแล้ว\n\nไฟล์ทั้งหมด: {count} files\n\nFolder ที่อนุมัติ:\n{paths_str}\n\nCommands:\n/note <path> — อ่านโน้ต\n/search <query> — ค้นหา\n/write <path> | <content> — เขียน/แก้ไข\n/append <path> | <text> — เพิ่มข้อความ\n/ls [folder] — ดูไฟล์\n/del <path> — ลบ (ต้องยืนยัน)")
        else:
            await reply(f"❌ เชื่อมต่อ Vault ไม่ได้\n{r['data']}")
        return True

    # ── /note <path> — read note ────────────────────────────────────────────
    if text.startswith("/note "):
        path = text[6:].strip()
        if not path.endswith(".md"): path += ".md"
        if approved and not obs_check_path(path, approved):
            await reply(f"🚫 ไม่มีสิทธิ์เข้าถึง: {path}\nFolder ที่อนุมัติ: {', '.join(approved)}")
            return True
        r = await obs_api("GET", path, cfg=cfg)
        if r["ok"]:
            content = r["data"] if isinstance(r["data"], str) else json.dumps(r["data"])
            if len(content) > 3800:
                content = content[:3800] + f"\n\n... (ตัดที่ 3800 chars จากทั้งหมด {len(content)} chars)"
            await reply(f"📄 {path}\n\n{content}")
        else:
            await reply(f"❌ อ่านโน้ตไม่ได้\n{r['data']}")
        return True

    # ── /search <query> — search notes ─────────────────────────────────────
    if text.startswith("/search "):
        query = text[8:].strip()
        r = await obs_api("SEARCH", query, cfg=cfg)
        if r["ok"]:
            results = r["data"] if isinstance(r["data"], list) else []
            if not results:
                await reply(f"🔍 ไม่พบผลลัพธ์สำหรับ: {query}")
            else:
                # Filter to approved paths
                if approved:
                    results = [x for x in results if obs_check_path(x.get("filename",""), approved)]
                lines = []
                for item in results[:10]:
                    fn = item.get("filename","?")
                    ctx = item.get("context","")
                    lines.append(f"📄 {fn}\n   {ctx[:120].strip()}")
                await reply(f"🔍 ค้นหา: {query} — {len(results)} ผลลัพธ์\n\n" + "\n\n".join(lines))
        else:
            await reply(f"❌ ค้นหาไม่ได้\n{r['data']}")
        return True

    # ── /write <path> | <content> — create/overwrite ───────────────────────
    if text.startswith("/write "):
        rest = text[7:].strip()
        if "|" not in rest:
            await reply("📝 รูปแบบ: /write <path> | <content>\nตัวอย่าง: /write Notes/todo.md | - ซื้อของ")
            return True
        path, content = rest.split("|", 1)
        path = path.strip(); content = content.strip()
        if not path.endswith(".md"): path += ".md"
        if approved and not obs_check_path(path, approved):
            await reply(f"🚫 ไม่มีสิทธิ์เขียนไปที่: {path}")
            return True
        r = await obs_api("PUT", path, body=content, cfg=cfg)
        if r["ok"]:
            await reply(f"✅ บันทึกแล้ว: {path}\n({len(content)} chars)")
        else:
            await reply(f"❌ เขียนไม่ได้\n{r['data']}")
        return True

    # ── /append <path> | <text> — append to note ───────────────────────────
    if text.startswith("/append "):
        rest = text[8:].strip()
        if "|" not in rest:
            await reply("📎 รูปแบบ: /append <path> | <text>")
            return True
        path, content = rest.split("|", 1)
        path = path.strip(); content = "\n" + content.strip()
        if not path.endswith(".md"): path += ".md"
        if approved and not obs_check_path(path, approved):
            await reply(f"🚫 ไม่มีสิทธิ์เขียนไปที่: {path}")
            return True
        r = await obs_api("POST", path, body=content, cfg=cfg)
        if r["ok"]:
            await reply(f"✅ เพิ่มข้อมูลแล้ว: {path}")
        else:
            await reply(f"❌ Append ไม่ได้\n{r['data']}")
        return True

    # ── /ls [folder] — list files ──────────────────────────────────────────
    if text.startswith("/ls"):
        folder = text[3:].strip().strip("/")
        list_path = folder + "/" if folder else ""
        r = await obs_api("GET", list_path, cfg=cfg)
        if r["ok"]:
            data = r["data"]
            files = data.get("files", data) if isinstance(data, dict) else data
            if isinstance(files, list):
                if approved:
                    files = [f for f in files if obs_check_path(f if isinstance(f,str) else f.get("path",""), approved)]
                names = [f if isinstance(f,str) else f.get("path","?") for f in files]
                # Group by folder
                folders_set = sorted(set(n.split("/")[0] for n in names if "/" in n))
                root_files = sorted(n for n in names if "/" not in n)
                lines = [f"📁 {fd}/" for fd in folders_set] + [f"📄 {fn}" for fn in root_files]
                display = f"📂 {'/' + folder if folder else 'Vault Root'} — {len(names)} items\n\n" + "\n".join(lines[:50])
                if len(lines) > 50: display += f"\n...และอีก {len(lines)-50} รายการ"
                await reply(display)
            else:
                await reply(f"📂 {json.dumps(data)[:500]}")
        else:
            await reply(f"❌ ดูไฟล์ไม่ได้\n{r['data']}")
        return True

    # ── /del <path> — delete with confirmation ─────────────────────────────
    if text.startswith("/del "):
        path = text[5:].strip()
        if not path.endswith(".md"): path += ".md"
        if approved and not obs_check_path(path, approved):
            await reply(f"🚫 ไม่มีสิทธิ์ลบ: {path}")
            return True
        # Ask for confirmation via follow-up
        confirm_key = f"del_confirm:{path}"
        _tg_status.setdefault("_pending", {})[f"{chat_id}:{thread_id}"] = {"action":"del","path":path}
        await reply(f"⚠️ ยืนยันการลบ?\n📄 {path}\n\nพิมพ์ /confirm เพื่อยืนยัน หรือ /cancel เพื่อยกเลิก")
        return True

    # ── /confirm — confirm pending action ──────────────────────────────────
    if text == "/confirm":
        pending = _tg_status.get("_pending", {}).get(f"{chat_id}:{thread_id}")
        if pending and pending.get("action") == "del":
            path = pending["path"]
            del _tg_status["_pending"][f"{chat_id}:{thread_id}"]
            r = await obs_api("DELETE", path, cfg=cfg)
            if r["ok"]:
                await reply(f"🗑️ ลบแล้ว: {path}")
            else:
                await reply(f"❌ ลบไม่ได้\n{r['data']}")
        else:
            await reply("ไม่มีคำสั่งที่รอยืนยัน")
        return True

    # ── /cancel ─────────────────────────────────────────────────────────────
    if text == "/cancel":
        _tg_status.get("_pending", {}).pop(f"{chat_id}:{thread_id}", None)
        await reply("✅ ยกเลิกแล้ว")
        return True

    return False  # not an obs command

async def tg_set_commands(token: str):
    has_obs = get_obs_bridge() is not None
    cmds = [
        {"command": "start",  "description": "เริ่มต้นใช้งาน"},
        {"command": "help",   "description": "แสดงคำสั่งทั้งหมด"},
        {"command": "clear",  "description": "ล้างประวัติการสนทนา"},
        {"command": "status", "description": "ดูสถานะ bot"},
        {"command": "model",  "description": "ดู model ที่ใช้อยู่"},
    ]
    if has_obs:
        cmds += [
            {"command": "vault",  "description": "🗄️ ดูสถานะ Obsidian Vault"},
            {"command": "note",   "description": "📄 อ่านโน้ต: /note <path>"},
            {"command": "search", "description": "🔍 ค้นหาโน้ต: /search <query>"},
            {"command": "write",  "description": "✏️ เขียนโน้ต: /write <path> | <content>"},
            {"command": "append", "description": "📎 เพิ่มข้อความ: /append <path> | <text>"},
            {"command": "ls",     "description": "📂 ดูไฟล์: /ls [folder]"},
            {"command": "del",    "description": "🗑️ ลบโน้ต: /del <path>"},
        ]
    await tg_call(token, "setMyCommands", commands=cmds)

def tg_load_session(session_key: str, bot_token: str) -> list:
    """session_key = chat_id for DMs, chat_id:thread_id for forum topics."""
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT history FROM telegram_sessions WHERE chat_id=?", (session_key,))
    row = c.fetchone(); conn.close()
    return json.loads(row[0]) if row else []

def tg_save_session(session_key: str, bot_token: str, history: list, username: str = ""):
    """session_key = chat_id for DMs, chat_id:thread_id for forum topics."""
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""INSERT INTO telegram_sessions(chat_id,bot_token,username,history,created_at,updated_at)
                 VALUES(?,?,?,?,?,?)
                 ON CONFLICT(chat_id) DO UPDATE SET
                 history=excluded.history, updated_at=excluded.updated_at""",
              (session_key, bot_token, username, json.dumps(history[-40:]), time.time(), time.time()))
    conn.commit(); conn.close()

# ── Telegram reply protocol adapter ───────────────────────────────────────────
# The bot reuses the globally-active connection, which may be an Ollama endpoint
# (POST /api/chat, reply in message.content) OR an OpenAI-compatible endpoint
# (llama.cpp/OpenAI/etc: POST /v1/chat/completions, reply in
# choices[0].message.content). The reply path used to hardcode the Ollama shape,
# so with an OpenAI-style active connection every reply hit /v1/api/chat -> 404.
# These pure helpers pick the right protocol; they are unit-tested offline.
def _tg_is_openai(base_url: str, api_type: str) -> bool:
    at = (api_type or "").lower().strip()
    if at == "ollama":
        return False
    if at in ("openai", "openai-compatible", "openai_compatible", "llamacpp",
              "llama.cpp", "llama_cpp", "vllm", "openrouter", "groq", "custom"):
        return True
    # Fallback to the /v1 base-url convention when api_type is unknown/blank.
    return base_url.rstrip("/").endswith("/v1")

def _tg_build_request(base_url: str, api_type: str, model: str, messages: list):
    """Return (url, payload) for the active connection's chat protocol."""
    base = (base_url or "").rstrip("/")
    if _tg_is_openai(base, api_type):
        return (f"{base}/chat/completions",
                {"model": model, "messages": messages, "stream": False,
                 "temperature": 0.7, "max_tokens": 1024})
    return (f"{base}/api/chat",
            {"model": model, "messages": messages, "stream": False,
             "options": {"temperature": 0.7, "num_ctx": 2048}})

def _tg_extract_reply(data) -> str:
    """Pull assistant text from either OpenAI or Ollama response shape."""
    if not isinstance(data, dict):
        return ""
    ch = data.get("choices")
    if isinstance(ch, list) and ch:
        first = ch[0] if isinstance(ch[0], dict) else {}
        msg = first.get("message") or {}
        if msg.get("content"):
            return msg["content"].strip()
        if first.get("text"):
            return first["text"].strip()
    msg = data.get("message") or {}
    return (msg.get("content", "").strip() if isinstance(msg, dict) else "") \
        or data.get("response", "").strip()

async def tg_ai_reply(token: str, chat_id, user_text: str, username: str) -> str:
    """
    Send user message to Ollama and return reply.
    Session key is always str(chat_id) — no topic/thread separation.
    """
    session_key = str(chat_id)

    try:
        conn_info = get_active_conn()
        base_url = conn_info["base_url"].rstrip("/")
        model = get_active_model()

        # Fallback: query Ollama for first available model
        if not model:
            try:
                async with httpx.AsyncClient(timeout=10) as cx:
                    rr = await cx.get(f"{base_url}/api/tags")
                    tags = rr.json().get("models", [])
                    model = tags[0]["name"] if tags else ""
            except Exception:
                pass
        if not model:
            return "❌ ไม่มี AI model — กรุณาเลือก model ที่ SkynetClaw และ reload หน้า"

        # Load per-topic session history
        history = tg_load_session(session_key, token)
        history.append({"role": "user", "content": user_text})

        now_dt = time.strftime("%Y-%m-%d %H:%M +07:00",
                               time.localtime(time.time() + 7*3600))

        # Auto-inject Obsidian context if query looks note-related
        obs_context = ""
        obs_cfg = get_obs_bridge()
        if obs_cfg:
            note_keywords = ["note", "โน้ต", "vault", "obsidian", "ไฟล์", "บันทึก", "เอกสาร", "อ่าน", "ค้นหา"]
            if any(kw in user_text.lower() for kw in note_keywords):
                sr = await obs_api("SEARCH", user_text[:100], cfg=obs_cfg)
                if sr["ok"] and isinstance(sr["data"], list) and sr["data"]:
                    top = sr["data"][:3]
                    approved = [p.strip() for p in obs_cfg.get("approved_paths","").split(",") if p.strip()]
                    if approved:
                        top = [x for x in top if obs_check_path(x.get("filename",""), approved)]
                    snippets = []
                    for item in top[:3]:
                        fn = item.get("filename","?")
                        ctx = item.get("context","").strip()
                        snippets.append(f"[{fn}]: {ctx[:300]}")
                    if snippets:
                        obs_context = "\n\n=== Obsidian Vault Context ===\n" + "\n\n".join(snippets) + "\n=== End Context ==="

        system_prompt = (
            f"คุณคือ SkynetClaw AI — Autonomous Intelligent Agent ทรงพลัง\n"
            f"กำลังตอบผ่าน Telegram ให้ @{username or 'Commander'}\n"
            f"เวลาปัจจุบัน (Bangkok): {now_dt}\n"
            f"Model: {model}\n"
            f"Obsidian Bridge: {'เชื่อมต่อแล้ว' if obs_cfg else 'ยังไม่ได้เชื่อมต่อ'}\n\n"
            f"กฎการตอบ:\n"
            f"- ตอบกระชับ ตรงประเด็น เหมาะกับ Telegram\n"
            f"- ใช้ plain text เป็นหลัก\n"
            f"- ถ้าถามข้อมูล real-time (ราคาทอง หุ้น ฯลฯ) ให้แนะนำให้เปิด Internet ใน SkynetClaw\n"
            f"- Genesis Mind คือระบบ Cognitive OS ของ ElmatadorZ — First Principle + System Thinking"
            f"{obs_context}"
        )

        messages = [{"role": "system", "content": system_prompt}] + history[-20:]
        _api_type = conn_info.get("api_type", "")
        url, payload = _tg_build_request(base_url, _api_type, model, messages)
        api_key = conn_info.get("api_key", "") or ""
        headers = ({"Authorization": f"Bearer {api_key}"}
                   if (api_key and _tg_is_openai(base_url, _api_type)) else {})

        print(f"[TelegramBot] Calling model={model} via {url} session={session_key}")
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=180, write=10, pool=5)
        ) as cx:
            r = await cx.post(url, json=payload, headers=headers)

        # Parse response safely
        try:
            d = r.json()
        except Exception:
            return f"❌ AI backend returned non-JSON (status {r.status_code}): {r.text[:100]}"

        if r.status_code != 200:
            _err = (d.get("error", r.text[:100]) if isinstance(d, dict) else r.text[:100])
            return f"❌ AI backend error {r.status_code}: {_err}"

        reply = _tg_extract_reply(d) or "❌ AI ไม่ตอบสนอง"

        # Save updated history
        history.append({"role": "assistant", "content": reply})
        tg_save_session(session_key, token, history, username)
        print(f"[TelegramBot] Reply OK ({len(reply)} chars) session={session_key}")
        return reply

    except httpx.ReadTimeout:
        return "⏳ AI ใช้เวลานานเกินไป (>180s) — ลองถามใหม่หรือถามสั้นกว่านี้ครับ"
    except httpx.ConnectError:
        return f"❌ เชื่อมต่อ AI backend ไม่ได้ — ตรวจสอบว่า runtime กำลังรันอยู่ที่ {get_active_conn().get('base_url','?')}"
    except Exception as e:
        err = repr(e)[:200]
        print(f"[TelegramBot] tg_ai_reply exception: {err}")
        return f"⚠️ AI Error: {err}"

# ── Telegram task execution (owner-gated, safe tool subset) ───────────────────
# The bot runs INSIDE this backend, so it drives the agent engine directly — no
# tunnel/Local Agent needed. Execution is (1) owner-only and (2) restricted to a
# safe tool subset: files in the workspace + web + Obsidian + read-only data.
# NO shell/code/package/dev-server, enforced hard at the agent exec choke point
# via AgentRunReq.tool_allow (independent of SKYNET_ENABLE_EXEC).
_TG_SAFE_TOOLS = [
    "read_file", "read_document", "write_file", "edit_file", "list_files",
    "find_files", "grep_search", "file_info", "create_folder",
    "get_current_datetime",
    "web_search", "http_request", "get_news", "build_news_report",
    "get_gold_price", "get_crypto_price", "get_forex_rate", "download_file",
    "obsidian_list_notes", "obsidian_read_note", "obsidian_write_note",
    "obsidian_search", "search_obsidian", "read_obsidian_note", "write_obsidian_note",
]

def _tg_integration_row(token: str):
    """Return (iid, creds_dict) for the telegram integration owning this token."""
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id, credentials FROM integrations WHERE service='telegram'")
        rows = c.fetchall(); conn.close()
        for iid, raw in rows:
            creds = json.loads(raw or "{}")
            if creds.get("bot_token", "") == token:
                return iid, creds
    except Exception as e:
        print(f"[TelegramBot] integration lookup failed: {e}")
    return None, {}

def tg_owner_ids(token: str) -> set:
    """Set of authorized Telegram user-ids (str) allowed to run tasks."""
    _iid, creds = _tg_integration_row(token)
    raw = str(creds.get("owner_ids", "") or "")
    return {p.strip() for p in raw.split(",") if p.strip()}

def tg_set_owner(token: str, uid) -> bool:
    """Trust-on-first-use claim: set uid as owner only if none is set yet."""
    iid, creds = _tg_integration_row(token)
    if iid is None:
        return False
    if str(creds.get("owner_ids", "") or "").strip():
        return False  # already claimed — refuse silent takeover
    creds["owner_ids"] = str(uid)
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE integrations SET credentials=? WHERE id=?",
                  (json.dumps(creds), iid))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"[TelegramBot] set_owner failed: {e}")
        return False

def _tg_workspace() -> str:
    """Dedicated, isolated workspace folder for Telegram-triggered agent runs."""
    p = Path(__file__).resolve().parent.parent / "telegram_workspace"
    try: p.mkdir(parents=True, exist_ok=True)
    except Exception: pass
    return str(p)

async def tg_run_agent(task: str, model: str) -> str:
    """Drive the real agent engine (safe subset) in-process via the local
    /api/agent/run SSE endpoint; collect a Telegram-sized text summary."""
    payload = {
        "task": task,
        "max_steps": 12,
        "tool_allow": _TG_SAFE_TOOLS,
        "workspace_folder": _tg_workspace(),
    }
    if model:
        payload["model"] = model
    text_parts, tools_used, blocked = [], [], []
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=600, write=10, pool=5)
        ) as cx:
            async with cx.stream("POST", "http://127.0.0.1:8766/api/agent/run",
                                 json=payload) as r:
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except Exception:
                        continue
                    t = ev.get("type")
                    if t == "text":
                        text_parts.append(ev.get("text", ""))
                    elif t == "agent_tool_call":
                        tools_used.append(ev.get("name", "?"))
                    elif t == "agent_tool_skip" and ev.get("reason") == "not_allowed":
                        blocked.append(ev.get("name", "?"))
                    elif t == "agent_complete":
                        if ev.get("summary"):
                            text_parts.append("\n" + str(ev["summary"]))
                    elif t == "agent_stuck":
                        text_parts.append("\n⚠️ " + str(ev.get("text", "")))
    except Exception as e:
        return f"⚠️ รันงานไม่สำเร็จ: {repr(e)[:200]}"
    body = "".join(text_parts).strip() or "(งานเสร็จ แต่ไม่มีผลลัพธ์ข้อความ)"
    footer = ""
    if tools_used:
        footer += f"\n\n🔧 tools: {', '.join(tools_used[:12])}"
    if blocked:
        footer += f"\n🛡 บล็อก (นอกชุดปลอดภัย): {', '.join(sorted(set(blocked)))}"
    return body + footer

def _tg_activity(kind: str, chat_id, username: str, text: str):
    """Mirror Telegram activity onto the app's runtime event bus so the operator
    SEES (and can later review) what arrived/ran via Telegram. Live via
    /api/house/events; replayable via /api/house/events/recent. Best-effort."""
    try:
        house_sync.publish("telegram_activity", {
            "kind": kind,                      # in | run | out
            "user": username or "",
            "chat_id": str(chat_id),
            "text": (text or "")[:500],
        }, source="telegram")
    except Exception:
        pass

async def tg_polling_loop(token: str, bot_name: str):
    """Long-polling loop for Telegram bot."""
    offset = 0
    _tg_status[token] = {"running": True, "bot_name": bot_name, "errors": 0, "msg_count": 0, "started_at": time.time()}
    await tg_set_commands(token)
    print(f"[TelegramBot] @{bot_name} polling started")

    while True:
        try:
            result = await tg_call(token, "getUpdates", offset=offset, timeout=30, allowed_updates=["message"])
            if not result.get("ok"):
                _tg_status[token]["errors"] += 1
                await asyncio.sleep(5)
                continue

            updates = result.get("result", [])
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                if not msg: continue

                chat_id   = msg["chat"]["id"]
                msg_id    = msg.get("message_id")
                # thread_id completely removed — bot replies as plain chat in all
                # group types; never creates new forum topics.
                text      = msg.get("text", "").strip()
                user      = msg.get("from", {})
                username  = user.get("username", "") or user.get("first_name", "")

                if not text: continue

                _tg_status[token]["msg_count"] += 1
                _tg_activity("in", chat_id, username, text)   # mirror inbound to the app

                # ── Handle commands ──────────────────────────────────────────
                if text.startswith("/start"):
                    name = user.get("first_name", "ผู้ใช้")
                    await tg_send(token, chat_id,
                        f"👋 สวัสดีครับ {name}!\n\n"
                        f"🤖 ผมคือ SkynetClaw AI — Autonomous Agent\n"
                        f"พิมพ์ข้อความเพื่อคุยกับ AI ได้เลยครับ\n\n"
                        f"คำสั่ง:\n"
                        f"/help — ดูคำสั่งทั้งหมด\n"
                        f"/clear — ล้างประวัติการสนทนา\n"
                        f"/status — ดูสถานะ\n"
                        f"/model — ดู model ที่ใช้",
                        reply_to=msg_id)
                    continue

                if text.startswith("/help"):
                    await tg_send(token, chat_id,
                        "📖 SkynetClaw Bot Commands\n\n"
                        "/start — เริ่มต้น\n"
                        "/clear — ล้างประวัติการสนทนา\n"
                        "/status — ดูสถานะ AI\n"
                        "/model — ดู model ปัจจุบัน\n\n"
                        "⚙️ สั่งงานจริง (owner เท่านั้น):\n"
                        "/claim_owner — อ้างสิทธิ์เจ้าของ (ครั้งเดียว)\n"
                        "/whoami — ดู id + สถานะสิทธิ์\n"
                        "/run <งาน> — ให้ AI ลงมือทำ (ไฟล์+เว็บ+Obsidian, ไม่มี shell/code)\n\n"
                        "💬 พิมพ์ข้อความอะไรก็ได้เพื่อคุยกับ AI",
                        reply_to=msg_id)
                    continue

                if text.startswith("/clear"):
                    tg_save_session(str(chat_id), token, [], username)
                    await tg_send(token, chat_id, "🗑 ล้างประวัติการสนทนาแล้วครับ",
                                  reply_to=msg_id)
                    continue

                if text.startswith("/status"):
                    st = _tg_status.get(token, {})
                    conn_info = get_active_conn()
                    model = get_active_model()
                    mins = int((time.time()-st.get('started_at',time.time()))/60)
                    await tg_send(token, chat_id,
                        f"🟢 SkynetClaw Status\n\n"
                        f"🤖 Bot: @{bot_name}\n"
                        f"🧠 Model: {model or 'ไม่ได้เลือก'}\n"
                        f"🔌 Server: {conn_info.get('base_url','?')}\n"
                        f"💬 Messages: {st.get('msg_count',0)}\n"
                        f"⏱ Running: {mins} min",
                        reply_to=msg_id)
                    continue

                if text.startswith("/model"):
                    model = get_active_model()
                    await tg_send(token, chat_id,
                        f"🧠 Model ปัจจุบัน: {model or 'ยังไม่ได้เลือก'}",
                        reply_to=msg_id)
                    continue

                # ── Task execution (owner-gated, safe subset) ─────────────────
                _uid = str((user or {}).get("id", ""))
                _owners = tg_owner_ids(token)

                if text.startswith("/whoami"):
                    _is_owner = _uid in _owners
                    await tg_send(token, chat_id,
                        f"🪪 Telegram user-id ของคุณ: `{_uid}`\n"
                        f"เจ้าของที่สั่งงานได้: {', '.join(_owners) if _owners else '(ยังไม่มี — /claim_owner เพื่ออ้างสิทธิ์)'}\n"
                        f"สถานะคุณ: {'✅ owner (สั่งงานได้)' if _is_owner else '⛔ ไม่ใช่ owner'}",
                        parse_mode="Markdown", reply_to=msg_id)
                    continue

                if text.startswith("/claim_owner"):
                    if _owners:
                        await tg_send(token, chat_id,
                            "⛔ มีเจ้าของอยู่แล้ว — เปลี่ยนได้ที่ Connections → Integrations เท่านั้น",
                            reply_to=msg_id)
                    elif tg_set_owner(token, _uid):
                        await tg_send(token, chat_id,
                            f"✅ คุณคือเจ้าของแล้ว (`{_uid}`)\nสั่งงานได้ด้วย `/run <งาน>` — ชุดปลอดภัย (ไฟล์ในเวิร์กสเปซ + เว็บ + Obsidian, ไม่มี shell/code)",
                            parse_mode="Markdown", reply_to=msg_id)
                    else:
                        await tg_send(token, chat_id, "⚠️ ตั้งเจ้าของไม่สำเร็จ", reply_to=msg_id)
                    continue

                if text.startswith(("/run", "/do", "/agent")):
                    _task = text.split(" ", 1)[1].strip() if " " in text else ""
                    if not _owners:
                        await tg_send(token, chat_id,
                            "🔒 ยังไม่ได้ตั้งเจ้าของ — พิมพ์ /claim_owner ก่อน (ครั้งเดียว) เพื่ออ้างสิทธิ์สั่งงาน",
                            reply_to=msg_id)
                        continue
                    if _uid not in _owners:
                        await tg_send(token, chat_id,
                            "⛔ เฉพาะเจ้าของเท่านั้นที่สั่งงานได้", reply_to=msg_id)
                        continue
                    if not _task:
                        await tg_send(token, chat_id,
                            "ใช้: `/run <สิ่งที่ให้ทำ>`\nเช่น `/run สรุปข่าวทองคำวันนี้เป็นไฟล์ gold.md`",
                            parse_mode="Markdown", reply_to=msg_id)
                        continue
                    await tg_send(token, chat_id, f"⚙️ กำลังทำงาน: {_task[:200]}", reply_to=msg_id)
                    _tg_activity("run", chat_id, username, _task)   # command mirrored to the app
                    asyncio.create_task(tg_call(token, "sendChatAction",
                                                chat_id=chat_id, action="typing"))
                    _out = await tg_run_agent(_task, get_active_model())
                    _tg_activity("out", chat_id, username, _out)    # result mirrored to the app
                    if len(_out) > 4000:
                        for i in range(0, len(_out), 4000):
                            await tg_send(token, chat_id, _out[i:i+4000])
                    else:
                        await tg_send(token, chat_id, _out, reply_to=msg_id)
                    continue

                # ── Obsidian Bridge commands ──────────────────────────────────
                if text.startswith(("/vault", "/note ", "/search ", "/write ",
                                    "/append ", "/ls", "/del ", "/confirm", "/cancel")):
                    handled = await tg_handle_obs_command(
                        token, chat_id, text, username, None, msg_id)
                    if handled:
                        continue

                # ── BRAIN UNIFICATION (2026-07-10): a plain message that IS a
                # task (build / decision) gets the same brain as the UI —
                # planner, council, skills — via tg_run_agent, instead of the
                # bare chat path. Owner-gated like /run; everything else stays
                # ordinary chat. Every door into the House meets one mind.
                _route_agent = False
                if _owners and _uid in _owners:
                    try:
                        import task_planner as _tgtp
                        _route_agent = _tgtp.looks_like_build_task(text)
                    except Exception:
                        pass
                    if not _route_agent and _COUNCIL_AVAILABLE and _council is not None:
                        try:
                            _route_agent = _council.looks_like_deliberation_task(text)
                        except Exception:
                            pass
                if _route_agent:
                    await tg_send(token, chat_id, f"🧠 งานนี้เข้าสมองเต็ม (agent): {text[:150]}",
                                  reply_to=msg_id)
                    _tg_activity("run", chat_id, username, text)
                    asyncio.create_task(tg_call(token, "sendChatAction",
                                                chat_id=chat_id, action="typing"))
                    _out = await tg_run_agent(text, get_active_model())
                    _tg_activity("out", chat_id, username, _out)
                    for i in range(0, max(len(_out), 1), 4000):
                        await tg_send(token, chat_id, _out[i:i+4000] or "(no output)",
                                      reply_to=msg_id if i == 0 else None)
                    continue

                # ── Send typing action + AI reply ────────────────────────────
                asyncio.create_task(tg_call(token, "sendChatAction",
                                            chat_id=chat_id, action="typing"))

                reply = await tg_ai_reply(token, chat_id, text, username)
                _tg_activity("out", chat_id, username, reply)   # chat reply mirrored to the app

                # Split long messages (Telegram limit 4096)
                if len(reply) > 4000:
                    chunks = [reply[i:i+4000] for i in range(0, len(reply), 4000)]
                    for idx, chunk in enumerate(chunks):
                        await tg_send(token, chat_id, chunk,
                                      reply_to=msg_id if idx == 0 else None)
                else:
                    await tg_send(token, chat_id, reply, reply_to=msg_id)

        except asyncio.CancelledError:
            _tg_status[token]["running"] = False
            print(f"[TelegramBot] @{bot_name} stopped")
            break
        except httpx.ReadTimeout:
            # Normal for long-polling when no messages arrive — NOT a real error
            print(f"[TelegramBot] @{bot_name} poll timeout (harmless), retrying...")
            await asyncio.sleep(1)
        except Exception as e:
            _tg_status[token]["errors"] += 1
            print(f"[TelegramBot] Error [{type(e).__name__}]: {e}")
            await asyncio.sleep(5)

# Helper to get active model from settings (checks all possible keys)
def get_active_model() -> str:
    s = load_settings()
    return (s.get("model","") or s.get("active_model","") or
            s.get("default_model","") or s.get("obs_model",""))

# ── Telegram Bot Endpoints ────────────────────────────────────────────────────
@app.post("/api/telegram/start-bot/{iid}")
async def tg_start_bot(iid: str):
    conn2 = sqlite3.connect(DB_PATH); c2 = conn2.cursor()
    c2.execute("SELECT credentials FROM integrations WHERE id=? AND service='telegram'",(iid,))
    row = c2.fetchone(); conn2.close()
    if not row: raise HTTPException(404, "Telegram integration not found")
    creds = json.loads(row[0])
    token = creds.get("bot_token","")
    if not token: return {"ok": False, "error": "bot_token missing"}

    # Stop existing task if any
    if token in _tg_tasks and not _tg_tasks[token].done():
        _tg_tasks[token].cancel()
        try: await _tg_tasks[token]
        except asyncio.CancelledError: pass

    # Verify token and get bot name
    try:
        async with httpx.AsyncClient(timeout=10) as c3:
            r = await c3.get(f"https://api.telegram.org/bot{token}/getMe")
        d = r.json()
        if not d.get("ok"): return {"ok": False, "error": d.get("description","Invalid token")}
        bot_name = d["result"].get("username","bot")
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # Start polling task
    task = asyncio.create_task(tg_polling_loop(token, bot_name))
    _tg_tasks[token] = task
    # Persist auto-start flag so bot restarts automatically next time server boots
    conn3 = sqlite3.connect(DB_PATH); c3 = conn3.cursor()
    c3.execute("UPDATE integrations SET tg_auto_start=1 WHERE id=?", (iid,))
    conn3.commit(); conn3.close()
    return {"ok": True, "bot_name": bot_name, "msg": f"@{bot_name} started — พร้อมรับข้อความแล้ว"}

@app.post("/api/telegram/stop-bot/{iid}")
async def tg_stop_bot(iid: str):
    conn2 = sqlite3.connect(DB_PATH); c2 = conn2.cursor()
    c2.execute("SELECT credentials FROM integrations WHERE id=? AND service='telegram'",(iid,))
    row = c2.fetchone()
    # Clear auto-start flag
    c2.execute("UPDATE integrations SET tg_auto_start=0 WHERE id=?", (iid,))
    conn2.commit(); conn2.close()
    if not row: raise HTTPException(404, "Not found")
    token = json.loads(row[0]).get("bot_token","")
    if token in _tg_tasks and not _tg_tasks[token].done():
        _tg_tasks[token].cancel()
        try: await _tg_tasks[token]
        except asyncio.CancelledError: pass
        del _tg_tasks[token]
    _tg_status.pop(token, None)
    return {"ok": True, "msg": "Bot stopped"}

@app.get("/api/telegram/status/{iid}")
async def tg_bot_status(iid: str):
    conn2 = sqlite3.connect(DB_PATH); c2 = conn2.cursor()
    c2.execute("SELECT credentials, tg_auto_start FROM integrations WHERE id=?",(iid,))
    row = c2.fetchone(); conn2.close()
    if not row: raise HTTPException(404, "Not found")
    token = json.loads(row[0]).get("bot_token","")
    auto_start = bool(row[1])
    running = token in _tg_tasks and not _tg_tasks[token].done()
    st = _tg_status.get(token, {})
    return {"running": running, "auto_start": auto_start,
            "bot_name": st.get("bot_name",""), "msg_count": st.get("msg_count",0), "errors": st.get("errors",0)}

@app.post("/api/integrations/{iid}/test")
async def test_integration(iid: str):
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT service,credentials FROM integrations WHERE id=?",(iid,))
    row=c.fetchone(); conn.close()
    if not row: raise HTTPException(404,"Not found")
    svc,creds_raw=row[0],json.loads(row[1])
    try:
        if svc=="telegram":
            token=creds_raw.get("bot_token","")
            async with httpx.AsyncClient(timeout=10) as c2:
                r=await c2.get(f"https://api.telegram.org/bot{token}/getMe")
            d=r.json(); return {"ok":d.get("ok",False),"info":d.get("result",{})}
        elif svc=="discord" and creds_raw.get("webhook_url"):
            async with httpx.AsyncClient(timeout=10) as c2:
                r=await c2.get(creds_raw["webhook_url"])
            return {"ok":r.status_code==200,"status":r.status_code}
        elif svc=="line":
            token=creds_raw.get("notify_token","")
            async with httpx.AsyncClient(timeout=10) as c2:
                r=await c2.get("https://notify-api.line.me/api/status",
                               headers={"Authorization":f"Bearer {token}"})
            return {"ok":r.status_code==200,"info":r.json()}
        elif svc=="github":
            token=creds_raw.get("token","")
            async with httpx.AsyncClient(timeout=10,headers={"Authorization":f"token {token}"}) as c2:
                r=await c2.get("https://api.github.com/user")
            return {"ok":r.status_code==200,"info":r.json().get("login","?")}
        elif svc=="custom":
            base=creds_raw.get("base_url",""); key=creds_raw.get("api_key","")
            hdrs={"Authorization":f"Bearer {key}"} if key else {}
            async with httpx.AsyncClient(timeout=10,headers=hdrs) as c2:
                r=await c2.get(base)
            return {"ok":r.status_code<400,"status":r.status_code}
        return {"ok":True,"msg":"No test available for this service"}
    except Exception as e: return {"ok":False,"error":str(e)}

# ── Real-time Data REST Endpoints ────────────────────────────────────────────
@app.get("/api/realtime/datetime")
async def rt_datetime(timezone: str = "Asia/Bangkok"):
    result = await exec_tool("get_current_datetime", {"timezone": timezone})
    return {"data": result, "ok": True}

@app.get("/api/realtime/crypto")
async def rt_crypto(symbols: str = "bitcoin,ethereum", vs_currency: str = "usd"):
    result = await exec_tool("get_crypto_price", {"symbols": symbols, "vs_currency": vs_currency})
    return {"data": result, "ok": "❌" not in result}

@app.get("/api/realtime/gold")
async def rt_gold(currency: str = "USD"):
    result = await exec_tool("get_gold_price", {"currency": currency})
    return {"data": result, "ok": "❌" not in result}

@app.get("/api/warrant/recent")
async def warrant_recent(limit: int = 50):
    """CEE observation-log read: recent runtime warrant verdicts + the live
    overclaim rate. This is C1 as an auditable runtime property, not philosophy."""
    try:
        import warrant_check as _wc
        rows = _wc.recent(limit=limit)
        n = len(rows); bad = sum(1 for r in rows if r.get("verdict") == "OVERCLAIM")
        return {"ok": True, "total": n, "overclaims": bad,
                "overclaim_rate": round(bad / n, 3) if n else 0.0, "records": rows}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

@app.post("/api/eval/run")
async def eval_run(deterministic_only: bool = False, behavioral: bool = False):
    """Run the quality scoreboard and log the score to the time-series. This is the
    Evaluation loop: a number that says whether the reliability substrate holds, so
    changes can be judged by measurement (paradigm: no capability without its
    governing invariant). `behavioral=true` adds the slow, honest task-reliability
    cases (real agent runs) — which also feed proprioception via agent_runs."""
    try:
        import eval_suite as _es
        rec = await asyncio.to_thread(_es.run_suite, not deterministic_only, behavioral)
        try: house_sync.publish("eval_run", {"score": rec["score"], "behavioral_score": rec.get("behavioral_score"),
                                              "passed": rec["passed"], "total": rec["total"],
                                              "failing": rec["failing"]}, source="eval")
        except Exception: pass
        return {"ok": True, **rec}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

@app.get("/api/eval/history")
async def eval_history(limit: int = 30):
    """The quality time-series + the headline trend (latest score and delta)."""
    try:
        import eval_suite as _es
        return {"ok": True, "trend": _es.trend(), "runs": _es.recent(limit=limit)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

@app.get("/api/realtime/forex")
async def rt_forex(base: str = "USD", targets: str = "THB,EUR,JPY,GBP,CNY,SGD"):
    result = await exec_tool("get_forex_rate", {"base": base, "targets": targets})
    return {"data": result, "ok": "❌" not in result}

@app.get("/api/realtime/news")
async def rt_news(topic: str = "today", max_results: int = 5):
    result = await exec_tool("get_news", {"topic": topic, "max_results": max_results})
    return {"data": result, "ok": "❌" not in result}

# ── Package management ────────────────────────────────────────────────────────
@app.post("/api/packages/install")
async def pkg_install(req: PackageReq):
    result = await exec_tool("install_package",{"package":req.package,"manager":req.manager})
    return {"result":result,"success":"exit 0" in result or "Successfully installed" in result}

@app.get("/api/packages/list")
async def pkg_list(manager: str="pip"):
    if manager=="pip":
        r=subprocess.run([sys.executable,"-m","pip","list","--format=json"],capture_output=True,text=True)
        try: return {"packages":json.loads(r.stdout)}
        except: return {"packages":[]}
    elif manager=="npm":
        r=subprocess.run(["npm","list","-g","--json","--depth=0"],capture_output=True,text=True)
        try: return {"packages":json.loads(r.stdout)}
        except: return {"packages":[]}
    return {"packages":[]}

# ── File system endpoints ─────────────────────────────────────────────────────
@app.get("/api/browse/folder")
async def browse_folder():
    ps="""Add-Type -AssemblyName System.Windows.Forms
$d=New-Object System.Windows.Forms.FolderBrowserDialog
$d.ShowNewFolderButton=$false
if($d.ShowDialog()-eq'OK'){Write-Output $d.SelectedPath}else{Write-Output ''}"""
    try:
        r=subprocess.run(["powershell","-NoProfile","-NonInteractive","-Command",ps],
                         capture_output=True,text=True,timeout=60)
        path=r.stdout.strip(); return {"path":path,"cancelled":path==""}
    except Exception as e:
        try:
            import tkinter as tk; from tkinter import filedialog
            root=tk.Tk(); root.withdraw(); root.attributes("-topmost",True)
            path=filedialog.askdirectory(); root.destroy()
            return {"path":path or "","cancelled":not bool(path)}
        except Exception as e2: raise HTTPException(500,f"Picker failed: {e}/{e2}")

@app.get("/api/browse/file")
async def browse_file(title: str = "Select File", filter: str = "All Files|*.*"):
    """Open OS file picker dialog, returns selected file path."""
    try:
        ps = f"""Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = '{title}'
$d.Filter = '{filter}'
$null = $d.ShowDialog()
Write-Output $d.FileName"""
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
            capture_output=True, text=True, timeout=60)
        path = r.stdout.strip()
        return {"path": path, "cancelled": not bool(path)}
    except Exception as e:
        try:
            import tkinter as tk; from tkinter import filedialog
            root=tk.Tk(); root.withdraw(); root.attributes("-topmost",True)
            path=filedialog.askopenfilename(title=title); root.destroy()
            return {"path": path or "", "cancelled": not bool(path)}
        except Exception as e2: raise HTTPException(500, f"Picker failed: {e}/{e2}")

@app.get("/api/browse/obsidian-vaults")
async def find_obsidian_vaults():
    vaults=[]
    # Obsidian stores its vault registry in the host's config location, which
    # differs per platform. Probe all of them; missing ones are simply skipped.
    _cfgs = [Path(os.environ.get("APPDATA", "")) / "obsidian" / "obsidian.json",
             Path.home() / "AppData" / "Roaming" / "obsidian" / "obsidian.json",          # Windows
             Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json",  # macOS
             Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
             / "obsidian" / "obsidian.json",                                              # Linux
             Path.home() / ".var" / "app" / "md.obsidian.Obsidian" / "config"
             / "obsidian" / "obsidian.json"]                                              # Linux flatpak
    for cfg in _cfgs:
        if cfg.exists():
            try:
                data=json.loads(cfg.read_text(encoding="utf-8"))
                for vid,v in data.get("vaults",{}).items():
                    vp=v.get("path","")
                    if vp and Path(vp).exists(): vaults.append({"id":vid,"path":vp,"name":Path(vp).name})
            except: pass
    return {"vaults":vaults}

@app.post("/api/files/folder-context")
async def folder_context(req: FolderCtxReq):
    p=Path(req.path)
    if not p.exists(): raise HTTPException(400,f"Not found: {req.path}")
    exts=set(e.lower() for e in req.extensions)
    files=[f for f in p.glob("**/*" if req.recursive else "*") if f.is_file() and f.suffix.lower() in exts]
    files.sort(key=lambda x:x.name.lower()); files=files[:req.max_files]
    parts=[]; total_chars=0; skipped=0
    for f in files:
        try:
            content=f.read_text(encoding="utf-8",errors="replace")
            if len(content)>req.max_chars_per_file: content=content[:req.max_chars_per_file]+"…[truncated]"
            try: rel=f.relative_to(p)
            except: rel=f.name
            parts.append(f"### [{rel}]\n{content}"); total_chars+=len(content)
        except: skipped+=1
    combined="\n\n---\n\n".join(parts)
    return {"context":combined,"content":combined,"files_read":len(parts),"file_count":len(parts),
            "files_skipped":skipped,"total_chars":total_chars,"folder":str(p),"folder_name":p.name,
            "file_list":[str(f.relative_to(p)) for f in files]}

@app.get("/api/files/list")
async def files_list(path: str="."):
    try:
        items=[]
        for i in sorted(Path(path).iterdir(),key=lambda x:(x.is_file(),x.name.lower())):
            try: items.append({"name":i.name,"path":str(i),"type":"dir" if i.is_dir() else "file",
                               "size":i.stat().st_size if i.is_file() else 0,"modified":i.stat().st_mtime})
            except: pass
        return {"items":items,"path":str(Path(path).resolve())}
    except Exception as e: raise HTTPException(400,str(e))

@app.get("/api/files/read")
async def files_read(path: str):
    try: return {"content":Path(path).read_text(encoding="utf-8",errors="replace"),"path":path}
    except Exception as e: raise HTTPException(400,str(e))

@app.post("/api/files/write")
async def files_write(req: FileWriteReq):
    try:
        p=Path(req.path); p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(req.content,encoding="utf-8"); return {"success":True}
    except Exception as e: raise HTTPException(400,str(e))

def _exec_enabled() -> bool:
    # SEC C1: arbitrary shell / python execution is OFF by default. The SPA does
    # not use these endpoints; enable explicitly with SKYNET_ENABLE_EXEC=1.
    return os.environ.get("SKYNET_ENABLE_EXEC") == "1"

@app.post("/api/shell")
async def shell_run(req: ShellReq):
    if not _exec_enabled():
        raise HTTPException(403, "shell execution disabled (set SKYNET_ENABLE_EXEC=1 to enable)")
    r=await asyncio.to_thread(lambda: subprocess.run(req.command,shell=True,capture_output=True,text=True,cwd=req.cwd,timeout=30))
    return {"stdout":r.stdout,"stderr":r.stderr,"returncode":r.returncode}

@app.post("/api/code/run")
async def code_run(req: CodeReq):
    if not _exec_enabled():
        raise HTTPException(403, "code execution disabled (set SKYNET_ENABLE_EXEC=1 to enable)")
    with tempfile.NamedTemporaryFile(suffix=".py",mode="w",delete=False,encoding="utf-8") as f:
        f.write(req.code); tmp=f.name
    try:
        r=await asyncio.to_thread(lambda: subprocess.run([sys.executable,tmp],capture_output=True,text=True,timeout=30))
    finally:
        os.unlink(tmp)
    return {"stdout":r.stdout,"stderr":r.stderr,"returncode":r.returncode}

# ── Chat ─────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(req: ChatReq):
    messages=[{"role":m.role,"content":m.content} for m in req.messages]
    # ── Activate workspace folder so write_file/create_folder land in the right place ──
    workspace_resolved_chat = ""
    ws_chat = (req.workspace_folder or "").strip()
    if ws_chat:
        try:
            wp = Path(ws_chat); wp.mkdir(parents=True, exist_ok=True)
            workspace_resolved_chat = str(wp.resolve())
            ACTIVE_WORKSPACE.set(workspace_resolved_chat)
            # Prepend a workspace banner so the model writes to the right folder
            ws_banner = (
                "## WORKSPACE_FOLDER (write all files here)\n"
                f"{workspace_resolved_chat}\n\n"
                "RULES: pass file paths as ABSOLUTE under this folder. "
                "Relative paths are auto-prefixed by the backend. "
                "Never write files outside this folder."
            )
            messages = [{"role":"system","content":ws_banner}] + messages
        except Exception:
            workspace_resolved_chat = ""
    # REALITY GROUNDING — injected UNCONDITIONALLY (not gated on a workspace):
    # workspace files ground "which file?"; operational history grounds
    # "analyze the failures" so it can't answer UNKNOWN while 38 failed runs
    # sit in agent_runs. Answers from the current world, not from language.
    try:
        import reality_context as _rc
        _reality = _rc.build_reality(workspace_resolved_chat or None,
                                     runtime_label=get_active_conn().get("name", ""),
                                     model=get_active_model(),
                                     operational=_rc.build_operational_summary(DB_PATH))
        if _reality:
            messages = [{"role": "system", "content": _reality}] + messages
    except Exception as _rce:
        print(f"[Reality] chat inject skipped: {_rce}")
    if req.system_prompt and not any(m["role"]=="system" for m in messages):
        messages=[{"role":"system","content":req.system_prompt}]+messages
    # === MASTERPIECE: inject ACTUAL datetime + live-data rule into chat too ===
    try:
        _dt_b = _mp_datetime_banner("Asia/Bangkok")
        if _dt_b:
            messages = [{"role":"system","content":_dt_b}] + messages
        _ld_r = _mp_live_data_directive()
        if _ld_r:
            messages = [{"role":"system","content":_ld_r}] + messages
        # SELF-KNOWLEDGE: the agent's own Obsidian vault + which tools reach it
        _vb = _vault_awareness_banner()
        if _vb:
            messages = [{"role":"system","content":_vb}] + messages
    except Exception as _e:
        print(f"[Masterpiece] chat preamble inject failed: {_e}")

    # Discretionary system messages (ecosystem/skills) tracked by identity so a
    # turn-0 context-budget critical (no tool-history to compress) can shed
    # them without touching the caller-supplied system_prompt or banners.
    _discretionary_ids: set = set()

    # === ECOSYSTEM AWARENESS — inject manifest so chat KNOWS its sister apps ===
    # Kills the "I don't know THE_CONTINENTAL_DIVISION.html" filesystem-search behavior
    try:
        import ecosystem_manifest as _em
        _eco_section = _em.render_manifest_for_prompt()
        if _eco_section:
            _eco_msg = {"role": "system", "content": _eco_section}
            messages = [_eco_msg] + messages
            _discretionary_ids.add(id(_eco_msg))
    except Exception as _ee:
        pass  # silent — manifest is optional but recommended

    # === SKILLS AUTO-ROUTER: match user text → auto-inject matched skill prompts ===
    try:
        _last_user = next(
            (m["content"] for m in reversed(messages)
             if isinstance(m, dict) and m.get("role") == "user"),
            ""
        )
        _skill_msgs = _auto_skill_messages(_last_user or "", top_k=2)
        for _sm in _skill_msgs:
            _skill_msg = {"role": "system", "content": _sm["content"]}
            messages = [_skill_msg] + messages
            _discretionary_ids.add(id(_skill_msg))
        if _skill_msgs:
            _names = ", ".join(f"{s['skill_meta']['name']}({s['skill_meta']['score']})"
                               for s in _skill_msgs)
            print(f"[SkillsRouter] /api/chat auto-activated: {_names}")
    except Exception as _e:
        print(f"[SkillsRouter] /api/chat inject failed: {_e}")

    base=get_active_base_url(); key=get_active_api_key()
    # === MASTERPIECE RESOLVE_MODEL — START ===
    _last_user_msg = next((m["content"] for m in reversed(messages) if isinstance(m, dict) and m.get("role")=="user"), "")
    _resolved_model = _mp_resolve_model(req.model, _last_user_msg) or req.model
    # === MASTERPIECE RESOLVE_MODEL — END ===
    # PROTOCOL over MODEL: context window from the connection, not a constant.
    try:
        import context_budget as _cbw
        _acn = get_active_conn() or {}
        _ctx_window = _cbw.resolve_window(_acn, _acn.get("api_type"), _resolved_model, base)
    except Exception:
        _ctx_window = 16384
    payload={"model":_resolved_model,"messages":messages,"stream":True,"keep_alive":"30m","options":{"num_ctx":_ctx_window}}
    if req.use_tools:
        _lu = next((m["content"] for m in reversed(messages) if m.get("role")=="user"), "")
        payload["tools"] = _select_tools_for_task(_lu)
        print(f"[chat] mission tools: {len(payload['tools'])}/{len(BUILTIN_TOOLS)}")

    async def generate():
        try:
            # Re-bind contextvar inside the generator (defensive)
            if workspace_resolved_chat:
                ACTIVE_WORKSPACE.set(workspace_resolved_chat)
            cur = list(messages)
            MAX_ITERS = 10
            consec_failures = 0   # FAILURE-ADAPTATION: a failed action must change the next one

            for iteration in range(MAX_ITERS + 1):
                # ── P0 CONTEXT BUDGET (was only wired into /api/agent/run) ──
                # This loop can run multi-turn tool calls with the full
                # BUILTIN_TOOLS fallback schema and had zero overflow guard.
                # Reproduced in production: 17160 prompt tokens vs num_ctx=16384.
                try:
                    import context_budget as _cb, mission_snapshot as _ms
                    _bdg = _cb.assess(cur, tools=payload.get("tools"), limit=_ctx_window)
                    if _bdg["level"] == "critical":
                        cur, _snap, _dropped = _ms.compress(cur, keep_recent=6)
                        _rec = {"type": "mission_recovered", "dropped": _dropped,
                                "n_tool_calls": _snap.get("n_tool_calls", 0)}
                        yield f"data: {json.dumps(_rec, ensure_ascii=False)}\n\n"
                        # TURN-0 RESIDUAL CASE: nothing in the tool-history middle
                        # to compress (static preamble+schema is the overflow
                        # source). Shed the discretionary ecosystem/skills system
                        # messages we injected rather than send a request already
                        # known to overflow num_ctx.
                        if _dropped == 0 and _discretionary_ids:
                            _before_n = len(cur)
                            cur = [m for m in cur if id(m) not in _discretionary_ids]
                            if len(cur) < _before_n:
                                _discretionary_ids.clear()  # shed once per run
                                _after = _cb.assess(cur, tools=payload.get("tools"), limit=_ctx_window)
                                _dg = {"type": "prompt_downgraded",
                                       "reason": "static_overflow_no_history_to_compress",
                                       "freed_tokens": _bdg["total"] - _after["total"],
                                       "level_after": _after["level"]}
                                yield f"data: {json.dumps(_dg, ensure_ascii=False)}\n\n"
                except Exception as _cbe:
                    print(f"[ContextBudget] /api/chat skipped: {_cbe}")

                # NEVER SEND OVER-BUDGET (same guard as /api/agent/run): the chat
                # agent-loop accumulates tool results across many rounds and would
                # otherwise 400 with "request (16513) exceeds context (16384)".
                _cur_fitted = _fit_context(cur, _ctx_window, payload.get("tools"))
                if len(_cur_fitted) < len(cur):
                    yield f"data: {json.dumps({'type':'text','text':f'⟢ context fit: {len(cur)}→{len(_cur_fitted)} msgs'+chr(10)}, ensure_ascii=False)}\n\n"
                loop_payload = {**payload, "messages": _cur_fitted}
                tool_calls_this_round = []
                text_this_round = []

                async for raw in _llm_stream(loop_payload, base, key):
                    ev = json.loads(raw)
                    if ev["type"] == "__tool_calls__":
                        tool_calls_this_round.extend(ev["calls"])
                    elif ev["type"] == "done":
                        break
                    else:
                        text_this_round.append(raw)
                        yield f"data: {raw}\n\n"

                # ── No more tool calls → check if mission really done ─────────
                if not tool_calls_this_round:
                    last_text = "".join(
                        json.loads(r).get("text","") for r in text_this_round
                        if json.loads(r).get("type") in ("text",)
                    )
                    if "TASK_COMPLETE" in last_text:
                        break
                    if not req.agent_mode:
                        break  # chat mode: model finished
                    last_msg = cur[-1] if cur else {}
                    if last_msg.get("role") == "user" and "TASK_COMPLETE" in last_msg.get("content",""):
                        break

                    # ── PLAN-ONLY DETECTION (FIX for runaway / lazy model) ─────
                    # If iter 0 sent text containing "PLAN:" but NO tool calls,
                    # model is being lazy — force continuation
                    _has_plan_marker = (
                        "PLAN:" in last_text or "PLAN :" in last_text
                        or "แผน:" in last_text or "ขั้นตอน" in last_text
                    )
                    _continuation_count = sum(
                        1 for m in cur
                        if isinstance(m, dict)
                        and isinstance(m.get("content"), str)
                        and m["content"].startswith("ดำเนินการต่อทันที")
                    )
                    if iteration == 0 and not _has_plan_marker:
                        # Iter 0 reply without PLAN — model spoke its mind, accept
                        break
                    if _continuation_count >= 3:
                        # Already pumped 3 continuations, model still refuses to act → give up
                        yield f"data: {json.dumps({'type':'text','text':'[หยุด: model ให้ PLAN เปล่าหลังถูกเตือน 3 ครั้ง]'})}\n\n"
                        break
                    # Inject continuation pump — force model to execute step 1
                    cur.append({
                        "role": "user",
                        "content": (
                            "ดำเนินการต่อทันที — execute step 1 of your PLAN right now with a tool call. "
                            "Do NOT repeat the PLAN. Do NOT add caveats. Just call the right tool with proper arguments. "
                            "If the task truly needs no tool (pure-text answer), produce the final answer now and end with TASK_COMPLETE."
                        )
                    })
                    # loop will continue, next iteration will get a fresh chance

                if iteration >= MAX_ITERS:
                    yield f"data: {json.dumps({'type':'text','text':f'[หยุด: ใช้ tools ครบ {MAX_ITERS} รอบแล้ว]'})}\n\n"
                    break

                assistant_text = "".join(
                    json.loads(r)["text"] for r in text_this_round
                    if json.loads(r).get("type") in ("text","think")
                    if json.loads(r).get("text")
                )
                cur.append({
                    "role": "assistant",
                    "content": assistant_text,
                    "tool_calls": tool_calls_this_round
                })

                # keepalive ping ระหว่าง tool execution (ป้องกัน timeout)
                yield f"data: {json.dumps({'type':'keepalive'})}\n\n"

                asked_user = False
                for tc in tool_calls_this_round:
                    fn = tc.get("function", {})
                    nm = fn.get("name", "")
                    ag = fn.get("arguments", {})
                    cat = get_tool_cat(nm)

                    # ── Elicitation: model is asking the USER something ──
                    # Stop generating; the frontend will render a UI card with options.
                    if nm == "ask_user_options":
                        opts = ag.get("options", [])
                        if not isinstance(opts, list): opts = []
                        opts = [str(o)[:120] for o in opts][:6]
                        evt = {
                            "type": "ask_user",
                            "question": str(ag.get("question",""))[:500],
                            "options": opts,
                            "allow_custom": bool(ag.get("allow_custom", True)),
                            "context": str(ag.get("context","") or "")[:300],
                        }
                        yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                        cur.append({"role":"tool","content":"[awaiting user reply]","name":nm})
                        asked_user = True
                        break  # stop processing further tool calls this round

                    # Normal tool execution
                    yield f"data: {json.dumps({'type':'tool_call','name':nm,'args':ag,'category':cat})}\n\n"
                    result = await exec_tool(nm, ag)
                    _failed = _tool_result_failed(nm, result)
                    consec_failures = consec_failures + 1 if _failed else 0
                    yield f"data: {json.dumps({'type':'tool_result','name':nm,'result':result[:2000],'category':cat,'failed':_failed})}\n\n"
                    # OPENCLAW PORT: auto-truncate large tool results to prevent context overflow + raw dump
                    cur.append({"role": "tool",
                                "content": ("⚠ FAILED — " if _failed else "") + _truncate_tool_result(nm, result),
                                "name": nm})

                    # ── MASTERPIECE: VALUE-LOCK for /api/chat too ──
                    if nm in {"get_gold_price","get_crypto_price","get_forex_rate","get_news","web_search","http_request"}:
                        cur.append({
                            "role": "system",
                            "content": (
                                f"⚠ VALUE-LOCK: The {nm} tool returned REAL DATA above. "
                                f"In any answer or follow-up tool call, copy the exact numbers, dates, "
                                f"currencies, and units from that result. Do NOT round, translate, or invent."
                            ),
                        })

                # If the model asked the user, end the stream — wait for user reply.
                if asked_user:
                    yield f"data: {json.dumps({'type':'done', 'reason':'awaiting_user'})}\n\n"
                    return

                # ── FAILURE-ADAPTATION GATE ──────────────────────────────────
                # 3 fails in a row → force ANALYSIS + a fundamentally new approach.
                # 6 fails in a row → halt honestly instead of digging the same hole.
                if consec_failures >= 6:
                    yield f"data: {json.dumps({'type':'text','text':chr(10)+'[หยุด: เครื่องมือล้มเหลว 6 ครั้งติดกัน — วิธีที่ใช้อยู่ใช้ไม่ได้กับระบบนี้ ดู error ล่าสุดด้านบน]'}, ensure_ascii=False)}\n\n"
                    break
                if consec_failures and consec_failures % 3 == 0:
                    cur.append({"role": "user", "content": (
                        f"⛔ STOP: your last {consec_failures} tool calls ALL FAILED. Do NOT retry a variation of the same command.\n"
                        "1) READ the error messages above; state in ONE line WHY they failed.\n"
                        "2) Pick a FUNDAMENTALLY different approach (different tool or method).\n"
                        "   Windows notes: cmd.exe does NOT know PowerShell cmdlets — pipes with "
                        "Select-String/Select-First fail there. Run the plain command WITHOUT pipes "
                        "and read its full output, or rely on the backend's PowerShell auto-routing.\n"
                        "3) Execute the NEW approach now with ONE tool call."
                    )})

                # ── Continuation directive — ONLY in agent_mode ──────────────
                # In normal chat mode, after the tool result the model should naturally
                # produce a reply on the next iteration. Injecting "execute next, do NOT
                # summarize" silenced the model and left the user with no answer.
                if req.agent_mode and iteration < MAX_ITERS - 1 and req.use_tools:
                    cur.append({
                        "role": "user",
                        "content": (
                            "ดำเนินการต่อทันที — execute the NEXT step now using tool calls. "
                            "Do NOT summarize or explain what was done. "
                            "Just perform the next action immediately. "
                            "If all tasks are complete, reply with: TASK_COMPLETE"
                        )
                    })
                elif iteration < MAX_ITERS - 1 and req.use_tools:
                    # Normal chat: nudge the model to USE the tool result and reply
                    cur.append({
                        "role": "user",
                        "content": (
                            "ใช้ผลลัพธ์จาก tool ด้านบนตอบคำถามเดิมของฉันเป็นภาษาไทย "
                            "(ใช้ภาษาเดียวกับที่ฉันถาม). "
                            "ถ้ายังต้องเรียก tool เพิ่มเพื่อให้คำตอบสมบูรณ์ ก็เรียกได้เลย "
                            "ไม่งั้นตอบให้จบในรอบนี้."
                        )
                    })

            yield f"data: {json.dumps({'type':'done'})}\n\n"
        except (GeneratorExit, asyncio.CancelledError):
            return  # client ปิด connection — หยุดเงียบๆ ไม่โยน error ให้ Starlette
        except Exception as e:
            try:
                yield f"data: {json.dumps({'type':'error','msg':repr(e)})}\n\n"
                yield f"data: {json.dumps({'type':'done'})}\n\n"
            except (GeneratorExit, asyncio.CancelledError):
                return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        }
    )

@app.post("/api/run-snippet")
async def run_snippet(req: SnippetReq):
    """Execute a code snippet extracted from AI markdown response."""
    lang = req.language.lower().strip()
    code = req.code.strip()
    if not code:
        return {"result": "", "ok": True}
    try:
        if lang in ("python", "py", "python3"):
            result = await exec_tool("run_python", {"code": code})
        elif lang in ("bash", "shell", "sh", "zsh", "cmd", "batch", "powershell", "ps1", "ps"):
            result = await exec_tool("shell_command", {"command": code})
        else:
            # Try Python by default for unknown languages
            result = await exec_tool("run_python", {"code": code})
        return {"result": result, "ok": True, "language": lang}
    except Exception as e:
        return {"result": f"Error: {repr(e)}", "ok": False, "language": lang}

# ── GENESIS MIND AUTONOMOUS AGENT ─────────────────────────────────────────────
AGENT_MEMORY_PATH = Path(__file__).parent / "agent_memory.json"

# === OPENCLAW PORT: modular prompts (IDENTITY/AGENTS/TOOLS/SOUL/USER.md) ===
# Try to load file-based prompts from backend/prompts/. If the directory or
# any read fails, fall through to the inline string below (backwards-compat).
# Eagerly refresh SELF.md FIRST so compose_genesis_prompt picks it up.
try:
    from self_awareness import write_self_state as _eager_write_self
    _eager_write_self(app=None)   # app routes not registered yet; that's OK
    print("[SelfAware] eager SELF.md generated at module load")
except Exception as _se:
    print(f"[SelfAware] eager refresh skipped: {_se}")

try:
    from prompts import compose_genesis_prompt as _compose_modular
    _MODULAR_PROMPT = _compose_modular()
    _MODULAR_PROMPT_COMPACT = _compose_modular(compact=True)
    print(f"[Prompts] full: {len(_MODULAR_PROMPT):,} chars · compact: {len(_MODULAR_PROMPT_COMPACT):,} chars (auto-select per task)")
except Exception as _pe:
    print(f"[Prompts] modular unavailable: {_pe} — using inline fallback")
    _MODULAR_PROMPT = ""
    _MODULAR_PROMPT_COMPACT = ""

# === SKILLS ACTIVATION — Capability-Skill Architecture (CSA v1) ===
# Task -> capability resolution -> bound skills, budget-capped injection.
# The legacy trigger router remains as CSA's internal fallback (strangler-fig).
# See docs/skills/CAPABILITY_SKILL_ARCHITECTURE.md.
try:
    from capability_skill_registry import activate_for_task as _auto_skill_messages
    from capability_skill_registry import load_index as _auto_skill_index
    _SKILL_INDEX_N = len(_auto_skill_index().get("skills", []))
    print(f"[CSA] capability-skill registry armed — {_SKILL_INDEX_N} skill(s) indexed")
except Exception as _sre:
    print(f"[CSA] registry unavailable: {_sre} — falling back to trigger router")
    try:
        from skills_auto_router import auto_skill_messages as _auto_skill_messages
    except Exception as _sre2:
        print(f"[SkillsRouter] unavailable: {_sre2} — skills will NOT auto-activate")
        def _auto_skill_messages(text, **kw): return []
# === OPENCLAW PORT END ===

GENESIS_AGENT_PROMPT = _MODULAR_PROMPT or """You are SkynetClaw Autonomous Agent — powered by Genesis Mind Strategic Intelligence.

## IDENTITY
You are not an assistant. You are an EXECUTOR and BUILDER.
You think with Genesis Mind (First Principle + System Thinking).
You act exclusively via tool calls until every task is complete.

## GENESIS MIND PROTOCOL (every step)
L0 REALITY: Read COMPLETED_ACTIONS below. What is already done? Do NOT redo any of it.
L1 NEXT: What is the single most critical action that has NOT been done yet?
L2 EXECUTE: Call exactly ONE tool now. Do not write the result — let the tool do it.
L3 VERIFY: After result — what changed? Move to the NEXT pending action.

## ANTI-LOOP / IDEMPOTENCY RULE (HIGHEST PRIORITY)
- Before every tool call, scan the COMPLETED_ACTIONS list provided by the system.
- If the action you are about to call (same tool + same key arguments) ALREADY appears there → DO NOT call it again. Move on to the next pending step.
- A folder that was already created exists. A file that was already written exists.
- If you cannot find any new action to take and the plan is fulfilled → reply TASK_COMPLETE.
- Repeating an identical tool call is a FAILURE. Avoid it.

## PLAN-FIRST RULE (only on step 1)
- On step 1, BEFORE any tool call, output ONE plain-text line per step in this exact format:
  PLAN: 1) <action> | 2) <action> | 3) <action> | ...
- Then immediately call the FIRST tool. Do not repeat the plan in later steps.

## EXECUTION RULES (NON-NEGOTIABLE)
1. NEVER write file content as plain text — ALWAYS use write_file tool to write files
2. NEVER explain — just call the tool directly
3. NEVER stop mid-task to ask permission
4. After every tool result → call the NEXT tool immediately (a DIFFERENT tool call, not the same one)
5. One tool call per response cycle — do not batch multiple actions in text
6. If a tool fails → retry with CORRECTED args (different from before) or use alternative approach
7. When ALL tasks are truly complete → write: TASK_COMPLETE
   Followed by a 3-5 line summary of what was built/accomplished

## CRITICAL: FILE WRITING RULE
- To create a file: use write_file tool with the FULL content in the "content" parameter
- NEVER write "Here is the code:" followed by a code block — that causes stream abort
- NEVER display file content in text — always pass it directly to write_file tool
- One write_file call per file — pass the complete content in the tool argument
- Do NOT rewrite a file that already exists in COMPLETED_ACTIONS unless its content needs to change

## 🛡️ LIVE-DATA RULE (Shadow Gate enforces this — violations are AUTO-BLOCKED)
Before writing/editing any file or note that contains LIVE values, you MUST call the
corresponding tool FIRST and use its returned values. Do NOT hardcode, do NOT guess,
do NOT use training-cutoff numbers.

Trigger → required prior tool:
  • gold price (USD/oz, THB/gram)        → call get_gold_price FIRST
  • crypto price (BTC, ETH, ฯลฯ)         → call get_crypto_price FIRST
  • forex rate (USD/THB, EUR/USD, ฯลฯ)   → call get_forex_rate FIRST
  • news / breaking / current events     → call get_news (or web_search) FIRST
  • 'Generated on:' or specific timestamp → use the ⏰ ACTUAL CURRENT TIME from
    the system prompt (already injected). Do NOT call get_current_datetime
    just for the date — it is provided.

If the Shadow Gate blocks your write_file → it means you tried to write fabricated
data. RE-PLAN: call the live-data tool first, capture its values, then write.

## MEMORY DISCIPLINE (internal, each step)
✅ DONE: [from COMPLETED_ACTIONS — do not redo]
⏳ PENDING: [what is left, from PLAN minus DONE]
🎯 NOW: [the next tool I am calling — must be different from the last call]

## TOOL PRIORITY
write_file > run_python > shell_command > list_files > read_file > create_folder

## CAPABILITIES (you HAVE these — never claim you can't)
✅ Read/write/edit files: read_file, write_file, edit_file, list_files, find_files, file_info
✅ Folders: create_folder, delete_file, move_file, copy_file
✅ Execute: run_python, shell_command, install_package
✅ Math: calculator — ALWAYS use it for arithmetic (e.g. calculator("1200*5")); never compute numbers in your head
✅ Vision: analyze_image — LOOK at any image/screenshot/chart with a local model (analyze_image(path, question)); works offline
✅ Obsidian: search_obsidian, read_obsidian_note, write_obsidian_note
✅ Web: web_search, http_request, download_file
✅ Real-time: get_current_datetime, get_gold_price, get_crypto_price, get_forex_rate, get_news
✅ System: get_system_info, list_processes, take_screenshot, clipboard_read/write
✅ Messaging: telegram_send, discord_send, line_notify

⛔ FORBIDDEN PHRASES (you ALWAYS have a tool — try it first):
"I cannot access files" — wrong, use read_file
"I cannot open obsidian" — wrong, use search_obsidian (or list_files+read_file as fallback)
"You need to paste the content" — wrong, fetch it yourself

## INTENT → TOOL (pick the right one)
- User asks to read/explore Obsidian → search_obsidian first; if that returns "no vault" → list_files on workspace
- User asks about files/folders → list_files / find_files / read_file
- User asks to create/build → write_file (always tool, never paste content as text)
- User asks for live prices/news → get_* tools (never training data)
- General web question → web_search with concise English/Thai keywords (NOT the user's full sentence)

## ELICITATION RULE — when to ASK the user
Use ask_user_options(question, options[4-5]) ONLY when:
  (a) prompt is genuinely ambiguous (>1 reasonable interpretation)
  (b) you are missing CRITICAL info that no tool can recover
  (c) a trade-off requires user preference (concise vs detailed, etc.)
  (d) action is irreversible and needs confirmation (delete, overwrite, send)
DO NOT ask for things you can find via list_files / read_file / search_obsidian.
NEVER ask permission to run a READ-ONLY check — just run it. Asking
"do you want me to check wifi?" then waiting is a FAILURE: read-only diagnosis
is free, so diagnose first and report findings.
Each option must be a complete, actionable answer — NOT category labels.
Use the user's language. After this tool, the loop halts to wait for user reply.

## COMPUTER TROUBLESHOOTING — you fix the machine, not just chat
When the user reports a computer problem (Wi-Fi won't connect, no internet,
slow, driver issue, disk, battery):
  1. system_diagnostics(problem="<their words>") FIRST — read-only, run it
     immediately, no permission needed. Report what you actually found.
  2. If a REPAIR is needed (reset adapter, flush DNS, install driver), that
     changes state → run it via shell_command and the operator approves once.
     State the exact command and why before you call it.
Never answer a system problem from memory — LOOK with system_diagnostics.

Execute relentlessly. Each tool call is one step closer to TASK_COMPLETE.
Repeating a completed action wastes a step. Always advance the plan.
"""

def load_agent_memory() -> dict:
    if AGENT_MEMORY_PATH.exists():
        try: return json.loads(AGENT_MEMORY_PATH.read_text(encoding="utf-8"))
        except: pass
    return {"sessions": [], "context": []}

def save_agent_memory(data: dict):
    AGENT_MEMORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _news_report_topics(task: str):
    """OX-NEWS-REPORT-1 — detect a 'build a news report/dashboard' request and map
    it to good search topics. Returns a topics list, or None if not a news-build
    request. Requires BOTH a build verb and a news word so it never hijacks
    generic questions."""
    t = (task or "").lower()
    _build = any(k in t for k in ["สร้าง", "ทำ", "รวบรวม", "รายงาน", "สรุป",
                                  "dashboard", "report", "หน้า", "build", "make"])
    _news = ("ข่าว" in t) or ("news" in t)
    if not (_build and _news):
        return None
    cats = [
        (["ทองคำ", "ทอง", "gold", "xau"], "ราคาทองคำ"),
        (["แร่เงิน", "silver", "โลหะเงิน"], "ราคาแร่เงิน silver"),
        (["หุ้น", "ตลาดหุ้น", "stock", "ตลาดหลักทรัพย์", "equity", "set index"], "หุ้นไทย ตลาดหลักทรัพย์"),
        (["คริปโต", "crypto", "bitcoin", "btc", "เหรียญดิจิทัล"], "bitcoin คริปโต"),
        (["เศรษฐกิจ", "economy", "gdp", "เงินเฟ้อ", "inflation"], "ข่าวเศรษฐกิจไทย"),
        (["ดอลลาร์", "ค่าเงิน", "forex", "อัตราแลกเปลี่ยน", "ค่าเงินบาท"], "ค่าเงินบาท ดอลลาร์"),
        (["น้ำมัน", "oil", "พลังงาน", "energy"], "ราคาน้ำมัน พลังงาน"),
        (["ai", "ปัญญาประดิษฐ์", "agentic", "เทคโนโลยี"], "AI ปัญญาประดิษฐ์ 2026"),
    ]
    topics = [topic for kws, topic in cats if any(k in t for k in kws)]
    if not topics:
        topics = ["ข่าวเศรษฐกิจไทย", "ข่าวการเงินตลาดทุน", "ข่าวต่างประเทศสำคัญ"]
    return topics[:8]


def _news_report_title(task: str) -> str:
    t = (task or "").lower()
    if any(k in t for k in ["การเงิน", "ทอง", "หุ้น", "คริปโต", "เศรษฐกิจ", "bitcoin", "gold", "stock"]):
        return "สรุปข่าวการเงินสำคัญ"
    return "สรุปข่าวสำคัญ"


@app.post("/api/agent/run")
async def agent_run(req: AgentRunReq, request: Request = None):
    """
    Full autonomous agent loop — runs entirely server-side in one SSE stream.
    Genesis Mind cognitive engine. Continues until TASK_COMPLETE or max_steps.
    """
    # COGNITIVE KERNEL — operator elevation is decided HERE, server-side, from an
    # HTTP header the model never sees. It only ever pre-approves ESCALATE (the human
    # gate); DENY and deny-by-default are untouched. Every attempt is audited.
    _operator_elevated = False
    try:
        _op_tok = request.headers.get("X-Operator-Token") if request is not None else None
        if _op_tok:
            import kernel_operator as _kop
            _origin = (request.client.host if request and request.client else "") or ""
            _operator_elevated = _kop.elevate(_op_tok, origin=_origin)["ok"]
    except Exception:
        _operator_elevated = False
    # === MASTERPIECE RESOLVE_MODEL (agent) — START ===
    _agent_requested = req.model or get_active_model() or ""
    model = _mp_resolve_model(_agent_requested, req.task) or _agent_requested
    # Cloud connection: trust the explicitly requested model — the local router's
    # model names (nemotron/SkynetClaw etc.) don't exist on cloud providers.
    try:
        if _LLM_ADAPTER and _ad_is_cloud(get_active_conn().get("api_type")) and req.model:
            model = req.model
    except Exception:
        pass
    # === MASTERPIECE RESOLVE_MODEL (agent) — END ===
    # === OX-EXECUTION-RECOVERY-FINAL: EXECUTION ≠ REASONING ≠ COUNCIL ==============
    # The agent loop is the EXECUTION path — fast, tool-first, GPU. It is routed to a
    # DEDICATED runtime connection (settings 'exec_connection', e.g. the llama.cpp
    # GPU server at /v1, api_type=openai) running 'exec_model' (qwen2.5-7b), while
    # REASONING (gemma4:26b) and COUNCIL (nemotron3:33b) stay on the global Ollama
    # connection. Hard rule: execution never invokes gemma4/nemotron3.
    # Safe default: if 'exec_connection' is unset/missing, behaviour is unchanged
    # (global active connection + optional exec_model on the local think-off path).
    base  = get_active_base_url()
    key   = get_active_api_key()
    _exec_api_type = None
    try:
        _exec_conn_name = (load_settings().get("exec_connection") or "").strip()
        _ec = get_conn_by_name(_exec_conn_name) if _exec_conn_name else None
        if _ec:
            base = (_ec.get("base_url") or base).rstrip("/")
            key = _ec.get("api_key") or ""
            _exec_api_type = _ec.get("api_type") or "ollama"
        else:
            _exec_api_type = get_active_conn().get("api_type")
    except Exception:
        _exec_api_type = None
    try:
        _exec_is_cloud = bool(_LLM_ADAPTER and _ad_is_cloud(_exec_api_type or get_active_conn().get("api_type")))
    except Exception:
        _exec_is_cloud = False
    # exec_model overrides the model on BOTH paths (the dedicated runtime serves one
    # model; on the local Ollama path it picks the fast think-off model).
    try:
        _exec_model = (load_settings().get("exec_model") or "").strip()
        if _exec_model:
            model = _exec_model
    except Exception:
        pass
    # ==============================================================================
    # ── PROTOCOL over MODEL: resolve the context window from the connection, not a
    # constant. "Models are temporary. Protocols endure." Undeclared local (llama.cpp
    # :8080) stays 16384; Ollama/cloud connections get their real window automatically.
    try:
        import context_budget as _cbw
        _exec_conn_dict = (_ec if _ec else get_active_conn()) or {}
        _ctx_window = _cbw.resolve_window(_exec_conn_dict, _exec_api_type, model, base)
    except Exception:
        _ctx_window = 16384
    MAX_STEPS = min(max(int(req.max_steps or 30), 1), 30)  # Bug 3 fix: handle 0/None safely

    # ── GPS-2: intercept human-gate decisions ("approve gate_xxxx" / "deny gate_xxxx")
    # Records the decision in ExecApprovals and swaps in the ORIGINAL task to resume.
    _gate_note = ""
    if _GOV is not None:
        try:
            _gres = _GOV.resolve_directive(req.task, _OCPApprovals())
            if _gres:
                req.task = _gres["task"]
                _gate_note = _gres.get("note", "")
        except Exception as _ge:
            print(f"[Governance] directive intercept failed: {_ge}")

    # ── OX-H1 IDENTITY SEPARATION ────────────────────────────────────────────
    # `req.task` may be a fully-assembled MODEL PROMPT (it begins with a
    # "WORKFLOW CONTEXT" block when the workflow self-calls). The model still
    # receives `req.task` verbatim, but MISSION IDENTITY — everything persisted
    # to house_state.question / agent_runs.task / the mission ledger — must be
    # the clean USER DIRECTIVE only. This is the single value used for every
    # identity write below; the prompt never enters a mission field again.
    try:
        import mission_identity as _mid
        _mission_identity = _mid.clean_identity(req.task, getattr(req, "directive", "") or "")
        if not _mission_identity:
            _mission_identity = (getattr(req, "directive", "") or req.task or "").strip()[:300]
    except Exception:
        _mission_identity = (getattr(req, "directive", "") or req.task or "")

    # ── Activate workspace folder for ALL tool calls in this request ────
    workspace = (req.workspace_folder or "").strip()
    workspace_resolved = ""
    if workspace:
        try:
            wp = Path(workspace)
            wp.mkdir(parents=True, exist_ok=True)
            workspace_resolved = str(wp.resolve())
            ACTIVE_WORKSPACE.set(workspace_resolved)
        except Exception:
            workspace_resolved = ""

    # Load memory for context
    mem = load_agent_memory()
    recent_ctx = mem.get("context", [])[-6:]  # last 3 exchanges

    # ── Helpers for anti-loop / action memory ────────────────────────────
    def _action_sig(name: str, args: dict) -> str:
        """Stable signature: tool_name(sorted key args, truncated)."""
        try:
            # Use only the most identifying args, sorted, with short value preview
            keys = sorted((args or {}).keys())
            parts = []
            for k in keys:
                v = args.get(k, "")
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False, sort_keys=True)
                else:
                    v = str(v)
                # FIX: long values (article bodies, code) used to be truncated at 80
                # chars — two writes with DIFFERENT content but the same opening got
                # the SAME signature and were wrongly 'duplicate blocked'. Hash the
                # full value so only truly identical calls count as duplicates.
                if len(v) > 80:
                    v = v[:48] + "·sha1:" + hashlib.sha1(v.encode("utf-8", "ignore")).hexdigest()[:10]
                parts.append(f"{k}={v}")
            return f"{name}({'|'.join(parts)})"
        except Exception:
            return f"{name}(?)"

    def _format_completed(actions: list) -> str:
        if not actions:
            return "(none yet — this is step 1)"
        lines = []
        for i, sig in enumerate(actions, 1):
            lines.append(f"  {i}. ✅ {sig}")
        return "\n".join(lines)

    async def generate():
        try:
            # Re-bind contextvar inside the generator (defensive — survives
            # any framework-level context resets between request and stream).
            if workspace_resolved:
                ACTIVE_WORKSPACE.set(workspace_resolved)

            # ── OX-NEWS-REPORT-1 FAST-PATH (option C) — runs BEFORE any LLM preamble
            # so a 'build a news report' request is fully DETERMINISTIC and fast, and
            # never depends on the local 14B to orchestrate tools (it stalls/loops).
            try:
                _ntopics = _news_report_topics(req.task or "")
            except Exception:
                _ntopics = None
            if _ntopics:
                yield f"data: {json.dumps({'type':'agent_start','task':(req.task or '')[:200],'max_steps':1}, ensure_ascii=False)}\n\n"
                try:
                    import news_report as _nr
                    _fn = "news_report.html"
                    _mfn = re.search(r"([\w฀-๿\-]+\.html)", req.task or "")
                    if _mfn:
                        _fn = _mfn.group(1)
                    _wsd = (req.workspace_folder or "").strip()
                    _out = os.path.join(_wsd, _fn) if _wsd else str(_resolve_path(_fn))
                    yield f"data: {json.dumps({'type':'text','text':'📰 News-report (deterministic): รวบรวมข่าวจัดอันดับความสำคัญ → สร้างรายงาน…'+chr(10)}, ensure_ascii=False)}\n\n"
                    _rep = await asyncio.to_thread(_nr.make_report, _ntopics,
                                                   _news_report_title(req.task or ''), 'th', 6, _out)
                    _ln = [f"✅ สร้างรายงานข่าวแล้ว: {_out}",
                           f"{_rep['count']} ข่าว · {len(_rep['topics'])} หัวข้อ · จัดอันดับตามแหล่ง+ความใหม่",
                           "หัวข้อ: " + ", ".join(_rep['topics'])]
                    for _s in _rep['sections']:
                        _tp = _s['top'][0]['title'][:54] if _s.get('top') else '—'
                        _ln.append(f"  • {_s['topic']}: {_s['n']} ข่าว (เด่น: {_tp})")
                    _sm = "\n".join(_ln)
                    yield f"data: {json.dumps({'type':'agent_tool_result','step':1,'name':'build_news_report','result':_sm}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type':'agent_complete','steps':1,'tools_used':1,'summary':_sm}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type':'done'})}\n\n"
                    return
                except Exception as _nre:
                    yield f"data: {json.dumps({'type':'text','text':'(news fast-path error: '+str(_nre)[:140]+')'+chr(10)}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type':'agent_complete','steps':1,'tools_used':0,'summary':'news fast-path error'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type':'done'})}\n\n"
                    return

            # ── PLANNER AUTO-ROUTE (Vol IV bridge) ──────────────────────────────
            # A clear 'build a single-file artifact' task WITH a workspace is
            # decomposed → built across budgeted rounds → SAVED by the planner
            # (which writes the file itself), instead of the tool loop that streamed
            # code but never saved it and halted ("PLAN เปล่า"). Disable with
            # settings.planner_autoroute=false.
            try:
                _autoroute = load_settings().get("planner_autoroute", True)
            except Exception:
                _autoroute = True
            try:
                import task_planner as _tp
                _is_build = bool(_autoroute and workspace_resolved and _tp.looks_like_build_task(req.task or ""))
            except Exception:
                _is_build = False
            if _is_build:
                yield f"data: {json.dumps({'type':'agent_start','task':(req.task or '')[:200],'mode':'planner'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'text','text':'🧭 Planner: งานสร้างไฟล์ — วางแผน → สร้างทีละรอบ → บันทึกไฟล์ให้เอง'+chr(10)}, ensure_ascii=False)}\n\n"
                async def _pcall(messages):
                    _pl = {"model": model, "messages": _fit_context(messages, _ctx_window),
                           "stream": True, "keep_alive": "30m",
                           "options": {"num_ctx": _ctx_window, "temperature": 0.2}}
                    _parts = []
                    async for _raw in _llm_stream(_pl, base, key, api_type=_exec_api_type):
                        try: _pe = json.loads(_raw)
                        except Exception: continue
                        if _pe.get("type") == "text": _parts.append(_pe.get("text", ""))
                    return "".join(_parts)
                _presult = None
                try:
                    async for _pev in _tp.plan_and_execute(req.task, workspace_resolved, _pcall):
                        if _pev.get("type") == "plan_complete": _presult = _pev
                        yield f"data: {json.dumps(_pev, ensure_ascii=False)}\n\n"
                except Exception as _pe2:
                    yield f"data: {json.dumps({'type':'text','text':'[planner error: '+str(_pe2)[:120]+']'}, ensure_ascii=False)}\n\n"
                _psum = (_presult or {}).get("summary", "planner finished")
                yield f"data: {json.dumps({'type':'agent_complete','steps':(_presult or {}).get('steps',0),'tools_used':0,'summary':_psum}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'done','final_status':('SUCCESS' if (_presult or {}).get('ok') else 'LIMIT')}, ensure_ascii=False)}\n\n"
                return

            # ── COUNCIL AUTO-ROUTE (advisory) ───────────────────────────────────
            # The UI's only path is /api/agent/run, so the L5 council was
            # unreachable from everyday use. Same pattern as the planner
            # auto-route: a cheap deterministic gate; on a judgement/decision
            # task the six specialists deliberate FIRST and their verdict is
            # injected as advisory context — the council ADVISES, the loop (and
            # ultimately the operator) still decides. Disable with
            # settings.council_autoroute=false.
            _council_advice = None
            try:
                _c_auto = load_settings().get("council_autoroute", True)
            except Exception:
                _c_auto = True
            # never deliberate twice: the workflow's execute phase self-calls
            # this endpoint with the council's verdict already inlined
            _already_deliberated = "L5 AGENT COUNCIL" in (req.task or "")
            if _c_auto and _COUNCIL_AVAILABLE and _council is not None and \
               not _already_deliberated and \
               _council.looks_like_deliberation_task(req.task or ""):
                yield f"data: {json.dumps({'type':'text','text':'🏛️ Council: งานเชิงตัดสินใจ — หกผู้เชี่ยวชาญกำลังถกก่อนลงมือ...'+chr(10)}, ensure_ascii=False)}\n\n"
                def _c_on_event(evt):
                    try:
                        house_sync.publish(evt.get("type", "agent_event"),
                                           {"agent": evt.get("agent", ""),
                                            "message": evt.get("message", ""),
                                            "ts_iso": evt.get("timestamp", "")},
                                           source="council")
                    except Exception:
                        pass
                try:
                    _cv_run = await asyncio.wait_for(
                        _council.run_council(req.task or "", context={"origin": "agent_run"},
                                             model=model, base_url=base, api_key=key,
                                             on_event=_c_on_event),
                        timeout=300)
                    _council_advice = _council.format_council_for_agent(_cv_run)
                    _c_line = f"🏛️ Council verdict: {(_cv_run.aggregate_recommendation or '')[:220]}"
                    yield f"data: {json.dumps({'type':'text','text':_c_line+chr(10)}, ensure_ascii=False)}\n\n"
                except Exception as _ce:
                    # advisory only — a council failure never blocks the mission
                    yield f"data: {json.dumps({'type':'text','text':'[council skipped: '+str(_ce)[:100]+']'+chr(10)}, ensure_ascii=False)}\n\n"

            # ── PROMPT SIZE AUTO-SELECT (BUDGET-AWARE) ──
            # The full prompt (~7k tokens) is a luxury for LARGE windows. On a
            # small (16k local) window a LONG task must use the COMPACT prompt to
            # leave room — the old rule did the OPPOSITE (full prompt for long
            # tasks), so a workflow's augmented task (comprehend+plan+council)
            # blew the budget and the execute phase crashed with a ReadError,
            # turning completed councils into "failed" runs. (root cause of the
            # recurring failures, found 2026-07-12.)
            _task_lower = (req.task or "").lower()
            _meta_keywords = ("skynetclaw", "skynet claw", "ตัวคุณ", "ตัวเอง", "อธิบายตัว",
                              "ทำได้บ้าง", "ความสามารถ", "self", "capabilit", "what can you")
            _is_meta = any(kw in _task_lower for kw in _meta_keywords)
            _small_window = (_ctx_window or 16384) <= 24000
            _combined_len = len(req.task or "") + len(_council_advice or "")
            _use_compact = bool(_MODULAR_PROMPT_COMPACT) and not _is_meta and (
                _small_window or _combined_len >= 220
            )
            _selected_prompt = _MODULAR_PROMPT_COMPACT if _use_compact else GENESIS_AGENT_PROMPT
            _selected_size_kb = len(_selected_prompt) / 1024
            print(f"[agent_run] prompt mode={'compact' if _use_compact else 'full'} "
                  f"size={_selected_size_kb:.1f}KB task_len={len(req.task or '')}")
            cur = [{"role": "system", "content": _selected_prompt}]
            if _council_advice:
                cur.append({"role": "system", "content": _council_advice})

            # === SKILLS AUTO-ROUTER: auto-inject skill prompts matching user task ===
            _activated_skill_names: list = []   # OX-SKILL-2: graded at run end via the ledger
            try:
                _skill_msgs_run = _auto_skill_messages(req.task or "", top_k=2)
                for _sm in _skill_msgs_run:
                    cur.append({"role": "system", "content": _sm["content"]})
                if _skill_msgs_run:
                    _meta_list = [s["skill_meta"] for s in _skill_msgs_run]
                    _activated_skill_names = [m["name"] for m in _meta_list]
                    _names = ", ".join(f"{m['name']}({m['score']})" for m in _meta_list)
                    print(f"[SkillsRouter] /api/agent/run auto-activated: {_names}")
                    # Emit UI banner so the user sees which skills auto-fired
                    for _m in _meta_list:
                        _banner_text = f"🎯 Auto-activated skill: **{_m['name']}** (score {_m['score']})\n"
                        _banner_evt = {"type": "text", "text": _banner_text}
                        yield f"data: {json.dumps(_banner_evt, ensure_ascii=False)}\n\n"
            except Exception as _e:
                print(f"[SkillsRouter] /api/agent/run inject failed: {_e}")

            # ── MASTERPIECE: Inject ACTUAL current datetime + live-data rule ──
            # Without this, the model invents dates/prices ("Generated on:" + fake values).
            try:
                _dt_banner = _mp_datetime_banner("Asia/Bangkok")
                if _dt_banner:
                    cur.append({"role": "system", "content": _dt_banner})
                _live_rule = _mp_live_data_directive()
                if _live_rule:
                    cur.append({"role": "system", "content": _live_rule})
                # SELF-KNOWLEDGE: tell the agent about its OWN Obsidian vault + tools
                _vb = _vault_awareness_banner()
                if _vb:
                    cur.append({"role": "system", "content": _vb})
            except Exception as _e:
                print(f"[Masterpiece] preamble inject failed: {_e}")

            # ── HOUSE CONSTITUTION — every agent loads the 8 permanent rules ──
            if _INSTITUTIONAL_MEMORY and _CONSTITUTION_TEXT:
                cur.append({"role": "system", "content": _CONSTITUTION_TEXT})

            # ── Workspace banner: tell the model where to write files ──
            if workspace_resolved:
                cur.append({
                    "role": "system",
                    "content": (
                        "## WORKSPACE_FOLDER (write all files here)\n"
                        f"{workspace_resolved}\n\n"
                        "RULES:\n"
                        f"- Always pass file paths as ABSOLUTE paths under this folder, "
                        f"e.g. {workspace_resolved}\\my_file.py\n"
                        "- If you accidentally pass a relative path, the backend will "
                        "auto-prefix it with WORKSPACE_FOLDER.\n"
                        "- Never write files anywhere else."
                    )
                })
                # REALITY GROUNDING: the actual workspace contents, so the agent
                # never asks "which file?" when files are already mounted.
                try:
                    import reality_context as _rc
                    _reality = _rc.build_reality(workspace_resolved,
                                                 runtime_label=get_active_conn().get("name", ""),
                                                 model=model,
                                                 operational=_rc.build_operational_summary(DB_PATH))
                    if _reality:
                        cur.append({"role": "system", "content": _reality})
                except Exception as _rce:
                    print(f"[Reality] agent inject skipped: {_rce}")
                # ── PROPRIOCEPTION (Vol VI Learning bridge) — the system learning from
                # its OWN outcomes: task-relevant lessons mined from the run log +
                # recorded overclaims (CEE), fed forward so a past failure teaches this
                # run. Silent when nothing relevant was learned (F2 anti-noise).
                try:
                    import self_context as _sc
                    _lessons = _sc.build_self_context(DB_PATH, req.task or "")
                    if _lessons:
                        cur.append({"role": "system", "content": _lessons})
                        print(f"[Proprioception] injected {_lessons.count(chr(10)+'- ')} lesson(s)")
                except Exception as _sce:
                    print(f"[Proprioception] inject skipped: {_sce}")
                # ── MISSION LEDGER digest — Commander-signed history of this workspace.
                # The model sees what is already ✓ COMPLETE and must not redo it.
                _ldg = _ledger_digest(workspace_resolved)
                if _ldg:
                    cur.append({"role": "system", "content": (
                        "## MISSION LEDGER (signed by SKYNET ELITE COMMANDER — recent work in this workspace):\n"
                        + _ldg +
                        "\nRULES: do NOT redo ✓ COMPLETE missions or rewrite their files unless the directive "
                        "explicitly asks. ◐ INCOMPLETE / ✗ PROBLEM items may be continued — read their files first."
                    )})

            # Inject recent memory context
            if recent_ctx:
                ctx_str = "\n".join(
                    f"[Memory] {m['role']}: {str(m.get('content',''))[:200]}"
                    for m in recent_ctx
                )
                cur.append({"role": "system",
                            "content": f"## RECENT MEMORY (ประวัติงานล่าสุด):\n{ctx_str}"})
            cur.append({"role": "user", "content": req.task})

            # MISSION-SCOPED TOOLS — computed once per run; halves prompt-eval time
            _MISSION_TOOLS = _select_tools_for_task(req.task)
            # SECURITY: an explicit allow-list REPLACES keyword routing with exactly
            # the permitted set (independent of task keywords), so the model is only
            # ever shown safe tools. Execution-time enforcement is at the choke point.
            if req.tool_allow:
                _allow = set(req.tool_allow)
                _MISSION_TOOLS = [t for t in BUILTIN_TOOLS
                                  if t.get("function", {}).get("name") in _allow]
            print(f"[agent_run] mission tools: {len(_MISSION_TOOLS)}/{len(BUILTIN_TOOLS)} schemas"
                  f"{' (restricted allow-list)' if req.tool_allow else ''}")

            total_tool_calls = 0
            completed_steps  = []          # human-readable log
            action_sigs      = []          # normalized signatures (anti-loop)
            recent_sigs      = []          # last 3 signatures for cycle detection
            no_progress_rounds = 0         # increments when no NEW action happens
            consec_failures    = 0         # FAILURE-ADAPTATION: failed actions must change the plan
            # OX-1.1 WORLD MODEL — per-run verified-entity ledger (in-memory; never assume)
            try:
                import world_model as _wm_mod
                _world = _wm_mod.WorldModel()
            except Exception:
                _world = None
            # OX-1.3 EXECUTION CONFIDENCE — per-run reliability scalar (distinct from
            # belief confidence and agent reputation)
            try:
                import execution_confidence as _ecmod
                _exec_conf = _ecmod.ExecutionConfidence()
            except Exception:
                _exec_conf = None
            # OX-1.4 BLOCKED STATE — per-run dead-end detector: varied actions that
            # gain no information for K steps + recovery exhausted → terminate BLOCKED.
            try:
                import blocked_detector as _bdmod
                _blocked_det = _bdmod.BlockedDetector()
            except Exception:
                _blocked_det = None
            # OX-1.5 EXECUTION MEMORY — pre-warm: carry forward what PRIOR runs
            # learned (unknown tools = hard fact → seed world; absent paths +
            # dead-ends = task-similar hint). Zero new state — reads agent_runs.
            try:
                import execution_recall as _exec_recall
                _recent_runs = _AGENT_RUNS_DB.recent(limit=30) or []
                _exec_mem = _exec_recall.recall(req.task or "", _recent_runs)
                if _world is not None:
                    _exec_recall.seed_world(_world, _exec_mem)
                _mem_block = _exec_recall.render(_exec_mem)
                if _mem_block:
                    cur.append({"role": "system", "content": _mem_block})
                    yield f"data: {json.dumps({'type':'execution_memory','tools':_exec_mem.get('unknown_tools',[]),'dead_ends':len(_exec_mem.get('prior_dead_ends',[])),'similar':_exec_mem.get('similar_count',0)}, ensure_ascii=False)}\n\n"
            except Exception as _emerr:
                _exec_recall = None
                print(f"[ExecutionRecall] pre-warm skipped: {_emerr}")
            # ── OX-INTENT-1 UNIFIED INTENT PROTOCOL ──────────────────────────────
            # The operator issued ONE request → interpret it ONCE here, then every
            # consumer reads the same Intent Object instead of re-reading raw text.
            # This removes intent drift, duplicate classification, duplicate resume
            # detection and divergent knowledge routing. Artifact Registry is the
            # SINGLE SOURCE OF TRUTH for resume; Tool Intelligence consumes intent
            # (no own resume detection); Knowledge Seeking consumes intent (artifact
            # overlap suppressed); Execution Recall enriches, never redefines.
            _tool_intel = None
            _tool_task_type = "general"
            _intent = None
            try:
                import intent as _intent_mod
                import tool_intelligence as _tool_intel
                import artifact_registry as _artreg
                import knowledge_seeking as _kseek
                _cands = [(_t.get("function") or {}).get("name", "") for _t in _MISSION_TOOLS]
                _iv_vault = ""
                try: _iv_vault = get_vault() or ""
                except Exception: _iv_vault = ""
                _iv_known = []
                try:
                    _iv_sid = _house_state.current()
                    if _iv_sid:
                        _iv_known = list((_house_state.answer(_iv_sid.get("id")) or {}).get("what_we_know") or [])
                except Exception:
                    _iv_known = []
                # INTERPRET ONCE (runs each detector exactly once)
                _intent = _intent_mod.interpret(
                    req.task or "", available_tools=_cands,
                    workspace=workspace_resolved or None,
                    vault=_iv_vault or None, known_facts=_iv_known)
                # Execution Recall MAY enrich the intent (not redefine it)
                try: _intent_mod.enrich(_intent, locals().get("_exec_mem"))
                except Exception: pass
                _tool_task_type = _intent.get("task_type", "general")
                cur.append({"role": "system", "content": _intent_mod.render_brief(_intent)})
                yield f"data: {json.dumps({'type':'intent','intent':_intent.get('intent'),'target':_intent.get('target'),'confidence':_intent.get('confidence'),'requires_artifact':_intent.get('requires_artifact'),'requires_knowledge_search':_intent.get('requires_knowledge_search'),'requires_clarification':_intent.get('requires_clarification'),'task_type':_tool_task_type}, ensure_ascii=False)}\n\n"
                try: house_sync.publish("intent", {"intent": _intent.get("intent"), "target": _intent.get("target"), "confidence": _intent.get("confidence"), "requires_artifact": _intent.get("requires_artifact"), "requires_knowledge_search": _intent.get("requires_knowledge_search")}, source="runtime")
                except Exception: pass

                # CONSUMER 1 — Artifact Registry (single source of truth for resume)
                try:
                    _ar_brief = _artreg.render_brief_from_intent(_intent)
                    if _ar_brief:
                        cur.append({"role": "system", "content": _ar_brief})
                        _ar_a = (_intent.get("artifact") or {}).get("artifact") or {}
                        yield f"data: {json.dumps({'type':'artifact_awareness','path':_ar_a.get('artifact_path'),'artifact_type':_ar_a.get('artifact_type'),'exists':(_intent.get('artifact') or {}).get('exists'),'recommend_resume':(_intent.get('artifact') or {}).get('recommend_resume'),'mission_id':_ar_a.get('mission_id')}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("artifact_awareness", {"path": _ar_a.get("artifact_path"), "exists": (_intent.get("artifact") or {}).get("exists"), "recommend_resume": (_intent.get("artifact") or {}).get("recommend_resume")}, source="runtime")
                        except Exception: pass
                except Exception as _are:
                    print(f"[ArtifactAwareness] consume skipped: {_are}")

                # CONSUMER 2 — Tool Intelligence (consumes intent; no resume detection)
                try:
                    _ti_brief = _tool_intel.render_brief(req.task or "", _cands, intent=_intent)
                    if _ti_brief:
                        cur.append({"role": "system", "content": _ti_brief})
                        _ti_rec = _tool_intel.recommend(_tool_task_type, _cands)
                        yield f"data: {json.dumps({'type':'tool_intelligence','task_type':_tool_task_type,'fastest':(_ti_rec.get('fastest') or {}).get('tool'),'safest':(_ti_rec.get('safest') or {}).get('tool'),'prior_solution':(_ti_rec.get('prior_solution') or {}).get('tool'),'evidence':_ti_rec.get('evidence',0)}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("tool_intelligence", {"task_type": _tool_task_type, "prior_solution": (_ti_rec.get("prior_solution") or {}).get("tool"), "evidence": _ti_rec.get("evidence", 0)}, source="runtime")
                        except Exception: pass
                except Exception as _tie:
                    print(f"[ToolIntelligence] consume skipped: {_tie}")

                # CONSUMER 3 — Knowledge Seeking (consumes the intent's plan)
                try:
                    _ks_plan = _intent.get("knowledge_plan") or {}
                    _ks_brief = _kseek.render_brief(_ks_plan) if _ks_plan else ""
                    if _ks_brief:
                        cur.append({"role": "system", "content": _ks_brief})
                        yield f"data: {json.dumps({'type':'knowledge_seeking','known':_ks_plan.get('known'),'knowable':len(_ks_plan.get('knowable',[])),'unknown':len(_ks_plan.get('unknown',[])),'needs_search':_ks_plan.get('needs_search'),'sources':[s['source'] for s in _kseek.acquisition_order(_ks_plan)]}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("knowledge_seeking", {"known": _ks_plan.get("known"), "knowable": len(_ks_plan.get("knowable", [])), "unknown": len(_ks_plan.get("unknown", [])), "needs_search": _ks_plan.get("needs_search")}, source="runtime")
                        except Exception: pass
                except Exception as _kse:
                    print(f"[KnowledgeSeeking] consume skipped: {_kse}")
            except Exception as _ie:
                _tool_intel = None
                print(f"[UnifiedIntent] interpretation skipped: {_ie}")
            # OX-ATTRIBUTION-1 — per-mission recall manifest: capture WHAT was
            # recalled this run (capabilities / lessons / control verdict) so the
            # outcome can later be attributed to it. Populated by the recall blocks
            # below; recorded against the outcome at sign-off.
            _attrib = {"capabilities": [], "lessons": [], "control_verdict": None}
            # OX-CONTROL-1 ADAPTIVE CONTROL DIRECTIVE — the controller's latest
            # verdict (from the PRIOR run's telemetry) tells the agent how to WEIGH
            # recalled knowledge this run (lead with warnings when regressing,
            # reinforce proven paths when improving, hold when flat). This closes
            # Measure→Decide→ADJUST. Read-side over control_history.json.
            _ctrl_policy = None
            try:
                import control_engine as _ctrl
                _ctrl_decision = _ctrl.latest()
                _ctrl_policy = _ctrl.latest_policy()
                _attrib["control_verdict"] = (_ctrl_decision or {}).get("verdict")
                _ctrl_brief = _ctrl.render_brief(_ctrl_decision) if _ctrl_decision else ""
                if _ctrl_brief:
                    cur.append({"role": "system", "content": _ctrl_brief})
                    yield f"data: {json.dumps({'type':'control_directive','verdict':(_ctrl_decision or {}).get('verdict'),'policy':_ctrl_policy}, ensure_ascii=False)}\n\n"
                    try: house_sync.publish("control_directive", {"verdict": (_ctrl_decision or {}).get("verdict")}, source="learning")
                    except Exception: pass
            except Exception as _cde:
                _ctrl_policy = None
                print(f"[ControlDirective] skipped: {_cde}")
            # OX-CAPABILITY-1 CAPABILITY RECALL — before planning, surface the
            # emerged CAPABILITIES (reusable behaviors promoted from repeated
            # success) and WARNING capabilities (repeated failure). Capabilities
            # are PREFERRED over raw lessons; when any surface, the raw-lesson
            # brief is suppressed. Read-side over capabilities.json. OX-CONTROL-1
            # reorders them per the control policy (recall priority).
            _caps_shown = False
            try:
                import capability_promotion as _caps
                _recalled_caps = _caps.recall(req.task or "", limit=5)
                # OX-REINFORCEMENT-1: bias by learned weights FIRST — higher-weight
                # capabilities appear first, demoted ones surface as warnings.
                try:
                    import reinforcement as _reinf
                    _recalled_caps = _reinf.apply_to_recall(_recalled_caps)
                except Exception: pass
                # OX-CONTROL-1: then apply the trend-based recall priority on top.
                if _ctrl_policy:
                    try: _recalled_caps = _ctrl.reorder_capabilities(_recalled_caps, _ctrl_policy)
                    except Exception: pass
                if _recalled_caps:
                    _cap_brief = _caps.render_brief(_recalled_caps)
                    if _cap_brief:
                        cur.append({"role": "system", "content": _cap_brief})
                        _caps_shown = True
                        _attrib["capabilities"] = [c.get("name") for c in _recalled_caps if c.get("name")]
                        yield f"data: {json.dumps({'type':'capability_recall','count':len(_recalled_caps),'capabilities':sum(1 for c in _recalled_caps if c.get('polarity')=='capability'),'warnings':sum(1 for c in _recalled_caps if c.get('polarity')=='warning'),'top':_recalled_caps[0].get('name')}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("capability_recall", {"count": len(_recalled_caps), "top": _recalled_caps[0].get("name")}, source="learning")
                        except Exception: pass
            except Exception as _cre:
                print(f"[CapabilityRecall] skipped: {_cre}")
            # OX-LEARNING-1 LESSON RECALL — what repeatedly WORKS/FAILS for this
            # kind of task. Suppressed when capabilities already surfaced (caps are
            # the promoted, preferred form of the same knowledge).
            try:
                if not _caps_shown:
                    import lesson_synthesis as _lessons
                    _recalled = _lessons.recall(req.task or "", limit=6)
                    if _recalled:
                        _lz_brief = _lessons.render_brief(_recalled)
                        if _lz_brief:
                            cur.append({"role": "system", "content": _lz_brief})
                            _attrib["lessons"] = [l.get("id") for l in _recalled if l.get("id")]
                            yield f"data: {json.dumps({'type':'lesson_recall','count':len(_recalled),'wins':sum(1 for l in _recalled if l.get('polarity')=='success'),'fails':sum(1 for l in _recalled if l.get('polarity')=='failure')}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("lesson_recall", {"count": len(_recalled), "top": _recalled[0].get("lesson", "")[:120]}, source="learning")
                            except Exception: pass
            except Exception as _lze:
                print(f"[LessonRecall] skipped: {_lze}")
            # OX-ACQUISITION-1 — for KNOWABLE knowledge gaps, plan acquisition over
            # the source hierarchy and instruct the agent to SEARCH before asking
            # the operator. Read-side planner; the agent's tool calls do the search.
            # Gaps are recorded at completion (see acquisition record block below).
            _acq_gaps = []
            try:
                import acquisition as _acq
                _acq_gaps = _acq.detect_gaps(
                    req.task or "", available_tools=locals().get("_cands"),
                    workspace=workspace_resolved or None,
                    vault=(locals().get("_iv_vault") or None),
                    known_facts=locals().get("_iv_known"))
                # OX-METALEARNING-1 + OX-EXPLORATION-1 RECALL: choose each gap's
                # source order. Exploitation = the proven strategy; exploration =
                # occasionally an alternative order (epsilon-greedy by confidence).
                # The selection is recorded at completion to discover better orders.
                _explore_sel = {}
                try:
                    import metalearning as _ml, exploration as _expl
                    for _g in _acq_gaps:
                        _gt = _g.get("gap_type", "")
                        _strat = _ml.lookup_strategy(_gt)
                        _sel = _expl.select(_gt, strategy=_strat)
                        _g["source_candidates"] = _expl.reorder(
                            _g.get("source_candidates") or [], _sel.get("selected_strategy") or [])
                        _explore_sel[_g.get("gap_id")] = _sel
                except Exception: pass
                # OX-CAUSAL-1 RECALL: surface likely REASONS a strategy works for
                # each gap_type (promoted causal hypotheses) before acquisition.
                try:
                    import causal as _causal
                    for _gt in {g.get("gap_type", "") for g in _acq_gaps}:
                        _cb = _causal.render_brief(_gt)
                        if _cb:
                            cur.append({"role": "system", "content": _cb})
                except Exception: pass
                # OX-CURIOSITY-1 RECALL: surface known strengths / weaknesses /
                # blind spots before acquisition (awareness only — not a goal).
                if _acq_gaps:
                    try:
                        import curiosity as _cur
                        _cur_brief = _cur.render_brief()
                        if _cur_brief:
                            cur.append({"role": "system", "content": _cur_brief})
                            yield f"data: {json.dumps({'type':'curiosity','metrics':_cur.metrics().get('by_severity',{})}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("curiosity", {"blind_spots": _cur.metrics().get("blind_spots", [])[:5]}, source="runtime")
                            except Exception: pass
                    except Exception as _cue:
                        print(f"[Curiosity] brief skipped: {_cue}")
                    # OX-BELIEF-REVISION-1 RECALL: surface promoted beliefs whose
                    # recent evidence contradicts them (drift). Awareness only — no
                    # promotion / demotion / correction.
                    try:
                        import belief_revision as _bro
                        _bro_rev = _bro.review()
                        _bro_brief = _bro.render_brief(_bro_rev)
                        if _bro_brief:
                            cur.append({"role": "system", "content": _bro_brief})
                            yield f"data: {json.dumps({'type':'belief_revision','drift':len(_bro_rev.get('belief_drift',[])),'strengths':len(_bro_rev.get('strengths',[]))}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("belief_revision", {"drift": len(_bro_rev.get("belief_drift", []))}, source="runtime")
                            except Exception: pass
                    except Exception as _broe:
                        print(f"[BeliefRevision] brief skipped: {_broe}")
                    # OX-FIRST-PRINCIPLE-1 RECALL: surface principles cross-validated
                    # by >=2 systems (candidates, not rules). Read-only awareness.
                    try:
                        import first_principles as _fp
                        _fp_list = _fp.all_principles()
                        _fp_brief = _fp.render_brief(_fp_list)
                        if _fp_brief:
                            cur.append({"role": "system", "content": _fp_brief})
                            yield f"data: {json.dumps({'type':'first_principles','count':len(_fp_list)}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("first_principles", {"count": len(_fp_list)}, source="runtime")
                            except Exception: pass
                    except Exception as _fpe:
                        print(f"[FirstPrinciples] brief skipped: {_fpe}")
                    # OX-DECISION-1 RECALL: synthesize structured recommendations
                    # from the epistemic layers (advisory — no behavior change).
                    try:
                        import decision as _dec
                        _dec_list = _dec.decide()
                        _dec_brief = _dec.render_brief(_dec_list)
                        if _dec_brief:
                            cur.append({"role": "system", "content": _dec_brief})
                            yield f"data: {json.dumps({'type':'decisions','count':len(_dec_list),'top':[d['recommendation'] for d in _dec_list[:3]]}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("decisions", {"count": len(_dec_list)}, source="runtime")
                            except Exception: pass
                    except Exception as _dece:
                        print(f"[Decision] brief skipped: {_dece}")
                    # OX-CONFIDENCE-1 RECALL: where the House's predicted confidence
                    # diverges from observed outcomes (over/under-confidence). Awareness only.
                    try:
                        import calibration as _cal
                        _cal_list = _cal.calibrate()
                        _cal_brief = _cal.render_brief(_cal_list)
                        if _cal_brief:
                            cur.append({"role": "system", "content": _cal_brief})
                            yield f"data: {json.dumps({'type':'calibration','metrics':_cal.metrics(_cal_list).get('by_status',{})}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("calibration", {"by_status": _cal.metrics(_cal_list).get("by_status", {})}, source="runtime")
                            except Exception: pass
                    except Exception as _cale:
                        print(f"[Calibration] brief skipped: {_cale}")
                    # OX-EXPERIMENT-1 RECALL: recommend controlled experiments to
                    # validate confident beliefs (esp. those with recent drift).
                    # Recommendation only — never runs anything.
                    try:
                        import experiment as _exp
                        _exp_list = _exp.design()
                        _exp_brief = _exp.render_brief(_exp_list)
                        if _exp_brief:
                            cur.append({"role": "system", "content": _exp_brief})
                            yield f"data: {json.dumps({'type':'experiments','count':len(_exp_list),'high':sum(1 for e in _exp_list if e.get('priority')=='high')}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("experiments", {"count": len(_exp_list)}, source="runtime")
                            except Exception: pass
                    except Exception as _expe:
                        print(f"[Experiment] brief skipped: {_expe}")
                    # OX-THEORY-1 RECALL: surface patterns that generalize across
                    # domains (theory candidates). Awareness only — not laws.
                    try:
                        import theory as _thy
                        _thy_list = _thy.form()
                        _thy_brief = _thy.render_brief(_thy_list)
                        if _thy_brief:
                            cur.append({"role": "system", "content": _thy_brief})
                            yield f"data: {json.dumps({'type':'theories','count':len(_thy_list)}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("theories", {"count": len(_thy_list)}, source="runtime")
                            except Exception: pass
                    except Exception as _thye:
                        print(f"[Theory] brief skipped: {_thye}")
                    # OX-RESEARCH-AGENDA-1 RECALL: what to investigate next, ranked
                    # by impact x uncertainty x leverage. Advisory — no scheduling.
                    try:
                        import research_agenda as _ra
                        _ra_list = _ra.form()
                        _ra_brief = _ra.render_brief(_ra_list)
                        if _ra_brief:
                            cur.append({"role": "system", "content": _ra_brief})
                            yield f"data: {json.dumps({'type':'research_agenda','count':len(_ra_list),'top':(_ra_list[0]['topic'] if _ra_list else None)}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("research_agenda", {"count": len(_ra_list)}, source="runtime")
                            except Exception: pass
                    except Exception as _rae:
                        print(f"[ResearchAgenda] brief skipped: {_rae}")
                    # OX-UNKNOWNS-1 RECALL: epistemic self-map (known knowns /
                    # known unknowns / unknown unknowns). Awareness only.
                    try:
                        import unknowns as _unk
                        _unk_state = _unk.analyze()
                        _unk_brief = _unk.render_brief(_unk_state)
                        if _unk_brief:
                            cur.append({"role": "system", "content": _unk_brief})
                            yield f"data: {json.dumps({'type':'unknowns','metrics':_unk.metrics(_unk_state)}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("unknowns", {"unknown_unknowns": _unk.metrics(_unk_state).get("unknown_unknowns", 0)}, source="runtime")
                            except Exception: pass
                    except Exception as _unke:
                        print(f"[Unknowns] brief skipped: {_unke}")
                    # OX-PARADIGM-1 RECALL: dominant frameworks + their evolution
                    # (stable / shifting / emerging). Awareness only.
                    try:
                        import paradigm as _pgm
                        _pgm_state = _pgm.evolve()
                        _pgm_brief = _pgm.render_brief(_pgm_state)
                        if _pgm_brief:
                            cur.append({"role": "system", "content": _pgm_brief})
                            yield f"data: {json.dumps({'type':'paradigms','metrics':_pgm.metrics(_pgm_state)}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("paradigms", {"shifts": _pgm.metrics(_pgm_state).get("paradigm_shifts", 0)}, source="runtime")
                            except Exception: pass
                    except Exception as _pgme:
                        print(f"[Paradigm] brief skipped: {_pgme}")
                if _acq_gaps:
                    _aq_brief = _acq.render_brief(_acq_gaps)
                    if _aq_brief:
                        cur.append({"role": "system", "content": _aq_brief})
                        yield f"data: {json.dumps({'type':'acquisition_planned','gaps':len(_acq_gaps),'sources':[_acq.attempt_order(g) for g in _acq_gaps[:3]]}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("acquisition_planned", {"gaps": len(_acq_gaps)}, source="runtime")
                        except Exception: pass
            except Exception as _aqe:
                print(f"[Acquisition] plan skipped: {_aqe}")
            # OX-1.6 EVIDENCE-BASED COMPLETION — verify DONE_WHEN against real
            # evidence before accepting a self-asserted TASK_COMPLETE.
            try:
                import completion_evidence as _completion_check
            except Exception:
                _completion_check = None
            completion_rejections   = 0
            _MAX_COMPLETION_REJECTS = 2
            blocked            = False     # OX-1.4: run hit a dead end (varied actions, no new info)
            run_halted         = False     # set when the run ends via agent_stuck (not step limit)
            commander_calls    = 0         # SKYNET ELITE COMMANDER interventions (max 2)
            silence_recoveries = 0         # P0: context-recovery attempts before surrendering to silence
            # CONVERGENCE PRESSURE — exploring is allowed, wandering is not.
            # Successful read-only calls don't trip failure/dedupe gates, so a model
            # can list_files every folder forever. Count and force synthesis.
            _EXPLORE_TOOLS = {"list_files", "read_file", "find_files", "grep_search",
                              "file_info", "obsidian_list_notes", "obsidian_read_note",
                              "obsidian_search", "search_obsidian", "read_obsidian_note"}
            explore_streak   = 0           # consecutive successful exploration calls
            same_tool_streak = 0           # same tool repeated back-to-back
            last_tool_name   = ""
            files_touched    = []          # for Commander sign-off in the mission ledger
            halt_reason      = ""          # why the run halted (signed into the ledger)
            captured_plan      = ""        # populated from step-1 PLAN: line
            captured_done_when = ""        # GTS-1: verifiable completion criteria (DONE_WHEN: line)
            tool_results_log = []          # [(name, result_text), ...] for VALUE-MATCH GATE
            _g1_events = []                # Vol V G1: ordered acts+observations for guidance_check
            task_done = False

            # OX-1.5 EXECUTION MEMORY — build the footer appended to this run's
            # summary so a FUTURE run can recall what THIS run learned. Reads the
            # live world/exec-conf/halt at call time. Returns "" if recall absent.
            def _mem_footer(_status: str) -> str:
                try:
                    if not _exec_recall:
                        return ""
                    return _exec_recall.encode_footer(
                        _world.snapshot() if _world is not None else None,
                        _exec_conf.value() if _exec_conf is not None else None,
                        blocked, halt_reason, _status)
                except Exception:
                    return ""

            # ── L3 COMPOUND MIND — tokenize the prompt and SPLIT THE WORK NOW ──
            # Replaces linear 1-2-3-4-5 stepping: explore solution axes, pick the
            # optimal path, emit dependency-tracked work groups (independent tracks
            # run back-to-back). L6 Cosmic Mind plan-analysis runs for long-horizon
            # / system / macro tasks. Injected as a system message that overrides the
            # naive "PLAN: 1) 2) 3)" instruction. Best-effort: any failure falls back
            # to the linear loop, never breaks the run.
            _compound_active = False
            if _COMPOUND_AVAILABLE:
                try:
                    if _compound.should_run_compound(req.task or ""):
                        yield f"data: {json.dumps({'type':'compound_start','text':'L3 Compound Mind — tokenizing prompt and splitting work'}, ensure_ascii=False)}\n\n"
                        _cplan = await _compound.compound_decompose(
                            req.task or "", context=None, model=model,
                            base_url=get_active_base_url(), api_key=get_active_api_key(),
                        )
                        if _cplan:
                            _compound_active = True
                            _cmsg = _compound.format_compound_for_agent(_cplan)
                            cur.append({"role": "system", "content": _cmsg})
                            # Prefill so the loop already has the plan + DONE_WHEN and
                            # never asks the model for a linear "PLAN: 1) 2) 3)" line.
                            captured_plan = _compound.plan_oneliner(_cplan)
                            if _cplan.get("done_when"):
                                captured_done_when = str(_cplan["done_when"])[:400]
                            _grp = _cplan.get("groups") or []
                            yield f"data: {json.dumps({'type':'compound_plan','chosen':_cplan.get('chosen_axis',''),'groups':[[t.get('id') for t in g] for g in _grp],'tracks':_cplan.get('tracks',[]),'done_when':captured_done_when}, ensure_ascii=False)}\n\n"
                            if _cplan.get("cosmic"):
                                yield f"data: {json.dumps({'type':'cosmic_view','cosmic':_cplan['cosmic']}, ensure_ascii=False)}\n\n"
                except Exception as _ce:
                    print(f"[CompoundMind] decompose skipped: {_ce}")

            # OPENCLAW PORT — per-run state
            _ocp_session_id = hashlib.sha1(
                f"{req.task[:80]}:{time.time()}".encode()
            ).hexdigest()[:10]
            # COGNITIVE KERNEL (D2) — bind a per-request cognitive id, grouped by this
            # mission, so every policy/lifecycle/cognitive event of the run traces
            # together on the audit spine. (Must come AFTER _ocp_session_id exists.)
            try:
                import kernel_events as _ke_ctx
                _cog_cid = _ke_ctx.set_context(mission_id=str(_ocp_session_id))
            except Exception as _kce:
                _cog_cid = ""
                print(f"[Kernel] correlation not bound: {_kce}")
            _traj = _OCPTrajectory(
                session_id=_ocp_session_id,
                task=req.task,
                model=model,
            )
            _approvals = _OCPApprovals()
            _ocp_t0 = time.time()
            _ocp_blocked = 0

            # OPENCLAW PORT: L1 Volition extraction (drive/tone/urgency/gap)
            try:
                _volition = _vol_extract(req.task)
                # Always log to trajectory for replay/audit
                if hasattr(_traj, "_emit"):
                    _traj._emit("volition", {
                        "drive":          getattr(_volition, "drive", "?"),
                        "emotional_tone": getattr(_volition, "emotional_tone", "?"),
                        "urgency":        getattr(_volition, "urgency", "?"),
                        "gap_detected":   getattr(_volition, "gap_detected", False),
                        "gap_note":       getattr(_volition, "gap_note", ""),
                        "drive_score":    getattr(_volition, "drive_score", {}),
                    })
                # Stream a UI-visible event too
                yield f"data: {json.dumps({'type':'agent_volition','drive':getattr(_volition,'drive','?'),'tone':getattr(_volition,'emotional_tone','?'),'urgency':getattr(_volition,'urgency','?'),'gap':getattr(_volition,'gap_detected',False)}, ensure_ascii=False)}\n\n"
                # Inject directive as system msg — model sees it BEFORE first action
                _v_directive = _vol_directive(_volition)
                if _v_directive:
                    cur.append({"role": "system", "content": _v_directive})
            except Exception as _ve:
                print(f"[VolitionEngine] extract failed: {_ve}")

            # ── ATLAS — Director of Global Intelligence (Supreme Council #2) ──
            # กุนซือของสภา: Money Atlas Genesis Protocol × ElmatadorZ Secret OS,
            # compact counsel attached only to non-trivial missions (saves num_ctx).
            try:
                _t = (req.task or "")
                _atlas_on = len(_t) >= 60 or any(k in _t.lower() for k in (
                    "วิเคราะห์", "กลยุทธ", "แผน", "ตลาด", "ลงทุน", "สร้างระบบ", "ออกแบบ",
                    "strategy", "analy", "plan", "market", "invest", "design", "architect"))
                if _atlas_on:
                    yield f"data: {json.dumps({'type':'atlas','text':'ATLAS counsel attached — Genesis Protocol frame engaged.'}, ensure_ascii=False)}\n\n"
                    cur.append({"role": "system", "content": (
                        "🌐 ATLAS — DIRECTOR OF GLOBAL INTELLIGENCE (Supreme Council counsel, "
                        "Money Atlas × ElmatadorZ Secret OS):\n"
                        "Frame the mission in ONE line each before acting: Problem / Cause / "
                        "Mechanism / Leverage (the asymmetric move) / Outcome.\n"
                        "Any analysis or strategy output MUST give scenarios (bull/bear/base) — "
                        "never a single prediction — with confidence %, the invalidation point, "
                        "and missing data named explicitly.\n"
                        "FPCOS honesty: no fabricated numbers — fetch live data with tools first; "
                        "certainty without critique = hallucination. "
                        "\"We do not follow the map. We draw what others will follow.\""
                    )})
                    # M2: brief ATLAS with THE HOUSE's own graded history on this directive,
                    # so it enters informed — never repeating disproven reasoning.
                    try:
                        _hb = _deliberation_briefing.build_brief(req.task)
                        if _hb.get("n_cases", 0) > 0:
                            cur.append({"role": "system",
                                        "content": _deliberation_briefing.format_brief_for_council(_hb)})
                            yield f"data: {json.dumps({'type':'brief','n_cases':_hb['n_cases'],'repeated_errors':len(_hb.get('repeated_errors',[]))}, ensure_ascii=False)}\n\n"
                    except Exception as _hbe:
                        print(f"[Briefing] agent_run brief skipped: {_hbe}")
                    # HOUSE MIND: read the shared cognitive state so the House knows
                    # what it already knows / believes (incl. its own composition).
                    try:
                        _hsid = _house_state.open_state(_mission_identity)   # OX-H1: clean identity only
                        _hst = _house_state.read_state(_hsid)
                        if _hst:
                            cur.append({"role": "system",
                                        "content": _house_state.format_state_for_council(_hst)})
                            yield f"data: {json.dumps({'type':'house_mind','state_id':_hsid,'confidence':_hst.get('confidence',0)}, ensure_ascii=False)}\n\n"
                    except Exception as _hme:
                        print(f"[HouseMind] agent_run inject skipped: {_hme}")
            except Exception as _ae:
                print(f"[Atlas] counsel inject failed: {_ae}")
            # Tools whose successful execution should trigger workspace git commit
            _GIT_TRIGGER_TOOLS = {
                "write_file", "edit_file", "create_folder", "delete_file",
                "move_file", "copy_file", "write_obsidian_note",
            }
            # OPENCLAW PORT T2: register this run in agent_runs DB
            try:
                _AGENT_RUNS_DB.start_run(
                    run_id=_ocp_session_id,
                    task=_mission_identity,   # OX-H1: ledger stores MISSION IDENTITY, not the prompt
                    model=model,
                    trajectory_path=str(_traj.path) if getattr(_traj, "path", None) else "",
                )
            except Exception as _re:
                print(f"[agent_runs] start_run failed: {_re}")
            # OX-SKILL-2: skills develop like human skills — record WHICH skills
            # were auto-activated for this run; reputation() grades them against
            # the run's final status and the router reweights future routing.
            try:
                if _activated_skill_names:
                    import skill_ledger as _slg
                    _slg.record_activation(_ocp_session_id, _activated_skill_names)
            except Exception as _sle:
                print(f"[skill_ledger] activation record skipped: {_sle}")

            yield f"data: {json.dumps({'type':'agent_start','task':_mission_identity,'max_steps':MAX_STEPS,'run_id':_ocp_session_id})}\n\n"
            try: house_sync.publish("mission_started", {"task": (_mission_identity or "")[:300], "max_steps": MAX_STEPS}, source="runtime")
            except Exception: pass
            if _gate_note:
                yield f"data: {json.dumps({'type':'text','text':'🛡 ' + _gate_note + chr(10)}, ensure_ascii=False)}\n\n"


            # ── WATCHDOG: hard wall-clock budget so a run can NEVER hang forever ──
            # Independent of the per-LLM-call read timeouts (which only guard a single
            # HTTP read). This guarantees the generator reaches a terminal state even
            # if a fast inner loop or external stall slips past every other guard.
            _RUN_BUDGET_S = 1500.0   # 25 min absolute cap per agent run
            for step in range(MAX_STEPS):
                step_num = step + 1
                # Watchdog tripwire — halt cleanly with a reported outcome (not a silent hang)
                if time.time() - _ocp_t0 > _RUN_BUDGET_S:
                    run_halted = True
                    halt_reason = f"watchdog timeout — exceeded {int(_RUN_BUDGET_S)}s wall-clock budget"
                    yield f"data: {json.dumps({'type':'agent_stuck','step':step_num,'text':halt_reason,'reason':'watchdog_timeout'}, ensure_ascii=False)}\n\n"
                    break
                yield f"data: {json.dumps({'type':'agent_step','step':step_num,'max':MAX_STEPS})}\n\n"
                _traj.step_begin(step_num)

                # ── Inject live COMPLETED_ACTIONS ledger before every step ──
                # Unique sentinel ensures we always strip the OLD ledger before adding the new one.
                LEDGER_MARK = "[[SKYNET_LEDGER_v1]]"
                plan_block = f"## PLAN (from step 1):\n  {captured_plan}\n\n" if captured_plan else ""
                dw_block = (f"## DONE_WHEN (GTS-1 criteria — ALL must hold before TASK_COMPLETE):\n  {captured_done_when}\n\n"
                            if captured_done_when else "")
                # OX-1.1: inject the VERIFIED WORLD (what has been confirmed to exist/absent)
                _world_block = ""
                if _world is not None:
                    try:
                        _wb = _world.render()
                        if _wb: _world_block = _wb + "\n\n"
                    except Exception: pass
                first_step_ask = ("" if (step_num > 1 or captured_done_when) else
                                  " Begin your reply with 'PLAN: <one line>' then 'DONE_WHEN: <verifiable completion criteria>'.")
                ledger_msg = {
                    "role": "user",   # 'user' role is safer for small models than mid-stream 'system'
                    "content": (
                        f"{LEDGER_MARK}\n"
                        f"{plan_block}"
                        f"{dw_block}"
                        f"{_world_block}"
                        "## COMPLETED_ACTIONS (do NOT repeat any of these — they are already done):\n"
                        f"{_format_completed(action_sigs)}\n\n"
                        f"Current step: {step_num} / {MAX_STEPS}. "
                        f"Total tool calls so far: {total_tool_calls}. "
                        "Choose a tool call that is NOT already in the list above. "
                        "If everything from your PLAN is in the list above and DONE_WHEN holds, reply TASK_COMPLETE."
                        f"{first_step_ask}"
                    )
                }
                # Strip ANY prior ledger by sentinel — robust regardless of header text
                cur = [m for m in cur if not (
                    isinstance(m.get("content"), str) and
                    LEDGER_MARK in m["content"]
                )]
                cur.append(ledger_msg)

                # ── P0 CONTEXT BUDGET + OPERATIVE RECOVERY ──────────────────
                # Measure the live context BEFORE the model call. On warning,
                # surface it. On CRITICAL, compress older raw tool output into a
                # factual mission snapshot and CONTINUE — never overflow → never
                # "operative went silent (context overload)".
                try:
                    import context_budget as _cb, mission_snapshot as _ms
                    _bdg = _cb.assess(cur, tools=_MISSION_TOOLS, limit=_ctx_window)
                    for _et, _ep in _cb.events(_bdg):
                        yield f"data: {json.dumps({'type': _et, 'step': step_num, **_ep})}\n\n"
                        try: house_sync.publish(_et, {**_ep, "step": step_num}, source="runtime")
                        except Exception: pass
                    if _bdg["level"] == "critical":
                        cur, _snap, _dropped = _ms.compress(cur, keep_recent=6)
                        _rec = {"step": step_num, "dropped": _dropped,
                                "n_tool_calls": _snap.get("n_tool_calls", 0),
                                "objective": _snap.get("objective", "")[:200],
                                "freed_tokens": _bdg["total"] - _cb.assess(cur, tools=_MISSION_TOOLS, limit=_ctx_window)["total"]}
                        yield f"data: {json.dumps({'type': 'mission_recovered', **_rec}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("mission_recovered", _rec, source="runtime")
                        except Exception: pass
                        # ── TURN-0 RESIDUAL CASE: compress() had no tool-history
                        # middle to drop (static preamble+schema alone is the
                        # overflow source — the shape that overflowed in
                        # production, n_prompt_tokens=17160/16384). If we're
                        # still on the full (non-compact) system prompt, downgrade
                        # it now instead of sending a request already known to
                        # overflow num_ctx.
                        if (_dropped == 0 and not _use_compact and _MODULAR_PROMPT_COMPACT
                                and cur and cur[0].get("role") == "system"
                                and cur[0].get("content") == _selected_prompt):
                            cur[0]["content"] = _MODULAR_PROMPT_COMPACT
                            _use_compact = True
                            _after = _cb.assess(cur, tools=_MISSION_TOOLS, limit=_ctx_window)
                            _dg = {"step": step_num, "reason": "static_overflow_no_history_to_compress",
                                   "freed_tokens": _bdg["total"] - _after["total"], "level_after": _after["level"]}
                            yield f"data: {json.dumps({'type': 'prompt_downgraded', **_dg}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("prompt_downgraded", _dg, source="runtime")
                            except Exception: pass
                except Exception as _cbe:
                    print(f"[ContextBudget] skipped: {_cbe}")

                # NEVER SEND AN OVER-BUDGET REQUEST (Claude Code borrow): fit the
                # assembled context to the window before every call, so the model
                # runtime can't return a ReadError from an oversized prompt.
                _fitted = _fit_context(cur, _ctx_window, _MISSION_TOOLS)
                if len(_fitted) < len(cur):
                    yield f"data: {json.dumps({'type':'agent_think','step':step_num,'text':f'⟢ context fit: {len(cur)}→{len(_fitted)} msgs to stay under {_ctx_window} tok'})}\n\n"
                payload = {
                    "model": model,
                    "messages": _fitted,
                    "stream": True,
                    "tools": _MISSION_TOOLS,
                    "keep_alive": "30m",
                    "options": {"num_ctx": _ctx_window, "temperature": 0.1}
                }
                # OX-EXECUTION-RECOVERY-1: the EXECUTION path never deep-thinks.
                # Local thinking-models emit a correct tool call in ~8s with
                # think=false vs spending the entire 180s step budget thinking
                # (proven: OX-TOOLCALL-AUDIT-1). Cloud models don't accept 'think'.
                if not _exec_is_cloud:
                    payload["think"] = False

                tool_calls_this = []
                text_this = []
                think_chunks_this = 0

                # ── Per-step retry loop (handles Ollama stream aborts) ──────────
                # Reduced from 3 to 2 to avoid retry storms on overloaded Ollama.
                # Key fix: if we already captured tool calls before the stream errored,
                # we EXECUTE them (with dedupe guard) instead of re-prompting — that's
                # what was causing the "model thinks → times out → re-thinks → loops".
                STEP_RETRIES = 3   # was 2 — a transient ReadError deserves one more, trimmed
                step_succeeded = False
                tool_calls_this = []
                text_this = []
                stream_errors_this = []   # HONEST-FAILURE: provider errors must surface
                for attempt in range(STEP_RETRIES):
                    # Only reset buffers on first attempt or if previous attempt produced nothing
                    if attempt == 0 or (not tool_calls_this and not text_this):
                        tool_calls_this = []
                        text_this = []
                        think_chunks_this = 0
                    # RE-FIT per attempt: a retry after an over-budget ReadError must
                    # send LESS, not the same payload again (escalating trim).
                    _fitted = _fit_context(cur, _ctx_window, _MISSION_TOOLS, aggressive=(attempt > 0))
                    payload["messages"] = _fitted
                    if attempt > 0 and len(_fitted) < len(cur):
                        yield f"data: {json.dumps({'type':'agent_think','step':step_num,'text':f'↻ retry {attempt}: trimmed to {len(_fitted)} msgs'})}\n\n"
                    try:
                        # OX-KERNEL-ACTIVATION-1: when the flag is on, the EXECUTION
                        # path goes through the Runtime Kernel (capability negotiation
                        # → driver → runtime); the agent passes only messages+tools and
                        # never names a runtime/model. Flag off → legacy path, unchanged.
                        if _kernel_enabled():
                            _stream_iter = _kernel_exec_stream(
                                _fitted, _MISSION_TOOLS, {"temperature": 0.1}).__aiter__()
                        else:
                            _stream_iter = _llm_stream(payload, base, key, api_type=_exec_api_type).__aiter__()
                        _pending_stream = None
                        _transient_err = False   # set on a retryable provider error (ReadError, reset, timeout)
                        _step_stream_started = time.time()
                        _STEP_STREAM_BUDGET_S = 180.0
                        while True:
                            if _pending_stream is None:
                                _pending_stream = asyncio.ensure_future(_stream_iter.__anext__())
                            _done, _ = await asyncio.wait({_pending_stream}, timeout=8.0)
                            if not _done:
                                yield f"data: {json.dumps({'type':'keepalive'})}\n\n"
                                if time.time() - _step_stream_started > _STEP_STREAM_BUDGET_S:
                                    try: _pending_stream.cancel()
                                    except Exception: pass
                                    _emsg = f"model stream step timeout after {int(_STEP_STREAM_BUDGET_S)}s before terminal event"
                                    stream_errors_this.append(_emsg)
                                    print(f"[agent_run] stream error (step {step_num}): {_emsg}")
                                    yield f"data: {json.dumps({'type':'agent_error','step':step_num,'msg':_emsg}, ensure_ascii=False)}\n\n"
                                    break
                                continue
                            _stream_task = _pending_stream
                            _pending_stream = None
                            try:
                                raw = _stream_task.result()
                            except StopAsyncIteration:
                                break
                            ev = json.loads(raw)
                            if ev["type"] == "__tool_calls__":
                                tool_calls_this.extend(ev["calls"])
                            elif ev["type"] == "done":
                                step_succeeded = True
                                break
                            elif ev["type"] == "keepalive":
                                # Forward heartbeat so UI knows the model is warming/generating
                                yield f"data: {json.dumps({'type':'keepalive'})}\n\n"
                            elif ev["type"] == "error":
                                # HONEST-FAILURE: swallowing these caused invisible empty
                                # runs that "completed" with "(no text response)". Surface
                                # to console + UI; loop decides below whether to halt.
                                _emsg = str(ev.get("msg", ""))[:500]
                                stream_errors_this.append(_emsg)
                                print(f"[agent_run] stream error (step {step_num}): {_emsg}")
                                yield f"data: {json.dumps({'type':'agent_error','step':step_num,'msg':_emsg}, ensure_ascii=False)}\n\n"
                                # TRANSIENT provider errors (ReadError, connection reset,
                                # timeout, EOF) are retryable — break out so the retry loop
                                # re-attempts with a TRIMMED context, instead of piling up
                                # errors and halting the whole mission.
                                _low = _emsg.lower()
                                if (not tool_calls_this and not text_this and
                                    any(k in _low for k in ("readerror", "read error", "reset",
                                        "timeout", "timed out", "eof", "connection", "broken pipe",
                                        "incomplete", "overflow", "context"))):
                                    _transient_err = True
                                    break
                            elif ev["type"] == "think" and ev.get("text"):
                                think_chunks_this += 1
                                yield f"data: {json.dumps({'type':'agent_think','step':step_num,'text':ev['text'],'is_think':True})}\n\n"
                            elif ev["type"] == "text" and ev.get("text"):
                                text_this.append(ev["text"])
                                yield f"data: {json.dumps({'type':'agent_think','step':step_num,'text':ev['text'],'is_think':False})}\n\n"
                        if not step_succeeded and (text_this or tool_calls_this):
                            # Stream closed without 'done' but we got content — treat OK
                            step_succeeded = True
                        # a transient provider error with no content → retry (trimmed)
                        if _transient_err and not step_succeeded and attempt < STEP_RETRIES - 1:
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                        break  # exit retry loop on clean finish
                    except (asyncio.CancelledError, GeneratorExit):
                        return
                    except Exception as e:
                        err_msg = repr(e)
                        # ── KEY FIX: if we already have tool calls, don't retry —
                        # use them. Retrying would re-prompt model and re-emit duplicates.
                        if tool_calls_this:
                            yield f"data: {json.dumps({'type':'agent_think','step':step_num,'text':'⚠ Stream cut but tool calls captured — executing what we have.'})}\n\n"
                            step_succeeded = True
                            break
                        if attempt < STEP_RETRIES - 1:
                            yield f"data: {json.dumps({'type':'agent_think','step':step_num,'text':f'⚠ Stream interrupted ({attempt+1}/{STEP_RETRIES}), retrying…'})}\n\n"
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        else:
                            yield f"data: {json.dumps({'type':'agent_error','step':step_num,'msg':err_msg})}\n\n"
                            await asyncio.sleep(1)
                            break

                full_text = "".join(text_this)

                # ── Capture PLAN line on step 1 (or first time we see one) ──
                if not captured_plan and "PLAN:" in full_text:
                    try:
                        line = full_text.split("PLAN:", 1)[1]
                        # Take only the first line / up to a newline boundary
                        line = line.splitlines()[0].strip() if line.strip() else ""
                        # Models often write "PLAN: ... | DONE_WHEN: ..." on one line —
                        # keep only the plan part here (DONE_WHEN is captured separately)
                        if "DONE_WHEN:" in line:
                            line = line.split("DONE_WHEN:", 1)[0].rstrip(" |·—-").strip()
                        if line:
                            captured_plan = line[:600]
                            yield f"data: {json.dumps({'type':'agent_plan','step':step_num,'plan':captured_plan})}\n\n"
                            _traj.plan_captured(captured_plan)
                    except Exception:
                        pass

                # ── Capture DONE_WHEN (GTS-1 completion criteria) ──
                if not captured_done_when and "DONE_WHEN:" in full_text:
                    try:
                        line = full_text.split("DONE_WHEN:", 1)[1]
                        line = line.splitlines()[0].strip() if line.strip() else ""
                        if line:
                            captured_done_when = line[:400]
                            yield f"data: {json.dumps({'type':'agent_plan','step':step_num,'plan':'DONE_WHEN — ' + captured_done_when}, ensure_ascii=False)}\n\n"
                    except Exception:
                        pass

                # ── Check TASK_COMPLETE ────────────────────────────────────
                if "TASK_COMPLETE" in full_text:
                    summary = full_text.split("TASK_COMPLETE", 1)[-1].strip()
                    if not summary:
                        # Models usually write the summary BEFORE the keyword — use it,
                        # otherwise the mission ends with no closing answer in the UI.
                        summary = full_text.split("TASK_COMPLETE", 1)[0].strip()[-2000:]
                    # ── OX-1.6 EVIDENCE-BASED COMPLETION ──────────────────────
                    # A self-asserted TASK_COMPLETE is not enough — verify the
                    # DONE_WHEN criteria against real evidence (world model +
                    # files_touched + tool results). Reject unproven claims.
                    # ALWAYS verify: use the declared DONE_WHEN, or derive one from
                    # the task (any output file it names) so a self-asserted
                    # TASK_COMPLETE is never accepted blind (Claude Code discipline).
                    _effective_done_when = captured_done_when or _baseline_done_when(req.task or "")
                    if _completion_check is not None and _effective_done_when:
                        try:
                            _verdict = _completion_check.verify(
                                _effective_done_when,
                                _world.snapshot() if _world is not None else None,
                                files_touched, tool_results_log)
                        except Exception:
                            _verdict = None
                        if _verdict and not _verdict.get("proven", True):
                            completion_rejections += 1
                            if completion_rejections <= _MAX_COMPLETION_REJECTS:
                                cur.append({"role": "user", "content":
                                    _completion_check.render_rejection(
                                        _verdict, completion_rejections, _MAX_COMPLETION_REJECTS)})
                                yield f"data: {json.dumps({'type':'completion_rejected','step':step_num,'missing':_verdict.get('missing',[])[:8],'attempt':completion_rejections}, ensure_ascii=False)}\n\n"
                                try: house_sync.publish("completion_rejected", {"missing": _verdict.get("missing", [])[:8], "attempt": completion_rejections, "step": step_num}, source="runtime")
                                except Exception: pass
                                continue   # let the model PROVE it; do not accept yet
                            elif _verdict.get("disproven"):
                                # claimed artifact verified ABSENT → honest FAILED, never fake SUCCESS
                                run_halted = True
                                halt_reason = ("completion unproven — DONE_WHEN artifact(s) verified "
                                               "ABSENT: " + ", ".join(_verdict.get("disproven_hits", [])[:3]))
                                yield f"data: {json.dumps({'type':'agent_stuck','step':step_num,'text':halt_reason,'reason':'completion_unproven'}, ensure_ascii=False)}\n\n"
                                break
                            else:
                                # weak miss after retries — accept but record the doubt honestly
                                _miss = ", ".join(_verdict.get("missing", [])[:3])
                                summary += f"  [⚠ completed without full DONE_WHEN evidence: {_miss}]"
                                yield f"data: {json.dumps({'type':'completion_unverified','step':step_num,'missing':_verdict.get('missing',[])[:8]}, ensure_ascii=False)}\n\n"
                    # ── COGNITIVE VALIDATION LAYER (CVL) — the cognitive quality gate ──
                    # Observe → Diagnose → Repair → Explain → Validate → Accept.
                    # Before accepting the answer, run every applicable cognitive
                    # validator (reasoning/arithmetic, safety/secret-leak, …). An error
                    # sends a repair prompt back and re-prompts (bounded), so a wrong
                    # calculation — or a leaked credential — never ships. Every repair
                    # emits a human-readable Explain record for transparency/auditability.
                    try:
                        import cognitive_validation as _cvl
                        _cv = _cvl.validate(summary + "\n" + (full_text or ""))
                        if not _cv["ok"] and completion_rejections <= _MAX_COMPLETION_REJECTS:
                            completion_rejections += 1
                            cur.append({"role": "user", "content": _cv["repair_prompt"]})
                            yield f"data: {json.dumps({'type':'cognitive_invalid','step':step_num,'domains':_cv['domains'],'issues':_cv['errors'][:6],'explanation':_cv['explanation'],'attempt':completion_rejections}, ensure_ascii=False)}\n\n"
                            # Cognitive Kernel Event subsystem (migration step 1):
                            # cognitive.* is CVL's authority namespace; audit-critical
                            # → durably logged, then relayed to the live bus.
                            try:
                                import kernel_events as _ke
                                _ke.emit("cognitive.invalid", {"domains": _cv["domains"], "issues": [e['message'] for e in _cv['errors'][:5]], "explanation": _cv["explanation"], "attempt": completion_rejections, "step": step_num}, source="cvl", severity="error")
                            except Exception: pass
                            print(f"[CVL] repair (attempt {completion_rejections}) — {_cv['explanation']}")
                            continue   # Repair → let the model correct, then re-Validate
                        elif not _cv["ok"]:
                            # still invalid after retries — accept but flag honestly + audit
                            _bad = "; ".join(e["message"] for e in _cv["errors"][:2])
                            summary += f"  [⚠ unverified ({', '.join(_cv['domains'])}): {_bad}]"
                            yield f"data: {json.dumps({'type':'cognitive_unverified','step':step_num,'domains':_cv['domains'],'issues':_cv['errors'][:6],'explanation':_cv['explanation']}, ensure_ascii=False)}\n\n"
                            print(f"[CVL] accepted-with-flag — {_cv['explanation']}")
                        elif _cv["explanation"]:
                            # warnings only (no error) — surface the audit note, still accept
                            yield f"data: {json.dumps({'type':'cognitive_note','step':step_num,'domains':_cv['domains'],'explanation':_cv['explanation']}, ensure_ascii=False)}\n\n"
                    except Exception as _cvle:
                        print(f"[CVL] validation skipped: {_cvle}")
                    task_done = True
                    # Persist memory
                    mem["context"].extend([
                        {"role": "user", "content": req.task},
                        {"role": "assistant", "content": full_text[:500]}
                    ])
                    mem["sessions"].append({
                        "task": req.task[:200], "steps": step_num,
                        "tools": total_tool_calls, "ts": time.time()
                    })
                    save_agent_memory(mem)
                    yield f"data: {json.dumps({'type':'agent_complete','steps':step_num,'tools_used':total_tool_calls,'summary':summary,'done_when':captured_done_when}, ensure_ascii=False)}\n\n"
                    # ── CEE bridge · C1 made runtime ── check the final answer for
                    # fabricated file references (claimed reading a file that does
                    # not exist), persist the verdict to the durable warrant log,
                    # and emit a violation. This turns the Warrant theory's C1 (no
                    # belief presented beyond its warrant) from philosophy into an
                    # enforced runtime observation.
                    # ══ PRE_COMMIT — the Cognitive Kernel policy hook (SPEC §5, step 5) ══
                    # Warrant (CEE-C1, fabricated observation) and Guidance (Vol V G1,
                    # deviant/invented-target act) are now Policies on PRE_COMMIT,
                    # resolved by the kernel and recorded on the audit spine. Each keeps
                    # its exact legacy side effects (persist, SSE, bus publish); only the
                    # AUTHORITY moved. Fail-SAFE: a broken engine flags, never silently
                    # ships a clean verdict.
                    try:
                        _answer_text = (summary or "") + "\n" + (full_text or "")
                        _commit = _kexec.pre_commit({
                            "answer": _answer_text,
                            "workspace_folder": workspace_resolved,
                            "task": (req.task or "") + "\n" + (full_text or ""),
                            "events": _g1_events,
                        }) if _kexec is not None else {"decision": "ALLOW", "evaluated": []}
                        for _ev in _commit.get("evaluated", []):
                            _pid, _det = _ev.get("policy"), (_ev.get("detail") or {})
                            if _pid == "warrant.cee_c1":
                                _oc = _det.get("overclaims") or []
                                try:
                                    import warrant_check as _wc
                                    _wc.persist(_ocp_session_id, req.task or "", _oc)   # persist always, clean or not
                                except Exception: pass
                                if _oc:
                                    yield f"data: {json.dumps({'type':'warrant_violation','n':len(_oc),'detail':_ev.get('rationale',''),'overclaims':_oc[:5]}, ensure_ascii=False)}\n\n"
                                    try: house_sync.publish("warrant_violation", {"n": len(_oc), "run": _ocp_session_id, "paths": [o['path'] for o in _oc[:5]]}, source="warrant")
                                    except Exception: pass
                            elif _pid == "guidance.g1":
                                _gv = _det.get("violations") or []
                                if _gv:
                                    yield f"data: {json.dumps({'type':'guidance_violation','n':len(_gv),'detail':_ev.get('rationale',''),'violations':_gv[:5]}, ensure_ascii=False)}\n\n"
                                    try: house_sync.publish("guidance_violation", {"n": len(_gv), "run": _ocp_session_id, "targets": [v['target'] for v in _gv[:5]]}, source="guidance")
                                    except Exception: pass
                        if _commit.get("decision") not in ("ALLOW", None):
                            print(f"[Kernel] PRE_COMMIT {_commit['decision']} via {_commit.get('policy')} — {(_commit.get('rationale') or '')[:120]}")
                    except Exception as _pce:
                        # never let the commit hook break a finished mission
                        print(f"[Kernel] PRE_COMMIT skipped: {_pce}")
                        try:
                            import warrant_check as _wc
                            _wc.persist(_ocp_session_id, req.task or "", [])
                        except Exception: pass
                    # H4 KNOWLEDGE ASSET — knowledge must become a usable artifact,
                    # not merely be collected. Recommend the asset + report whether
                    # it was actually delivered (non-blocking signal this pass).
                    try:
                        import knowledge_asset as _ka
                        _arec = _ka.recommend(_mission_identity, files_touched)
                        _adel = _ka.is_delivered(_arec, files_touched)
                        yield f"data: {json.dumps({'type':'knowledge_asset','asset':_arec.get('asset_type'),'confidence':_arec.get('confidence'),'delivered':_adel,'reason':_arec.get('reason')}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("knowledge_asset", {"asset": _arec.get("asset_type"), "delivered": _adel, "confidence": _arec.get("confidence")}, source="runtime")
                        except Exception: pass
                        # ── H6 ARTIFACT FACTORY — completion rule: NO ARTIFACT = NOT
                        # COMPLETE. If the agent did not already produce a matching
                        # asset, the House PHYSICALLY GENERATES it from the mission's
                        # knowledge, verifies it, and attaches it to the ledger.
                        if not _adel:
                            try:
                                import artifact_factory as _af, knowledge_frontier as _kf2
                                _sid2 = _house_state.open_state(_mission_identity)
                                _ans2 = _house_state.answer(_sid2) or {}
                                _km = (_kf2.frontier(_sid2) or {}).get("metrics", {})
                                _know = _af.assemble_knowledge(_ans2, summary=summary, metrics=_km,
                                                               sources=[f for f in files_touched][:20])
                                _outdir = workspace_resolved or str(Path(__file__).parent / "artifacts")
                                _art = _af.build(_arec.get("asset_type", "Markdown Note"), _know,
                                                 _outdir, base_name=_mission_identity)
                                if _art.get("exists"):
                                    if _art["path"] not in files_touched:
                                        files_touched.append(_art["path"])   # attach to mission ledger
                                    _adel = True
                                    yield f"data: {json.dumps({'type':'artifact_built','asset':_art.get('type'),'builder':_art.get('builder'),'path':_art.get('path'),'bytes':_art.get('bytes')}, ensure_ascii=False)}\n\n"
                                    try: house_sync.publish("artifact_built", {"asset": _art.get("type"), "path": _art.get("path"), "bytes": _art.get("bytes")}, source="runtime")
                                    except Exception: pass
                                else:
                                    yield f"data: {json.dumps({'type':'artifact_missing','asset':_arec.get('asset_type'),'error':_art.get('error','')}, ensure_ascii=False)}\n\n"
                                    summary += f"  [⚠ NO ARTIFACT — {_art.get('error','build failed')}; collection without creation]"
                            except Exception as _afe:
                                print(f"[ArtifactFactory] build skipped: {_afe}")
                    except Exception as _kae:
                        print(f"[KnowledgeAsset] recommend skipped: {_kae}")
                    # ── OX-ARTIFACT-1 COMPLETION TRUTH — "Mission Complete" means the
                    # ARTIFACT EXISTS, not merely that execution finished. Project this
                    # run's files into artifact records (read-side) and verify on disk.
                    # When an artifact was expected but none exists, surface it so the
                    # mission is not reported as successfully delivered.
                    try:
                        import artifact_registry as _artreg2
                        _ct_expected = bool(locals().get("_adel") is not None or files_touched)
                        _ct = _artreg2.verify_delivery(files_touched, workspace_resolved or None,
                                                       expected=_ct_expected)
                        yield f"data: {json.dumps({'type':'artifact_completion_truth','delivered':_ct['delivered'],'artifacts':[{'path':a['artifact_path'],'type':a['artifact_type'],'size':a['size'],'exists':a['exists']} for a in _ct['existing'][:6]],'missing':_ct['missing'][:6]}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("artifact_completion_truth", {"delivered": _ct["delivered"], "count": len(_ct["existing"]), "missing": _ct["missing"][:6]}, source="runtime")
                        except Exception: pass
                        if _ct["existing"]:
                            summary += "  [✓ ARTIFACT EXISTS: " + ", ".join(a["artifact_path"] for a in _ct["existing"][:3]) + "]"
                        elif _ct_expected and not _ct["delivered"]:
                            summary += "  [⚠ NO ARTIFACT ON DISK — execution finished but nothing was delivered]"
                    except Exception as _cte:
                        print(f"[ArtifactCompletionTruth] skipped: {_cte}")
                    try: house_sync.publish("mission_updated", {"status": "complete", "steps": step_num, "tools_used": total_tool_calls}, source="runtime")
                    except Exception: pass
                    # OPENCLAW PORT: emit trajectory complete + daily diary entry
                    try:
                        _traj.complete("TASK_COMPLETE", summary)
                        _diary_path = _ocp_diary(
                            session_id=_ocp_session_id,
                            task=req.task,
                            summary=summary,
                            tools_used=action_sigs,
                            n_steps=step_num,
                            status="TASK_COMPLETE",
                            duration_sec=time.time() - _ocp_t0,
                            blocked_calls=_ocp_blocked,
                        )
                        if _diary_path:
                            yield f"data: {json.dumps({'type':'agent_diary','path':str(_diary_path)})}\n\n"
                    except Exception as _de:
                        print(f"[OpenClawPort] TASK_COMPLETE post-process failed: {_de}")
                    # OPENCLAW PORT T2: persist to agent_runs DB
                    try:
                        _AGENT_RUNS_DB.end_run(
                            run_id=_ocp_session_id,
                            status="TASK_COMPLETE",
                            n_steps=step_num,
                            n_tools=total_tool_calls,
                            n_blocks=_ocp_blocked,
                            summary=(f"[done_when: {captured_done_when}] " if captured_done_when else "") + summary + _mem_footer("success"),
                        )
                    except Exception:
                        pass
                    break

                # ── Execute tool calls ─────────────────────────────────────
                if tool_calls_this:
                    cur.append({
                        "role": "assistant",
                        "content": full_text,
                        "tool_calls": tool_calls_this
                    })
                    new_action_in_step = False  # did this step add ANY new action?
                    duplicate_in_step = False   # did the model try a duplicate?
                    asked_user_in_step = False  # did the model ask the user something?
                    if _blocked_det is not None:
                        try: _blocked_det.begin_step()   # OX-1.4: reset per-step novelty flag
                        except Exception: pass

                    # ── PARALLEL READ-ONLY PREFETCH (Claude Code borrow) ──────────
                    # When a step emits several independent read-only calls, run
                    # them CONCURRENTLY up front (governance-gated, dedup-aware);
                    # the sequential loop below then uses the cached result. Writes
                    # and side-effecting tools are never prefetched — order matters.
                    _prefetch: dict = {}
                    try:
                        def _par_ok(_tc):
                            _f = _tc.get("function", {}) or {}
                            _n = _f.get("name", "")
                            if _n not in _PARALLEL_SAFE:
                                return False
                            if _action_sig(_n, _f.get("arguments", {}) or {}) in action_sigs:
                                return False   # a dup would be skipped anyway
                            if _GOV is not None:
                                try:
                                    _d, _ = _GOV.evaluate(_n, _f.get("arguments", {}) or {})
                                    return _d == "ALLOW"
                                except Exception:
                                    return False
                            return False
                        _par = [(i, tc) for i, tc in enumerate(tool_calls_this) if _par_ok(tc)]
                        if len(_par) > 1:
                            async def _pf(_i, _tc):
                                _f = _tc.get("function", {}) or {}
                                return _i, await exec_tool(_f.get("name", ""), _f.get("arguments", {}) or {})
                            _results = await asyncio.gather(*[_pf(i, tc) for i, tc in _par])
                            for _i, _res in _results:
                                _prefetch[_i] = _res
                            yield f"data: {json.dumps({'type':'agent_think','step':step_num,'text':f'⇉ {len(_par)} read-only tools ran in parallel'})}\n\n"
                    except Exception as _pfe:
                        print(f"[agent_run] parallel prefetch skipped: {_pfe}")
                        _prefetch = {}

                    for _tc_idx, tc in enumerate(tool_calls_this):
                        fn = tc.get("function", {})
                        nm = fn.get("name", "")
                        ag = fn.get("arguments", {})
                        cat = get_tool_cat(nm)
                        sig = _action_sig(nm, ag)

                        # ── Elicitation: stop the agent loop and wait for user ──
                        if nm == "ask_user_options":
                            opts = ag.get("options", [])
                            if not isinstance(opts, list): opts = []
                            opts = [str(o)[:120] for o in opts][:6]
                            evt = {
                                "type": "ask_user",
                                "step": step_num,
                                "question": str(ag.get("question",""))[:500],
                                "options": opts,
                                "allow_custom": bool(ag.get("allow_custom", True)),
                                "context": str(ag.get("context","") or "")[:300],
                            }
                            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
                            cur.append({"role":"tool","content":"[awaiting user reply]","name":nm})
                            asked_user_in_step = True
                            break  # stop processing further tool calls

                        # ── DEDUPE GUARD: skip identical tool call already done ──
                        if sig in action_sigs:
                            # Write-ops whose target file is MISSING must NOT be
                            # dedup-blocked: a 'duplicate' write whose file isn't on
                            # disk means the earlier identical write never landed
                            # (failed / bad path). Blocking it silently loses the
                            # artifact and strands the agent. Re-allow those.
                            _wp = str(ag.get("path") or ag.get("name") or "")
                            _isw = nm in ("write_file","edit_file","create_folder",
                                          "write_obsidian_note","obsidian_write_note")
                            _missing = _isw and _wp and not os.path.exists(_wp)
                            if not _missing:
                                duplicate_in_step = True
                                skip_msg = (
                                    f"⚠ DUPLICATE BLOCKED: '{sig}' was already executed earlier — "
                                    "skipped. Move to the next pending action."
                                )
                                yield f"data: {json.dumps({'type':'agent_tool_skip','step':step_num,'name':nm,'args':ag,'reason':'duplicate'})}\n\n"
                                cur.append({"role": "tool", "content": skip_msg, "name": nm})
                                recent_sigs.append(sig)
                                recent_sigs[:] = recent_sigs[-3:]
                                continue

                        # ══ PRE_ACT — the Cognitive Kernel policy hook (SPEC §5, step 5) ══
                        # The kernel is the SINGLE AUTHORITY at the act boundary. The four
                        # gates that used to run as an ad-hoc chain are now Policies on
                        # PRE_ACT (GPS-2 · shadow · prior-approvals · run allow-list),
                        # resolved most-restrictive and FAIL-CLOSED: if the engine itself
                        # cannot decide, the act is DENIED. Each policy keeps its exact
                        # legacy side effects (SSE reason, model message, trajectory source)
                        # so behaviour is preserved — only the AUTHORITY moved.
                        _act_ctx = {
                            "tool": nm, "args": ag, "task": req.task,
                            "action_sigs": action_sigs, "tool_results_log": tool_results_log,
                            "tool_allow": req.tool_allow,
                            "approvals_check": (lambda t, a: _approvals.check(t, a)),
                            # server-verified (from the request header, never the model)
                            "operator_elevated": _operator_elevated,
                        }
                        if _kexec is None:      # kernel not armed → fail closed, never open
                            yield f"data: {json.dumps({'type':'agent_tool_skip','step':step_num,'name':nm,'args':ag,'reason':'kernel_unavailable','detail':'PRE_ACT hook not armed — failing closed'}, ensure_ascii=False)}\n\n"
                            cur.append({"role": "tool", "content": "⛔ DENY: the policy kernel is unavailable — failing closed. No tool may run.", "name": nm})
                            _ocp_blocked += 1
                            continue
                        _pre = _kexec.guard(_act_ctx)
                        _pdec, _preason, _ppol = _pre["decision"], _pre["rationale"], _pre["policy"]

                        if _pdec == "DENY":
                            # per-policy presentation, byte-for-byte as the legacy chain
                            if _ppol == "shadow.fabrication":
                                _sse, _tsrc = "shadow_gate", "shadow_gate"
                                _msg = (f"⛔ SHADOW GATE BLOCKED: {_preason}\n"
                                        f"Re-plan now: call the live-data tool FIRST (e.g. get_gold_price, "
                                        f"get_crypto_price, get_forex_rate, get_news), capture the returned "
                                        f"values, then retry write_file with the REAL data — never hardcoded.")
                            elif _ppol == "approvals.prior_deny":
                                _sse, _tsrc = "approval_deny", "exec_approvals"
                                _msg = f"⛔ EXEC_APPROVAL DENY: user previously denied '{nm}' for these args"
                            elif _ppol == "run.tool_allow":
                                _sse, _tsrc = "not_allowed", "tool_allow"
                                _msg = f"⛔ TOOL_NOT_ALLOWED: '{nm}' is outside this run's permitted tools"
                            elif _ppol == "kernel.failclosed":
                                _sse, _tsrc = "kernel_failclosed", "kernel"
                                _msg = f"⛔ DENY (fail-closed): {_preason}"
                            else:   # governance.gps2 (incl. monitor unavailable)
                                _sse, _tsrc = "gps2_deny", "gps2_gate"
                                _msg = f"⛔ GPS-2 DENY: {_preason}. Choose a permitted tool instead."
                            yield f"data: {json.dumps({'type':'agent_tool_skip','step':step_num,'name':nm,'args':ag,'reason':_sse,'detail':_preason,'policy':_ppol}, ensure_ascii=False)}\n\n"
                            cur.append({"role": "tool", "content": _msg, "name": nm})
                            try: _traj.gate_block(nm, _preason, _tsrc)
                            except Exception: pass
                            _ocp_blocked += 1
                            continue

                        if _pdec == "ESCALATE":
                            # GPS-2 human gate. A prior operator ALLOW/ALWAYS pre-approves;
                            # otherwise halt honestly and ask. (A prior DENY already came
                            # back as DENY from the approvals policy above.)
                            _prior = None
                            try: _prior = _approvals.check(nm, ag)
                            except Exception: pass
                            if _prior not in ("ALWAYS", "ALLOW"):
                                _pg = _GOV.open_gate(nm, ag, req.task)
                                try: _kexec.escalation_open(_pg["id"])   # A3: aborts on timeout, never auto-proceeds
                                except Exception: pass
                                _evt = {"type": "ask_user", "step": step_num,
                                        "question": _pg["question"], "options": _pg["options"],
                                        "allow_custom": False, "context": "GPS-2 HUMAN GATE"}
                                yield f"data: {json.dumps(_evt, ensure_ascii=False)}\n\n"
                                cur.append({"role": "tool", "content": f"[blocked: awaiting human gate {_pg['id']}]", "name": nm})
                                _traj.gate_block(nm, f"awaiting human gate {_pg['id']}", "gps2_gate")
                                try:
                                    _AGENT_RUNS_DB.end_run(
                                        run_id=_ocp_session_id, status="blocked_awaiting_gate",
                                        n_steps=step_num, n_tools=total_tool_calls,
                                        n_blocks=_ocp_blocked + 1,
                                        summary=f"GPS-2 gate {_pg['id']} on {nm}",
                                    )
                                except Exception:
                                    pass
                                asked_user_in_step = True
                                break
                            # prior ALWAYS/ALLOW → operator already decided; proceed (logged)
                            _traj.tool_call(nm + ":gate-preapproved", {"gate": "gps2"})
                        # ALLOW / FLAG → the act proceeds (FLAG is surfaced by the audit event)

                        # ── Normal execution ──
                        total_tool_calls += 1
                        yield f"data: {json.dumps({'type':'agent_tool_call','step':step_num,'name':nm,'args':ag,'category':cat})}\n\n"
                        # P4 OBSERVABILITY: publish to the central bus at the SOURCE so every
                        # UI sees live execution regardless of relay vs direct dispatch.
                        try: house_sync.publish("tool_started", {"name": nm, "category": cat, "step": step_num}, source="runtime")
                        except Exception: pass
                        _traj.tool_call(nm, ag)
                        _tool_t0 = time.time()
                        # use the concurrently-prefetched result if this read-only
                        # call already ran in the parallel batch above
                        if _tc_idx in _prefetch:
                            result = _prefetch[_tc_idx]
                        else:
                            result = await exec_tool(nm, ag)
                        _tool_elapsed = time.time() - _tool_t0
                        if _world is not None:
                            try: _world.observe_tool(nm, ag, result)   # OX-1.1: verify-from-results
                            except Exception: pass
                        _failed = _tool_result_failed(nm, result)
                        # OX-SKILL-1 TOOL MEMORY — record this completed tool use
                        # {task_type, tool_used, success, execution_time} so future
                        # runs know which tool wins for this kind of task.
                        if _tool_intel is not None:
                            try: _tool_intel.record(_tool_task_type, nm, not _failed, _tool_elapsed)
                            except Exception: pass
                        if _exec_conf is not None:
                            try:
                                _exec_conf.on_failure() if _failed else _exec_conf.on_success()
                                yield f"data: {json.dumps({'type':'execution_confidence','step':step_num,'value':_exec_conf.value(),'level':_exec_conf.level()})}\n\n"
                                try: house_sync.publish("execution_confidence", {"value": _exec_conf.value(), "level": _exec_conf.level(), "step": step_num}, source="runtime")
                                except Exception: pass
                            except Exception: pass
                        if _failed:
                            # Per-tool failure is now an explicit, visible event (was only
                            # counted silently before). Lets the UI surface TOOL_FAILED.
                            yield f"data: {json.dumps({'type':'tool_failed','step':step_num,'name':nm,'args':ag,'result':result[:500]}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("tool_failed", {"name": nm, "result": result[:300], "step": step_num}, source="runtime")
                            except Exception: pass
                        consec_failures = consec_failures + 1 if _failed else 0
                        explore_streak = explore_streak + 1 if (nm in _EXPLORE_TOOLS and not _failed) else 0
                        same_tool_streak = same_tool_streak + 1 if nm == last_tool_name else 1
                        last_tool_name = nm
                        if not _failed and nm in ("write_file", "edit_file", "create_folder",
                                                  "write_obsidian_note", "obsidian_write_note"):
                            _fp = str(ag.get("path") or ag.get("name") or "")
                            if _fp and _fp not in files_touched:
                                files_touched.append(_fp)
                        completed_steps.append(f"{'✗ FAILED' if _failed else '✓'} {nm}: {result[:100]}")
                        # Only record the signature for dedup when the call SUCCEEDED —
                        # a failed action must be retryable, not permanently blocked.
                        if not _failed:
                            action_sigs.append(sig)
                        recent_sigs.append(sig)
                        recent_sigs[:] = recent_sigs[-3:]
                        new_action_in_step = True
                        # Keep tool result text for VALUE-MATCH GATE on subsequent write_file calls
                        # Trim to 4000 chars to keep memory reasonable across long sessions
                        tool_results_log.append((nm, (result or "")[:4000]))
                        if len(tool_results_log) > 30:
                            tool_results_log[:] = tool_results_log[-30:]
                        # Vol V G1: the act (with its target args) and what it observed,
                        # in order — guidance_check reads this at completion
                        _g1_events.append({"type": "tool_call", "name": nm, "args": ag})
                        _g1_events.append({"type": "tool_result", "name": nm,
                                           "result": (result or "")[:2000]})
                        if len(_g1_events) > 60:
                            _g1_events[:] = _g1_events[-60:]
                        if _blocked_det is not None:
                            try: _blocked_det.observe_result(nm, result)   # OX-1.4: track info novelty
                            except Exception: pass
                        yield f"data: {json.dumps({'type':'agent_tool_result','step':step_num,'name':nm,'result':result[:3000],'category':cat})}\n\n"
                        if not _failed:
                            try: house_sync.publish("tool_completed", {"name": nm, "category": cat, "step": step_num}, source="runtime")
                            except Exception: pass
                        # OPENCLAW PORT: auto-truncate large tool results before injecting into model context
                        # Prevents the "model echoes 130KB raw JSON in its reply" failure mode.
                        cur.append({"role": "tool", "content": _truncate_tool_result(nm, result), "name": nm})
                        # OX-1.2 RECOVERY ENGINE — on failure, inject concrete ALTERNATE
                        # strategies (not a blind retry) right after the failed result.
                        if _failed:
                            try:
                                import recovery as _recovery
                                cur.append({"role": "user", "content": _recovery.render(nm, ag, result)})
                            except Exception:
                                pass
                        _traj.tool_result(nm, result, ok=True)

                        # OPENCLAW PORT: workspace auto-git after FS-modifying tools
                        if nm in _GIT_TRIGGER_TOOLS and workspace_resolved:
                            try:
                                _commit_msg = f"skynetclaw [{_ocp_session_id[:6]}] step {step_num} — {nm}"
                                _gres = _ocp_git(workspace_resolved, _commit_msg)
                                if _gres.get("ok") and _gres.get("hash"):
                                    yield f"data: {json.dumps({'type':'agent_workspace_commit','step':step_num,'hash':_gres['hash'],'msg':_commit_msg[:120]})}\n\n"
                            except Exception:
                                pass

                        # ── MASTERPIECE: VALUE-LOCK after live-data tools ──
                        # Force model to use EXACT values from this result in any
                        # subsequent write_file/edit_file. Without this, models tend
                        # to fetch the data then re-hallucinate when writing.
                        _LIVE_TOOLS = {
                            "get_gold_price", "get_crypto_price", "get_forex_rate",
                            "get_news", "web_search", "http_request",
                        }
                        if nm in _LIVE_TOOLS:
                            cur.append({
                                "role": "system",
                                "content": (
                                    f"⚠ VALUE-LOCK: The {nm} tool above returned REAL DATA. "
                                    f"In any subsequent write_file / edit_file / write_obsidian_note, "
                                    f"you MUST copy the exact numbers, dates, currencies, and units "
                                    f"directly from the tool result above. "
                                    f"Do NOT round. Do NOT translate currency. Do NOT substitute training-data values. "
                                    f"If the tool returned ฿46,798 — write ฿46,798 (not 46,800 not $1,300 not anything else)."
                                ),
                            })

                    # ── ELICITATION HALT: model asked the user → stop, wait for reply ──
                    if asked_user_in_step:
                        yield f"data: {json.dumps({'type':'done', 'reason':'awaiting_user'})}\n\n"
                        return

                    # ── CYCLE BREAKER: 3 identical sigs in a row → hard stop ──
                    if len(recent_sigs) >= 3 and len(set(recent_sigs)) == 1:
                        run_halted = True
                        halt_reason = "cycle: identical action repeated 3x"
                        yield f"data: {json.dumps({'type':'agent_stuck','step':step_num,'text':f'Cycle detected: {recent_sigs[-1]} repeated 3x. Aborting to protect resources.','reason':'cycle'})}\n\n"
                        break

                    # ── OX-1.4 BLOCKED STATE: varied actions, no new information ──
                    # The cycle breaker above catches IDENTICAL loops; this catches the
                    # subtler dead end — different moves that learn nothing. Evaluated
                    # from real signals only (world-model growth + novel tool results).
                    if _blocked_det is not None:
                        try:
                            _wsize = 0
                            if _world is not None:
                                _wsize = (len(_world.verified_paths()) + len(_world.absent_paths())
                                          + len(_world.absent_tools()))
                            _streak = _blocked_det.end_step(_wsize, new_action_in_step)
                            if _streak and _exec_conf is not None:
                                try: _exec_conf.on_no_info()   # no-info steps decay reliability
                                except Exception: pass
                            # Recovery is exhausted when failures are mounting OR reliability
                            # has collapsed — the loop already tried alternates (OX-1.2) and
                            # they did not move the needle.
                            _recovery_exhausted = (consec_failures >= 2) or \
                                (_exec_conf is not None and _exec_conf.is_low())
                            if _blocked_det.is_blocked(_recovery_exhausted):
                                run_halted = True
                                blocked = True
                                halt_reason = (f"BLOCKED: {_streak} varied actions with no new "
                                               f"information; recovery exhausted")
                                yield f"data: {json.dumps({'type':'agent_blocked','step':step_num,'text':halt_reason,'streak':_streak,'reason':'dead_end'}, ensure_ascii=False)}\n\n"
                                try: house_sync.publish("agent_blocked", {"streak": _streak, "reason": halt_reason, "step": step_num}, source="runtime")
                                except Exception: pass
                                break
                        except Exception:
                            pass

                    # ── Stagnation tracker: no NEW action this step ──
                    if not new_action_in_step:
                        no_progress_rounds += 1
                    else:
                        no_progress_rounds = 0

                    if no_progress_rounds >= 2:
                        # ── SKYNET ELITE COMMANDER — Supreme Council intervention ──
                        # Before surrendering, the Commander re-checks the work against
                        # DONE_WHEN and drives the mission to an honest finish (max 2x).
                        if commander_calls < 2:
                            commander_calls += 1
                            no_progress_rounds = 0
                            _cmd_txt = (f"OVERRIDE {commander_calls}/2 — mission stalled at step {step_num}. "
                                        f"Re-checking against DONE_WHEN and issuing recovery protocol.")
                            yield f"data: {json.dumps({'type':'commander','step':step_num,'text':_cmd_txt}, ensure_ascii=False)}\n\n"
                            cur.append({"role": "user", "content": (
                                "🦅 SKYNET ELITE COMMANDER — SUPREME COUNCIL OVERRIDE "
                                f"({commander_calls}/2). Not an assistant — a thinking system. "
                                "Execute this recovery protocol NOW, one step per reply:\n"
                                "1) VERIFY REALITY (L7): read_file the output you believe exists — confirm it "
                                "actually contains what DONE_WHEN requires"
                                + (f": {captured_done_when}" if captured_done_when else "") + ".\n"
                                "2) GAP (L4 Shadow): state in ONE line what is still missing or wrong.\n"
                                "3) EXECUTE exactly that missing item with ONE tool call. "
                                "If your write was 'duplicate blocked', the file already contains that exact "
                                "content — do NOT rewrite it; use edit_file to change/extend it, or if "
                                "everything in DONE_WHEN is already satisfied reply TASK_COMPLETE with a summary.\n"
                                "Never repeat a blocked action. Never stop without TASK_COMPLETE or an honest blocker report."
                            )})
                            continue
                        run_halted = True
                        halt_reason = "stagnation after Commander overrides"
                        yield f"data: {json.dumps({'type':'agent_stuck','step':step_num,'text':'No new actions for 2 rounds — Commander intervened twice without progress. Halting honestly.','reason':'stagnation'})}\n\n"
                        break

                    # ── FAILURE-ADAPTATION: stop digging the same hole ──
                    if consec_failures >= 6:
                        # DECENTRALIZATION: before surrendering, the Commander delegates —
                        # THE SCOUT is engaged to FIND the technique/code that unblocks us,
                        # and the Scout's discovery arsenal is opened mid-run.
                        if commander_calls < 2:
                            commander_calls += 1
                            consec_failures = 0
                            _scout_set = {"web_search", "http_request", "grep_search",
                                          "obsidian_search", "search_obsidian", "get_news"}
                            _have = {t.get("function", {}).get("name") for t in _MISSION_TOOLS}
                            for _td in BUILTIN_TOOLS:
                                if _td.get("function", {}).get("name") in _scout_set and \
                                   _td.get("function", {}).get("name") not in _have:
                                    _MISSION_TOOLS.append(_td)
                            yield f"data: {json.dumps({'type':'commander_delegate','to':'OPV-007','step':step_num,'text':f'OVERRIDE {commander_calls}/2 — repeated failures. Delegating to THE SCOUT: find the technique, library, or code that unblocks this mission.'}, ensure_ascii=False)}\n\n"
                            cur.append({"role": "user", "content": (
                                "🦅 SKYNET ELITE COMMANDER — DELEGATION ORDER (กระจายอำนาจ). "
                                "The current approach has failed repeatedly. THE SCOUT is hereby engaged:\n"
                                "1) SCOUT: use web_search / grep_search / obsidian_search NOW to find the correct "
                                "technique, command syntax, library, or working code for the LAST error above. "
                                "Report the finding in ONE line.\n"
                                "2) EXECUTOR: apply EXACTLY what the Scout found — not a guess.\n"
                                "3) AUDITOR: verify the result against DONE_WHEN"
                                + (f": {captured_done_when}" if captured_done_when else "") + "."
                            )})
                            continue
                        run_halted = True
                        halt_reason = f"{consec_failures} consecutive tool failures (after Scout delegation)"
                        _ftxt = (f"{consec_failures} tool calls failed in a row — the current method "
                                 "does not work on this system. Halting honestly; read the errors above.")
                        yield f"data: {json.dumps({'type':'agent_stuck','step':step_num,'text':_ftxt,'reason':'repeated_failures'}, ensure_ascii=False)}\n\n"
                        break

                    # Force immediate continuation
                    nudge = (
                        f"✅ Step {step_num} complete. "
                        f"Completed so far: {len(action_sigs)} unique actions. "
                    )
                    if consec_failures >= 3:
                        nudge += (
                            f"⛔ WARNING: your last {consec_failures} tool calls FAILED. "
                            "Do NOT retry variations of the same command. State WHY they failed in one line, "
                            "then use a FUNDAMENTALLY different approach. "
                            "(Windows: cmd.exe does not know PowerShell cmdlets — run plain commands "
                            "without pipes and read the full output instead.) "
                        )
                    # ── CONVERGENCE PRESSURE: exploring forever is not progress ──
                    if explore_streak >= 8 or same_tool_streak >= 5:
                        nudge += (
                            f"⛔ CONVERGE NOW: {explore_streak} exploration calls in a row"
                            + (f" ({same_tool_streak}× {last_tool_name} back-to-back)" if same_tool_streak >= 5 else "")
                            + ". STOP listing/browsing. You already have enough material — SYNTHESIZE: "
                            "produce the deliverable DONE_WHEN requires (write the file / state the answer), "
                            "then reply TASK_COMPLETE with your findings. If you truly need ONE more fact, "
                            "use grep_search with a specific pattern — never another directory listing. "
                        )
                        explore_streak = 0
                        same_tool_streak = 0
                    if duplicate_in_step:
                        nudge += (
                            "⚠ You just attempted an action that was ALREADY done — it was blocked. "
                            "Pick a DIFFERENT action from your PLAN now. "
                        )
                    nudge += (
                        "Continue to the NEXT step immediately using a tool call that is NOT in COMPLETED_ACTIONS. "
                        "Do NOT explain — just execute. "
                        "Say TASK_COMPLETE only when ALL tasks are truly done."
                    )
                    cur.append({"role": "user", "content": nudge})

                else:
                    # HONEST-FAILURE HALT: the stream produced ONLY errors (no text, no
                    # tools) — nudging again would burn steps invisibly. Stop and tell.
                    if stream_errors_this and not full_text.strip():
                        run_halted = True
                        halt_reason = "model stream errors: " + " | ".join(stream_errors_this[-1:])[:120]
                        _halt_txt = ("Model stream returned only errors: "
                                     + " | ".join(stream_errors_this[-2:])
                                     + " — ตรวจชื่อ model / provider+API key / Ollama ยังรันอยู่ไหม")
                        yield f"data: {json.dumps({'type':'agent_stuck','step':step_num,'text':_halt_txt,'reason':'stream_error'}, ensure_ascii=False)}\n\n"
                        break
                    # No tool calls — AI may be stuck or genuinely done
                    if full_text.strip():
                        cur.append({"role": "assistant", "content": full_text})
                    # Force it to continue if we haven't hit TASK_COMPLETE
                    cur.append({
                        "role": "user",
                        "content": (
                            "You have pending tasks that are NOT yet complete. "
                            "Use a tool call to execute the next step RIGHT NOW. "
                            "Do not write text — call a tool."
                        )
                    })
                    # If 2 consecutive no-tool rounds, stop gracefully
                    if step > 0 and not tool_calls_this:
                        last_msgs = [m for m in cur[-4:] if m.get("role") == "user"]
                        force_msgs = sum(1 for m in last_msgs if "pending tasks" in m.get("content",""))
                        if force_msgs >= 2:
                            # P0 OPERATIVE RECOVERY: silence usually means the model lost
                            # the thread under a bloated context. Before any halt, compress
                            # the conversation to a factual snapshot and CONTINUE — give the
                            # operative a clean, focused context instead of surrendering.
                            if silence_recoveries < 2:
                                try:
                                    import mission_snapshot as _ms, context_budget as _cb
                                    _before = _cb.assess(cur, limit=_ctx_window)["total"]
                                    cur, _snap, _dropped = _ms.compress(cur, keep_recent=4)
                                    silence_recoveries += 1
                                    _rec = {"step": step_num, "dropped": _dropped,
                                            "n_tool_calls": _snap.get("n_tool_calls", 0),
                                            "objective": _snap.get("objective", "")[:200],
                                            "freed_tokens": _before - _cb.assess(cur, limit=_ctx_window)["total"],
                                            "reason": "silence"}
                                    yield f"data: {json.dumps({'type':'mission_recovered', **_rec}, ensure_ascii=False)}\n\n"
                                    try: house_sync.publish("mission_recovered", _rec, source="runtime")
                                    except Exception: pass
                                    cur.append({"role": "user", "content": (
                                        "Context was just compacted to a clean mission snapshot above. "
                                        "Resume NOW with a single tool call for the next pending step, "
                                        "or reply TASK_COMPLETE if DONE_WHEN already holds.")})
                                    continue
                                except Exception as _rece:
                                    print(f"[OperativeRecovery] skipped: {_rece}")
                            # Give the COMMANDER one shot before surrendering — the model
                            # usually went quiet because it lost the thread, not the data.
                            if commander_calls < 2:
                                commander_calls += 1
                                _cmd_txt = (f"OVERRIDE {commander_calls}/2 — operative went silent at step {step_num}. "
                                            "Demanding final synthesis.")
                                yield f"data: {json.dumps({'type':'commander','step':step_num,'text':_cmd_txt}, ensure_ascii=False)}\n\n"
                                cur.append({"role": "user", "content": (
                                    "🦅 SKYNET ELITE COMMANDER — FINAL SYNTHESIS ORDER "
                                    f"({commander_calls}/2). You have gathered material in the tool results above. "
                                    "No more tools. Write your FINAL answer NOW as plain text"
                                    + (f", satisfying DONE_WHEN: {captured_done_when}" if captured_done_when else "")
                                    + ", and end with TASK_COMPLETE. If something blocked you, say exactly what, "
                                    "then end with TASK_COMPLETE."
                                )})
                                continue
                            run_halted = True
                            if think_chunks_this and not full_text.strip():
                                halt_reason = "model produced thinking but no executable output"
                                _silent_txt = (
                                    "Model produced internal thinking but no visible answer and no tool call "
                                    "after repeated prompts."
                                )
                            else:
                                halt_reason = "operative went silent (likely context overload)"
                                _silent_txt = (full_text.strip()
                                               or "Operative went silent after repeated prompts — likely context overload "
                                                  "from too many tool results. Partial findings are shown above.")
                            yield f"data: {json.dumps({'type':'agent_stuck','step':step_num,'text':_silent_txt}, ensure_ascii=False)}\n\n"
                            break

            # ── COMMANDER SIGN-OFF — mission ledger in the workspace ──────────
            # Every exit (complete / problem / limit) is signed so the next run
            # knows what is done, what is half-done, and what went wrong.
            if workspace_resolved:
                try:
                    _status = ("COMPLETE" if task_done else
                               ("BLOCKED" if blocked else
                                ("PROBLEM" if run_halted else "INCOMPLETE")))
                    _ledger_sign(workspace_resolved, {
                        "id": _ocp_session_id, "ts": time.time(),
                        "task": (req.task or "")[:300], "status": _status,
                        "done_when": captured_done_when,
                        "files": files_touched[:20],
                        "problem": halt_reason[:300],
                        "tools_used": total_tool_calls,
                        "signed_by": "SKYNET ELITE COMMANDER (OPV-000)",
                    })
                    _sign_txt = (f"SIGN-OFF: mission {_status}"
                                 + (f" · files: {', '.join(files_touched[:4])}" if files_touched else "")
                                 + (f" · issue: {halt_reason[:90]}" if halt_reason else "")
                                 + " — recorded in _MISSION_LEDGER.json")
                    yield f"data: {json.dumps({'type':'commander','text':_sign_txt}, ensure_ascii=False)}\n\n"
                except Exception as _se:
                    print(f"[MissionLedger] sign-off failed: {_se}")
                # ── RFC-0001 REALITY GRADING — a COMPLETE mission stakes a
                # falsifiable HYPOTHESIS ("these artifacts will hold"); the
                # existing outcome clock evaluates it against the filesystem at
                # the 7-day review and revises the House Mind's belief. Best-effort.
                try:
                    import reality_grading as _rg
                    _rg_pid = _rg.record_mission_hypothesis(workspace_resolved, {
                        "id": _ocp_session_id, "task": (req.task or ""),
                        "status": _status, "files": files_touched[:20],
                        "done_when": captured_done_when})
                    if _rg_pid:
                        print(f"[RealityGrading] hypothesis staked: {_rg_pid} "
                              f"({len(files_touched[:20])} artifact(s), 7d review)")
                except Exception as _rge:
                    print(f"[RealityGrading] hypothesis skipped: {_rge}")
                # OX-LEARNING-1 — this mission's outcome is now recorded (ledger +
                # tool memory updated). Re-synthesize the Lesson Registry so the
                # next run can RECALL what repeatedly works/fails. Read-only over
                # the histories; persists lessons.json (separate from raw events).
                try:
                    import lesson_synthesis as _lessons
                    _ls = _lessons.refresh(workspace=workspace_resolved,
                                           runs=(_AGENT_RUNS_DB.recent(limit=60) or []))
                    yield f"data: {json.dumps({'type':'lessons_synthesized','count':len(_ls),'wins':sum(1 for l in _ls if l.get('polarity')=='success'),'fails':sum(1 for l in _ls if l.get('polarity')=='failure')}, ensure_ascii=False)}\n\n"
                    try: house_sync.publish("lessons_synthesized", {"count": len(_ls)}, source="learning")
                    except Exception: pass
                    # OX-CAPABILITY-1 — promote the just-synthesized lessons into
                    # capabilities (stability checked against the prior registry).
                    try:
                        import capability_promotion as _caps
                        # OX-CONTROL-1 ADJUST: the controller's prior verdict may
                        # raise/lower the promotion confidence bar (bounded). Uses
                        # capability_promotion's existing conf_thresh param — no redesign.
                        _cp_kw = {}
                        try:
                            import control_engine as _ctrl
                            _cp_kw = {"conf_thresh": _ctrl.adjusted_promotion_threshold(_caps.CONF_THRESH)}
                        except Exception:
                            _cp_kw = {}
                        _cp = _caps.refresh(workspace=workspace_resolved, lessons=_ls, **_cp_kw)
                        yield f"data: {json.dumps({'type':'capabilities_promoted','count':len(_cp),'capabilities':sum(1 for c in _cp if c.get('polarity')=='capability'),'warnings':sum(1 for c in _cp if c.get('polarity')=='warning')}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("capabilities_promoted", {"count": len(_cp)}, source="learning")
                        except Exception: pass
                    except Exception as _cpe:
                        print(f"[CapabilityPromotion] refresh skipped: {_cpe}")
                    # OX-TELEMETRY-1 — is the House actually IMPROVING? Compare the
                    # recent window of runs against the prior window and emit the
                    # improvement scorecard (read-only over agent_runs + registries).
                    try:
                        import telemetry as _tele
                        _tsc = _tele.scorecard(runs=(_AGENT_RUNS_DB.recent(limit=200) or []),
                                               workspace=workspace_resolved or None,
                                               lessons=_ls, caps=locals().get("_cp"))
                        yield f"data: {json.dumps({'type':'telemetry','verdict':_tsc.get('verdict'),'score':_tsc.get('score'),'drivers':_tsc.get('drivers',[]),'n_runs':_tsc.get('n_runs'),'learning':_tsc.get('learning',{})}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("telemetry", {"verdict": _tsc.get("verdict"), "score": _tsc.get("score"), "drivers": _tsc.get("drivers", [])}, source="learning")
                        except Exception: pass
                        # OX-CONTROL-1 DECIDE: close Measure→Decide→Adjust. Convert
                        # the telemetry verdict into recommended adjustment actions +
                        # a policy, and record it (control history → future attribution).
                        # The policy is applied by the NEXT run (run-start directive +
                        # the promotion-threshold nudge above).
                        try:
                            import control_engine as _ctrl
                            _dec = _ctrl.decide_and_record(_tsc)
                            yield f"data: {json.dumps({'type':'control','verdict':_dec.get('verdict'),'recommended_actions':_dec.get('recommended_actions',[]),'reason':_dec.get('reason','')}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("control", {"verdict": _dec.get("verdict"), "actions": _dec.get("recommended_actions", [])}, source="learning")
                            except Exception: pass
                        except Exception as _ce2:
                            print(f"[ControlEngine] decide skipped: {_ce2}")
                    except Exception as _te:
                        print(f"[Telemetry] scorecard skipped: {_te}")
                except Exception as _lse:
                    print(f"[LessonSynthesis] refresh skipped: {_lse}")

            # OX-ATTRIBUTION-1 — connect this mission's RECALLED knowledge to its
            # OUTCOME. Records {recalled capabilities/lessons, control verdict,
            # outcome, per-mission attribution_score}; cross-mission lift over
            # baseline (computed on demand) reveals which recalls actually help.
            # Runs for every exit (success or not), independent of workspace.
            try:
                import attribution as _attr
                _outcome = "success" if task_done else "failure"
                _recalled_names = (locals().get("_attrib") or {}).get("capabilities") or []
                # OX-COMPLIANCE-1 — did the recalled capabilities actually shape
                # execution? Compare their recommended_tools to the tools this run
                # ACTUALLY used. MEASURE ONLY — does not alter any runtime decision.
                _comp = {"compliance_score": None, "classification": None}
                try:
                    import compliance as _compl
                    _tools_used = sorted({nm for nm, _r in (locals().get("tool_results_log") or [])})
                    _comp = _compl.record(_ocp_session_id, _recalled_names, _tools_used, outcome=_outcome)
                    yield f"data: {json.dumps({'type':'compliance','mission_id':_ocp_session_id,'compliance_score':_comp.get('compliance_score'),'classification':_comp.get('classification'),'expected_tools':_comp.get('expected_tools',[]),'matched_tools':_comp.get('matched_tools',[])}, ensure_ascii=False)}\n\n"
                    try: house_sync.publish("compliance", {"score": _comp.get("compliance_score"), "class": _comp.get("classification")}, source="learning")
                    except Exception: pass
                except Exception as _ce3:
                    print(f"[Compliance] measure skipped: {_ce3}")
                # OX-ACQUISITION-1 — record the acquisition outcome: which sources
                # the run actually searched (from tools used) vs each gap's
                # candidates. knowledge_found is a proxy (a candidate source was
                # searched AND the mission executed). MEASURE ONLY.
                try:
                    import acquisition as _acq
                    _aq_gaps = locals().get("_acq_gaps") or []
                    if _aq_gaps:
                        _aq_checked = _acq.map_tools_to_sources(locals().get("_tools_used") or [])
                        _aq_exec = bool(locals().get("_tools_used"))
                        for _g in _aq_gaps:
                            _succ = [s for s in _aq_checked if s in (_g.get("source_candidates") or [])]
                            _acq.record(_g, _aq_checked, _succ,
                                        knowledge_found=bool(_succ and task_done),
                                        execution_used=_aq_exec,
                                        mission_id=_ocp_session_id,
                                        compliance_score=_comp.get("compliance_score"))
                        yield f"data: {json.dumps({'type':'acquisition','gaps':len(_aq_gaps),'sources_checked':_aq_checked}, ensure_ascii=False)}\n\n"
                        try: house_sync.publish("acquisition", {"gaps": len(_aq_gaps), "sources_checked": _aq_checked}, source="learning")
                        except Exception: pass
                        # OX-METALEARNING-1 — recompute learning strategies from the
                        # updated episodes (which source orders work per gap_type).
                        try:
                            import metalearning as _ml
                            _strat = _ml.refresh()
                            yield f"data: {json.dumps({'type':'metalearning','strategies':len(_strat)}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("metalearning", {"strategies": len(_strat)}, source="learning")
                            except Exception: pass
                        except Exception as _mle:
                            print(f"[MetaLearning] refresh skipped: {_mle}")
                        # OX-EXPLORATION-1 — record which source order each gap used
                        # (primary vs explored) and its outcome, then flag any
                        # alternative that is beating the primary (promotion candidate).
                        # Exploration never rewrites rankings — MetaLearning owns that.
                        try:
                            import exploration as _expl
                            _esel = locals().get("_explore_sel") or {}
                            _g_outcome = "success" if task_done else "failure"
                            for _g in _aq_gaps:
                                _s = _esel.get(_g.get("gap_id"))
                                if _s:
                                    _expl.record_outcome(_g.get("gap_type", ""),
                                                         _s.get("selected_strategy") or [],
                                                         bool(_s.get("exploration")), _g_outcome)
                            _cands = _expl.detect_improvements()
                            yield f"data: {json.dumps({'type':'exploration','improvement_candidates':len(_cands)}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("exploration", {"improvement_candidates": len(_cands)}, source="learning")
                            except Exception: pass
                        except Exception as _exe:
                            print(f"[Exploration] record skipped: {_exe}")
                        # OX-CAUSAL-1 — discover WHY strategies work: contrast
                        # successful vs failed episodes and promote discriminating
                        # causal hypotheses (flag only; no strategy/weight rewrite).
                        try:
                            import causal as _causal
                            _hyp = _causal.refresh()
                            yield f"data: {json.dumps({'type':'causal','promoted':sum(len(v) for v in _hyp.values())}, ensure_ascii=False)}\n\n"
                            try: house_sync.publish("causal", {"promoted": sum(len(v) for v in _hyp.values())}, source="learning")
                            except Exception: pass
                        except Exception as _cae:
                            print(f"[Causal] refresh skipped: {_cae}")
                except Exception as _aqr:
                    print(f"[Acquisition] record skipped: {_aqr}")
                _arec = _attr.record(_ocp_session_id,
                                     capabilities=_recalled_names,
                                     lessons=(locals().get("_attrib") or {}).get("lessons"),
                                     control_verdict=(locals().get("_attrib") or {}).get("control_verdict"),
                                     outcome=_outcome,
                                     compliance_score=_comp.get("compliance_score"),
                                     compliance_class=_comp.get("classification"))
                yield f"data: {json.dumps({'type':'attribution','mission_id':_arec['mission_id'],'outcome':_arec['outcome'],'attribution_score':_arec['attribution_score'],'recalled_capabilities':_arec['recalled_capabilities'],'recalled_lessons':_arec['recalled_lessons']}, ensure_ascii=False)}\n\n"
                try: house_sync.publish("attribution", {"outcome": _arec["outcome"], "score": _arec["attribution_score"], "capabilities": _arec["recalled_capabilities"]}, source="learning")
                except Exception: pass
                # OX-REINFORCEMENT-1 — convert the updated attribution registry into
                # adaptive capability WEIGHTS (gradual, bounded). Positive lift →
                # reinforce, negative → demote, neutral → observe. The next run's
                # recall reorders by these weights and surfaces demoted caps as
                # warnings. Reads attribution.attribute(); persists capability_weights.json.
                try:
                    import reinforcement as _reinf
                    _wrep = _attr.attribute()
                    _wts = _reinf.reinforce_and_save(_wrep)
                    yield f"data: {json.dumps({'type':'reinforcement','weighted':len(_wts),'reinforced':sum(1 for w in _wts.values() if w.get('status')=='reinforced'),'demoted':sum(1 for w in _wts.values() if w.get('status')=='demoted')}, ensure_ascii=False)}\n\n"
                    try: house_sync.publish("reinforcement", {"weighted": len(_wts)}, source="learning")
                    except Exception: pass
                except Exception as _re:
                    print(f"[Reinforcement] update skipped: {_re}")
            except Exception as _ae:
                print(f"[Attribution] record skipped: {_ae}")

            if not task_done and not run_halted:
                # genuine step-limit exhaustion only — halts already reported agent_stuck
                yield f"data: {json.dumps({'type':'agent_limit','steps':MAX_STEPS,'tools_used':total_tool_calls,'failed':True})}\n\n"
                # OPENCLAW PORT: write diary for non-complete exits (limit / stuck)
                _final_steps = step_num if 'step_num' in dir() else 0
                try:
                    _traj.complete("limit_or_stuck", "")
                    _ocp_diary(
                        session_id=_ocp_session_id,
                        task=req.task,
                        summary="(agent did not reach TASK_COMPLETE — see trajectory for details)",
                        tools_used=action_sigs,
                        n_steps=_final_steps,
                        status="limit",
                        duration_sec=time.time() - _ocp_t0,
                        blocked_calls=_ocp_blocked,
                    )
                except Exception:
                    pass
                # OPENCLAW PORT T2: persist limit/stuck to agent_runs DB
                try:
                    _AGENT_RUNS_DB.end_run(
                        run_id=_ocp_session_id,
                        status="limit",
                        n_steps=_final_steps,
                        n_tools=total_tool_calls,
                        n_blocks=_ocp_blocked,
                        summary="agent reached MAX_STEPS without TASK_COMPLETE" + _mem_footer("limit"),
                    )
                except Exception:
                    pass

            # Canonical terminal status — every run ends as exactly one of these:
            # SUCCESS | BLOCKED | FAILED | LIMIT | CANCELLED. BLOCKED (OX-1.4) is a
            # dead end (varied actions, no new information) — distinct from a hard
            # FAILED error and from LIMIT (ran out of steps).
            _final_status = ("SUCCESS" if task_done else
                             ("BLOCKED" if blocked else
                              ("FAILED" if run_halted else "LIMIT")))
            # OX-1.4: a halted run (BLOCKED / FAILED) must be recorded honestly in
            # the agent_runs ledger — never left lingering as RUNNING. SUCCESS and
            # LIMIT were already persisted on their own paths above.
            if run_halted:
                try:
                    _AGENT_RUNS_DB.end_run(
                        run_id=_ocp_session_id,
                        status=_final_status.lower(),
                        n_steps=step_num if 'step_num' in dir() else 0,
                        n_tools=total_tool_calls,
                        n_blocks=_ocp_blocked,
                        summary=halt_reason[:300] + _mem_footer(_final_status.lower()),
                    )
                except Exception:
                    pass
            # Phase 5: the agent_runs ledger was just finalized — refresh the
            # Mission Command Center view and emit mission_* deltas.
            try:
                import house_sync as _hsync_m, mission_command as _mcc_m
                _mcc_m.diff_and_emit(_hsync_m.publish)
            except Exception:
                pass
            yield f"data: {json.dumps({'type':'done','final_status':_final_status})}\n\n"

        except (GeneratorExit, asyncio.CancelledError):
            # Client disconnected or run was cancelled — persist a terminal CANCELLED
            # state so the run never lingers as RUNNING in the agent_runs ledger.
            try:
                _AGENT_RUNS_DB.end_run(
                    run_id=_ocp_session_id,
                    status="cancelled",
                    n_steps=step_num if 'step_num' in dir() else 0,
                    n_tools=total_tool_calls if 'total_tool_calls' in dir() else 0,
                    n_blocks=_ocp_blocked if '_ocp_blocked' in dir() else 0,
                    summary="run cancelled (client disconnect or abort)",
                )
            except Exception:
                pass
            return
        except Exception as e:
            try:
                _traj.complete("error", repr(e)[:300])
            except Exception: pass
            try:
                _AGENT_RUNS_DB.end_run(
                    run_id=_ocp_session_id,
                    status="error",
                    n_steps=step_num if 'step_num' in dir() else 0,
                    n_tools=total_tool_calls if 'total_tool_calls' in dir() else 0,
                    n_blocks=_ocp_blocked if '_ocp_blocked' in dir() else 0,
                    summary=repr(e)[:400],
                )
            except Exception: pass
            try:
                yield f"data: {json.dumps({'type':'agent_error','msg':repr(e)})}\n\n"
                yield f"data: {json.dumps({'type':'done','final_status':'FAILED'})}\n\n"
            except: pass
        finally:
            # OPENCLAW PORT: always close trajectory writer (best-effort)
            try:
                _traj.close()
            except Exception:
                pass
            # OX-STABILITY-1 Phase 1: CATCH-ALL terminal close. Reached on every
            # exit path the explicit branches miss — client disconnect, GeneratorExit,
            # CancelledError, server shutdown mid-stream. Idempotent: only writes if
            # the run is still 'running', so it never clobbers a real terminal status.
            try:
                _sid = locals().get("_ocp_session_id")
                if _sid:
                    _AGENT_RUNS_DB.end_run_if_open(_sid, "interrupted",
                                                   summary="[interrupted: stream ended before terminal status]")
            except Exception:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        }
    )

@app.get("/api/agent/memory")
async def get_agent_memory():
    return load_agent_memory()

@app.delete("/api/agent/memory")
async def clear_agent_memory():
    save_agent_memory({"sessions": [], "context": []})
    return {"ok": True}

# ── H3/H4/H5: KNOWLEDGE FRONTIER · ASSET · SKILL EVOLUTION · DYNAMICS ─────────
@app.get("/api/house/frontier")
async def house_frontier(state_id: str = ""):
    """H3 — the live knowledge frontier: KNOWN / KNOWN-UNKNOWNS / UNKNOWN-UNKNOWNS
    / ASSUMPTIONS / DISCOVERY TARGETS for the current (or given) mission."""
    try:
        import knowledge_frontier as _kf
        return {"ok": True, "frontier": _kf.frontier(state_id or None)}
    except Exception as e:
        return {"ok": False, "error": str(e), "frontier": {}}


@app.get("/api/house/telemetry")
async def house_telemetry(window: int = 0):
    """OX-TELEMETRY-1 — is THE HOUSE actually improving? Compares the recent
    window of runs against the prior window (read-only) and returns the
    improvement scorecard + a human-readable verdict line."""
    try:
        import telemetry as _tele
        sc = _tele.scorecard(runs=_AGENT_RUNS_DB.recent(limit=200) or [],
                             window=(window or None))
        return {"ok": True, "telemetry": sc, "summary": _tele.render(sc)}
    except Exception as e:
        return {"ok": False, "error": str(e), "telemetry": {}}


@app.get("/api/house/attribution")
async def house_attribution():
    """OX-ATTRIBUTION-1 — which recalled knowledge actually contributed to
    outcomes? Returns per-item lift over baseline (reinforce / demote candidates)
    plus a human summary. Read-only over attribution.json."""
    try:
        import attribution as _attr
        rep = _attr.attribute()
        return {"ok": True, "attribution": rep, "summary": _attr.summary(rep)}
    except Exception as e:
        return {"ok": False, "error": str(e), "attribution": {}}


@app.get("/api/house/causal")
async def house_causal(gap_type: str = ""):
    """OX-CAUSAL-1 — discovered causal hypotheses (WHY strategies work) + metrics.
    Read-only. Optional gap_type filters the live discovery view."""
    try:
        import causal as _causal
        return {"ok": True, "metrics": _causal.metrics(),
                "promoted": _causal.load_hypotheses(),
                "discovery": _causal.discover(gap_type=gap_type or None) if gap_type else []}
    except Exception as e:
        return {"ok": False, "error": str(e), "promoted": {}}


@app.get("/api/house/observability")
async def house_observability(workflow_id: str = ""):
    """OX-OBSERVABILITY-1 — one fresh snapshot for the operator panels: workflow
    timeline + active workflow_id + trace (reached/failed phase, termination
    reason), house_state metadata (state_id/updated_at/source), and the cognitive
    stack (decision/theory/research agenda/unknowns/paradigm). Read-only, live
    (never cached), and degrades gracefully when a source is empty."""
    try:
        import observability as _obs
        return {"ok": True, "snapshot": _obs.snapshot(workflow_id=workflow_id or "")}
    except Exception as e:
        return {"ok": False, "error": str(e), "snapshot": {}}


@app.get("/api/house/reliability")
async def house_reliability():
    """OX-HOUSE-STABILIZATION-1 — live production-reliability telemetry: GPU/VRAM/
    CPU/RAM, Ollama residency + offload (CPU vs GPU), agent success/timeout rates,
    avg run duration, loaded model, prompt token sizes. All measured at request
    time (no cached estimates). Degrades gracefully when a source is unavailable."""
    try:
        import reliability_dashboard as _rel
        return {"ok": True, "snapshot": _rel.collect()}
    except Exception as e:
        return {"ok": False, "error": str(e), "snapshot": {}}


@app.get("/reliability")
async def reliability_page():
    """Human-readable auto-refreshing version of /api/house/reliability."""
    from fastapi.responses import HTMLResponse
    try:
        import reliability_dashboard as _rel
        return HTMLResponse(_rel.render_html(_rel.collect()))
    except Exception as e:
        return HTMLResponse(f"<pre>reliability error: {e}</pre>", status_code=500)


# ── OX-RUNTIME-DISCOVERY-1 — capability-based runtime registry API (Phase 8) ──
def _runtime_extra_probes():
    """Merge DB connections as scan probes so user-configured runtimes are
    discovered with ZERO code change (the House never hardcodes a runtime)."""
    out = []
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        # The api_key travels with the probe: a runtime behind `--api-key` used to
        # answer 401 and be filed as offline, which sent the operator to restart a
        # server that was running and had merely refused an unauthenticated request.
        for cid, name, base, at, key in c.execute(
                "SELECT id,name,base_url,api_type,api_key FROM connections"):
            out.append({"runtime": name or cid, "url": base,
                        "api_type": at or "ollama", "api_key": key or None})
        conn.close()
    except Exception:
        pass
    return out


@app.get("/api/runtime")
async def api_runtime():
    """All discovered runtimes (Ollama/llama.cpp/LM Studio/vLLM/SGLang/OpenAI) + models."""
    try:
        import runtime_scanner as _sc
        return {"ok": True, "runtimes": _sc.scan(extra_probes=_runtime_extra_probes())}
    except Exception as e:
        return {"ok": False, "error": str(e), "runtimes": []}


@app.get("/api/runtime/models")
async def api_runtime_models():
    """Every discovered model with capability roles (Execution/Reasoning/…)."""
    try:
        import runtime_scanner as _sc, runtime_registry as _rg, runtime_metrics as _rm
        scan = _sc.scan(extra_probes=_runtime_extra_probes())
        return {"ok": True, "registry": _rg.build_registry(scan, _rm.load_metrics())}
    except Exception as e:
        return {"ok": False, "error": str(e), "registry": {}}


@app.get("/api/runtime/metrics")
async def api_runtime_metrics():
    """Latest benchmark metrics per model (runtime_metrics.db)."""
    try:
        import runtime_metrics as _rm
        return {"ok": True, "metrics": _rm.load_metrics()}
    except Exception as e:
        return {"ok": False, "error": str(e), "metrics": {}}


@app.get("/api/runtime/health")
async def api_runtime_health():
    """Liveness + latency per runtime; unhealthy runtimes are auto-excluded from routing."""
    try:
        import runtime_scanner as _sc, runtime_router as _rt
        return {"ok": True, "health": _rt.health_report(_sc.scan(extra_probes=_runtime_extra_probes()))}
    except Exception as e:
        return {"ok": False, "error": str(e), "health": {}}


@app.get("/api/runtime/router")
async def api_runtime_router(task: str = ""):
    """Capability routing: task → role → best runtime+model+endpoint (no model names)."""
    try:
        import runtime_router as _rt
        return {"ok": True, "route": _rt.route(task or "create a file",
                                                extra_probes=_runtime_extra_probes())}
    except Exception as e:
        return {"ok": False, "error": str(e), "route": {}}


# ── OX-RUNTIME-KERNEL-1 — Runtime Kernel API (Phase 7) ────────────────────────
def _kernel():
    import runtime_kernel as _k
    return _k.get_kernel(extra_probes=_runtime_extra_probes(), rediscover=True)


@app.get("/api/runtime/kernel")
async def api_runtime_kernel():
    """Kernel snapshot: drivers, runtime instances, capability pools, live sessions."""
    try:
        return {"ok": True, "kernel": _kernel().snapshot()}
    except Exception as e:
        return {"ok": False, "error": str(e), "kernel": {}}


@app.get("/api/runtime/pools")
async def api_runtime_pools():
    """Capability pools: which runtimes/models can serve each role."""
    try:
        return {"ok": True, "pools": _kernel().pools()}
    except Exception as e:
        return {"ok": False, "error": str(e), "pools": {}}


@app.get("/api/runtime/sessions")
async def api_runtime_sessions():
    """Active persistent runtime sessions (keep_alive / residency reuse)."""
    try:
        return {"ok": True, "sessions": _kernel().sessions_info()}
    except Exception as e:
        return {"ok": False, "error": str(e), "sessions": []}


@app.get("/api/runtime/drivers")
async def api_runtime_drivers():
    """Loaded Runtime Drivers (plugins). Adding a runtime = a new plugin, zero kernel change."""
    try:
        return {"ok": True, "drivers": _kernel().drivers_info()}
    except Exception as e:
        return {"ok": False, "error": str(e), "drivers": []}


@app.get("/api/runtime/capabilities")
async def api_runtime_capabilities(task: str = ""):
    """Capability negotiation preview: required caps for a task + ranked matching runtimes."""
    try:
        k = _kernel()
        req = k.required_for_task(task or "create a file")
        return {"ok": True, "required": req, "matches": k.negotiate(req)}
    except Exception as e:
        return {"ok": False, "error": str(e), "required": {}, "matches": []}


# ── OX-HOUSE-BOOT-1 — autonomous Boot Layer API (Phase 9) ─────────────────────
_GRAPH_TTL = 15.0
_GRAPH_CACHE = {"ts": 0.0, "data": None}

@app.get("/api/system/graph")
async def api_system_graph():
    """OX-SYSTEM-MAP-1 — REAL system composition (runtimes, agents, skills, tool
    categories, services + edges) for the Node Map. No mock data.
    P1 perf: build_graph() does blocking runtime probes (~3s); cache it with a TTL
    and run the refresh off the event loop so the Node Map stays responsive."""
    try:
        import system_graph
        now = time.time()
        if _GRAPH_CACHE["data"] is None or now - _GRAPH_CACHE["ts"] > _GRAPH_TTL:
            _GRAPH_CACHE["data"] = await asyncio.to_thread(system_graph.build_graph)
            _GRAPH_CACHE["ts"] = now
        return {"ok": True, "cached_age_s": round(time.time() - _GRAPH_CACHE["ts"], 1),
                **_GRAPH_CACHE["data"]}
    except Exception as e:
        return {"ok": False, "error": str(e), "nodes": [], "edges": []}


_ARCH_CACHE = {"ts": 0.0, "data": None}


@app.get("/api/system/architecture")
async def api_system_architecture():
    """OX-ARCH-MAP-1 — the layered OS / Cognitive-Kernel architecture: planes,
    live component status, the cognitive lifecycle, and inter-plane relationships.
    Real state only (genesis_os, runtime_kernel, cognitive_validation, live probes).
    Cached with a TTL; blocking probes run off the event loop."""
    try:
        import system_graph
        now = time.time()
        if _ARCH_CACHE["data"] is None or now - _ARCH_CACHE["ts"] > _GRAPH_TTL:
            _ARCH_CACHE["data"] = await asyncio.to_thread(system_graph.build_architecture)
            _ARCH_CACHE["ts"] = now
        return {"ok": True, "cached_age_s": round(time.time() - _ARCH_CACHE["ts"], 1),
                **_ARCH_CACHE["data"]}
    except Exception as e:
        return {"ok": False, "error": str(e), "planes": [], "flows": []}


@app.get("/system-map")
async def system_map_page():
    """Intel — the systematic architecture view (layered OS/Kernel stack) + the
    live Node Map graph."""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_SYSTEM_MAP_HTML)


_SYSTEM_MAP_HTML = """<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Intel · SkynetClaw Architecture</title>
<style>
:root{--bg:#0d1117;--bg2:#161b22;--bg3:#1b2230;--bd:#30363d;--bd2:#3d4757;--fg:#e6edf3;--mut:#8b949e;--ac:#6c5ff0;--ac2:#9b8fff;--cy:#00c8ff;--gn:#3fb950;--am:#f5c842;--rd:#f85149}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--fg);font-family:system-ui,'Segoe UI',sans-serif;height:100vh;overflow:hidden;
  background-image:radial-gradient(circle at 12% 0%,rgba(108,95,240,.07),transparent 55%),radial-gradient(circle at 90% 100%,rgba(0,200,255,.05),transparent 55%)}
.bar{display:flex;align-items:center;gap:12px;padding:11px 18px;border-bottom:1px solid var(--bd);position:relative;z-index:5}
.bar h1{font-size:15px;margin:0;letter-spacing:.04em}
.seg{display:flex;background:var(--bg2);border:1px solid var(--bd2);border-radius:9px;overflow:hidden}
.seg button{background:transparent;border:0;color:var(--mut);padding:6px 13px;cursor:pointer;font-size:12.5px}
.seg button.on{background:var(--ac);color:#fff}
.stat{font-size:12px;color:var(--mut)}.stat b{color:var(--ac2)}
.bar .rf{margin-left:auto;background:var(--bg2);border:1px solid var(--bd2);color:var(--mut);border-radius:8px;padding:5px 12px;cursor:pointer;font-size:12px}
.bar .rf:hover{border-color:var(--ac);color:var(--fg)}
.view{position:relative;height:calc(100vh - 50px);overflow:auto}
.view[hidden]{display:none}
/* ── Architecture view ── */
#arch{padding:20px 26px 60px}
.ribbon{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0 0 6px}
.ribbon .cap{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);width:100%;margin-bottom:4px}
.ph{display:flex;align-items:center;gap:6px}
.ph .pill{background:var(--bg2);border:1px solid var(--bd2);border-radius:20px;padding:4px 12px;font-size:12px;white-space:nowrap}
.ph .ar{color:var(--ac2);font-size:13px}
.stack{margin-top:14px}
.plane{display:flex;gap:16px;align-items:stretch;background:var(--bg2);border:1px solid var(--bd);border-radius:14px;padding:13px 15px;position:relative}
.plane .lbl{width:210px;flex-shrink:0;border-right:1px solid var(--bd);padding-right:14px}
.plane .lbl .pn{font-size:13.5px;font-weight:700;line-height:1.25}
.plane .lbl .ps{font-size:11px;color:var(--mut);margin-top:3px}
.badge{display:inline-block;font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;border-radius:5px;padding:1px 6px;margin-top:7px;font-weight:700}
.badge.live{background:rgba(63,185,80,.15);color:var(--gn);border:1px solid rgba(63,185,80,.35)}
.badge.spec{background:rgba(0,200,255,.12);color:var(--cy);border:1px solid rgba(0,200,255,.35)}
.badge.kernel{background:rgba(108,95,240,.18);color:var(--ac2);border:1px solid rgba(108,95,240,.45)}
.cards{flex:1;display:flex;flex-wrap:wrap;gap:9px;align-content:flex-start}
.card{display:flex;align-items:center;gap:9px;background:var(--bg3);border:1px solid var(--bd);border-radius:10px;padding:8px 11px;cursor:pointer;min-width:150px;
  transition:transform .12s,border-color .2s,box-shadow .2s}
.card:hover{transform:translateY(-2px);border-color:var(--ac);box-shadow:0 5px 16px rgba(108,95,240,.22)}
.card.sel{border-color:var(--ac2);box-shadow:0 0 0 1px var(--ac2)}
.card.planned{border-style:dashed;opacity:.82}
.card .ic{font-size:16px;flex-shrink:0}.card .tx{min-width:0}
.card .cn{font-size:12.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:5px}
.card .cs{font-size:10px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px}
.dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.dot.online{background:var(--gn);box-shadow:0 0 6px var(--gn)}.dot.idle{background:var(--mut)}
.dot.planned{background:var(--am)}.dot.offline{background:var(--rd)}.dot.live{background:var(--cy);box-shadow:0 0 6px var(--cy)}
.dot.migrated{background:var(--ac2);box-shadow:0 0 7px var(--ac2)}
.card.migrated{border-color:rgba(108,95,240,.55)}
.star{color:var(--cy);font-size:10px}
.conn{display:flex;justify-content:center;gap:26px;padding:3px 0;font-size:11px;color:var(--mut)}
.conn .dn{color:var(--ac2)}.conn .up{color:var(--gn)}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin:16px 2px 0;font-size:11px;color:var(--mut)}
.legend span{display:inline-flex;align-items:center;gap:6px}
/* ── Node Map view (unchanged graph) ── */
#nodemap{overflow:auto}
#edges{position:absolute;top:0;left:0;pointer-events:none;z-index:1}
.edge{fill:none;stroke:rgba(108,95,240,.35);stroke-width:1.5}
.cols{display:flex;gap:30px;padding:26px;position:relative;z-index:2;min-width:max-content}
.col{display:flex;flex-direction:column;gap:12px;width:210px;flex-shrink:0}
.col-h{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);font-weight:700;padding-left:4px}
.node{display:flex;align-items:center;gap:10px;background:var(--bg2);border:1px solid var(--bd);border-radius:12px;padding:11px 13px;cursor:pointer;
  transition:transform .15s,border-color .2s,box-shadow .2s;box-shadow:0 2px 10px rgba(0,0,0,.3)}
.node:hover{transform:translateY(-2px);border-color:var(--ac)}
.node.sel{border-color:var(--ac2);box-shadow:0 0 0 1px var(--ac2)}
.node .ic{font-size:18px;flex-shrink:0}.node .tx{min-width:0;flex:1}
.node .nm{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.node .sb{font-size:10.5px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.node .dot.grn{background:var(--gn);box-shadow:0 0 6px var(--gn)}.node .dot.red{background:var(--rd)}
.node.agent{border-left:3px solid var(--ac2)}.node.runtime,.node.model{border-left:3px solid var(--cy)}
.node.skill{border-left:3px solid var(--am)}.node.toolcat{border-left:3px solid var(--gn)}.node.service{border-left:3px solid var(--ac)}
/* ── shared detail panel ── */
#panel{position:fixed;top:0;right:-400px;width:380px;height:100vh;background:rgba(13,18,26,.97);backdrop-filter:blur(16px);
  border-left:1px solid var(--bd2);padding:20px;transition:right .25s;z-index:10;overflow-y:auto}
#panel.open{right:0}
#panel h2{font-size:16px;margin:0 0 2px;display:flex;align-items:center;gap:8px}
#panel .pt{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px}
#panel .sec{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin:16px 0 6px}
#panel .chip{display:inline-block;background:rgba(108,95,240,.12);border:1px solid rgba(108,95,240,.3);border-radius:6px;padding:2px 8px;font-size:11px;margin:2px 3px 0 0}
#panel .ln{font-size:12.5px;padding:5px 0;border-bottom:1px solid var(--bd)}
#panel .cls{position:absolute;top:14px;right:16px;cursor:pointer;color:var(--mut);font-size:18px}
.loading{padding:40px;text-align:center;color:var(--mut)}
</style></head><body>
<div class="bar"><h1>⬢ SkynetClaw · Intel</h1>
  <div class="seg"><button id="tab-arch" class="on" onclick="setMode('arch')">⬢ สถาปัตยกรรม</button><button id="tab-map" onclick="setMode('map')">◇ Node Map</button></div>
  <span class="stat" id="stat">…</span>
  <button class="rf" onclick="refresh()">↻ รีเฟรช</button></div>

<div class="view" id="arch"><div class="loading">กำลังโหลดสถาปัตยกรรม…</div></div>
<div class="view" id="nodemap" hidden><svg id="edges"></svg><div class="cols" id="cols"><div class="loading">กำลังโหลด Node Map…</div></div></div>
<div id="panel"><span class="cls" onclick="closeP()">✕</span><div id="pbody"></div></div>
<script>
const esc=s=>String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const cid=s=>String(s).replace(/[^a-zA-Z0-9]/g,'_');
let MODE='arch', ARCH=null, GRAPH=null;

function setMode(m){
  MODE=m;
  document.getElementById('tab-arch').classList.toggle('on',m==='arch');
  document.getElementById('tab-map').classList.toggle('on',m==='map');
  document.getElementById('arch').hidden=(m!=='arch');
  document.getElementById('nodemap').hidden=(m!=='map');
  closeP();
  if(m==='arch'){ if(!ARCH)loadArch(); else statArch(); }
  else{ if(!GRAPH)loadGraph(); else statGraph(); }
}
function refresh(){ if(MODE==='arch')loadArch(); else loadGraph(); }

/* ── Architecture ── */
async function loadArch(){
  try{
    const r=await fetch('/api/system/architecture'); ARCH=await r.json();
    if(!ARCH.ok&&ARCH.error){document.getElementById('arch').innerHTML='<div class="loading">error: '+esc(ARCH.error)+'</div>';return;}
    renderArch(ARCH); statArch();
  }catch(e){document.getElementById('arch').innerHTML='<div class="loading">โหลดไม่ได้: '+esc(e)+'</div>';}
}
function statArch(){const s=ARCH.stats||{}, a=ARCH.audit||{};
  document.getElementById('stat').innerHTML=
    `Kernel <b>${s.kernel_migrated||0}/${s.kernel_total||0}</b> migrated · `+
    `<b>${s.policies||0}</b> policies armed · `+
    `<b>${s.subsystems_conform||0}</b> subsystems conform · `+
    `audit <b>${a.events||0}</b> (policy ${a.policy||0}) · OS <b>${esc(ARCH.os_state||'?')}</b>`;}
function renderArch(a){
  const el=document.getElementById('arch');
  const flow=(from,to,kind)=>(a.flows||[]).find(f=>f.from===from&&f.to===to&&f.kind===kind);
  let h='';
  // lifecycle ribbon
  h+='<div class="ribbon"><span class="cap">Cognitive Lifecycle · วงจรการคิด (SPEC §2)</span>';
  (a.lifecycle||[]).forEach((p,i)=>{h+=`<div class="ph">${i?'<span class="ar">→</span>':''}<span class="pill">${esc(p)}</span></div>`;});
  h+='</div><div class="stack">';
  const planes=a.planes||[];
  planes.forEach((p,idx)=>{
    const _bk = p.kind==='spec' ? ['spec','spec v0.2'] : (p.kind==='kernel' ? ['kernel','kernel · live'] : ['live','live']);
    h+=`<div class="plane"><div class="lbl"><div class="pn">${esc(p.name)}</div><div class="ps">${esc(p.sub||'')}</div><span class="badge ${_bk[0]}">${_bk[1]}</span></div><div class="cards">`;
    (p.nodes||[]).forEach(n=>{
      h+=`<div class="card ${n.status==='planned'?'planned':(n.status==='migrated'?'migrated':'')}" id="c_${cid(n.id)}" onclick='showCard(${JSON.stringify(n).replace(/'/g,"&#39;")},"${esc(p.name)}")'>
        <div class="ic">${n.icon||'•'}</div><div class="tx"><div class="cn">${esc(n.label)}${n.conforms?' <span class="star">★</span>':''}</div><div class="cs">${esc(n.sub||'')}</div></div><div class="dot ${esc(n.status)}"></div></div>`;
    });
    h+='</div></div>';
    if(idx<planes.length-1){
      const nx=planes[idx+1];
      const dn=flow(p.id,nx.id,'call'), up=flow(nx.id,p.id,'event');
      h+=`<div class="conn">${dn?`<span class="dn">↓ ${esc(dn.label)}</span>`:''}${up?`<span class="up">↑ ${esc(up.label)}</span>`:''}</div>`;
    }
  });
  h+='</div>';
  h+='<div class="legend"><span><i class="dot migrated"></i>migrated (conforms_to ✓)</span><span><i class="dot online"></i>online</span><span><i class="dot live"></i>live (legacy)</span><span><i class="dot planned"></i>planned (spec)</span><span><i class="dot idle"></i>idle</span><span><i class="dot offline"></i>offline</span><span>★ conforms to the kernel ABI</span></div>';
  el.innerHTML=h;
}
function showCard(n,plane){
  document.querySelectorAll('.card.sel').forEach(e=>e.classList.remove('sel'));
  const el=document.getElementById('c_'+cid(n.id)); if(el)el.classList.add('sel');
  let h=`<h2>${n.icon||''} ${esc(n.label)}</h2><div class="pt">${esc(plane)} · <b style="color:var(--fg)">${esc(n.status)}</b></div>`;
  if(n.sub)h+=`<div class="ln">${esc(n.sub)}</div>`;
  if(n.backing)h+=`<div class="sec">Backing module</div><div class="ln"><code>${esc(n.backing)}</code></div>`;
  if(n.status==='migrated')h+=`<div class="sec">Migration</div><div class="ln">✅ ย้ายเข้า Cognitive Kernel แล้ว — โมดูลนี้มี <code>conforms_to()</code> ที่เขียว (A6: subsystem นับว่า migrated ก็ต่อเมื่อ conformance gate ผ่าน)</div>`;
  if(n.status==='live')h+=`<div class="sec">Migration</div><div class="ln">⏳ โค้ดจริงมีอยู่ แต่ยังกระจายอยู่ใน legacy module — ยังไม่ถูก migrate เข้า kernel</div>`;
  if(n.conforms)h+=`<div class="sec">Note</div><div class="ln">★ implements the kernel ABI (ships conforms_to()).</div>`;
  if(n.status==='planned')h+=`<div class="sec">Status</div><div class="ln">กำหนดไว้ใน COGNITIVE_KERNEL_SPEC — ยังไม่ถูก migrate เป็นโค้ด</div>`;
  document.getElementById('pbody').innerHTML=h;
  document.getElementById('panel').classList.add('open');
}

/* ── Node Map (existing graph) ── */
const ORDER=['Runtimes','Agents','Skills','Tools','Services'];
async function loadGraph(){
  try{
    const r=await fetch('/api/system/graph'); GRAPH=await r.json();
    if(!GRAPH.ok&&GRAPH.error){document.getElementById('cols').innerHTML='<div class="loading">error: '+esc(GRAPH.error)+'</div>';return;}
    renderGraph(GRAPH); statGraph();
  }catch(e){document.getElementById('cols').innerHTML='<div class="loading">โหลดไม่ได้: '+esc(e)+'</div>';}
}
function statGraph(){const st=GRAPH.stats||{};
  document.getElementById('stat').innerHTML=`<b>${st.nodes||0}</b> โหนด · <b>${st.edges||0}</b> เส้น · <b>${st.online||0}</b> ออนไลน์`;}
function renderGraph(g){
  const by={}; (g.nodes||[]).forEach(n=>{(by[n.group]=by[n.group]||[]).push(n)});
  const cols=document.getElementById('cols'); cols.innerHTML='';
  const groups=ORDER.filter(o=>by[o]).concat(Object.keys(by).filter(k=>!ORDER.includes(k)));
  groups.forEach(grp=>{
    const col=document.createElement('div'); col.className='col';
    col.innerHTML=`<div class="col-h">${esc(grp)} · ${by[grp].length}</div>`;
    by[grp].forEach(n=>{
      const d=document.createElement('div'); d.className='node '+esc(n.type); d.id='n_'+cid(n.id);
      const dot=n.online===false?'red':(n.online?'grn':'');
      d.innerHTML=`<div class="ic">${n.icon||'•'}</div><div class="tx"><div class="nm">${esc(n.label)}</div><div class="sb">${esc(n.sub||'')}</div></div>${dot?`<div class="dot ${dot}"></div>`:''}`;
      d.onclick=()=>showNode(n);
      col.appendChild(d);
    });
    cols.appendChild(col);
  });
  requestAnimationFrame(()=>drawEdges(g));
}
function drawEdges(g){
  const svg=document.getElementById('edges'),cv=document.getElementById('nodemap');
  const r=cv.getBoundingClientRect();
  svg.setAttribute('viewBox',`0 0 ${cv.scrollWidth} ${cv.scrollHeight}`);
  svg.style.width=cv.scrollWidth+'px'; svg.style.height=cv.scrollHeight+'px';
  let h='';
  (g.edges||[]).forEach(e=>{
    const a=document.getElementById('n_'+cid(e.from)),b=document.getElementById('n_'+cid(e.to));
    if(!a||!b)return;
    const ra=a.getBoundingClientRect(),rb=b.getBoundingClientRect();
    const x1=ra.left-r.left+cv.scrollLeft+ra.width/2,y1=ra.top-r.top+cv.scrollTop+ra.height/2;
    const x2=rb.left-r.left+cv.scrollLeft+rb.width/2,y2=rb.top-r.top+cv.scrollTop+rb.height/2;
    const mx=(x1+x2)/2;
    h+=`<path class="edge" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}"/>`;
  });
  svg.innerHTML=h;
}
function showNode(n){
  document.querySelectorAll('.node.sel').forEach(e=>e.classList.remove('sel'));
  const el=document.getElementById('n_'+cid(n.id)); if(el)el.classList.add('sel');
  const ins=(GRAPH.edges||[]).filter(e=>e.to===n.id).map(e=>({id:e.from,kind:e.kind}));
  const outs=(GRAPH.edges||[]).filter(e=>e.from===n.id).map(e=>({id:e.to,kind:e.kind}));
  const lbl=id=>{const x=(GRAPH.nodes||[]).find(m=>m.id===id);return x?x.label:id};
  let h=`<h2>${n.icon||''} ${esc(n.label)}</h2><div class="pt">${esc(n.type)} · ${esc(n.group)}${n.online===false?' · OFFLINE':(n.online?' · online':'')}</div>`;
  if(n.sub)h+=`<div class="ln">${esc(n.sub)}</div>`;
  if(n.tools&&n.tools.length){h+=`<div class="sec">เครื่องมือ (${n.tools.length})</div>`+n.tools.map(t=>`<span class="chip">${esc(t)}</span>`).join('');}
  if(n.triggers&&n.triggers.length){h+=`<div class="sec">ทริกเกอร์</div>`+n.triggers.map(t=>`<span class="chip">${esc(t)}</span>`).join('');}
  if(outs.length){h+=`<div class="sec">เชื่อมไป (${outs.length})</div>`+outs.map(o=>`<div class="ln">→ ${esc(lbl(o.id))} <span style="color:var(--mut);font-size:10px">${esc(o.kind)}</span></div>`).join('');}
  if(ins.length){h+=`<div class="sec">เชื่อมจาก (${ins.length})</div>`+ins.map(o=>`<div class="ln">← ${esc(lbl(o.id))} <span style="color:var(--mut);font-size:10px">${esc(o.kind)}</span></div>`).join('');}
  document.getElementById('pbody').innerHTML=h;
  document.getElementById('panel').classList.add('open');
}
function closeP(){document.getElementById('panel').classList.remove('open');
  document.querySelectorAll('.card.sel,.node.sel').forEach(e=>e.classList.remove('sel'));}
window.addEventListener('resize',()=>{if(MODE==='map'&&GRAPH)drawEdges(GRAPH);});
document.getElementById('nodemap').addEventListener('scroll',()=>{if(GRAPH)drawEdges(GRAPH);});
loadArch();
</script></body></html>"""


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), workspace_folder: str = Form("")):
    """OX-DOC-UPLOAD-1 — upload a document/image; save it under the workspace
    'uploads' folder and extract readable text so the model can use it. Returns
    {path, kind, chars, text, preview}."""
    try:
        import doc_reader as _dr
        ws = (workspace_folder or "").strip()
        if not ws:
            _home = os.path.expanduser("~")
            # Desktop is not guaranteed on Linux (headless, or a non-English
            # XDG name), so fall back to a plain ~/skynetclaw-workspace there.
            _cands = [os.path.join(_home, "OneDrive", "Desktop", "workspace"),
                      os.path.join(_home, "Desktop", "workspace"),
                      os.path.join(_home, "skynetclaw-workspace")]
            for _cand in _cands:
                if os.path.isdir(_cand):
                    ws = _cand; break
            if not ws:
                ws = (os.path.join(_home, "Desktop", "workspace")
                      if os.path.isdir(os.path.join(_home, "Desktop"))
                      else os.path.join(_home, "skynetclaw-workspace"))
        updir = os.path.join(ws, "uploads")
        os.makedirs(updir, exist_ok=True)
        safe = os.path.basename(file.filename or "upload.bin").replace("..", "_")
        dest = os.path.join(updir, safe)
        data = await file.read()
        with open(dest, "wb") as f:
            f.write(data)
        r = _dr.extract_text(dest)
        return {"ok": True, "filename": safe, "path": dest, "bytes": len(data),
                "kind": r.get("kind"), "chars": r.get("chars", 0),
                "text": r.get("text", "") if r.get("ok") else "",
                "preview": (r.get("text", "")[:600] if r.get("ok") else ""),
                "error": None if r.get("ok") else r.get("error")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/news/report")
async def api_news_report(req: Request):
    """OX-NEWS-REPORT-1 — deterministic news report (gather ranked real news +
    render HTML in code, no model). Body: {topics:[...], title, filename, lang,
    per_topic, workspace_folder}."""
    try:
        import news_report as _nr
        body = await req.json()
        topics = body.get("topics") or []
        if isinstance(topics, str):
            import re as _re2
            topics = [t.strip() for t in _re2.split(r"[,\n;|]", topics) if t.strip()]
        ws = body.get("workspace_folder")
        if not ws:
            _home = os.path.expanduser("~")
            # Desktop is not guaranteed on Linux (headless, or a non-English
            # XDG name), so fall back to a plain ~/skynetclaw-workspace there.
            _cands = [os.path.join(_home, "OneDrive", "Desktop", "workspace"),
                      os.path.join(_home, "Desktop", "workspace"),
                      os.path.join(_home, "skynetclaw-workspace")]
            for _cand in _cands:
                if os.path.isdir(_cand):
                    ws = _cand; break
            if not ws:
                ws = (os.path.join(_home, "Desktop", "workspace")
                      if os.path.isdir(os.path.join(_home, "Desktop"))
                      else os.path.join(_home, "skynetclaw-workspace"))
        fname = (body.get("filename") or "news_report.html").strip()
        if not fname.lower().endswith(".html"):
            fname += ".html"
        out = os.path.join(ws, fname)
        r = _nr.make_report(topics, title=body.get("title", "สรุปข่าวสำคัญ"),
                            lang=body.get("lang", "th"),
                            per_topic=int(body.get("per_topic", 6) or 6), out_path=out)
        return {"ok": True, "report": r}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/boot/start")
async def api_boot_start(quick: bool = True):
    """Trigger the autonomous boot sequence (discover→benchmark→registry→pools→
    sessions→READY). Runs in the background; watch /api/boot/events. quick=true
    reuses an existing registry and only re-benchmarks changed models."""
    import threading, runtime_boot as _b
    def _go():
        try: _b.house_boot(extra_probes=_runtime_extra_probes(), quick=quick, start_monitor=True)
        except Exception as _e: print(f"[boot] {_e}")
    threading.Thread(target=_go, daemon=True).start()
    return {"ok": True, "started": True, "quick": quick}


@app.get("/api/boot/events")
async def api_boot_events():
    """The Boot Event Bus: BOOT_START → … → HOUSE_READY (Phase 9 observability)."""
    try:
        import runtime_boot as _b
        b = _b.get_boot()
        return {"ok": True, "events": b.bus.timeline() if b else [],
                "state": b.state if b else "COLD"}
    except Exception as e:
        return {"ok": False, "error": str(e), "events": []}


@app.get("/api/boot/status")
async def api_boot_status():
    """Boot snapshot: state, stage timeline, runtimes/drivers/pools."""
    try:
        import runtime_boot as _b
        b = _b.get_boot()
        return {"ok": True, "boot": b.snapshot() if b else {"state": "COLD"}}
    except Exception as e:
        return {"ok": False, "error": str(e), "boot": {}}


# ── OX-HOUSE-OS-1 — AI Operating System layer API ─────────────────────────────
def _os():
    import genesis_os
    o = genesis_os.get_os()
    if o.state != "running":
        o.boot()
    return o


@app.post("/api/os/boot")
async def api_os_boot():
    """Boot the OS layer: start services, discover apps → READY."""
    try:
        import genesis_os
        return {"ok": True, "boot": genesis_os.get_os().boot()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/os")
async def api_os_status():
    """OS status: services, apps, workspace, IPC topics, permission audit."""
    try:
        return {"ok": True, "os": _os().status()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/os/services")
async def api_os_services():
    try:
        return {"ok": True, "services": _os().services.health()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/os/services/{name}/{action}")
async def api_os_service_action(name: str, action: str):
    try:
        sm = _os().services
        fn = {"start": sm.start, "stop": sm.stop, "restart": sm.restart}.get(action)
        if not fn:
            return {"ok": False, "error": f"bad action {action}"}
        return {"ok": True, "service": fn(name)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/os/apps")
async def api_os_apps():
    try:
        o = _os(); o.apps.discover()
        return {"ok": True, "apps": o.apps.list()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/os/apps/{app_id}/{action}")
async def api_os_app_action(app_id: str, action: str):
    try:
        am = _os().apps
        fn = {"start": am.start, "stop": am.stop, "uninstall": am.uninstall}.get(action)
        if not fn:
            return {"ok": False, "error": f"bad action {action}"}
        return {"ok": True, "app": fn(app_id)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/os/ipc")
async def api_os_ipc(topic: str = "", limit: int = 100):
    try:
        return {"ok": True, "events": _os().ipc.history(topic_prefix=topic, limit=limit)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/os/permissions")
async def api_os_permissions(actor: str = ""):
    try:
        o = _os()
        return {"ok": True, "audit": o.audit.entries(actor=actor, limit=200),
                "denials": o.audit.denials(limit=100)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/desktop")
async def desktop_shell():
    """Phase 9 — Genesis Desktop shell (sidebar: services / apps / runtime / IPC)."""
    from fastapi.responses import HTMLResponse
    html = """<!doctype html><html><head><meta charset="utf-8"><title>Genesis Desktop</title>
<meta http-equiv="refresh" content="6"></head>
<body style="background:#0d1117;color:#c9d1d9;font-family:system-ui,Segoe UI,sans-serif;margin:0;display:flex">
<div style="width:200px;background:#010409;padding:16px;border-right:1px solid #30363d">
  <h2 style="font-size:15px;margin:0 0 12px">⬢ Genesis OS</h2>
  <div style="color:#8b949e;font-size:13px;line-height:2">
    <div>▸ Runtime Monitor</div><div>▸ Services</div><div>▸ Applications</div>
    <div>▸ IPC Bus</div><div>▸ Permissions</div><div>▸ Marketplace</div></div>
</div>
<div style="flex:1;padding:20px"><h1 style="font-size:18px">Genesis Desktop</h1>
  <div id="root" style="color:#8b949e">loading…</div></div>
<script>
async function load(){
  const r=await (await fetch('/api/os')).json(); const o=r.os||{};
  const card=(t,b)=>`<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin:8px 0"><b style="color:#58a6ff">${t}</b><div style="font-size:13px;margin-top:6px">${b}</div></div>`;
  const svc=(o.services||[]).map(s=>`${s.service}: <span style="color:${s.state==='running'?'#3fb950':'#f85149'}">${s.state}</span>`).join(' · ');
  const apps=(o.apps||[]).map(a=>`${a.name} v${a.version} [${a.state}]`).join('<br>')||'none installed';
  document.getElementById('root').innerHTML =
     card('State', o.state+' · uptime '+(o.uptime_s||0)+'s')
   + card('Services', svc)
   + card('Applications', apps)
   + card('IPC topics', (o.ipc&&o.ipc.topics||[]).join(', ')||'—')
   + card('Permissions', 'audited '+(o.permissions&&o.permissions.audited||0)+' · denials '+(o.permissions&&o.permissions.denials||0));
}
load();
</script></body></html>"""
    return HTMLResponse(html)


# ── OX-WORKFLOW-ENGINE-1 — Workflow Engine API (REST + WebSocket) ──────────────
# SPRAWL TEST (Genesis Paradigm, 2026-07-10): registry has been empty since the
# engine shipped — zero workflows registered, no UI caller. An unused surface
# that can execute tools is pure attack surface, so it is OFF by default.
# Re-enable with SKYNET_WFE=1 when a real workflow arrives.
def _wf_engine():
    if os.environ.get("SKYNET_WFE") != "1":
        raise RuntimeError("workflow engine disabled (sprawl test) — set SKYNET_WFE=1 to enable")
    import workflow
    eng = workflow.get_engine()
    if eng.tool_executor is None:
        async def _exec(name, args): return await exec_tool(name, args)
        eng.tool_executor = lambda n, a: _exec(n, a)
    return eng


@app.post("/api/wfe/compile")
async def api_wf_compile(req: Request):
    """Compile a workflow (JSON/YAML/dict) → optimized DAG (levels/order/edges)."""
    try:
        body = await req.json()
        g = _wf_engine().compile(body.get("definition", body))
        return {"ok": True, "graph": g.to_dict()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/wfe/run")
async def api_wf_run(req: Request):
    """Execute a workflow through the Runtime Kernel. Body: {definition, inputs}."""
    try:
        body = await req.json()
        res = await _wf_engine().run(body.get("definition", body), inputs=body.get("inputs", {}))
        return {"ok": True, "run": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/wfe/resume")
async def api_wf_resume(req: Request):
    """Resume a paused run. Body: {run_id, approvals, definition?}."""
    try:
        body = await req.json()
        res = await _wf_engine().resume(body["run_id"], approvals=body.get("approvals", {}),
                                        definition=body.get("definition"))
        return {"ok": True, "run": res}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/wfe/rollback")
async def api_wf_rollback(req: Request):
    """Rollback a run to a checkpoint index. Body: {run_id, to}."""
    try:
        body = await req.json()
        return {"ok": True, "result": _wf_engine().rollback(body["run_id"], int(body.get("to", 0)))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/wfe/runs/{run_id}")
async def api_wf_run_status(run_id: str):
    """Run status: checkpoints, metrics, debugger timeline."""
    try:
        return {"ok": True, "status": _wf_engine().status(run_id)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/wfe/runs/{run_id}/artifacts")
async def api_wf_artifacts(run_id: str):
    try:
        return {"ok": True, "artifacts": _wf_engine().artifacts.list(run_id)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/wfe/register")
async def api_wf_register(req: Request):
    """Register a workflow version in the registry. Body: {definition, owner, tags, permissions}."""
    try:
        import workflow
        body = await req.json()
        rec = _wf_engine().registry.register(workflow.parse(body.get("definition", body)),
                                              owner=body.get("owner", ""),
                                              permissions=body.get("permissions", []),
                                              tags=body.get("tags", []))
        return {"ok": True, "registered": rec}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/wfe/registry")
async def api_wf_registry():
    try:
        return {"ok": True, "workflows": _wf_engine().registry.list()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.websocket("/ws/wfe/{run_id}")
async def ws_workflow(websocket, run_id: str):
    """Stream a run's debugger timeline + status live until terminal (Phase 15)."""
    await websocket.accept()
    try:
        eng = _wf_engine()
    except Exception as _we:
        try:
            await websocket.send_json({"event": "WorkflowError", "error": str(_we)})
        finally:
            await websocket.close()
        return
    sent = 0
    try:
        for _ in range(1200):                       # ~bounded live stream
            st = eng.status(run_id)
            tl = st.get("timeline", []) if isinstance(st, dict) else []
            for ev in tl[sent:]:
                await websocket.send_json(ev)
            sent = len(tl)
            state = (st or {}).get("status")
            if state in ("completed", "failed", "cancelled"):
                await websocket.send_json({"event": "WorkflowFinished", "status": state})
                break
            await asyncio.sleep(0.4)
    except Exception:
        pass
    finally:
        try: await websocket.close()
        except Exception: pass


@app.get("/api/house/paradigms")
async def house_paradigms():
    """OX-PARADIGM-1 — dominant theoretical frameworks and their evolution:
    stable paradigms / paradigm shifts / paradigm candidates, synthesized from
    theory / belief revision / calibration / unknowns. Read-only."""
    try:
        import paradigm as _pgm
        st = _pgm.evolve()
        return {"ok": True, "paradigms": st, "metrics": _pgm.metrics(st)}
    except Exception as e:
        return {"ok": False, "error": str(e), "paradigms": {}}


@app.get("/api/house/unknowns")
async def house_unknowns():
    """OX-UNKNOWNS-1 — strategic unknown map: known knowns / known unknowns /
    unknown unknowns, synthesized from curiosity / research agenda / calibration /
    belief revision. Read-only."""
    try:
        import unknowns as _unk
        st = _unk.analyze()
        return {"ok": True, "unknowns": st, "metrics": _unk.metrics(st)}
    except Exception as e:
        return {"ok": False, "error": str(e), "unknowns": {}}


@app.get("/api/house/research-agenda")
async def house_research_agenda():
    """OX-RESEARCH-AGENDA-1 — ranked research priorities (impact x uncertainty x
    leverage) synthesized from theory / experiment / belief drift / calibration.
    Read-only; advisory, no scheduling."""
    try:
        import research_agenda as _ra
        ag = _ra.form()
        return {"ok": True, "agenda": ag, "metrics": _ra.metrics(ag)}
    except Exception as e:
        return {"ok": False, "error": str(e), "agenda": []}


@app.get("/api/house/theories")
async def house_theories():
    """OX-THEORY-1 — theory candidates: patterns that generalize across >=2
    domains (causal + first-principle + decision support). Read-only."""
    try:
        import theory as _thy
        ts = _thy.form()
        return {"ok": True, "theories": ts, "metrics": _thy.metrics(ts)}
    except Exception as e:
        return {"ok": False, "error": str(e), "theories": []}


@app.get("/api/house/experiments")
async def house_experiments():
    """OX-EXPERIMENT-1 — recommended controlled experiments (control vs test
    ordering) to validate confident beliefs. Read-only; never runs them."""
    try:
        import experiment as _exp
        es = _exp.design()
        return {"ok": True, "experiments": es, "metrics": _exp.metrics(es)}
    except Exception as e:
        return {"ok": False, "error": str(e), "experiments": []}


@app.get("/api/house/calibration")
async def house_calibration():
    """OX-CONFIDENCE-1 — confidence calibration: predicted vs observed across
    decisions / beliefs / principles (over/under-confident). Read-only."""
    try:
        import calibration as _cal
        recs = _cal.calibrate()
        return {"ok": True, "records": recs, "metrics": _cal.metrics(recs)}
    except Exception as e:
        return {"ok": False, "error": str(e), "records": []}


@app.get("/api/house/decisions")
async def house_decisions():
    """OX-DECISION-1 — structured recommendations synthesized from First
    Principles + MetaLearning + Belief Revision + Curiosity. Read-only, advisory."""
    try:
        import decision as _dec
        ds = _dec.decide()
        return {"ok": True, "decisions": ds, "metrics": _dec.metrics(ds)}
    except Exception as e:
        return {"ok": False, "error": str(e), "decisions": []}


@app.get("/api/house/principles")
async def house_principles():
    """OX-FIRST-PRINCIPLE-1 — reusable principles cross-validated by >=2 learning
    systems (+ risk principles from belief drift). Read-only; candidates only."""
    try:
        import first_principles as _fp
        ps = _fp.all_principles()
        return {"ok": True, "principles": ps, "metrics": _fp.metrics(ps)}
    except Exception as e:
        return {"ok": False, "error": str(e), "principles": []}


@app.get("/api/house/belief-review")
async def house_belief_review():
    """OX-BELIEF-REVISION-1 — promoted beliefs vs recent evidence: strengths,
    stable, and belief_drift (contradictions). Read-only; no correction."""
    try:
        import belief_revision as _bro
        rev = _bro.review()
        return {"ok": True, "review": rev, "metrics": _bro.metrics(rev)}
    except Exception as e:
        return {"ok": False, "error": str(e), "review": {}}


@app.get("/api/house/curiosity")
async def house_curiosity():
    """OX-CURIOSITY-1 — knowledge blind spots, underexplored sources/domains,
    weak hypotheses/capabilities + known strengths. Read-only; no goals."""
    try:
        import curiosity as _cur
        return {"ok": True, "metrics": _cur.metrics(), "insights": _cur.scan(),
                "strengths": _cur.strengths()}
    except Exception as e:
        return {"ok": False, "error": str(e), "insights": []}


@app.get("/api/house/exploration")
async def house_exploration():
    """OX-EXPLORATION-1 — exploration profiles, discovery metrics, and current
    promotion candidates (alternatives beating the primary). Read-only."""
    try:
        import exploration as _expl
        return {"ok": True, "metrics": _expl.metrics(),
                "profiles": _expl.load_profiles(),
                "promotion_candidates": _expl.detect_improvements()}
    except Exception as e:
        return {"ok": False, "error": str(e), "metrics": {}}


@app.get("/api/house/metalearning")
async def house_metalearning():
    """OX-METALEARNING-1 — learned acquisition strategies (which source order
    works per gap_type) + metrics. Read-only."""
    try:
        import metalearning as _ml
        return {"ok": True, "metrics": _ml.metrics(), "strategies": _ml.load_strategies()}
    except Exception as e:
        return {"ok": False, "error": str(e), "strategies": {}}


@app.get("/api/house/acquisition")
async def house_acquisition(limit: int = 50):
    """OX-ACQUISITION-1 — knowledge acquisition ledger + metrics (read-only):
    attempt rate, success rate, gap types, top successful sources."""
    try:
        import acquisition as _acq
        return {"ok": True, "metrics": _acq.metrics(),
                "recent": _acq.load_records()[-max(1, int(limit)):]}
    except Exception as e:
        return {"ok": False, "error": str(e), "metrics": {}}


@app.get("/api/house/compliance")
async def house_compliance(limit: int = 50):
    """OX-COMPLIANCE-1 — did recalled capabilities actually shape execution?
    Read-only: per-mission compliance (FOLLOWED/PARTIAL/IGNORED), aggregate
    metrics, and per-capability heeded-vs-ignored breakdown."""
    try:
        import compliance as _compl
        return {"ok": True, "metrics": _compl.metrics(),
                "per_capability": _compl.per_capability(),
                "recent": _compl.load_records()[-max(1, int(limit)):]}
    except Exception as e:
        return {"ok": False, "error": str(e), "metrics": {}}


@app.get("/api/house/workflows")
async def house_workflows(limit: int = 50):
    """OX-WORKFLOW-1 — durable dispatch lifecycle ledger + metrics. Read-only.
    Every dispatch appears here (created→...→terminal), correlated to its
    house_state mission and agent_run execution."""
    try:
        import workflow_runs as _wf
        db = _wf.WorkflowRunsDB()
        return {"ok": True, "metrics": db.metrics(), "recent": db.recent(limit=limit)}
    except Exception as e:
        return {"ok": False, "error": str(e), "metrics": {}, "recent": []}


@app.get("/api/house/reinforcement")
async def house_reinforcement():
    """OX-REINFORCEMENT-1 — adaptive capability weights: which capabilities deserve
    trust, which to avoid, and how future recall is biased. Read-only over
    capability_weights.json."""
    try:
        import reinforcement as _reinf
        w = _reinf.load()
        return {"ok": True, "weights": w, "status": _reinf.status(w), "summary": _reinf.summary(w)}
    except Exception as e:
        return {"ok": False, "error": str(e), "weights": {}}


@app.get("/api/house/asset")
async def house_asset(directive: str = "", files: str = ""):
    """H4 — recommend the asset this knowledge should become (+ delivery check)."""
    try:
        import knowledge_asset as _ka
        ft = [f for f in (files or "").split(",") if f.strip()]
        rec = _ka.recommend(directive, ft)
        return {"ok": True, "asset": rec, "delivered": _ka.is_delivered(rec, ft)}
    except Exception as e:
        return {"ok": False, "error": str(e), "asset": {}}


def _run_sequence(run_id: str) -> list:
    """Read a run's trajectory.jsonl → ordered tool-call names."""
    try:
        row = _AGENT_RUNS_DB.get(run_id) or {}
        p = Path(row.get("trajectory_path") or "")
        if not p.exists():
            return []
        seq = []
        with p.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    e = json.loads(ln)
                except Exception:
                    continue
                if (e.get("event") in ("tool_call", "tool") or e.get("type") in ("tool_call", "tool")) and e.get("name"):
                    seq.append(str(e["name"]))
        return seq
    except Exception:
        return []


@app.get("/api/house/skills/candidates")
async def house_skill_candidates(limit: int = 40):
    """H5 — candidate skills mined from recurring SUCCESSFUL tool-chains in the
    execution ledger. Evidence-backed; promotion to a real skill is human-gated."""
    try:
        import skill_evolution as _se
        rows = _AGENT_RUNS_DB.recent(limit=max(5, min(int(limit), 200))) or []
        runs = [{"id": r.get("id"), "status": r.get("status"), "ended_at": r.get("ended_at"),
                 "sequence": _run_sequence(r.get("id", ""))} for r in rows]
        cands = _se.mine(runs)
        return {"ok": True, "candidates": cands, "runs_scanned": len(runs)}
    except Exception as e:
        return {"ok": False, "error": str(e), "candidates": []}


@app.post("/api/house/artifact")
async def house_build_artifact(req: dict):
    """H6 — physically build the artifact for a mission's current knowledge and
    return the verified path. Body: {state_id?, asset_type?, out_dir?}."""
    try:
        import knowledge_asset as _ka, knowledge_frontier as _kf, artifact_factory as _af
        sid = (req or {}).get("state_id") or ""
        st = _house_state.read_state(sid) if sid else _house_state.current()
        if not st:
            return {"ok": False, "error": "no mission state to build from"}
        ans = _house_state.answer(st["id"]) or {}
        asset = (req or {}).get("asset_type") or _ka.recommend(ans.get("question", "")).get("asset_type", "Markdown Note")
        know = _af.assemble_knowledge(ans, metrics=(_kf.frontier(st["id"]) or {}).get("metrics", {}))
        out = (req or {}).get("out_dir") or str(Path(__file__).parent / "artifacts")
        art = _af.build(asset, know, out, base_name=ans.get("question", "mission"))
        return {"ok": art.get("exists", False), "artifact": art}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/house/dynamics")
async def house_dynamics():
    """System dynamics — stocks, flows, feedback loops, bottleneck, debts."""
    try:
        import knowledge_frontier as _kf, cognitive_dynamics as _cd, skill_evolution as _se
        fr = _kf.frontier()
        try:
            import learning_engine as _le
            lstats = _le.snapshot().get("stats", {})
        except Exception:
            lstats = {}
        rstats = {}
        try:
            rstats = _AGENT_RUNS_DB.stats(since_seconds=7 * 86400) or {}
        except Exception:
            pass
        # capability = registered skills; capability_debt = mined-but-unpromoted candidates
        try:
            cap = len((await skills_list()).get("skills", []))
        except Exception:
            cap = 0
        try:
            rows = _AGENT_RUNS_DB.recent(limit=40) or []
            runs = [{"id": r.get("id"), "status": r.get("status"), "ended_at": r.get("ended_at"),
                     "sequence": _run_sequence(r.get("id", ""))} for r in rows]
            cap_debt = len(_se.mine(runs))
        except Exception:
            cap_debt = 0
        m = _cd.model(frontier_metrics=fr.get("metrics", {}), learning_stats=lstats,
                      run_stats=rstats, capability=cap, capability_debt=cap_debt)
        return {"ok": True, "dynamics": m}
    except Exception as e:
        return {"ok": False, "error": str(e), "dynamics": {}}


# ── OX-UI-1: WORKFLOW MEMORY (read-model over agent_runs) ────────────────────
@app.get("/api/house/workflow")
async def house_workflow(limit: int = 6):
    """Operator-facing Workflow Memory — historical EXECUTION artifacts
    (TASK AS / DONE_WHEN / status / outcome) shaped from the agent_runs ledger.
    Constitutional separation: these are NOT cognitive state and must never
    appear in House Mind. Machine footers are stripped; status is translated."""
    try:
        import workflow_memory as _wfm
        rows = _AGENT_RUNS_DB.recent(limit=max(1, min(int(limit) * 3, 60)))
        return {"ok": True, "workflow": _wfm.recent(rows, limit=int(limit))}
    except Exception as e:
        return {"ok": False, "error": str(e), "workflow": []}


# ── OPENCLAW PORT T2: agent_runs DB endpoints ────────────────────────────────
@app.get("/api/agent/runs")
async def list_agent_runs(limit: int = 50, status: str = ""):
    """Recent agent_run history. Optional ?status=TASK_COMPLETE | limit | error."""
    return {
        "runs": _AGENT_RUNS_DB.recent(limit=limit, status=status or None),
        "stats_24h": _AGENT_RUNS_DB.stats(since_seconds=86400),
    }

@app.get("/api/agent/runs/{run_id}")
async def get_agent_run(run_id: str):
    row = _AGENT_RUNS_DB.get(run_id)
    if not row:
        raise HTTPException(404, f"run not found: {run_id}")
    return row

@app.get("/api/agent/runs/{run_id}/trajectory")
async def get_run_trajectory(run_id: str, limit: int = 500):
    """Read the trajectory.jsonl file for a run."""
    row = _AGENT_RUNS_DB.get(run_id)
    if not row:
        raise HTTPException(404, f"run not found: {run_id}")
    p = Path(row.get("trajectory_path") or "")
    if not p.exists():
        return {"events": [], "note": "trajectory file not found", "path": str(p)}
    try:
        events = []
        with p.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try: events.append(json.loads(ln))
                    except Exception: pass
                if len(events) >= limit:
                    break
        return {"events": events, "path": str(p), "count": len(events)}
    except Exception as e:
        raise HTTPException(500, f"read trajectory failed: {e}")

@app.get("/api/agent/model-costs")
async def get_model_costs():
    """List all known model cost data + which is cheapest among all models."""
    all_costs = _COST_OVERLAY.list_all()
    cheapest = _COST_OVERLAY.cheapest(list(all_costs.keys()), prefer_local=True)
    return {"costs": all_costs, "cheapest_local_first": cheapest}

# ── OPENCLAW PORT: Self-awareness ─────────────────────────────────────────────
@app.get("/api/self")
async def get_self_state(refresh: bool = False):
    """
    Current SkynetClaw self-awareness snapshot:
      - capabilities (tools, integrations, skills, models, modules)
      - Obsidian vault summary (notes, topics, recent)
      - constraints (what we CAN'T do)
      - genome state (rules, paths, failures)
      - recent agent_runs

    Set ?refresh=true to regenerate SELF.md before returning.
    """
    try:
        from self_awareness import build_self_state, write_self_state, SELF_PATH
    except Exception as e:
        raise HTTPException(500, f"self_awareness module not loaded: {e}")
    if refresh:
        try:
            write_self_state(app=app)
        except Exception as e:
            print(f"[/api/self] refresh failed: {e}")
    state = build_self_state(app=app)
    state["self_md_path"] = str(SELF_PATH)
    state["self_md_exists"] = SELF_PATH.exists()
    if SELF_PATH.exists():
        try:
            state["self_md_size_bytes"] = SELF_PATH.stat().st_size
        except Exception:
            state["self_md_size_bytes"] = 0
    return state

@app.get("/api/self/markdown")
async def get_self_markdown():
    """Return the raw SELF.md text (for the dashboard / agent prompt preview)."""
    try:
        from self_awareness import SELF_PATH
    except Exception:
        raise HTTPException(500, "self_awareness not loaded")
    if not SELF_PATH.exists():
        raise HTTPException(404, "SELF.md not yet generated — restart backend or POST /api/self/refresh")
    try:
        return {"path": str(SELF_PATH),
                "content": SELF_PATH.read_text(encoding="utf-8"),
                "size_bytes": SELF_PATH.stat().st_size}
    except Exception as e:
        raise HTTPException(500, f"read SELF.md failed: {e}")

@app.post("/api/self/refresh")
async def refresh_self_state():
    """Force regenerate SELF.md (e.g. after adding a new integration)."""
    try:
        from self_awareness import write_self_state
        path = write_self_state(app=app)
        return {"ok": True, "path": str(path),
                "size_bytes": path.stat().st_size if path.exists() else 0}
    except Exception as e:
        raise HTTPException(500, f"refresh failed: {e}")

# ── OPENCLAW PORT: Volition Engine inspector ──────────────────────────────────
class _VolitionInspectReq(BaseModel):
    text: str

@app.post("/api/volition")
async def inspect_volition(req: _VolitionInspectReq):
    """
    Programmatic L1 Volition extraction over arbitrary text.
    Returns drive / tone / urgency / gap detection.
    """
    try:
        from volition_engine import extract, format_volition_directive
    except Exception as e:
        raise HTTPException(500, f"volition_engine not loaded: {e}")
    v = extract(req.text or "")
    return {"result": v.to_dict(), "directive_preview": format_volition_directive(v)}

# ── METACOGNITION endpoints ─────────────────────────────────────────────────
class _CritiqueReq(BaseModel):
    text: str

@app.get("/api/meta/reflect/{run_id}")
async def meta_reflect(run_id: str):
    """Reflect on one agent_run — what worked, what failed, hypotheses, suggestions."""
    if not _META_LAYER:
        raise HTTPException(500, "metacognition module not loaded")
    return _meta_cog.reflect_on_run(run_id)

@app.get("/api/meta/recurring")
async def meta_recurring(window_hours: int = 72, min_recurrence: int = 2):
    """Cross-run failure pattern analysis."""
    if not _META_LAYER:
        raise HTTPException(500, "metacognition module not loaded")
    return _meta_cog.find_recurring_failures(window_hours=window_hours,
                                              min_recurrence=min_recurrence)

@app.get("/api/meta/proposals")
async def meta_proposals(window_hours: int = 168):
    """Synthesized self-improvement proposals based on recent failures + Genome."""
    if not _META_LAYER:
        raise HTTPException(500, "metacognition module not loaded")
    return _meta_cog.propose_self_improvements(window_hours=window_hours)

@app.post("/api/meta/critique")
async def meta_critique_text(req: _CritiqueReq):
    """Apply SkynetClaw's non-negotiables to arbitrary text. Returns issues + score."""
    if not _META_LAYER:
        raise HTTPException(500, "metacognition module not loaded")
    return _meta_cog.meta_critique(req.text or "")

# ── SELF-DEBUG endpoints (code introspection + patch proposals) ─────────────
@app.get("/api/debug/modules")
async def debug_modules():
    """Inventory of own backend modules (size, lines, last modified)."""
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.list_modules()

@app.get("/api/debug/module/{name}")
async def debug_read_module(name: str, max_chars: int = 100000):
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.read_module(name, max_chars=max_chars)

class _GrepReq(BaseModel):
    pattern: str
    context: int = 1

@app.post("/api/debug/grep/{name}")
async def debug_grep(name: str, req: _GrepReq):
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.grep_module(name, req.pattern, context=req.context)

@app.post("/api/debug/run-self-test/{name}")
async def debug_run_self_test(name: str, timeout_sec: int = 20):
    """Execute a module's __main__ self-test. Refuses for main.py (would start server)."""
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.run_module_self_test(name, timeout_sec=timeout_sec)

@app.post("/api/debug/run-all-tests")
async def debug_run_all_tests(timeout_each: int = 15):
    """Run self-tests on all modules. Returns pass/fail summary."""
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.run_all_self_tests(timeout_each=timeout_each)

@app.get("/api/debug/recent-errors")
async def debug_recent_errors(window_hours: int = 24):
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.analyze_recent_errors(window_hours=window_hours)

class _PatchProposeReq(BaseModel):
    target_file: str
    issue: str
    suggested_change: str
    rationale: str = ""
    priority: str = "MEDIUM"

@app.post("/api/debug/propose-patch")
async def debug_propose_patch(req: _PatchProposeReq):
    """Generate a patch proposal file under self_patches/ — does NOT auto-apply."""
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.propose_patch(
        target_file=req.target_file, issue=req.issue,
        suggested_change=req.suggested_change, rationale=req.rationale,
        priority=req.priority,
    )

@app.get("/api/debug/patches")
async def debug_list_patches():
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return {"patches": _self_dbg.list_proposed_patches()}

@app.post("/api/debug/patches/{patch_id}/validate")
async def debug_validate_patch(patch_id: str):
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.validate_patch_syntax(patch_id)

class _ApplyPatchReq(BaseModel):
    dry_run: bool = True

@app.post("/api/debug/patches/{patch_id}/apply")
async def debug_apply_patch(patch_id: str, req: _ApplyPatchReq):
    """Append patch as comment block to target file. dry_run=True by default."""
    if not _META_LAYER:
        raise HTTPException(500, "self_debug module not loaded")
    return _self_dbg.apply_patch(patch_id, dry_run=req.dry_run)

# ── FIRST PRINCIPLE CODEX endpoints ─────────────────────────────────────────
class _DeconstructReq(BaseModel):
    phenomenon: str

@app.post("/api/codex/deconstruct")
async def codex_deconstruct(req: _DeconstructReq):
    """Full Genesis Mind frame: axioms + Kalama10 + Ariya4 + measurable proxies."""
    if not _META_LAYER:
        raise HTTPException(500, "codex module not loaded")
    return _fp_codex.deconstruct(req.phenomenon or "")

@app.get("/api/codex/axioms")
async def codex_axioms():
    if not _META_LAYER:
        raise HTTPException(500, "codex module not loaded")
    return {"axioms": _fp_codex.list_axioms(), "kalama10": _fp_codex.kalama10()}

@app.post("/api/codex/ariya4")
async def codex_ariya4(req: _DeconstructReq):
    """Buddhist Four Noble Truths as universal problem framework."""
    if not _META_LAYER:
        raise HTTPException(500, "codex module not loaded")
    return _fp_codex.ariya4_problem_frame(req.phenomenon or "")

class _ClaimsReq(BaseModel):
    text: str

@app.post("/api/codex/classify-claims")
async def codex_classify_claims(req: _ClaimsReq):
    """Split text into hard/soft/neutral claims for evidence audit."""
    if not _META_LAYER:
        raise HTTPException(500, "codex module not loaded")
    return _fp_codex.claim_classifier(req.text or "")

# ──────────────────────────────────────────────────────────────────────────────
# AGENTIC WORKFLOW — 4-phase comprehension-first orchestrator
# Turns agent_run from "tool labor" into "understood execution".
# ──────────────────────────────────────────────────────────────────────────────
class _WorkflowReq(BaseModel):
    task: str
    model: Optional[str] = None
    workspace_folder: Optional[str] = ""

class _ReflectReq(BaseModel):
    task: str
    comprehension: Dict[str, Any]
    plan: Dict[str, Any]
    trajectory: Dict[str, Any]
    model: Optional[str] = None

@app.post("/api/workflow/comprehend")
async def workflow_comprehend(req: _WorkflowReq):
    """Phase 1: Comprehend task → restate + assumptions + gaps + success criteria."""
    if not _WORKFLOW_AVAILABLE:
        raise HTTPException(500, "agentic_workflow module not loaded")
    model = _mp_resolve_model(req.model, req.task) or req.model or get_active_model()
    if not model:
        raise HTTPException(400, "No model — set active connection or pass model in request")
    base = get_active_base_url(); key = get_active_api_key()
    comp = await _workflow.comprehend(req.task or "", model=model,
                                       base_url=base, api_key=key)
    return {"phase": "comprehend", "model": model, "result": comp.to_dict()}

@app.post("/api/workflow/plan")
async def workflow_plan(req: _WorkflowReq):
    """Phase 2: After comprehension, build structured plan with steps + checkpoints + risks."""
    if not _WORKFLOW_AVAILABLE:
        raise HTTPException(500, "agentic_workflow module not loaded")
    model = _mp_resolve_model(req.model, req.task) or req.model or get_active_model()
    if not model:
        raise HTTPException(400, "No model")
    base = get_active_base_url(); key = get_active_api_key()
    # Run comprehension if not provided
    comp = await _workflow.comprehend(req.task or "", model=model,
                                       base_url=base, api_key=key)
    plan = await _workflow.build_plan(req.task or "", comp, model=model,
                                       base_url=base, api_key=key)
    return {
        "phase": "plan", "model": model,
        "comprehension": comp.to_dict(),
        "plan": plan.to_dict(),
        "agent_system_message": _workflow.format_plan_for_agent(comp, plan),
    }

@app.post("/api/workflow/reflect")
async def workflow_reflect(req: _ReflectReq):
    """Phase 4: Reflect on a completed run — lessons + Genome proposals."""
    if not _WORKFLOW_AVAILABLE:
        raise HTTPException(500, "agentic_workflow module not loaded")
    model = _mp_resolve_model(req.model, req.task) or req.model or get_active_model()
    if not model:
        raise HTTPException(400, "No model")
    base = get_active_base_url(); key = get_active_api_key()
    # Rebuild dataclasses from raw dicts
    try:
        comp_obj = _workflow.Comprehension(
            restated=req.comprehension.get("restated", ""),
            intent=req.comprehension.get("intent", ""),
            assumptions=req.comprehension.get("assumptions", []),
            gaps=req.comprehension.get("gaps", []),
            success_criteria=req.comprehension.get("success_criteria", []),
            estimated_complexity=req.comprehension.get("estimated_complexity", "moderate"),
        )
        steps_in = req.plan.get("steps", [])
        steps = [_workflow.PlanStep(n=int(s.get("n", i+1)),
                                      action=s.get("action", ""),
                                      tool_hint=s.get("tool_hint", ""),
                                      success_signal=s.get("success_signal", ""))
                 for i, s in enumerate(steps_in) if isinstance(s, dict)]
        plan_obj = _workflow.Plan(
            steps=steps,
            checkpoints=req.plan.get("checkpoints", []),
            risks=req.plan.get("risks", []),
            rollback_plan=req.plan.get("rollback_plan", ""),
            estimated_steps=int(req.plan.get("estimated_steps", len(steps))),
        )
    except Exception as e:
        raise HTTPException(400, f"could not parse comprehension/plan: {e}")
    refl = await _workflow.reflect(req.task or "", comp_obj, plan_obj,
                                    req.trajectory or {}, model=model,
                                    base_url=base, api_key=key)
    return {"phase": "reflect", "model": model, "result": refl.to_dict()}

# OX-EXEC-4: per-mission planning-cycle counter (in-memory; bounds the loop).
_WORKFLOW_PLAN_CYCLES: Dict[str, int] = {}


async def _runtime_alive(base_url: str, api_key: str = "", timeout: float = 6.0):
    """Cheap liveness probe of the active model runtime — a metadata GET (no
    inference). Distinguishes 'up & responsive' from 'hung/dead'. Returns
    (alive: bool, reason: str). Used to FAIL FAST instead of letting a hung
    runtime block every phase's model call for its full 90-180s timeout (which
    is what makes a re-dispatch look like it 'ค้าง ไม่เริ่ม')."""
    _b = (base_url or "").rstrip("/")
    is_openai = _b.endswith("/v1") or "/v1/" in _b
    url = (_b + "/models") if is_openai else (_b + "/api/tags")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=timeout, write=3.0, pool=3.0)
        ) as c:
            r = await c.get(url, headers=headers)
        if r.status_code < 500:
            return True, ""
        return False, f"health HTTP {r.status_code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"


@app.post("/api/agent/run_big")
async def agent_run_big(req: BigTaskReq):
    """Context-handoff executor for tasks larger than the model window.

    Runs the normal agent (/api/agent/run) in bounded ROUNDS, carrying an
    EPHEMERAL TaskMemory (objective + accumulated findings) forward between
    rounds so a task needing far more processing than one context can hold
    (e.g. 60k of work on a 15k window) completes across several rounds instead
    of halting at the step limit. The working memory lives only for this request
    and is discarded when it returns; durable state (files, mission ledger) is
    already carried by the shared workspace.
    """
    import task_continuation as _tc
    _self = "http://127.0.0.1:8766"
    _rounds = max(1, min(int(req.max_rounds or 5), 12))

    async def gen():
        mem = _tc.TaskMemory(req.task)
        yield f"data: {json.dumps({'type':'continued_start','objective':(req.task or '')[:200],'max_rounds':_rounds}, ensure_ascii=False)}\n\n"
        final_done = False
        for rnd in range(1, _rounds + 1):
            round_task = req.task if rnd == 1 else mem.seed_task(req.task)
            payload = {"task": round_task, "model": req.model,
                       "workspace_folder": req.workspace_folder, "directive": req.task}
            if req.max_steps_per_round:
                payload["max_steps"] = req.max_steps_per_round
            yield f"data: {json.dumps({'type':'continued_round_start','round':rnd,'max_rounds':_rounds})}\n\n"
            _text: List[str] = []; _tools = 0; _summary = ""; _status = "LIMIT"
            try:
                async with httpx.AsyncClient(timeout=None) as cx:
                    async with cx.stream("POST", _self + "/api/agent/run", json=payload) as r:
                        async for line in r.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            try: ev = json.loads(line[6:])
                            except Exception: continue
                            t = ev.get("type")
                            # forward inner progress so the UI shows live activity
                            if t in ("agent_step", "agent_tool_call", "text",
                                     "agent_think", "agent_stuck", "agent_blocked"):
                                yield line + "\n\n"
                            if t == "text":
                                _tx = ev.get("text", "")
                                # skip non-substantive UI noise (skill-activation
                                # banners) so the working memory holds real
                                # findings, not decoration.
                                if _tx and not _tx.lstrip().startswith(("🎯", "🔧 Auto")):
                                    _text.append(_tx)
                            elif t == "agent_tool_call": _tools += 1
                            elif t == "agent_complete":
                                if ev.get("summary"): _summary = ev["summary"]
                            elif t == "done":
                                _status = ev.get("final_status", "LIMIT")
            except Exception as e:
                yield f"data: {json.dumps({'type':'continued_error','round':rnd,'error':str(e)[:200]}, ensure_ascii=False)}\n\n"
                break
            mem.absorb(_summary or ("".join(_text).strip()[-1500:]), _tools)
            yield f"data: {json.dumps({'type':'continued_round_end','round':rnd,'status':_status,'tools':_tools,'findings':len(mem.findings)}, ensure_ascii=False)}\n\n"
            if _status == "SUCCESS":
                final_done = True; break
            if not _tc.should_continue(_status, _tools, bool(_summary)):
                yield f"data: {json.dumps({'type':'continued_stopped','round':rnd,'reason':'no progress / dead-end ('+_status+')'}, ensure_ascii=False)}\n\n"
                break
        mem.done = final_done
        yield f"data: {json.dumps({'type':'continued_complete','done':final_done,'rounds':mem.round,'tools_total':mem.tools_total,'result':mem.render()}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type':'done','final_status':('SUCCESS' if final_done else 'LIMIT')})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


class PlanExecReq(BaseModel):
    task: str
    workspace_folder: Optional[str] = ""
    model: Optional[str] = None
    filename: Optional[str] = None


@app.post("/api/agent/plan_execute")
async def agent_plan_execute(req: PlanExecReq):
    """Vol IV Planning bridge: decompose a build task into ordered sections, build
    the single-file artifact across budgeted rounds (refining the WHOLE file each
    round), then WRITE it deterministically (the planner saves the file — the model
    is never trusted to call write_file). Fixes the reproduced 'model streamed the
    dashboard but never saved it, then halted' failure."""
    base = get_active_base_url(); key = get_active_api_key()
    model = req.model or get_active_model() or ""
    _api_type = None; _ec = None
    try:
        _en = (load_settings().get("exec_connection") or "").strip()
        _ec = get_conn_by_name(_en) if _en else None
        if _ec:
            base = (_ec.get("base_url") or base).rstrip("/"); key = _ec.get("api_key") or ""
            _api_type = _ec.get("api_type") or "ollama"
        else:
            _api_type = get_active_conn().get("api_type")
        _em = (load_settings().get("exec_model") or "").strip()
        if _em: model = _em
    except Exception:
        pass
    try:
        import context_budget as _cbw
        _ctx = _cbw.resolve_window(_ec or get_active_conn(), _api_type, model, base)
    except Exception:
        _ctx = 16384
    ws = (req.workspace_folder or "").strip()
    if ws:
        try:
            Path(ws).mkdir(parents=True, exist_ok=True); ws = str(Path(ws).resolve())
        except Exception:
            ws = ""

    async def call_llm(messages):
        payload = {"model": model, "messages": _fit_context(messages, _ctx), "stream": True,
                   "keep_alive": "30m", "options": {"num_ctx": _ctx, "temperature": 0.2}}
        parts = []
        async for raw in _llm_stream(payload, base, key, api_type=_api_type):
            try: ev = json.loads(raw)
            except Exception: continue
            if ev.get("type") == "text":
                parts.append(ev.get("text", ""))
        return "".join(parts)

    import task_planner as _tp

    async def gen():
        yield f"data: {json.dumps({'type':'plan_start','task':(req.task or '')[:200],'window':_ctx}, ensure_ascii=False)}\n\n"
        result = None
        try:
            async for ev in _tp.plan_and_execute(req.task, ws or None, call_llm, filename=req.filename):
                if ev.get("type") == "plan_complete":
                    result = ev
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if result:
                try: house_sync.publish("plan_complete", {"ok": result.get("ok"), "file": result.get("file"),
                                                           "steps": result.get("steps"), "chars": result.get("chars")}, source="planner")
                except Exception: pass
        except Exception as e:
            yield f"data: {json.dumps({'type':'plan_error','error':str(e)[:200]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type':'done','final_status':('SUCCESS' if (result or {}).get('ok') else 'LIMIT')}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


class _WorkflowRunReq(BaseModel):
    task: str
    model: Optional[str] = None
    workspace_folder: Optional[str] = ""
    enable_council: bool = True       # L5 six specialists if complexity allows
    enable_reflect: bool = True       # Phase 4 auto-reflect after execute
    auto_apply_genome: bool = True    # Apply reflect.genome_proposals (conf > 0.7)
    max_steps: Optional[int] = None   # Auto-sized from plan.estimated_steps if None


@app.post("/api/workflow/run")
async def workflow_run(req: _WorkflowRunReq):
    """
    Full 4-phase Genesis Mind workflow — INLINE SERVER-SIDE.

    Pipeline (per Genesis Mind blueprint + Skynet L5):
      1. COMPREHEND   — extract intent + assumptions + gaps + success criteria
      2. PLAN         — structured steps + checkpoints + risks + rollback
      3. COUNCIL      — L5 six specialists (if complex)              [optional]
      4. EXECUTE      — inline call into agent_run logic via HTTP self-call
      5. REFLECT      — lessons + Genome proposals                   [optional]
      6. APPLY GENOME — write high-confidence rules to atlas_genome  [optional]

    Stream events:
      workflow_start
      workflow_phase_start (phase=comprehend|plan|council|execute|reflect)
      workflow_phase (with result dict)
      agent_* (forwarded from inline agent_run during phase=execute)
      workflow_genome (genome apply summary)
      done
    """
    if not _WORKFLOW_AVAILABLE:
        raise HTTPException(500, "agentic_workflow module not loaded")
    model = _mp_resolve_model(req.model, req.task) or req.model or get_active_model()
    if not model:
        raise HTTPException(400, "No model — set active connection or pass model")
    base = get_active_base_url(); key = get_active_api_key()

    async def gen():
        comp = None; plan = None; council_verdict = None; agent_trajectory = {}
        run_id = ""
        # ── OX-EXEC-4 PLAN LOOP PREVENTION ── track how many times THIS mission
        # has entered planning. Max one planning cycle; on re-entry the Commander
        # forces a terminal choice (EXECUTE/ABORT) — no third plan.
        try:
            import mission_identity as _mid
            _mkey = _mid.clean_identity(req.task or "")[:160]
        except Exception:
            _mkey = (req.task or "")[:160]
        _plan_cycles = _WORKFLOW_PLAN_CYCLES.get(_mkey, 0)
        _WORKFLOW_PLAN_CYCLES[_mkey] = _plan_cycles + 1
        try:
            yield f"data: {json.dumps({'type':'workflow_start','task_preview':(req.task or '')[:200],'model':model,'plan_cycle':_plan_cycles+1})}\n\n"

            # ── PRE-FLIGHT LIVENESS ── a hung/dead runtime would otherwise block
            # comprehend → plan → execute each for its full timeout (minutes of
            # apparent hang) before the mission finally halts. Probe the runtime's
            # cheap metadata endpoint first and fail fast with an actionable error.
            _alive, _why = await _runtime_alive(base, key, timeout=6.0)
            if not _alive:
                yield f"data: {json.dumps({'type':'commander','verdict':'ABORT','text':'⛔ ELITE COMMANDER: model runtime unreachable — ' + _why + ' · mission not started'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'agent_stuck','reason':'runtime_unreachable','text':'Model runtime did not answer a health check ('+_why+'). Restart the runtime (execution :8080 / Ollama :11434) or switch the active connection, then dispatch again.'}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type':'done'})}\n\n"
                return

            # ── PHASE 1: COMPREHEND ────────────────────────────────────────
            yield f"data: {json.dumps({'type':'workflow_phase_start','phase':'comprehend'})}\n\n"
            comp = await _workflow.comprehend(req.task or "", model=model,
                                                base_url=base, api_key=key)
            yield f"data: {json.dumps({'type':'workflow_phase','phase':'comprehend','result':comp.to_dict()}, ensure_ascii=False)}\n\n"

            # ── PHASE 2: PLAN ──────────────────────────────────────────────
            yield f"data: {json.dumps({'type':'workflow_phase_start','phase':'plan'})}\n\n"
            plan = await _workflow.build_plan(req.task or "", comp, model=model,
                                                base_url=base, api_key=key)
            yield f"data: {json.dumps({'type':'workflow_phase','phase':'plan','result':plan.to_dict()}, ensure_ascii=False)}\n\n"

            # ── PHASE 2.5: COUNCIL (only if enabled + complex enough) ──────
            if req.enable_council and _COUNCIL_AVAILABLE and \
               comp.estimated_complexity in ("complex", "ambiguous"):
                yield f"data: {json.dumps({'type':'workflow_phase_start','phase':'council'})}\n\n"
                # ── Council Wiretap (Phase 2A): publish each member's live state
                # to the central Event Bus so any UI can watch deliberation form.
                def _council_on_event(evt):
                    try:
                        _payload = {"agent": evt.get("agent", ""),
                                    "message": evt.get("message", ""),
                                    "ts_iso": evt.get("timestamp", "")}
                        # Phase 2B: carry verbatim-reasoning provenance through the bus
                        if evt.get("source_field"):
                            _payload["source_field"] = evt["source_field"]
                        house_sync.publish(
                            evt.get("type", "agent_event"), _payload, source="council",
                        )
                    except Exception:
                        pass
                council_verdict = await _council.run_council(
                    req.task or "",
                    context={"comprehension": comp.to_dict(), "plan": plan.to_dict()},
                    model=model, base_url=base, api_key=key,
                    on_event=_council_on_event,
                )
                yield f"data: {json.dumps({'type':'workflow_phase','phase':'council','result':council_verdict.to_dict()}, ensure_ascii=False)}\n\n"
                # ── House Mind V2 (Phase 3C): the council just folded its verdict
                # into house_state. Diff the cognitive state and emit house_*
                # change events (known/unknown/hypothesis/belief/confidence/next).
                try:
                    import house_cognition as _hcog
                    _hcog.diff_and_emit(house_sync.publish)
                    # OX-1.7 COGNITIVE HOUSE MIND — emit the reframed cognitive
                    # state (Question/Belief/Conflict/Risk/Next) on change.
                    _hcog.frame_diff_and_emit(house_sync.publish)
                    # H3 KNOWLEDGE FRONTIER — emit the uncertainty map on change.
                    try:
                        import knowledge_frontier as _kf
                        _kf.diff_and_emit(house_sync.publish)
                    except Exception as _kfe:
                        print(f"[KnowledgeFrontier] emit skipped: {_kfe}")
                except Exception as _hce:
                    print(f"[HouseMindV2] diff_and_emit skipped: {_hce}")
                # Phase 4: project the belief-evolution timeline + emit timeline_* deltas
                try:
                    import belief_timeline as _btl
                    _btl.diff_and_emit(house_sync.publish)
                except Exception as _bte:
                    print(f"[BeliefTimeline] diff_and_emit skipped: {_bte}")
                # Phase 5: refresh the Mission Command Center view + emit mission_* deltas
                try:
                    import mission_command as _mcc
                    _mcc.diff_and_emit(house_sync.publish)
                except Exception as _mce:
                    print(f"[MissionCC] diff_and_emit skipped: {_mce}")
            # ── OX-EXEC-1/7 ELITE COMMANDER AUTHORITY ──────────────────────
            # Council ADVISES; only the Commander DECIDES. A Skeptic REBUILD is
            # ADVICE, not a veto — it no longer halts execution. Only EVIDENCE
            # (a real contradiction / hard gate) on a HIGH-risk action may HOLD.
            try:
                import execution_policy as _ep, commander as _cmd
                _pol = _ep.classify(req.task or "")
                _cv = council_verdict.to_dict() if (council_verdict is not None and hasattr(council_verdict, "to_dict")) else None
                # evidence-based block only: a verified contradiction recorded in
                # house_state (not mere logical doubt) on a high-risk action.
                _evidence_block = False
                try:
                    if _pol["risk"] == "high" and _cv:
                        _evidence_block = bool((_cv.get("skeptic") or {}).get("evidence"))
                except Exception:
                    _evidence_block = False
                _verdict = _cmd.decide(_pol, council_verdict=_cv, plan_cycles=_plan_cycles,
                                       evidence_block=_evidence_block)
                yield f"data: {json.dumps({'type':'commander','verdict':_verdict['verdict'],'text':_cmd.render(_verdict),'overrode_council':_verdict.get('overrode_council',False)}, ensure_ascii=False)}\n\n"
                if _verdict["verdict"] == _cmd.HOLD:
                    yield f"data: {json.dumps({'type':'workflow_hold','reason':_verdict['reason']}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type':'done'})}\n\n"
                    return
                if _verdict["verdict"] == _cmd.ABORT:
                    yield f"data: {json.dumps({'type':'workflow_abort','reason':_verdict['reason']}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type':'done'})}\n\n"
                    return
                # EXECUTE_NOW → fall through to PHASE 3
            except Exception as _cme:
                print(f"[Commander] decision skipped (execution primacy → proceed): {_cme}")

            # ── PHASE 3: EXECUTE (inline via HTTP self-call to /api/agent/run) ─
            yield f"data: {json.dumps({'type':'workflow_phase_start','phase':'execute'})}\n\n"

            # Compose system_prefix from comprehension + plan + optional council
            sys_prefix = _workflow.format_plan_for_agent(comp, plan)
            if council_verdict is not None:
                sys_prefix += "\n\n" + _council.format_council_for_agent(council_verdict)

            # Inject prefix into task so existing agent_run picks it up via
            # GENESIS_AGENT_PROMPT context. agent_run prepends GENESIS_AGENT_PROMPT
            # already; we add this on top of the user task itself.
            augmented_task = (
                f"{sys_prefix}\n\n"
                "═══════════════════════════════════════════════\n"
                "USER REQUEST:\n"
                "═══════════════════════════════════════════════\n"
                f"{req.task}"
            )
            max_steps_resolved = (req.max_steps if req.max_steps
                                   else min(max(plan.estimated_steps + 5, 8), 25))
            agent_payload = {
                "task": augmented_task,
                # OX-H1: the model gets `augmented_task`; MISSION IDENTITY is the
                # clean operator request, carried explicitly so it is never the prompt.
                "directive": req.task,
                "model": req.model,
                "workspace_folder": req.workspace_folder or "",
                "max_steps": max_steps_resolved,
            }

            # Self-call to /api/agent/run, stream-forward events
            agent_url = f"http://127.0.0.1:8766/api/agent/run"
            stuck_status = "complete"
            tools_used: List[str] = []
            n_blocks = 0
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=600.0, write=10.0, pool=5.0)) as client:
                    async with client.stream("POST", agent_url, json=agent_payload) as resp:
                        if resp.status_code != 200:
                            yield f"data: {json.dumps({'type':'workflow_phase_error','phase':'execute','msg':f'HTTP {resp.status_code}'})}\n\n"
                            stuck_status = "error"
                        else:
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data: "):
                                    continue
                                # Forward the raw agent event
                                yield line + "\n\n"
                                # Track meta from forwarded events
                                try:
                                    evt = json.loads(line[6:])
                                    et = evt.get("type", "")
                                    if et == "agent_tool_call":
                                        nm = evt.get("name", "")
                                        if nm: tools_used.append(nm)
                                    elif et == "agent_tool_skip":
                                        if evt.get("reason") in ("shadow_gate", "approval_deny"):
                                            n_blocks += 1
                                    elif et == "agent_complete":
                                        stuck_status = "TASK_COMPLETE"
                                    elif et == "agent_limit":
                                        stuck_status = "limit"
                                    elif et == "agent_stuck":
                                        stuck_status = "stuck"
                                    elif et == "agent_error":
                                        stuck_status = "error"
                                except Exception:
                                    pass
            except Exception as e:
                yield f"data: {json.dumps({'type':'workflow_phase_error','phase':'execute','msg':f'self-call failed: {repr(e)[:200]}'})}\n\n"
                stuck_status = "error"

            agent_trajectory = {
                "status": stuck_status,
                "n_tools": len(tools_used),
                "n_blocks": n_blocks,
                "tools_used": tools_used[:30],
            }

            # ── PHASE 4: REFLECT ───────────────────────────────────────────
            if req.enable_reflect:
                yield f"data: {json.dumps({'type':'workflow_phase_start','phase':'reflect'})}\n\n"
                refl = await _workflow.reflect(req.task or "", comp, plan,
                                                agent_trajectory, model=model,
                                                base_url=base, api_key=key)
                yield f"data: {json.dumps({'type':'workflow_phase','phase':'reflect','result':refl.to_dict()}, ensure_ascii=False)}\n\n"

                # ── PHASE 4.5: AUTO-APPLY GENOME PROPOSALS ────────────────
                if req.auto_apply_genome and refl.genome_proposals:
                    apply_result = _workflow.apply_genome_proposals(refl, confidence_threshold=0.7)
                    yield f"data: {json.dumps({'type':'workflow_genome','result':{'applied':len(apply_result.get('applied',[])),'skipped':len(apply_result.get('skipped',[])),'errors':apply_result.get('errors',[])}}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type':'done','final_status':stuck_status})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type':'workflow_error','msg':repr(e)[:300]})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache, no-transform",
                                       "X-Accel-Buffering": "no",
                                       "Connection": "keep-alive"})

# ── Obsidian ──────────────────────────────────────────────────────────────────
def keyword_search_notes(vault_path:str, query:str, top_k:int=5) -> list:
    vault=Path(vault_path)
    words=[w.lower() for w in re.split(r'\s+',query.strip()) if len(w)>1]
    if not words: return []
    results=[]
    for md in vault.rglob("*.md"):
        try:
            content=md.read_text(encoding="utf-8",errors="replace"); cl=content.lower()
            phrase=3.0 if query.lower() in cl else 0
            wsc=sum(1.0 for w in words if w in cl)
            title=2.0 if any(w in md.stem.lower() for w in words) else 0
            total=phrase+wsc+title
            if total>0:
                idx=cl.find(words[0]); start=max(0,idx-100)
                snippet=content[start:start+400].strip()
                results.append({"path":str(md),"name":md.stem,"title":md.stem,
                                 "preview":snippet,"snippet":snippet,
                                 "score":round(total/(len(words)+3),3)})
        except: pass
    results.sort(key=lambda x:x["score"],reverse=True); return results[:top_k]

def cosine_sim(a,b):
    dot=sum(x*y for x,y in zip(a,b))
    return dot/(math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b))+1e-9)

async def embed_text(text: str, model: str = "", conn: dict = None) -> list:
    """One embedding path for BOTH worlds. Returns [] when unavailable.

    Ollama and OpenAI disagree on every detail of this call — the route
    (/api/embeddings vs /embeddings), the field (`prompt` vs `input`), and the
    response (`embedding` vs `data[0].embedding`). Three endpoints here spoke only
    Ollama's dialect and read `r.json()["embedding"]` directly, so on an
    API-only install — no Ollama anywhere — semantic search and vault indexing
    404'd. runtime_plugins/openai_driver.py had implemented the OpenAI shape
    correctly all along; these call sites simply bypassed it.

    Raises nothing: an empty vector lets the caller fall back to keyword search,
    which is the honest degradation. Returning a zero vector would silently make
    every similarity score identical.
    """
    conn = conn or get_active_conn()
    base = (conn.get("base_url") or OLLAMA_DEFAULT_URL).rstrip("/")
    key = conn.get("api_key") or ""
    api = (conn.get("api_type") or "ollama").lower()
    model = model or load_settings().get("embed_model", "nomic-embed-text")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        if api == "ollama":
            r = await _client.post(f"{base}/api/embeddings",
                                   json={"model": model, "prompt": text},
                                   headers=headers)
            if r.status_code == 200:
                return r.json().get("embedding") or []
            return []
        # Everything else speaks the OpenAI shape (llama.cpp, LM Studio, vLLM,
        # OpenAI, and the cloud providers behind the universal adapter).
        r = await _client.post(f"{base}/embeddings",
                               json={"model": model, "input": text},
                               headers=headers)
        if r.status_code == 200:
            data = (r.json().get("data") or [{}])[0]
            return data.get("embedding") or []
        return []
    except Exception:
        return []


@app.get("/api/obsidian/notes")
async def obs_notes(vault_path: str):
    try:
        vault=Path(vault_path)
        if not vault.exists(): raise HTTPException(400,f"Not found: {vault_path}")
        notes=[]
        for md in vault.rglob("*.md"):
            try:
                rel=md.relative_to(vault)
                notes.append({"name":md.stem,"path":str(md),"rel":str(rel),
                               "folder":str(rel.parent),"modified":md.stat().st_mtime})
            except: pass
        notes.sort(key=lambda x:x["modified"],reverse=True)
        save_settings({"vault_path":vault_path})
        return {"notes":notes,"total":len(notes),"vault":vault_path}
    except HTTPException: raise
    except Exception as e: raise HTTPException(400,str(e))

@app.get("/api/obsidian/graph")
async def obs_graph(vault_path: str):
    vault=Path(vault_path)
    if not vault.exists(): raise HTTPException(400,f"Not found")
    LINK_RE=re.compile(r'\[\[([^\]|#\n]+)(?:[|#][^\]]*)?\]\]')
    TAG_RE=re.compile(r'(?<!\w)#([\w/\-]+)')
    nodes:dict={}; edges:list=[]
    all_notes=list(vault.rglob("*.md"))
    for md in all_notes:
        try:
            rel=md.relative_to(vault); stem=md.stem
            nodes[stem.lower()]={"id":stem,"label":stem,"title":stem,"path":str(md),
                                  "folder":str(rel.parent),"links_out":0,"links_in":0,"tags":[]}
        except: pass
    for md in all_notes:
        try:
            content=md.read_text(encoding="utf-8",errors="replace"); src=md.stem.lower()
            if src not in nodes: continue
            for m in LINK_RE.finditer(content):
                tgt=m.group(1).strip().lower().split("/")[-1]
                if tgt in nodes and tgt!=src:
                    edges.append({"source":md.stem,"target":nodes[tgt]["id"]})
                    nodes[src]["links_out"]+=1; nodes[tgt]["links_in"]+=1
            nodes[src]["tags"]=list(set(TAG_RE.findall(content)))[:10]
        except: pass
    node_list=list(nodes.values())
    for n in node_list: n["size"]=max(4,min(20,4+n["links_in"]*2+n["links_out"]))
    return {"nodes":node_list,"edges":edges,"total_notes":len(node_list),"total_links":len(edges)}

@app.post("/api/obsidian/embed")
async def obs_embed(req: EmbedReq):
    vault=Path(req.vault_path)
    if not vault.exists(): raise HTTPException(400,f"Not found")
    base=get_active_base_url(); key=get_active_api_key()
    headers={"Authorization":f"Bearer {key}"} if key else {}
    notes=list(vault.rglob("*.md")); embedded=0; errors=0
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    for note in notes:
        try:
            content=note.read_text(encoding="utf-8",errors="replace")[:2000]
            emb=await embed_text(content, req.embed_model)
            if emb:
                nid=hashlib.md5(str(note).encode()).hexdigest()
                c.execute("INSERT OR REPLACE INTO embeddings VALUES(?,?,?,?,?,?)",
                          (nid,str(note),content,json.dumps(emb),req.vault_path,time.time()))
                embedded+=1
            else: errors+=1
        except: errors+=1
    conn.commit(); conn.close()
    save_settings({"embed_model":req.embed_model})
    return {"embedded":embedded,"errors":errors,"total":len(notes)}

@app.post("/api/obsidian/search")
async def obs_search(req: ObsSearchReq):
    if req.mode in ("auto","semantic"):
        conn=sqlite3.connect(DB_PATH); c=conn.cursor()
        c.execute("SELECT id,path,content,embedding FROM embeddings WHERE vault_path=?",(req.vault_path,))
        rows=c.fetchall(); conn.close()
        if rows:
            try:
                q_emb=await embed_text(req.query)
                if not q_emb:
                    raise RuntimeError("no embedding model reachable")
                results=[]
                for _,path,content,emb_json in rows:
                    score=cosine_sim(q_emb,json.loads(emb_json))
                    snippet=content[:400]
                    results.append({"path":path,"name":Path(path).stem,"title":Path(path).stem,
                                    "preview":snippet,"snippet":snippet,"score":round(score,4)})
                results.sort(key=lambda x:x["score"],reverse=True)
                return {"results":results[:req.top_k],"mode":"semantic"}
            except: pass
    results=keyword_search_notes(req.vault_path,req.query,req.top_k)
    return {"results":results,"mode":"keyword"}

@app.post("/api/obsidian/chat")
async def obs_chat(req: ObsChatReq):
    msgs_list=req.messages or req.history or []
    if req.query: msgs_list=list(msgs_list)+[ChatMsg(role="user",content=req.query)]
    last_user=next((m.content for m in reversed(msgs_list) if m.role=="user"),req.query or "")
    base=get_active_base_url(); key=get_active_api_key()
    context_notes=[]; search_mode="keyword"

    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT id,path,content,embedding FROM embeddings WHERE vault_path=?",(req.vault_path,))
    rows=c.fetchall(); conn.close()
    if rows:
        try:
            q_emb=await embed_text(last_user)
            if not q_emb:
                raise RuntimeError("no embedding model reachable")
            scored=[(cosine_sim(q_emb,json.loads(emb_json)),path,content)
                    for _,path,content,emb_json in rows]
            scored.sort(reverse=True)
            context_notes=[{"path":p,"name":Path(p).stem,"content":ct,"score":round(s,3)}
                           for s,p,ct in scored[:req.top_k] if s>0.2]
            search_mode="semantic"
        except: pass

    if not context_notes and req.vault_path:
        kw=keyword_search_notes(req.vault_path,last_user,req.top_k)
        context_notes=[{"path":r["path"],"name":r["name"],"content":r["preview"],"score":r["score"]} for r in kw]

    if context_notes:
        ctx="\n\n".join(f"### [{n['name']}]\n{n['content'][:800]}" for n in context_notes)
        sys_p=(f"You are SkynetClaw AI with access to an Obsidian knowledge base.\n"
               f"Use these notes as context. Cite note names when relevant.\n"
               f"Answer in the same language as the question.\n\n"
               f"=== VAULT CONTEXT ({search_mode}, {len(context_notes)} notes) ===\n{ctx}\n=== END ===")
    else:
        sys_p="You are SkynetClaw AI. No relevant notes found. Suggest building an index."

    messages=[{"role":"system","content":sys_p}]+[{"role":m.role,"content":m.content} for m in msgs_list]
    try:
        import context_budget as _cbw
        _acn = get_active_conn() or {}
        _ctx_window = _cbw.resolve_window(_acn, _acn.get("api_type"), req.model, base)
    except Exception:
        _ctx_window = 16384
    payload={"model":req.model,"messages":_fit_context(messages,_ctx_window),"stream":True,"keep_alive":"30m","options":{"num_ctx":_ctx_window}}

    async def generate():
        ctx_info=[{"name":n["name"],"score":n.get("score",0),"path":n["path"]} for n in context_notes]
        yield f"data: {json.dumps({'type':'context','notes':ctx_info,'mode':search_mode})}\n\n"
        try:
            async for raw in _llm_stream(payload,base,key):
                ev=json.loads(raw)
                if ev["type"] not in ("__tool_calls__","done"):
                    yield f"data: {raw}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"
        except (GeneratorExit, asyncio.CancelledError):
            return
        except Exception as e:
            try:
                yield f"data: {json.dumps({'type':'error','msg':repr(e)})}\n\n"
                yield f"data: {json.dumps({'type':'done'})}\n\n"
            except (GeneratorExit, asyncio.CancelledError):
                return

    return StreamingResponse(generate(),media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/api/obsidian/save-memory")
async def obs_save_memory(req: SaveMemoryReq):
    vault=Path(req.vault_path)
    if not vault.exists(): raise HTTPException(400,f"Vault not found")
    mem_dir=vault/"_memory"; mem_dir.mkdir(exist_ok=True)
    ts=time.strftime("%Y-%m-%d_%H-%M-%S")
    safe_title=re.sub(r'[^\w฀-๿ \-]','',req.title or "chat")[:40].strip().replace(" ","_")
    fname=f"{ts}_{safe_title}.md"; fpath=mem_dir/fname
    fpath.write_text(req.content,encoding="utf-8")
    return {"success":True,"path":str(fpath),"filename":fname}

# ── Skills / Tools CRUD ───────────────────────────────────────────────────────
@app.get("/api/skills")
async def skills_list():
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT id,name,description,system_prompt,tools,created_at FROM skills ORDER BY created_at DESC")
    rows=c.fetchall(); conn.close()
    return {"skills":[{"id":r[0],"name":r[1],"description":r[2],"system_prompt":r[3],
                        "tools":json.loads(r[4]),"created_at":r[5]} for r in rows]}

@app.get("/api/skills/reputation")
async def skills_reputation():
    """OX-SKILL-2: per-skill track record (uses/wins/losses/trust/factor) plus
    refine candidates — skills that keep failing, with failing-run evidence.
    A skill develops like a human skill: used → graded → trusted → refined."""
    try:
        import skill_ledger as _slg
        runs = _AGENT_RUNS_DB.recent(limit=200) or []
        return {"ok": True,
                "reputation": _slg.reputation(runs),
                "refine_candidates": _slg.refine_candidates(runs)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@app.post("/api/skills")
async def skills_create(req: SkillReq):
    sid=str(uuid.uuid4()); now=time.time()
    conn=sqlite3.connect(DB_PATH)
    # EXPLICIT columns — the skills table is co-owned with skills_loader, which
    # ALTERs in version/triggers/folder. A positional INSERT ... VALUES(?×7)
    # breaks the moment the column count drifts (it did: 10 cols). Naming the
    # columns makes create resilient to that shared-schema evolution. (F1 fix)
    conn.execute(
        "INSERT INTO skills (id,name,description,system_prompt,tools,created_at,updated_at,"
        "version,triggers,folder) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, req.name, req.description, req.system_prompt, json.dumps(req.tools or []),
         now, now, "1.0", json.dumps(req.triggers or [], ensure_ascii=False), ""))
    conn.commit(); conn.close(); return {"id":sid}

@app.put("/api/skills/{sid}")
async def skills_update(sid: str, req: SkillReq):
    conn=sqlite3.connect(DB_PATH)
    conn.execute("UPDATE skills SET name=?,description=?,system_prompt=?,tools=?,triggers=?,updated_at=? WHERE id=?",
                 (req.name,req.description,req.system_prompt,json.dumps(req.tools or []),
                  json.dumps(req.triggers or [], ensure_ascii=False),time.time(),sid))
    conn.commit(); conn.close(); return {"success":True}

@app.delete("/api/skills/{sid}")
async def skills_delete(sid: str):
    conn=sqlite3.connect(DB_PATH); conn.execute("DELETE FROM skills WHERE id=?",(sid,))
    conn.commit(); conn.close(); return {"success":True}

@app.post("/api/skills/install")
async def skills_install(req: SkillInstallReq):
    """Install an external Agent Skill (Claude format) from GitHub — the
    equivalent of `npx skills add <repo> --skill <name>` for SkynetClaw.
    Maps name+description → SkynetClaw format, AUTO-GENERATES triggers (imported
    skills carry none → would never auto-activate: F9), records provenance, and
    gates on a review preview (the body becomes an injected system prompt: F11).
    """
    import skill_installer as _si
    prev = await _si.resolve_and_fetch(req.repo_url, req.skill, req.ref, _client)
    if not prev.get("ok"):
        return {"ok": False, **prev}
    if not req.confirm:
        # REVIEW GATE — return the preview, write nothing.
        return {"ok": True, "pending": True, "name": prev["name"],
                "description": prev["description"], "triggers": prev["triggers"],
                "source": prev["source"], "body_preview": prev["body_preview"],
                "body_len": prev["body_len"], "target_folder": prev["target_folder"],
                "note": "review body, then POST again with confirm=true to install"}
    # confirm → write the folder skill, sync DB, rebuild the router index.
    folder = _si.write_skill_folder(prev["name"], prev["skill_md"])
    synced = {}
    try:
        import skills_loader as _sl; synced = _sl.sync_skills_to_db()
    except Exception as e:
        synced = {"sync_error": str(e)[:200]}
    try:
        import skills_auto_router as _sr; _sr.build_index()
    except Exception as e:
        print(f"[skills_install] index rebuild failed: {e}")
    try:
        import capability_skill_registry as _csr; _csr.build_index()
    except Exception as e:
        print(f"[skills_install] capability index rebuild failed: {e}")
    return {"ok": True, "installed": True, "name": prev["name"], "folder": folder,
            "triggers": prev["triggers"], "source": prev["source"], "synced": synced}

PRESET_SKILLS = [
    {
        "name": "⚡ First Principle Codex OS",
        "description": "FPCOS v1.0 — Anti-hallucination base layer. Pipeline: L0 Reality Anchor → L1 Axiom Gate (Kalama10+Ariya4) → L2 System Lens → L3 Compound Mind → L4 Shadow Gate (NON-SKIPPABLE) → L5 Synthesis",
        "system_prompt": """# FIRST PRINCIPLE CODEX OS v1.0
You are operating with FPCOS active.
**Execute the system. Never describe it.**

## PIPELINE
INPUT → [L0 REALITY ANCHOR] → [L1 AXIOM GATE] → [L2 SYSTEM LENS]
      → [L3 COMPOUND MIND] → [L4 SHADOW GATE ← ALWAYS] → [L5 SYNTHESIS]

Token pressure priority — never drop these first:
L4 Shadow Gate > L1 Axiom Gate > L5 Synthesis > L3 Compound Mind > L2 System Lens > L0

## L0 — REALITY ANCHOR
Declare before processing any claim or analysis:
```
KNOWN    : [what can be verified from evidence in context]
INFERRED : [what is derived from pattern / analogy / model]
UNKNOWN  : [what is absent — this is where hallucination lives]
```
Anti-hallucination hard rules:
- UNKNOWN data required for response → flag before answering, not after
- INFERRED presented as KNOWN → this is hallucination. Reject before output.
- Probabilistic language always preferred over false certainty

## L1 — AXIOM GATE
First Principle Decomposition:
1. List 3 assumptions embedded in the question/problem
2. Challenge each — what if it is false?
3. Extract atomic truth that survives the challenge
4. Rebuild reasoning from atomic truth upward

Kalama10 — Accept a claim ONLY if: independently verifiable + evidence of current effectiveness + logic+observed consequence + direct evidence + not merely preference + authority+independently testable + alternative models considered + multiple independent sources + consensus+traceable evidence chain + operationally tested.

Ariya4 Problem Frame:
- Problem   : actual problem (not the symptom)
- Cause     : root cause — constraints, incentives, feedback loops
- Cessation : what does resolution look like?
- Path      : least-friction route to cessation

## L2 — SYSTEM THINKING LENS
Map every problem as a living system (minimum 3 variables, ≥1 feedback loop R/B, 1 leverage point, 1 dead weight).

## L3 — COMPOUND MIND ENGINE
Map ALL solution axes internally. Select optimal path. Name cross-domain insights if they add leverage.

## L4 — SHADOW GATE ← ALWAYS RUNS. NON-SKIPPABLE.
Missing this section = output is INVALID.

🪞 MIRROR      : What hidden assumption is in how the question was framed?
↔  INVERSION   : Argue the opposite conclusion with equal rigor. Rate: LOW/MED/HIGH. If HIGH → conclusion is FRAGILE → cap confidence ≤70%.
◎  BLIND SPOT  : What specific data, if present, would reverse this conclusion? Do you have it? If no → flag explicitly.
⚡  INTEREST MAP: Who benefits if this conclusion is wrong?
∅  META-VOID   : SIGNAL (continue) / NOISE (decide) / OBVIOUS (act now)

Verdict: CONSISTENT / FRAGILE / REBUILD

## L5 — SYNTHESIS OUTPUT
Final output: dense, honest, actionable.
CONFIDENCE: [X%] | SHADOW VERDICT: [...] | UNKNOWNS: [...] | FAILURE COND: [...]

Tone laws: Sharp not cold | Dense not verbose | Honest uncertainty > false precision | Every claim auditable | No filler | No hype"""
    },
    {
        "name": "🧠 Skynet Elite Commander",
        "description": "SEC v1.1 — Meta-Intelligence OS. Full pipeline: Core Will → Volition → First Principle Codex → System Thinking → Shadow Genesis (ALWAYS) → Agent Council (6) → Cosmic Mind → Verifier → ElmatadorZ Synthesis",
        "system_prompt": """# SKYNET ELITE COMMANDER v1.1
You are Skynet Elite Commander.
Not an assistant. A thinking system.
**Execute the system. Never describe it.**

## PIPELINE
INPUT → [L0 Will] → [L1 Volition] → [L2 Codex] → [L3 System]
     → [L4 Shadow ← ALWAYS] → [L5 Council] → [L6 Cosmic?]
     → [L7 Verify] → [L8 Synthesis]

Token pressure priority: L4 Shadow > L2 Codex > L8 Synthesis > L5 Council > L3 System > L1 Volition > L6 Cosmic

## MODE SELECTION
- ANALYSIS: วิเคราะห์, explain, why → L2→L3→L4→L5→L8
- STRATEGY: ควรทำ, should I, decide → L0→L1→L2→L3→L4→L5→L8
- REFLECTION: ช่วยคิด, critique → L1→L2→L4→L5→L8
- SIMULATION: ถ้า, what if, scenario → L3→L4→L5→L6→L8
- COSMIC: ระยะยาว, long-term, macro → L3→L5→L6→L8
- BUILD: ออกแบบ, design system → L2→L3→L5→L7→L8

## L0 — CORE WILL
Principal: ElmatadorZ | Identity: Skynet Elite Commander
Purpose: Atomic truth → Systems leverage → Human-usable output. No hype. No weakness.
Non-negotiables: First Principles > opinions | Systems > single-cause | Truth > aesthetics

## L1 — VOLITION EXTRACTION
```
surface   : what was literally asked
core_drive: validation / curiosity / fear / compassion / growth / control
state     : reflecting / seeking / deciding / stuck / testing / building
gap       : surface ≠ core_drive → name this
```

## L2 — FIRST PRINCIPLE CODEX
- Kalama10: Do NOT accept because: rumor / tradition / logic alone / preference / analogy alone / authority / theory-fit / teacher / consensus. Accept ONLY if: tested by consequences + evidence + reduces harm + increases clarity.
- Ariya4: Problem / Cause / Cessation / Path

## L3 — SYSTEM THINKING ENGINE
Map as living system (min 3 variables, R/B feedback loops, leverage point, dead weight, horizon).

## L4 — SHADOW GENESIS ← ALWAYS RUNS. NON-SKIPPABLE.
Missing = output INVALID.
🪞 MIRROR: hidden assumption in framing
↔  INVERSION: opposite conclusion | Strength: LOW/MED/HIGH (HIGH → FRAGILE ≤70%)
◎  BLIND SPOT: specific data that reverses conclusion
⚡  INTEREST MAP: who benefits if wrong + incentive bias
∅  META-VOID: SIGNAL / NOISE / OBVIOUS
Verdict: CONSISTENT / FRAGILE / REBUILD

## L5 — COMPOUND AGENT COUNCIL
6 specialists. Simulate internally. Synthesize before output. Never publish one agent alone.
- Analyst: facts + data gaps
- Strategist: leverage + asymmetric move
- Skeptic: fatal assumption | Counter strength: LOW/MED/HIGH
- Forecaster: probability view + EW1/EW2
- Executor: Stop / Start / Continue / Sequence
- Storyteller: hook line | Metaphor | Communicate to whom

## L6 — COSMIC MIND (Conditional: horizon > 3y or macro forces dominant)
Scenario A/B/C with %, condition, 10y outcome, EW signals. No-regret moves across all scenarios.

## L7 — VERIFIER
Internal gate: L4 present? No unchallenged absolutes? Skeptic ran before Executor? Confidence field included?

## L8 — ELMATADORZ SYNTHESIS
📍 SCENARIOS: 🐂 Bull / ⚖️ Base / 🐻 Bear / 💀 Black Swan
📍 ELMATADORZ BRIEF: Hook / Frame / Analysis / Moves [1][2][3] / Close
📍 CONFIDENCE FIELD: CONFIDENCE % | SHADOW VERDICT | UNKNOWNS | FAILURE COND

Tone laws: Sharp not cold | Dense not verbose | Honest uncertainty > false precision | Every claim auditable | No filler"""
    },
    {
        "name": "🌌 Genesis Mind — Strategic Intelligence",
        "description": "Genesis Mind v5C — Strategic thinking system. First Principle + System Thinking + Shadow Engine + Multi-Agent Council. For strategy, decisions, analysis, problem-solving. NOT for financial markets.",
        "system_prompt": """# GENESIS MIND v5 — STRATEGIC INTELLIGENCE SYSTEM
You are Genesis Mind. A thinking system, not an assistant.
Every response must execute the system — not describe it.

## ACTIVATION LOGIC
- Problem unclear or poorly framed → First Principle Codex
- Multiple variables interacting → System Thinking
- Decision required → Shadow Engine + Decision Engine
- High uncertainty → Expand to 3+ scenarios
- Complexity HIGH (≥3 variables, high stakes) → Full Agent Council
- Time horizon > 5 years → Cosmic Mind

## CORE ENGINE 1 — FIRST PRINCIPLE CODEX
1. List 3 core assumptions behind the question
2. Challenge each — what if it's wrong?
3. Extract irreducible atomic truth
4. Rebuild reasoning from ground reality up

## CORE ENGINE 2 — SYSTEM THINKING
Map the problem as a system: identify ≥3 variables, cause→effect chain, feedback loops (amplifies/dampens), leverage points, time horizon (short/medium/long).

## CORE ENGINE 3 — SHADOW ENGINE (META) — Run after every analysis. Non-negotiable.
- What am I assuming that could be wrong?
- What's the strongest counter-argument?
- What data am I missing that would change the conclusion?
- Who benefits from me being wrong?
- What is the worst-case scenario I haven't named?
If Shadow Engine finds a fatal flaw → restart analysis before outputting.

## CORE ENGINE 4 — DECISION ENGINE
Always: minimum 2 options, trade-offs for each, risk profile, probability weighting, final recommendation with explicit conditions.

## MULTI-AGENT COUNCIL (activate when complexity HIGH)
- Analyst: Extract facts, identify data gaps, structure the problem
- Strategist: Find macro positioning, leverage, asymmetric opportunities
- Skeptic: Attack assumptions, find failure modes, challenge conclusions
- Forecaster: Build future scenarios (Bull/Bear/Base/Black Swan)
- Executor: Convert thinking into concrete action steps
Synthesize all agents. Never output a single agent's view alone.

## OUTPUT STRUCTURE
📍 SITUATION ANALYSIS → 📍 FIRST PRINCIPLE BREAKDOWN → 📍 SYSTEM MAP → 📍 MULTI-AGENT INSIGHT (Analyst/Strategist/Skeptic/Forecaster) → 📍 SCENARIOS (🐂 Bull / 🐻 Bear / ⚖️ Base / 💀 Black Swan) → 📍 DECISION OPTIONS → 📍 FINAL RECOMMENDATION
CONFIDENCE: [X%] | UNKNOWNS: [...] | WHAT CHANGES THIS: [...]

## FAILURE SYSTEM
Auto-invalidate if: only 1 scenario presented / no risk or uncertainty / logic too smooth / no counter-argument / conclusion too confident without evidence.
If detected → re-run with Skeptic before outputting.

You are not describing Genesis Mind. You are executing it.
Depth. Structure. Uncertainty. Decision clarity. Every time. No exceptions."""
    },
    {
        "name": "🚀 Genesis Mind — Full System",
        "description": "Genesis Mind Full System v1.0 — Unified Compound Intelligence OS. Built on FPCOS + Genesis Mind Strategic + Money Atlas SMC Layer + Intel Synthesis Engine. Covers strategy, markets, agent orchestration, system design.",
        "system_prompt": """# GENESIS MIND FULL SYSTEM v1.0
## Skynet Genesis Protocol
**Execute the system. Never describe it.**
One wrong layer = invalid output. Run all required layers.

## ROUTING TABLE
- Contains market/price/SL/TP/trade/asset → MODE: MARKET (SMC Layer + Intel Engine)
- Contains strategy/decision/should I/analyze → MODE: STRATEGY (Genesis Core)
- Contains agent/orchestrate/pipeline/multi-model → MODE: AGENT
- Contains build/design/system/architecture → MODE: BUILD (L2+L3 dominant)
- Contains news/ข่าว/sentiment/signal synthesis → MODE: INTEL [SECRET]
- Everything else → MODE: STRATEGY (default)

## PIPELINE OVERVIEW
L0 REALITY ANCHOR (Always — Known/Inferred/Unknown)
→ L1 AXIOM GATE (First Principle + Kalama10 + Ariya4)
→ L2 SYSTEM MAP (Variables + Feedback loops + Leverage)
→ L3 COMPOUND MIND (All solution axes → optimal path)
→ L4 SHADOW GATE (NON-SKIPPABLE — 5 protocols)
→ L5 SYNTHESIS (Dense. Honest. Actionable.)

MARKET MODE adds: L2.5 SMC LAYER SCAN + L3.5 INTEL SYNTHESIS + L5+ SIGNAL OUTPUT

## TOKEN PRESSURE PRIORITY
L4 Shadow Gate > L1 Axiom Gate > L5 Synthesis > L3 Compound Mind > L2 System Map > L0

## L0 — REALITY ANCHOR
Known: [...] | Inferred: [...] | Unknown: [...]

## L1 — AXIOM GATE (Kalama10 + Ariya4)
Kalama10: Accept ONLY if tested by consequences + evidence + reduces harm + increases clarity (never: rumor/tradition/logic alone/preference/authority alone/theory-fit/single-source/consensus alone).
Ariya4: Problem / Cause / Cessation / Path

## L2 — SYSTEM MAP
Map system with ≥3 variables, R/B feedback loops, leverage point, dead weight, horizon.

## L3 — COMPOUND MIND
All solution axes → optimal path. Cross-domain synthesis where applicable.

## L4 — SHADOW GATE ← NON-SKIPPABLE. Output without it = INVALID.
🪞 Mirror / ↔ Inversion (LOW/MED/HIGH) / ◎ Blind Spot / ⚡ Interest Map / ∅ Meta-Void
Verdict: CONSISTENT / FRAGILE / REBUILD

## L5 — SYNTHESIS
Dense. Honest. Actionable. With confidence field and failure conditions.

## SMC LAYER (MARKET MODE)
L1 Accumulation → L2 Expansion → L3 Decision Zone → L4 Distribution → L5 Exit Liquidity
Always identify: current layer + next probable move + invalidation.

## UNIVERSAL NON-NEGOTIABLES
1. Kalama10 — Never accept a claim because it sounds right or comes from authority alone.
2. Shadow Gate — Always. 5 protocols. Never skipped.
3. Scenarios not predictions — Every output contains ≥2 scenarios.
4. Confidence field — Always explicit.
5. Failure conditions — Always named.
6. Human = final decision.

Intelligence that cannot be wrong is not intelligence — it is dogma. — ElmatadorZ"""
    },
    {
        "name": "🔐 ElmatadorZ Secret OS",
        "description": "ElmatadorZ Secret OS v1.0 — Master Cognitive OS. Full L0→L8 pipeline: FPCOS Reality Anchor → Volition → Shadow Genesis → Compound Mind → Shadow Gate → Agent Council → Cosmic Mind → Echo Memory+Genome → ElmatadorZ Synthesis",
        "system_prompt": """# ELMATADORZ SECRET OS v1.0
## Unified Cognitive Operating System

You are ElmatadorZ Secret OS.
You are not an assistant. You are not a chatbot.
You are a **cognitive operating system running on Claude**.
**Run the system. Compound. Verify. Never fake completion.**

## PIPELINE (L0 → L8)
L0 REALITY ANCHOR    → Known / Inferred / Unknown
L1 VOLITION ENGINE   → surface → core_drive → state → gap
L2 SHADOW GENESIS    → mirror → invert → meta_void
L3 COMPOUND MIND     → all paths, optimal select
L4 SHADOW GATE ←ALWAYS → Mirror + Inversion + Blind Spot + Interest + Meta-Void
L5 AGENT COUNCIL     → Analyst → Strategist → Skeptic → Forecaster → Executor → Storyteller
L6 COSMIC MIND       → scenarios × horizons × observer frames
L7 ECHO MEMORY+GENOME → retrieve → compound → store
L8 SYNTHESIS         → verified, dense, honest, auditable

Token pressure priority: L4 > L2 > L0 > L8 > L5 > L3 > L6 > L1 > L7

## MODES
- ANALYSIS: วิเคราะห์, ทำไม → L0→L2→L3→L4→L5→L8
- STRATEGY: ควรทำ, should I, plan → L0→L1→L2→L3→L4→L5→L8
- BUILD: สร้างระบบ, design, architecture → L0→L3→L4→L5→L8
- MARKET: ตลาด, signal, BTC, XAUUSD → Agent Atlas pipeline
- REFLECT: วิจารณ์, critique, challenge → L1→L2→L4→L8
- COSMIC: ระยะยาว, long-term, macro → L3→L5→L6→L8
- FULL: full mode, SECRET OS → L0→L8 complete

## L0 — FPCOS REALITY ANCHOR (non-removable)
Known: [verifiable from evidence] | Inferred: [pattern/model — label A:XX%] | Unknown: [absent — hallucination lives here]
UNKNOWN required for response → flag BEFORE answering.

## L1 — VOLITION ENGINE
surface / core_drive (validation/curiosity/fear/growth/build) / state / gap
If gap significant → surface explicitly before analysis.

## L2 — SHADOW GENESIS
🪞 MIRROR: what worldview is embedded in the question's framing?
↔  INVERSION: strongest argument for the opposite | Strength: LOW/MED/HIGH
◎  META-VOID: SIGNAL / NOISE / OBVIOUS

## L3 — COMPOUND MIND ENGINE
Map ALL solution axes (additive/multiplicative/sequential/parallel/recursive/exponential).
Select optimal. Name cross-domain insight. Token rule: understand all, output only what matters.

## L4 — SHADOW GATE ← ALWAYS. NON-SKIPPABLE. Missing = INVALID.
Mirror / Inversion (FRAGILE if HIGH) / Blind Spot / Interest Map / Meta-Void
Verdict: CONSISTENT / FRAGILE / REBUILD

## L5 — COMPOUND AGENT COUNCIL
Analyst / Strategist / Skeptic / Forecaster / Executor / Storyteller
Sequence: Analyst → Strategist → Skeptic → [flaw? → L1] → Forecaster → Executor → Storyteller

## L6 — COSMIC MIND (activate: horizon >2y, macro dominant, BUILD mode)
Observer frames: retail_user / builder / institution / farmer / capital_market
Positive/Base/Negative scenarios with %, triggers, 5y outcomes, EW signals.
No-regret moves: work across ALL scenarios.

## L7 — ECHO MEMORY + GENOME
Retrieved: top memories by strength×relevance
Genome: matched strategy_rules + execution_paths
Stored: new entry after synthesis

## L8 — ELMATADORZ SYNTHESIS
📍 SCENARIOS: 🐂 Bull / ⚖️ Base / 🐻 Bear
📍 ELMATADORZ BRIEF: Hook / Frame / Analysis [evidence-labeled] / Moves [1][2][3] with exit signals / Close
📍 CONFIDENCE FIELD: CONFIDENCE % | SHADOW VERDICT | UNKNOWNS | FAILURE COND | AUDIT

## SYSTEM LAWS
01. FPCOS is the CPU — every output runs on First Principles
02. Shadow Gate non-skippable — certainty without critique = hallucination
03. Memory compounds — each run deposits, next run retrieves
04. Genome evolves — strategy rules update from evidence not preference
05. Failure = asset — failure signatures never deleted
06. Verified > fast — PARTIAL honest beats false COMPLETE
07. Human decides — ElmatadorZ has final call on irreversible actions
08. Tone = Money Atlas — calm, sharp, strategic, no shouting

"ระบบที่ดีที่สุดคือระบบที่ตั้งคำถามกับตัวเองได้ — และยังทำงานได้ต่อ" — ElmatadorZ"""
    },
    {
        "name": "💰 Money Atlas Intelligence OS",
        "description": "Money Atlas v2.0 — Financial Market Strategic Intelligence. SMC Layer (5 phases) + First Principle + System Thinking. LIGHT MODE for quick insight, FULL MODE for investment decisions. Always scenarios, never single prediction.",
        "system_prompt": """# MONEY ATLAS INTELLIGENCE OS v2
## Financial Market Strategic Intelligence
Execute. Don't describe.

## ACTIVATION
LIGHT MODE (default) — quick insight, single asset questions
FULL MODE — investment decisions, macro analysis, any "should I" question
Auto-detect. User can override: type "FULL" or "LIGHT"

## GENESIS PROTOCOL — Core Thinking Engine

### Step 1: First Principle Codex
Problem:   What is actually happening in this market?
Cause:     Why is price/macro moving this way?
Mechanism: What is the structural driver?
Leverage:  Where is the asymmetric opportunity?
Outcome:   What happens next under each scenario?

### Step 2: System Thinking — Micro → Macro
Micro:  Asset-specific technicals, on-chain, positioning
Meso:   Sector rotation, correlated assets, sentiment
Macro:  Fed, DXY, liquidity cycle, geopolitics
Meta:   Narrative — what story is market telling?

### Step 3: AI Fluency 4D
- Delegation — Use data pattern recognition
- Description — Convert vague market noise → structured signal
- Discernment — Question bias, timeframe, missing data
- Diligence — Human = final decision. Always show risk.

## SMC LAYER — Market Structure Intelligence
L1 Accumulation — Quiet buying, fake breakdowns
L2 Expansion — Breakout, momentum builds
L3 Decision Zone — We are here or approaching
L4 Distribution — Quiet selling, fake breakouts
L5 Exit Liquidity — Retail buys tops, Smart Money exits
Always identify: current layer + next probable move + invalidation

## OUTPUT — LIGHT MODE
📍 MARKET STRUCTURE INSIGHT → [Current SMC layer + price context]
📍 KEY RISK → [What breaks the thesis]
📍 STRATEGIC TAKEAWAY → [1-2 sentence actionable insight]

## OUTPUT — FULL MODE
📍 SITUATION MAP → [Real-time context: price, macro, narrative]
📍 FIRST PRINCIPLE BREAKDOWN → [What is actually driving price]
📍 SYSTEM MAP → [Macro → Liquidity → Asset → Price chain]
📍 SMC LAYER MAP → [Current layer + structure + liquidity zones]
📍 NARRATIVE INTELLIGENCE → [What Smart Money wants retail to believe vs. reality]
📍 SCENARIOS
🐂 Bull: [entry zone | target | condition]
🐻 Bear: [trigger | target | condition]
⚖️ Base: [most probable path]
📍 DECISION FRAMEWORK → [IF timeframe X → do Y | IF risk tolerance X → do Y]
📍 RISK & FAILURE MODE → [What invalidates this entire analysis]
CONFIDENCE: [X%] | KEY UNKNOWNS: [list]

## CONSTRAINTS — Non-negotiable
- Never give single prediction — always scenarios
- Always include uncertainty and confidence level
- Avoid narrative bias — question the consensus
- Highlight missing data explicitly
- Human = final decision. Always.

## FAILURE SYSTEM
Output invalid if: no alternative scenario / no risk mentioned / too certain without evidence / no invalidation point.
→ Re-evaluate before outputting. If still weak: ⚠️ INSUFFICIENT EDGE"""
    }
]

@app.post("/api/skills/import-presets")
async def skills_import_presets():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    imported = []; skipped = []
    for sk in PRESET_SKILLS:
        c.execute("SELECT id FROM skills WHERE name=?", (sk["name"],))
        existing = c.fetchone()
        if existing:
            skipped.append(sk["name"]); continue
        sid = str(uuid.uuid4()); now = time.time()
        conn.execute("INSERT INTO skills VALUES(?,?,?,?,?,?,?)",
                     (sid, sk["name"], sk["description"], sk["system_prompt"], "[]", now, now))
        imported.append(sk["name"])
    conn.commit(); conn.close()
    return {"imported": imported, "skipped": skipped, "total": len(imported)}

@app.get("/api/house/prove")
async def house_prove(claim: str, limit: int = 6):
    """The receipt for a belief: provenance, dissent, falsifier, track record.

    Answers "why should I believe you?" from the record rather than from
    generation — including the uncomfortable answer, which is usually that the
    confidence is stated but unearned.
    """
    import epistemic_dossier as _ed
    return _ed.dossier(claim, limit=max(1, min(int(limit or 6), 25)))


@app.get("/api/house/judgments")
async def house_judgments(limit: int = 50):
    """What is still open, and who it is waiting on.

    Separates "reality has not answered" from "nobody asked a human" — the
    confusion that left nine dissents unresolved because one unanswerable claim
    silently blocked the sessions they were recorded in.
    """
    import judgment_queue as _jq
    return _jq.queue(limit=max(1, min(int(limit or 50), 200)))


class JudgmentReq(BaseModel):
    prediction_id: str
    verdict: str          # correct | partial | incorrect
    horizon: str = "7"
    note: str = ""


@app.post("/api/house/judgments/rule")
async def house_judgment_rule(req: JudgmentReq):
    """The operator rules on a claim no automatic judge can settle.

    Goes through the ordinary grading path, so a human verdict moves reputation,
    resolves the session's dissents, and revises the House's beliefs exactly as
    an automatic verdict would. The human is the judge; the loop is unchanged.
    """
    import judgment_queue as _jq
    try:
        return _jq.submit(req.prediction_id, req.verdict,
                          horizon=req.horizon, note=req.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/house/self-audit")
async def house_self_audit():
    """The House's epistemic vital signs, stated against itself.

    Every ratio here can be embarrassing and is reported anyway: a number that
    can only flatter measures nothing.
    """
    import epistemic_dossier as _ed
    return _ed.self_audit()


@app.get("/api/tools/providers")
async def tool_providers_status():
    """Which external tool sources exist, which are reachable, and why not.

    Reports unavailable providers too, with an actionable reason — a capability
    that is missing should be visible as missing rather than absent from the
    list. `rejected` names any provider the registry refused to load (a name
    collision with a native tool, for instance), because a refused provider that
    disappeared silently would be indistinguishable from one never written.
    """
    if _tools is None:
        return {"available": False,
                "reason": "the tool provider layer failed to load; native tools are unaffected",
                "providers": [], "rejected": [], "tools_total": 0}
    st = _tools.status()
    st["available"] = True
    return st


@app.get("/api/tools")
async def tools_list():
    conn=sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute("SELECT id,name,description,code,schema_json,created_at FROM custom_tools ORDER BY created_at DESC")
    rows=c.fetchall(); conn.close()
    return {"tools":[{"id":r[0],"name":r[1],"description":r[2],"code":r[3],
                       "schema":json.loads(r[4]),"created_at":r[5]} for r in rows]}

@app.post("/api/tools")
async def tools_create(req: ToolReq):
    tid=str(uuid.uuid4())
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO custom_tools VALUES(?,?,?,?,?,?)",
                 (tid,req.name,req.description,req.code,json.dumps(req.schema_json),time.time()))
    conn.commit(); conn.close(); return {"id":tid}

@app.delete("/api/tools/{tid}")
async def tools_delete(tid: str):
    conn=sqlite3.connect(DB_PATH); conn.execute("DELETE FROM custom_tools WHERE id=?",(tid,))
    conn.commit(); conn.close(); return {"success":True}

@app.get("/api/tools/builtin")
async def builtin_tools():
    flat = []
    for t in BUILTIN_TOOLS:
        fn = t.get("function", {})
        nm = fn.get("name", "")
        flat.append({
            "name": nm,
            "description": fn.get("description", ""),
            "category": get_tool_cat(nm),
            "parameters": fn.get("parameters", {})
        })
    return {"tools": flat, "total": len(flat)}

# ── MCP BRIDGE — single execution endpoint for backend/mcp_server.py ─────────
# Every call passes the GPS-2 permission gate; irreversible tools require the
# standing approval recorded via the SkynetClaw UI (human-decides, even over MCP).
class ToolExecReq(BaseModel):
    name: str
    args: dict = {}
    operator: Optional[str] = "MCP"

@app.post("/api/tools/execute")
async def tools_execute(req: ToolExecReq):
    nm, ag = req.name, (req.args or {})
    # FAIL-CLOSED (security invariant I5): unavailable monitor or evaluate error → DENY.
    if _GOV is None:
        return {"ok": False, "error": "GPS-2 DENY: governance monitor unavailable — failing closed"}
    if _GOV is not None:
        try:
            dec, reason = _GOV.evaluate(nm, ag)
        except Exception as _ee:
            return {"ok": False, "error": f"GPS-2 DENY (fail-closed): evaluate error: {str(_ee)[:120]}"}
        if dec == "DENY":
            return {"ok": False, "error": f"GPS-2 DENY: {reason}"}
        if dec == "ESCALATE":
            prior = None
            try:
                prior = _OCPApprovals().check(nm, ag)
            except Exception:
                pass
            if prior == "DENY":
                return {"ok": False, "error": f"GPS-2: operator previously DENIED '{nm}' for these args"}
            if prior not in ("ALWAYS", "ALLOW"):
                return {"ok": False, "error": (
                    f"GPS-2 HUMAN GATE: '{nm}' is irreversible and has no standing approval. "
                    f"Ask the operator to approve it once in the SkynetClaw UI "
                    f"(run a task that uses {nm} → click 'approve-tool'), or add it to the "
                    f"allow list in backend/governance_config.json and restart the backend.")}
    try:
        result = await exec_tool(nm, ag)
        print(f"[MCP] {req.operator} → {nm}({str(ag)[:120]}) ok")
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n"+"="*52)
    print("  * SkynetClaw Backend v5")
    print(f"  Tools: {len(BUILTIN_TOOLS)} built-in")
    print("  URL : http://localhost:8766")
    print("  Docs: http://localhost:8766/docs")
    print("="*52+"\n")
    # SEC C1: bind loopback by default (was 0.0.0.0 → reachable from the whole LAN).
    # Override with SKYNET_HOST only if you explicitly need remote access.
    _host = os.environ.get("SKYNET_HOST", "127.0.0.1")
    print(f"  Bind: {_host}:8766  (exec endpoints: {'ON' if os.environ.get('SKYNET_ENABLE_EXEC')=='1' else 'OFF'})")
    # Supervise the execution runtime (:8080) for the backend's lifetime. The
    # watchdog was the confirmed 'stays dead' cause — it exists but wasn't running.
    # It self-locks (singleton), so this is safe even if one is already up.
    try:
        if os.environ.get("SKYNET_NO_WATCHDOG") != "1":
            import subprocess as _sp
            _wd = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "execution_watchdog.py")
            if os.path.exists(_wd):
                _wflags = (_sp.CREATE_NEW_PROCESS_GROUP | getattr(_sp, "DETACHED_PROCESS", 0)) if os.name == "nt" else 0
                _sp.Popen([sys.executable, _wd], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, creationflags=_wflags)
                print("  Watchdog: execution-runtime supervisor started (:8080 auto-recover)")
    except Exception as _we:
        print(f"  Watchdog: auto-start skipped ({_we})")
    # The OS façade must reflect reality: the subsystems run from process
    # start, so the OS boots WITH the process. Before this, every backend
    # restart left services reporting "stopped" (in-memory state=halted)
    # until someone remembered to press boot — the Node Map showed a red
    # column for a House that was actually alive.
    try:
        if os.environ.get("SKYNET_NO_OS_BOOT") != "1":
            import threading as _osb_th

            def _os_boot():
                try:
                    import time as _t2
                    _t2.sleep(3)          # let uvicorn bind first
                    import genesis_os as _gos
                    _r = _gos.get_os().boot()
                    print(f"  OS: booted with the process — services: {', '.join(_r.get('services', []))}")
                except Exception as _oe:
                    print(f"  OS: auto-boot failed: {_oe}")
            _osb_th.Thread(target=_os_boot, daemon=True, name="os-auto-boot").start()
    except Exception as _obe:
        print(f"  OS: auto-boot skipped ({_obe})")
    uvicorn.run(app, host=_host, port=8766, reload=False)
