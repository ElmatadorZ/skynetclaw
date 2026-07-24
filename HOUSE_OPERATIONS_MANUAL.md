# THE HOUSE — OPERATIONS MANUAL

> Operational runbook for **SkynetClaw-Agent / THE HOUSE**. This document lets a
> future operator run the House without the original builder. No code knowledge
> required — only the procedures below.

---

## 0 · System At A Glance

| Thing | Value |
|-------|-------|
| Backend | `backend/main.py` → uvicorn on **`0.0.0.0:8766`** |
| LLM engine | **Ollama** at `http://localhost:11434` |
| Default/active model | `settings.json` → `active_model` (recommend **`SkynetClaw:latest`** 33B) |
| Institutional DB | `backend/skynerclaw.db` (SQLite, WAL) |
| Other DBs | `chat_history.db`, `data.db`, `openclaw.db` |
| Audit logs | `audit_trail.jsonl`, `bridge_log.jsonl`, `continental_audit.jsonl`, `router_audit.jsonl` |
| Operator UIs | `THE CONTINENTAL DIVISION.html` · Council Intelligence at `http://localhost:8766/api/council/dashboard` |
| Event bus | `GET /api/house/events` (SSE) — the single source of runtime truth |
| Health | `GET /api/system/health` (full) · `/api/system/health/quick` (liveness) |
| Obsidian vault | `settings.json` → `vault_path` |

**Architecture in one line:** Runtime → Council → Reasoning → House Mind → Timeline → Mission → Learning → Policy, all flowing through **one event bus** (`house_sync.publish` → `/api/house/events`) over **one DB**. See `backend/ARCHITECTURE.md` for the full map.

---

## 1 · System Startup

**Purpose:** bring the House online and ready for directives.

**Normal Operation**
1. Ensure **Ollama is running** and the model is pulled:
   `curl -s http://localhost:11434/api/tags` should list `active_model`.
2. Confirm `backend/settings.json` has a valid `active_model` and `vault_path`.
3. Start the backend: from `backend/`, run **`python main.py`** (serves `:8766`).
4. Wait for the boot banner lines (`[HouseSync] … mounted`, `[Council] … loaded`, `[Health] mounted`).
5. Verify: `GET /api/system/health/quick` returns alive; open the Continental UI; the model selector shows `active_model`.

**Failure Symptoms**
- Backend exits immediately → bad `settings.json` or port `8766` already in use.
- UI loads but every directive returns an error → Ollama down or model not pulled.
- `[HouseSync] mount failed` in console → import error; backend partially up.

**Recovery Actions**
- Port in use: stop the previous instance (find the process on `:8766`) and restart.
- Ollama down: start Ollama, `ollama pull <model>`, retry a directive.
- Bad settings: restore from the **settings backup chain** (see §7), restart.

**Escalation Path:** console boot log → `GET /api/system/health` (full report) → check Ollama logs → re-pull model.

---

## 2 · System Shutdown

**Purpose:** stop the House without losing state.

**Normal Operation**
1. Ensure no mission is mid-execution (Continental chamber idle; no live `mission_started` without `mission_updated`).
2. Stop the backend process (Ctrl-C / terminate). SQLite WAL checkpoints on clean close.
3. Optionally back up DBs (see §7) before maintenance.

**Failure Symptoms**
- Hard kill during a write → WAL `-wal`/`-shm` sidecar files remain (normal; SQLite recovers on next open).

**Recovery Actions**
- On next startup SQLite auto-recovers the WAL. If a DB is suspected corrupt, restore from backup (§7/§8).

**Escalation Path:** clean stop preferred; only hard-kill if the process is unresponsive after a watchdog window (~25 min max per run).

---

## 3 · Model Configuration

**Purpose:** select the reasoning engine.

**Normal Operation**
- Models live in Ollama. Set the House model in `settings.json` (`model` + `active_model`) **or** via the UI model selector (syncs cross-tab via `/api/house/state`).
- **Recommended: a capable model for the council** (`SkynetClaw:latest` / `nemotron3:33b`). Small models (e.g. `qwen3.5:9b`) work for tools/chat but **may emit empty reasoning under the council's enriched context** (known limitation §11).

**Failure Symptoms**
- Council members show empty reasoning / blank deliberation map → model not conforming to strict-JSON under load (usually a too-small model).
- First-token latency very high → large model cold-start (normal up to a few minutes on a 33B).

**Recovery Actions**
- Switch `active_model` to a larger model; re-run the directive.
- Keep the model warm (`keep_alive` is set to 30m in requests).

**Escalation Path:** verify the model alone with `/api/system/health` → test a single role via a simple directive → upgrade model.

---

## 4 · Mission Operations

**Purpose:** run a directive end-to-end and observe it.

**Normal Operation**
1. Issue a directive in the **Continental** command bar (or POST `/api/continental/dispatch`).
2. Watch live: seats illuminate (READING/SEARCHING/EXECUTING), the network conduits pulse, the chamber fills.
3. In **Council Intelligence**, House Mind shows Objective/Belief/Confidence; Mission Center shows health (evidence/reasoning/risks).
4. Mission ends in exactly one terminal state: **SUCCESS / FAILED / LIMIT / CANCELLED** (a `done` event with `final_status`).

