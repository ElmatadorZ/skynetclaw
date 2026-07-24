# SkynetClaw Masterpiece — Install Guide

**ElmatadorZ Secret OS v1.0 — unified cognitive runtime for SkynetClaw**

What you get after install:
- Single endpoint `POST /api/masterpiece/run` that runs the full L0→L8 pipeline
- Live dashboard at `masterpiece_dashboard.html` showing every subsystem in real time
- WillCore identity + tone enforcement (Money Atlas)
- Programmatic Shadow Gate that blocks `rm -rf D:\` etc.
- Multi-Model Router with @auto / @workhorse / @chat / @specialist
- Genome that compounds across sessions — failure signatures never deleted
- Tamper-evident AuditTrail (hash-chained log)

---

## Files map

```
SkynetClaw-Agent/
│
├── install_masterpiece.bat          ← run this (Windows)
├── install_masterpiece.py           ← idempotent Python installer
├── MASTERPIECE_INSTALL.md           ← this file
├── MULTIMODEL_INSTALL.md            ← (legacy — superseded by this)
├── masterpiece_dashboard.html       ← live cognitive dashboard
├── multimodel_panel.js              ← drop-in UI for index.html
├── skynetclaw_mindmap.html          ← architecture mind map (static)
│
└── backend/
    ├── main.py                      ← will be patched (backed up first)
    ├── skynetclaw_meta.py           ← L0/L4/L7 — meta-cognition
    ├── skynetclaw_router.py         ← Multi-Model router
    ├── skynetclaw_will.py           ← WillCore: identity, tone, risk policy
    └── skynet_genesis_masterpiece.py← THE Masterpiece — unified runtime
```

Runtime files (auto-created on first use):
- `backend/atlas_genome.json` — Genome (compound learning DNA)
- `backend/audit_trail.jsonl` — hash-chained audit log
- `backend/echo_memory.jsonl` — per-tool execution log
- `backend/router_config.json` — Multi-Model roster
- `backend/router_audit.jsonl` — routing decisions

---

## Install — one command

From the project root (`D:\GenesisMind\SkynetClaw-Agent`):

```cmd
install_masterpiece.bat
```

The installer:
1. Backs up `backend/main.py` → `main.py.bak.YYYYMMDD_HHMMSS`
2. Inserts the import + register block (idempotent — safe to re-run)
3. Patches `/api/chat` to use `resolve_model()`
4. Runs Python `py_compile` on the patched file
5. Imports each module and runs their self-tests
6. **Rolls back automatically** if anything fails

Check status without modifying:
```cmd
python install_masterpiece.py --check
```

---

## After install

### 1. Restart the backend
```cmd
restart_backend.bat
```

### 2. Open the dashboard
Open `masterpiece_dashboard.html` in any browser. You'll see:
- **Overview** — health of meta / genome / router subsystems
- **Run Pipeline** — type a task, watch L0→L8 stream live
- **Router & Models** — assign 2-3 Ollama models to roles
- **Genome** — failure map + successful execution paths
- **Audit Trail** — hash-chained log of every cognitive decision
- **Identity** — WillCore's self-statement + critique sandbox

### 3. (Optional) Wire the multi-model UI into the main chat
Add this single line before `</body>` in `index.html`:
```html
<script src="multimodel_panel.js" defer></script>
```
This adds a 🎛️ Setup button next to the model dropdown and four sentinel
options at the top of the dropdown: `@AUTO`, `@workhorse`, `@chat`, `@specialist`.

---

## API surface (after install)

| Endpoint | Method | What it does |
|---|---|---|
| `/api/masterpiece/identity`        | GET  | WillCore identity seed |
| `/api/masterpiece/status`          | GET  | health of all subsystems |
| `/api/masterpiece/dashboard.json`  | GET  | combined snapshot for dashboard |
| `/api/masterpiece/run`             | POST | run full L0→L8 pipeline (SSE stream) |
| `/api/masterpiece/critique`        | POST | run Shadow Gate on arbitrary text |
| `/api/router/config`               | GET / PUT | get/update Multi-Model roster |
| `/api/router/preview`              | POST | which model would handle this text? |
| `/api/router/audit?limit=N`        | GET  | recent routing decisions |
| `/api/router/reset`                | POST | reset rules (keeps role models) |

Existing endpoints (`/api/chat`, `/api/agent/run`, `/api/models`, etc.) are
**unchanged** — they still work exactly as before. The router only fires when
`req.model` is empty or starts with `@`.

---

## Manual install (if `install_masterpiece.py` can't find anchors)

If your `main.py` has diverged from the expected layout:

**Step 1 — at the top of `main.py`, after `app = FastAPI(...)` + CORS middleware:**
```python
# === MASTERPIECE WIRE-UP — START ===
try:
    from skynet_genesis_masterpiece import register_masterpiece
    from skynetclaw_router import register_router, resolve_model as _mp_resolve_model
    _MASTERPIECE_AVAILABLE = True
