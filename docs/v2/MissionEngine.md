# Mission Engine

> The Mission is the primary OS object — V2's "process". Everything else (councils,
> agents, skills, tools, runtimes, memory) exists to serve missions.
> Parent: [Architecture](Architecture.md) · Related: [CouncilEngine](CouncilEngine.md) ·
> [ExecutionStateMachine](ExecutionStateMachine.md) · [ReflectionEngine](ReflectionEngine.md)

## 1. Why a Mission is the root object
In V1 a user request maps to an *agent run* (`/api/agent/run`) — ephemeral, with no
durable identity, no lifecycle, no graph, no learning loop. V2 makes the **Mission**
the unit the whole OS schedules around. A mission is created once, governed once,
planned by a council, executed as a workflow, observed throughout, and reflected on
at the end. Every task, tool call, decision, and memory write **belongs to a mission**.

This is built on the **existing mission ledger** `house_state.py` (House Mind) and
`workflow_runs.py` — V2 formalizes their schema and lifecycle; it is not a rewrite.

## 2. Mission object (canonical schema)
```jsonc
{
  "id": "OX-...-N",                 // stable, human-readable
  "objective": "string",            // what success means in one sentence
  "constraints": ["read-only", "no external publish", "deadline 2026-07-01"],
  "priority": "low|normal|high|critical",
  "deadline": "ISO-8601 | null",
  "resources": {                    // declared budget — enforced by governance/runtime
    "max_tokens": 200000, "max_cost_usd": 1.0,
    "runtimes": ["execution","cloud-fallback"], "tools": ["*"], "skills": ["*"]
  },
  "success_criteria": [             // checkable predicates, drive completion %
    {"id":"sc1","desc":"report file exists","check":"file:workspace/out.html"},
    {"id":"sc2","desc":"contains >=10 sources","check":"assert"}
  ],
  "state": "DRAFT",                 // see §4 lifecycle
  "completion_pct": 0,              // derived from success_criteria + graph progress
  "graph": { "nodes": [], "edges": [] },   // the Mission Graph (sub-missions/tasks)
  "memory": { "working": "wm:OX-..", "longterm_refs": ["kg:.."] },
  "log": [ {"ts":..,"actor":"council","event":"plan.approved"} ],
  "timeline": [ {"phase":"planning","start":..,"end":..} ],
  "reflection": null,              // populated on completion by ReflectionEngine
  "council_id": "council:OX-..",   // the deliberating body
  "created_by": "user|agent|cron", "created_at": .., "updated_at": ..
}
```

## 3. Mission Graph
A mission decomposes into a DAG of **sub-missions and tasks** (the council's plan).
Nodes are tasks; edges are dependencies (`needs`, `then`, `or-fallback`). This graph
is the same structure the [Execution Engine](ExecutionStateMachine.md) compiles into
the workflow DAG (`workflow/ir.py` → `compiler.py` → leveled DAG). Completion % =
weighted fraction of satisfied `success_criteria` plus completed graph nodes.

## 4. Lifecycle (mission-level state machine)
```
DRAFT → ADMITTED → PLANNING → APPROVED → EXECUTING ⇄ BLOCKED/PAUSED
                                   ↓                      ↓
                                 REVIEW → REFLECTING → DONE
                                   ↓
                                 FAILED / CANCELLED  → REFLECTING → ARCHIVED
```
| Transition | Trigger | Owner |
|---|---|---|
| DRAFT→ADMITTED | governance risk-rates & admits | Governance Engine |
| ADMITTED→PLANNING | council convened | Council Engine |
| PLANNING→APPROVED | plan passes governance + (if needed) human gate | Governance |
| APPROVED→EXECUTING | execution engine starts the DAG | Execution Engine |
| EXECUTING⇄BLOCKED | missing resource / failed gate / awaiting input | Execution |
| EXECUTING→REVIEW | all critical nodes done | Execution |
| REVIEW→REFLECTING | success criteria evaluated | Reflection Engine |
| *→FAILED | unrecoverable error / budget exhausted | any |
| REFLECTING→DONE/ARCHIVED | reflection written to memory | Reflection |

Agent-level states (Planning/Researching/Coding/…) live in
[ExecutionStateMachine](ExecutionStateMachine.md); mission-level states are coarser.

## 5. Interfaces (SOLID + DI)
```python
class MissionStore(Protocol):              # persistence (house_state-backed)
    def create(self, m: Mission) -> str: ...
    def get(self, mid: str) -> Mission: ...
    def update(self, mid: str, **patch) -> None: ...
    def query(self, **filter) -> list[Mission]: ...

class MissionEngine:
    def __init__(self, store: MissionStore, bus: EventBus,
                 governance: GovernanceGate, council: CouncilEngine,
                 execution: ExecutionEngine, telemetry: Telemetry): ...
    def admit(self, draft: Mission) -> Mission       # → governance.admit
    def plan(self, mid: str) -> Plan                  # → council.deliberate
    def execute(self, mid: str) -> None              # → execution.run(graph)
    def advance(self, mid: str, node_result) -> None # updates graph + completion
    def complete(self, mid: str) -> None             # → reflection.run
```
All collaborators are **injected**; the engine never imports a runtime or a model.
It only emits/consumes events.

## 6. Events (on `os_ipc.EventBus`)
`mission.created`, `mission.admitted`, `mission.planning`, `mission.plan.approved`,
`mission.executing`, `mission.node.started/finished`, `mission.blocked`,
`mission.completed`, `mission.failed`, `mission.reflected`. Telemetry, the dashboard,
and the Reflection Engine subscribe; nothing is polled.

## 7. Persistence & compatibility
- Backed by `house_state.py` (existing SQLite ledger) — V2 adds columns
  (`objective`, `constraints`, `success_criteria`, `graph`, `completion_pct`,
  `reflection`) via additive migration; old rows default sensibly.
- `workflow_runs.py` becomes the **per-execution record** linked by `mission_id`.
- The V1 `/api/agent/run` path keeps working: an ad-hoc run is auto-wrapped in an
  implicit "quick mission" so the new pipeline applies uniformly, behind the
  `mission_engine` feature flag (see [MigrationPlan](MigrationPlan.md)).

## 8. API surface
`POST /api/mission` (create/admit) · `GET /api/mission/{id}` ·
`GET /api/mission/{id}/graph` · `GET /api/missions?state=…` ·
`POST /api/mission/{id}/pause|resume|cancel` · `GET /api/mission/{id}/timeline` ·
WS `/ws/mission/{id}` (live state + log). These feed the mission-first
[Dashboard](DashboardArchitecture.md).