**Failure Symptoms**
- Continental "frozen" during execution → it is being driven by the bus; if truly idle, the relay is down and it fell back to direct dispatch (still functional; events publish at the source).
- "Operative went silent" / "context overload" → should **not** occur in normal operation (auto-recovery handles it). If seen repeatedly, the model is degrading.

**Recovery Actions**
- The loop **auto-recovers** on context-critical (emits `mission_recovered`, compresses to a snapshot, continues). No operator action needed.
- If a mission hangs past the **25-minute watchdog**, it self-halts with a reported outcome.
- To stop a mission: use the Continental "stand down" / abort.

**Escalation Path:** watch `/api/house/events` for `tool_failed` / `budget_critical` / `mission_recovered` → check the transcript → if the model is the issue, upgrade model (§3).

---

## 5 · Council Operations

**Purpose:** six-specialist deliberation (Analyst, Strategist, Skeptic, Forecaster, Executor, Storyteller).

**Normal Operation**
- Triggered for complex/ambiguous directives (council mode / `/api/workflow/run`). Members run in **parallel**; each emits verbatim `reasoning_*` events (one event per fact — single source of truth).
- Watch the **Deliberation Map** (Live Council tab): consensus cluster, challenge cluster, minority, and **consensus strength** (derived from the real Skeptic verdict: CONSISTENT 85 / FRAGILE 55 / REBUILD 25).
- A `REBUILD` verdict halts before execution by design.

**Failure Symptoms**
- Six members complete but reasoning panels stay empty → model JSON non-conformance (§3, §11).
- Council slow → 6 LLM calls **serialize on one GPU**; latency ≈ 6 × single-call. Normal.

**Recovery Actions**
- Empty reasoning → upgrade model and re-run.
- Slow → expected on one GPU; no action.

**Escalation Path:** Live Council cards show per-member status; if one member errors it degrades gracefully (empty role) — re-run if needed.

---

## 6 · Recovery Procedures

**Purpose:** the House should recover from failure without halting.

**Normal Operation (automatic)**
- **Context budget**: measured before every model call. On **critical** (~88% of window), the loop compresses old tool output into a factual mission snapshot and **continues** — never overflows.
- **Tool failures** (timeout, missing file, nonzero exit, network error) are caught and surfaced as `tool_failed`; the loop adapts.
- **Watchdog**: 25-minute wall-clock cap per run guarantees a terminal state.

**Failure Symptoms**
- Repeated `budget_critical` + `mission_recovered` on every step → context churn (very long mission or verbose tools); still safe, just slower.
- A run that produced zero output → model/provider returned errors all run (check model).

**Recovery Actions**
- Usually none — recovery is automatic.
- If the backend itself is wedged: clean restart (§1). In-flight mission state is persisted to `agent_runs`/`house_state`.

**Escalation Path:** `/api/house/events` (`mission_recovered` count) → transcript → model upgrade if churn is model-driven.

---

## 7 · Backup Procedures

**Purpose:** protect institutional memory and settings.

**Normal Operation**
- **Settings**: `settings.json` is auto-rotated through a backup chain on every save (`SettingsBackupChain`). Safe-load falls back to the last good copy.
- **Databases (manual, recommended weekly)**: with the backend **stopped** (or after a clean WAL checkpoint), copy:
  - `backend/skynerclaw.db` (+ `-wal`, `-shm` if present) — **the institutional memory (critical)**
  - `backend/chat_history.db`, `data.db`, `openclaw.db`
- **Audit logs**: `*.jsonl` are append-only; archive periodically.

**Failure Symptoms**
- Settings reverted unexpectedly → safe-load used a backup (a save was corrupt).

**Recovery Actions**
- Restore a DB: stop backend → replace the `.db` (and remove stale `-wal`/`-shm`) with the backup → restart.

**Escalation Path:** keep ≥7 daily DB backups; verify a restore quarterly.

---

## 8 · Database Maintenance

**Purpose:** keep SQLite healthy and bounded.

**Normal Operation**
- DB is SQLite **WAL** (single-writer). Growth tables: `predictions`, `belief_changes`, `state_items`, `agent_runs`, `council_*`.
- Monthly: check `skynerclaw.db` size; run a `VACUUM` (backend stopped) if it has grown large after archival.

**Failure Symptoms**
- DB file growing steadily over weeks → no rotation (expected; see §11).
- "database is locked" under heavy concurrent grading + runs → single-writer contention.

**Recovery Actions**
- Archive old rows (export then delete) before a 30-day run; `VACUUM` to reclaim space.
- Locking: reduce concurrency; WAL is already enabled.

**Escalation Path:** if corruption suspected → restore from backup (§7). Never edit the DB live during a mission.

---

## 9 · Architecture Overview (operator view)

