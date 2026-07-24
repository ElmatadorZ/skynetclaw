# THE HOUSE — Institutional Memory

The House now remembers. Every council session is persisted, archived, scored,
and evaluated against reality. Agents accrue reputation from the accuracy of
their predictions, and the House measures its own performance over time.

Built on the existing stack (SQLite `skynerclaw.db`, the L5 Agent Council,
Obsidian integration). All modules are best-effort and degrade gracefully — if
institutional memory is unavailable the council still runs.

---

## 1. Architecture

```
                         ┌──────────────────────────────────────────┐
                         │            THE HOUSE (14 agents)          │
                         │  Commander · Atlas · Analyst · Strategist  │
                         │  Skeptic · Auditor · Governor · Architect  │
                         │  Scout · Storyteller · Concierge ·         │
                         │  Forecaster · Sentinel · Executor          │
                         └───────────────┬──────────────────────────┘
                                         │ run_council()  (agent_council.py)
                       _persist_council() │  ← auto-hook on EVERY run
                                         ▼
   ┌──────────────────────────  INSTITUTIONAL MEMORY  ──────────────────────────┐
   │                                                                            │
   │  house_constitution.py   7 permanent rules → injected into every agent     │
   │                                                                            │
   │  council_memory.py  ──save──►  CouncilSession (id, directive, participants,│
   │     │  from_verdict()          verdict, confidence, evidence, dissent)     │
   │     │  recall()  ◄── Historical Recall Layer (similarity over prior runs)  │
   │     ▼                                                                      │
   │  deliberation_archive.py ──►  SQLite  +  Obsidian: Council Archive/YYYY/MM/│
   │                                                                            │
   │  agent_reputation.py    quality(evidence/critique/forecast) + W/L/D + Elo  │
   │     ▲                                                                      │
   │     │ apply_outcome()                                                      │
   │  outcome_tracker.py     predictions → 7/30/90/180-day reviews → reputation   │
   │                                                                            │
   │  atlas_system_map.py    ATLAS V2 — 7 civilization layers, 2nd/3rd order    │
   │  obsidian_knowledge_protocol.py   SCOUT V2 — read/search/link/JD/MOC       │
   │                                                                            │
   │  institutional_db.py    one schema owner · connect() · ensure_schema()     │
   └───────────────────────────────────┬────────────────────────────────────────┘
                                        │ council_intelligence_api.py
                                        ▼
                 /api/council/*  ──►  Council Intelligence Dashboard
                 (memory · reputation · outcomes · archive · learning · constitution)
```

Data flow: a council deliberates → `_persist_council` saves the session, scores
each agent's contribution, and writes an archive note → later, predictions are
reviewed at 7/30/90/180 days → results update agent reputation → the dashboard and
the Historical Recall Layer expose what the House has learned.

---

## 2. Folder tree

```
backend/
├── institutional_db.py              # schema owner: connect, ensure_schema, rollback
├── council_memory.py                # PART 1 Council Memory Engine + Historical Recall
├── deliberation_archive.py          # PART 2 archive → SQLite + Obsidian
├── house_constitution.py            # PART 3 seven permanent rules + compliance check
├── agent_reputation.py              # PART 4 reputation (quality + W/L/D + Elo)
├── outcome_tracker.py               # PART 5 7/30/90/180-day outcome reviews
├── atlas_system_map.py              # PART 6 ATLAS V2 — 7 civilization layers
├── obsidian_knowledge_protocol.py   # PART 7 SCOUT V2 — executable vault protocol
├── council_intelligence_api.py      # PART 9 FastAPI router  (register(app))
├── council_dashboard.html           # PART 8 Council Intelligence Dashboard
├── migrate.py                       # PART 9 migration runner (up / down / status)
├── migrations/
│   ├── 001_institutional_memory.up.sql
│   └── 001_institutional_memory.down.sql
├── tests/
│   ├── conftest.py
│   └── test_institutional_memory.py # 48 tests · 92% coverage
└── INSTITUTIONAL_MEMORY.md          # this file
```