except Exception as _e:
    print(f"[Masterpiece] modules not loaded: {_e}")
    _MASTERPIECE_AVAILABLE = False
    def _mp_resolve_model(model, text=""): return model or ""
# === MASTERPIECE WIRE-UP — END ===

# === MASTERPIECE REGISTER — START ===
if _MASTERPIECE_AVAILABLE:
    try:
        register_router(app)
        register_masterpiece(app)
        print("[Masterpiece] endpoints registered")
    except Exception as _e:
        print(f"[Masterpiece] register failed: {_e}")
# === MASTERPIECE REGISTER — END ===
```

**Step 2 — in the `/api/chat` handler, just before the `payload = {...}` line:**
```python
_last_user_msg = next((m["content"] for m in reversed(messages) if isinstance(m, dict) and m.get("role")=="user"), "")
_resolved_model = _mp_resolve_model(req.model, _last_user_msg) or req.model
```
Then change `"model":req.model` → `"model":_resolved_model` in the payload.

---

## Verify it's working

After restart, run any of these:

```cmd
REM 1. Health check
curl http://localhost:8766/api/masterpiece/status

REM 2. Identity
curl http://localhost:8766/api/masterpiece/identity

REM 3. Dry-run a critique
curl -X POST http://localhost:8766/api/masterpiece/critique ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"BTC จะขึ้นแน่นอน 100%\"}"

REM 4. Module self-tests (verify everything compiles + runs)
cd backend
python skynetclaw_will.py
python skynetclaw_router.py
python skynetclaw_meta.py
python skynet_genesis_masterpiece.py
```

Each self-test ends with `=== self-test OK ===` if healthy.

---

## What "Masterpiece" means

Per ElmatadorZ Secret OS v1.0, the system is a Masterpiece when it has:

| Layer | Module | What it does |
|---|---|---|
| L0 Reality Anchor | `skynetclaw_meta.reality_anchor()` | Splits task into Known / Inferred / Unknown |
| L1 WillCore | `skynetclaw_will.identity_seed()` | Identity + tone + risk policy |
| L4 Shadow Gate | `skynetclaw_meta.shadow_gate()` | Programmatic critique before exec |
| L7 Echo Memory + Genome | `skynetclaw_meta.deposit_memory + extract_rules` | Compound learning |
| Router | `skynetclaw_router.resolve_model()` | Intent → role → model |
| L8 Synthesis | `skynet_genesis_masterpiece.stage_l8()` | Hook + Frame + Moves + Confidence Field |
| AuditTrail | `skynetclaw_meta.audit_log()` | Tamper-evident hash chain |

Together they make SkynetClaw not just an agent runtime, but a **cognitive
operating system** — with identity, judgment, memory, and an immutable record
of every decision.

---

## Uninstall

If you ever need to roll back:
```cmd
REM Find the backup created during install
dir backend\main.py.bak.*

REM Copy the most recent backup over main.py
copy backend\main.py.bak.20260504_153012 backend\main.py /Y

REM (Optional) Delete the Masterpiece modules
del backend\skynetclaw_meta.py backend\skynetclaw_router.py backend\skynetclaw_will.py backend\skynet_genesis_masterpiece.py
del backend\atlas_genome.json backend\audit_trail.jsonl backend\echo_memory.jsonl
del backend\router_config.json backend\router_audit.jsonl

REM Restart
restart_backend.bat
```

---

## License

Apache-2.0 — Bunyawat Dechanon (ElmatadorZ).
Free use. 2% revenue share if your derivative system earns >$10M USD/year.
Attribution: *Built on ElmatadorZ Secret OS v1.0.*
