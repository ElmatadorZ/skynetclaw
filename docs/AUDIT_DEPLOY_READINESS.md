# SkynetClaw — Deploy Readiness Audit
**First Principle + System Thinking · macro-level**

---

## 1. First-Principle Reduction

**What is this system, stripped to fundamentals?**

```
User intent → text → LLM → tool calls → side-effects → text → User
```

Everything else is scaffolding around this loop.

The 5 immutable atomic units:

| Atom | Reality |
|---|---|
| Intent | Text typed by Operator |
| LLM | Local Ollama model — finite memory, finite speed |
| Tools | Side-effect functions (filesystem, web, shell, obsidian) |
| State | SQLite + JSONL logs + .md prompts |
| Response | Streaming text back to Operator |

Every failure mode collapses to ONE of:
- intent unclear → wrong tool
- LLM hallucinates tool name → silent fail
- tool execution errors → loop or stall
- state corrupted → desync between UI ↔ backend
- response stalls → user thinks "broken"

---

## 2. System Architecture (current layers)

```
L5 ▸ PERSISTENCE     skynerclaw.db · chat_history.db · audit.jsonl · bridge_log.jsonl · atlas_genome.json
L4 ▸ UI SURFACES     SkynetClaw Chat (index.html) · THE_CONTINENTAL_DIVISION.html · bridge_console.html
L3 ▸ ORCHESTRATION   /api/agent/run iteration loop · continental_relay · agentic_workflow · agent_council
L2 ▸ COGNITION       prompts/* · skills_auto_router · genesis_router · ecosystem_manifest (NEW)
L1 ▸ BACKEND         FastAPI on :8766 · Ollama HTTP · 15+ Python modules
L0 ▸ OS              Windows / D:\ · Python 3.10 · Ollama runtime
```

---

## 3. Production-Readiness Scorecard

| Dimension | Score | Note |
|---|---|---|
| Functional correctness | 7/10 | Core loop works · interrupt + timeout · ecosystem aware now |
| Observability | 4/10 | Bridge log + audit chain ✓ · no structured logs · no metrics |
| Reliability | 5/10 | Watchdog ✓ · timeout ✓ · no health check · no graceful shutdown |
| Testability | 2/10 | No test suite · no CI · manual verification only |
| Security | 3/10 | CORS ★ · no auth · no rate limit · runs as local user |
| Configurability | 3/10 | Port/path/model hardcoded · no .env · no profile system |
| Documentation | 5/10 | README ✓ · INSTALL ✓ · no DEPLOY.md · no RUNBOOK |
| Maintainability | 4/10 | main.py 5,000 lines monolith · 15 sidecar modules · no module boundaries |
| Recoverability | 3/10 | DB backup chain ✓ · no manifest sync · no schema migration framework |
| Release pipeline | 1/10 | No versioning · no CI · no build · no release notes |

**Aggregate: 37/100 — not deploy-ready as open-source product. Functional as local-dev tool.**

---

## 4. Gap Analysis (the 12 deploy blockers)

### Critical (must fix before any deploy)

1. **No comprehensive health endpoint** → ops can't see what's up
2. **No smoke test** → no way to verify a change didn't break the pipeline
3. **Port/path hardcoded** → can't run alongside other services
4. **No graceful shutdown** → Ctrl+C may leave corrupted state
5. **No auth/rate limit** → `POST /api/agent/run` is open to anything on LAN
6. **No structured logging** → `print()` everywhere, can't aggregate

### Important (fix in v6)

7. **main.py is 5,000+ lines** → un-PR-able · split into routers
8. **No versioned API** → breaking change breaks all 3 surfaces
9. **No service worker / offline UI** → flaky on local network
10. **No DB schema migrations** → ALTER TABLE in code is fragile
11. **No metrics endpoint** (`/metrics` prom-style) → no SLO tracking
12. **No browser-side error boundary** → one JS error nukes the whole tab

---

## 5. System Thinking — Feedback Loops

### Loop 1 — Bridge log → Insights → Operator
✓ Working. CBP envelopes → feedback_engine → /bridge console

### Loop 2 — Reflection → Genome → Next mission
⚠ Partial. agentic_workflow writes proposals but Genome rules not actively re-injected.

### Loop 3 — Manifest → SELF.md → System prompt
✓ Just added. Validate by chatting "อธิบาย ecosystem".

### Loop 4 — Issue detection → Auto-patch
✗ Missing. feedback_engine emits issues but no automated remediation.

### Loop 5 — Smoke test → Block bad commit
✗ Missing. No test gate. Every change is "deploy and pray".

---

## 6. Prioritized Roadmap to Deploy

**P0 — ship in this round (today)**
- `health_check.py` — `/api/system/health` reports every subsystem status
- `smoke_test.py` — verifies the 5-atom loop end-to-end
- This audit doc

**P1 — next round**
- `.env` configuration (port, paths, model defaults)
- Split main.py into `routers/` (chat, agent, continental, skills, ...)
- Structured logging via `logging` module (replace `print`)
- Schema migration framework (Alembic-style)

**P2 — for v6 public**
- API key auth on mutating endpoints (`POST /api/agent/run`, `POST /api/files/write`)
- Rate limit (in-memory token bucket)
- Versioned API (`/api/v1/...`)
- Browser error boundary + service worker
- Metrics `/metrics` endpoint
- Release pipeline (git tag → version bump → changelog)

---

## 7. Operating Philosophy (what this product IS)

SkynetClaw is **a local autonomous agent for a single operator** — not SaaS, not multi-tenant.

Therefore:
- ✓ Auth optional (local LAN trust)
- ✓ Monolithic backend OK (no microservices)
- ✓ SQLite OK (not Postgres)
- ⚠ But **observability MANDATORY** — operator must SEE what the agent is doing
- ⚠ **Recoverability MANDATORY** — agent acts on operator's filesystem; must rollback
- ⚠ **Audit chain MANDATORY** — every action traceable (CBP already does this)

Deploy-readiness for this category = a developer can `git clone && pip install && python main.py` and have a working agent on their machine, with clear logs, working health check, and one-shot smoke test.

---

*Generated: see `git log` · revisit after each major change.*