Wiring (already applied):
- `agent_council.py` → `_persist_council()` runs on every `run_council`.
- `main.py` → `council_intelligence_api.register(app)` + House Constitution
  injected into every `agent_run`.

---

## 3. Database schema (in `skynerclaw.db`)

```
council_sessions(id PK, ts, directive, participants[json], verdict, confidence,
                 evidence_summary, dissent_summary, model, created_at)
council_contributions(id PK, session_id FK→sessions, agent, role, stance,
                 confidence, evidence_quality, critique_quality, forecast_quality,
                 note, created_at)
deliberation_archive(id PK, session_id FK, date, question, agents[json],
                 reasoning_summary, final_verdict, confidence, predicted_outcome,
                 obsidian_path, created_at)
agent_reputation(agent PK, score, wins, losses, draws, n_predictions, n_correct,
                 accuracy_rate, forecast_quality, evidence_quality,
                 critique_quality, updated_at)
predictions(id PK, session_id FK, agent, statement, predicted_outcome,
                 invalidation, confidence, made_at, due_30, due_90, due_180,
                 review_30, review_90, review_180, status, evaluated_at)
schema_migrations(version PK, name, applied_at)

Indexes: sessions(ts), contributions(agent), contributions(session_id),
         archive(date), archive(session_id), predictions(status),
         predictions(agent), predictions(due_30), reputation(score)
```

Foreign keys cascade (`contributions`) or null-out (`archive`, `predictions`) on
session delete. Rollback drops only institutional tables — never the pre-existing
app tables.

---

## 4. Migrations

```bash
python migrate.py up           # apply pending migrations (idempotent)
python migrate.py status       # show applied versions
python migrate.py down 001     # roll back migration 001
```

`institutional_db.ensure_schema()` also self-heals the schema on boot, so the app
works even if migrations were never run manually.

---

## 5. Tests

```bash
cd backend
python -m pytest tests/ -q                      # 48 tests
python -m pytest tests/ --cov=council_memory --cov=agent_reputation \
   --cov=outcome_tracker --cov=deliberation_archive --cov=house_constitution \
   --cov=atlas_system_map --cov=obsidian_knowledge_protocol \
   --cov=council_intelligence_api --cov=institutional_db --cov-report=term-missing
```

Coverage: **92%** (unit · integration · routing · database · memory-retrieval ·
forecast-evaluation). Tests use an isolated temp DB (`INSTITUTIONAL_DB` env) and
never touch production data.

---

## 6. API

```
GET  /api/council/memory/recent?limit=
GET  /api/council/memory/recall?q=            # Historical Recall Layer
GET  /api/council/memory/{id}
GET  /api/council/memory/stats
GET  /api/council/reputation?limit=
GET  /api/council/reputation/best-worst
GET  /api/council/outcomes/summary
GET  /api/council/outcomes/recent
GET  /api/council/outcomes/due/{30|90|180}
POST /api/council/outcomes/{pid}/evaluate      {horizon, result}
GET  /api/council/archive/recent
GET  /api/council/constitution
GET  /api/council/learning                     # consensus + confidence trends
GET  /api/council/dashboard                    # the dashboard UI
```

The dashboard (`/api/council/dashboard`) replaces the static council screen with
live panels: Institutional Learning, Agent Reputation, Prediction Outcomes,
Council Memory, Deliberation Archive, Best Performing, Recent Failures/Successes.

---

## 7. The Constitution (loaded by every agent)

```
R1 Evidence before opinion          R5 Minority opinions preserved
R2 No fabricated data               R6 Historical comparisons required
R3 State uncertainty explicitly     R7 Source traceability mandatory
R4 Forecasts require invalidation conditions
```

`house_constitution.check_compliance(text)` scores any deliberation against these
rules; a verdict scoring < 0.5 is flagged invalid.