- **One bus, one truth**: every runtime/cognitive fact is published **once** to `/api/house/events`; both UIs are views of that one stream.
- **Projections** (read-models over the DB) emit change events: `house_cognition` (House Mind), `belief_timeline` (Timeline), `mission_command` (Mission), `learning_engine` (Lessons), `house_os` (Policies). Their diff-baselines are **keyed per state/mission** → concurrent missions don't cross-talk.
- **State**: runtime/cognitive truth = event bus + `skynerclaw.db`. `house_sync._STATE` holds **only** UI prefs (model, connection).
- Full map: `backend/ARCHITECTURE.md`.

---

## 10 · Troubleshooting (symptom → cause → action)

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Directive errors instantly | Ollama down / model not pulled | start Ollama, `ollama pull`, retry |
| Continental seats never light | mission run outside the bus path OR no events | confirm backend up; check `/api/house/events` |
| Council reasoning empty | model too small for strict-JSON under load | switch `active_model` to 33B (§3) |
| "operative went silent" repeatedly | model degrading; recovery thrashing | upgrade model; check `mission_recovered` rate |
| Mission never ends | should hit 25-min watchdog | wait for self-halt; else restart backend |
| UI shows stale data | SSE dropped | reload tab (re-subscribes + replays recent events) |
| Backend won't start | port 8766 busy / bad settings | free port; restore settings (§7) |
| "database is locked" | single-writer contention | lower concurrency; retry |
| Memory creeping over days | unbounded projection baselines | restart backend (resets baselines) (§11) |

---

## Daily Checklist
- [ ] `GET /api/system/health/quick` → alive.
- [ ] Ollama up; `active_model` present in `/api/tags`.
- [ ] Run one trivial directive end-to-end → terminal `final_status` reached.
- [ ] Scan console for repeated `tool_failed` / `budget_critical`.
- [ ] Confirm Continental seats + Council Intelligence update live.

## Weekly Checklist
- [ ] Stop backend cleanly; **back up** `skynerclaw.db` (+ sidecars) and other `.db` files.
- [ ] Archive `*.jsonl` audit logs.
- [ ] Review Mission Center for stuck/failed missions; review Lessons tab.
- [ ] **Restart the backend** (clears in-memory projection baselines; neutralizes long-run growth).
- [ ] `GET /api/system/health` → full report green.

## Monthly Checklist
- [ ] Check `skynerclaw.db` size; archive old `predictions`/`belief_changes`/`agent_runs`; `VACUUM`.
- [ ] Verify a DB **restore** from a backup into a scratch copy.
- [ ] Re-run the test suites: `python backend/tests/test_reliability.py` and `test_concurrency.py` (both PASS).
- [ ] Optionally `RUN_REAL_COUNCIL=1 python backend/tests/test_production.py` against the live model.
- [ ] Review `ARCHITECTURE.md` vs reality; update if changed.

---

## Production Best Practices
1. **Pin a capable council model** (`SkynetClaw:latest`/33B). This is the single biggest reliability lever.
2. **Run single-operator, sequential (or lightly concurrent) missions** — the proven sweet spot.
3. **Restart weekly** until projection-baseline eviction is added (prevents slow memory growth).
4. **Back up `skynerclaw.db` weekly**; it is the institution's memory.
5. **Never edit DBs or `settings.json` while a mission is running.**
6. **Keep Ollama warm**; allow cold-start time for big models.
7. **Trust auto-recovery** — `mission_recovered`/`budget_critical` are healthy self-healing, not failures.
8. **Watch `/api/house/events`** as the single source of truth; if a UI disagrees, reload it (the bus is authoritative).

---

## Known Limitations
- **Single GPU** serializes the 6 council calls → council latency ≈ 6× a single call.
- **Small models** can emit empty reasoning under the enriched council context (use a 33B).
- **SQLite single-writer**: heavy concurrent grading + runs can contend ("database is locked").
- **In-memory projection baselines** are keyed but **not evicted** → slow memory growth over long uptimes (mitigation: weekly restart).
- **DB has no auto-rotation** → grows over time (mitigation: monthly archival + `VACUUM`).
- **Event bus is in-memory, single-process** → a synchronous burst beyond the subscriber queue could drop for a stalled client; no horizontal scaling (by design — one House).
- **PAUSED missions** are not supported (no real pause source) — the bucket is intentionally empty.
- **Not yet validated**: 30-minute continuous mission, 100k-file workspace, concurrent missions under real models, multi-user. Treat these as unproven envelopes.

---

## Escalation Summary
1. **Liveness** → `/api/system/health/quick`.
2. **Full diagnosis** → `/api/system/health`.
3. **Runtime truth** → `/api/house/events` (look for `tool_failed`, `budget_critical`, `mission_recovered`, `final_status`).
4. **Model issues** → Ollama `/api/tags`, upgrade `active_model`.
5. **State/DB issues** → stop, restore from backup, restart.
6. **Architecture reference** → `backend/ARCHITECTURE.md`.

*The House recovers itself by design. Most incidents resolve with: upgrade the model, or restart the backend, or restore the last DB backup.*
