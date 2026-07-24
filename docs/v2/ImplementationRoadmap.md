# Implementation Roadmap

> Concrete, sequenced work to build the V2 AIOS on top of the existing codebase. Maps
> the [MigrationPlan](MigrationPlan.md) phases to deliverables, owners-of-truth, and
> done-criteria. Avoids overengineering: one process, in-proc bus, SQLite.
> Parent: [Architecture](Architecture.md)

## 1. Milestones
| M | Theme | Flags introduced | Outcome |
|---|---|---|---|
| **M0** | Foundations | — | DI container, flags, engine shells, interfaces |
| **M1** | See everything | — | Telemetry facade + spans on all existing paths |
| **M2** | One runtime door | `runtime_orchestrator` | all model calls via orchestrator; fallback works |
| **M3** | One governance door | `governance_v2` | every action passes the unified gate; audit log |
| **M4** | Visible execution | `execution_engine` | agent state machine + workflow DAG path |
| **M5** | Missions are real | `mission_engine` | missions admitted/planned/executed/tracked |
| **M6** | Councils decide | `council_engine` | hierarchy, opinions, voting, review |
| **M7** | Unified memory | `knowledge_graph` | KG + working/long-term + retrieval |
| **M8** | Self-learning | `reflection_engine` | post-mission reflection → memory (+gated evolution) |
| **M9** | Mission-first UI | `dashboard_v2` | new dashboard; node map secondary |
| **M10** | Tidy | — | physical relocation into `engines/*` w/ shims |

## 2. Workstream detail
### M0 — Foundations
- `core/di.py` (container, constructor injection), `core/flags.py` + `config/flags.yaml`.
- Empty `engines/*/` packages exporting Protocols from the architecture docs.
- **Done when:** container builds all engines wired to V1 implementations; all flags off; app behaves exactly as today.

### M1 — Observability
- `core/telemetry.py` facade over `telemetry.py`/`observability.py`; ring buffer + `runtime_metrics.db`.
- Instrument existing seams: tool calls, LLM calls, agent runs.
- Endpoints `/api/observability/*`. **Done when:** token/latency/cost/failure visible for current V1 flows.

### M2 — Runtime Orchestrator
- Wrap `runtime_kernel`/`runtime_router`/`runtime_registry`; implement routing policy, health TTL cache, fallback, circuit breaker, cost table.
- Flag routes `_llm_stream` → orchestrator. **Done when:** kill the local server → request auto-falls back to a configured cloud runtime; flag off restores direct path.

### M3 — Governance v2
- `GovernanceGate` unifying `os_permissions.require` + `governance.GPS2Gate` + `skynetclaw_meta.shadow_gate`; single `gate(action, ctx)`.
- Audit log table + `/api/governance/audit`. **Done when:** no tool/runtime/memory write reaches a side effect without a gate decision; denials produce BLOCKED + reason.

### M4 — Execution Engine
- Agent loop → state machine (PLANNING…FINISHED); emit `agent.state`.
- Run plans via `workflow/` DAG; pause/resume/idempotent resume. **Done when:** dashboard can show live per-agent state for a run; parity with V1 outputs.

### M5 — Mission Engine
- Extend `house_state` schema (additive); `MissionEngine.admit/plan/execute/advance/complete`.
- `/api/agent/run` wraps requests as quick-missions. **Done when:** a request creates a tracked mission with completion %, timeline, log; V1 chat still works.

### M6 — Council Engine
- Tier/authority/veto config (`council.yaml`); deliberation protocol (convene→gather→debate→vote→decide→review) over the 14-agent roster.
- **Done when:** a mission plan is produced by a recorded vote with dissent captured; Skeptic veto path works.

### M7 — Knowledge Graph + Memory
- `knowledge_graph.db` (nodes/edges/embeddings); `KnowledgeGraph` + `MemoryService` (working TTL + long-term versioned).
- Idempotent importer for existing stores; four retrieval modes. **Done when:** memory hit-ratio metric live; no duplicate facts on re-import.

### M8 — Reflection Engine
- On `mission.completed/failed`: answer the 7 questions; auto remember/forget + calibration; emit gated evolution proposals.
- **Done when:** completing a mission writes versioned lessons; a proposal appears as an approval card and applies only on approval.

### M9 — Dashboard v2
- Missions view (default), council/thinking/execution/knowledge/memory/reflection/logs/metrics panels; per-mission WS; node map → System tab.
- **Done when:** operator runs a mission and watches it end-to-end without reading server logs.

### M10 — Relocation
- Move modules into `engines/*` with re-export shims; deprecate old paths next release.

## 3. Sequencing rationale
Observability (M1) before behavior changes so every later phase is measurable.
Runtime + Governance (M2–M3) are the load-bearing kernels every other engine depends
on. Execution (M4) before Mission (M5) so missions have something concrete to run.
Council (M6) shapes plans Execution already runs. Memory (M7) before Reflection (M8)
because reflection writes to it. Dashboard (M9) last, once there are real missions to
show. Relocation (M10) only after everything is proven.

## 4. Definition of done (whole program)
- All engines on-by-default, V1 fallbacks retained one release.
- A mission can be created, governed, planned by a council, executed as a visible
  state-machine workflow over the best available runtime, recorded in the knowledge
  graph, reflected on, and shown mission-first in the dashboard — **with no V1
  capability lost.** That is the AIOS.
