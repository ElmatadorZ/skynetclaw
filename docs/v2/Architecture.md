# SkynetClaw V2 — AI Operating System (AIOS)

> Master architecture. Companion docs: [MissionEngine](MissionEngine.md) ·
> [CouncilEngine](CouncilEngine.md) · [KnowledgeGraph](KnowledgeGraph.md) ·
> [ReflectionEngine](ReflectionEngine.md) · [RuntimeArchitecture](RuntimeArchitecture.md) ·
> [ExecutionStateMachine](ExecutionStateMachine.md) · [SkillArchitecture](SkillArchitecture.md) ·
> [DashboardArchitecture](DashboardArchitecture.md) · [FolderStructure](FolderStructure.md) ·
> [MigrationPlan](MigrationPlan.md) · [ImplementationRoadmap](ImplementationRoadmap.md)

## 1. Thesis
SkynetClaw V1 is a multi-agent platform: `Runtime → Agent → Skill → Tool → Service → Execution`.
V2 is an **operating system** in which **Missions** are processes, **Councils** are
schedulers/decision-makers, the **Knowledge Graph** is the filesystem, **Memory**
is RAM+disk, **Governance** is the kernel's permission system, the **Runtime
Orchestrator** is the hardware abstraction layer, and the **Reflection Engine** is
the OS that rewrites itself. The result is not "an assistant" but an environment
where agents collaborate, remember, govern, and evolve while executing missions.

Three invariants: **everything is modular, replaceable, and observable.**

## 2. Layered model (kernel → userland)
```
┌────────────────────────────────────────────────────────────────────┐
│ L7  DASHBOARD / API          mission-first UI · REST · WS · SSE      │
├────────────────────────────────────────────────────────────────────┤
│ L6  MISSION ENGINE           Mission = the primary OS object/process │  ← NEW (wraps house_state)
├────────────────────────────────────────────────────────────────────┤
│ L5  COUNCIL ENGINE           hierarchical decision (Cmd→Gov→Council)  │  ← evolves agent_council/commander
│ L5  REFLECTION ENGINE        post-mission learning → memory/evolution │  ← evolves agentic_workflow.reflect
├────────────────────────────────────────────────────────────────────┤
│ L4  EXECUTION ENGINE         per-agent state machine + workflow DAG   │  ← workflow/ + ExecutionStateMachine
├────────────────────────────────────────────────────────────────────┤
│ L3  GOVERNANCE ENGINE        risk→security→approval→audit (mandatory) │  ← governance.py GPS-2 + shadow_gate
├────────────────────────────────────────────────────────────────────┤
│ L2  COGNITION SERVICES       skills · tools · knowledge graph · memory│  ← skills_auto_router, tools, KG
├────────────────────────────────────────────────────────────────────┤
│ L1  RUNTIME ORCHESTRATOR     kernel · drivers · routing · fallback    │  ← runtime_kernel + runtime_plugins
├────────────────────────────────────────────────────────────────────┤
│ L0  OS CORE                  services · IPC bus · permissions · pkgs  │  ← genesis_os + os_*.py (exists)
└────────────────────────────────────────────────────────────────────┘
            cross-cutting: OBSERVABILITY (telemetry on every layer)
```
Calls flow **down** (mission → council → execution → governance → runtime); events
flow **up and sideways** over the IPC bus (`os_ipc.EventBus`).

## 3. Engine map — V2 ↔ existing code (this is an evolution)
| V2 Engine | Status | Built on (real files) |
|---|---|---|
| OS Core (services/IPC/permissions/packages/workspace) | **exists** | `genesis_os.py`, `os_ipc.py`, `os_permissions.py`, `os_services.py`, `os_packages.py`, `os_workspace.py`, `os_apps.py` |
| Runtime Orchestrator | **exists** | `runtime_kernel.py`, `runtime_plugins/`, `runtime_router.py`, `runtime_registry.py`, `runtime_boot.py`, `llm_adapter.py` |
| Governance Engine | **exists, extend** | `governance.py` (GPS-2), `skynetclaw_meta.py` (shadow_gate), `governance_engine.py` |
| Execution Engine | **exists, formalize** | `workflow/` (ir/compiler/context/nodes/engine), agent loop in `main.py` |
| Skills/Tools/Cognition | **exists** | `skills_auto_router.py` + `skills/*/SKILL.md`, `BUILTIN_TOOLS`/`exec_tool` |
| Council Engine | **evolve to hierarchy** | `agent_council.py`, `commander.py`, the 14-agent roster |
| Mission Engine | **new (wraps ledger)** | `house_state.py` (mission ledger), `workflow_runs.py` |
| Knowledge Graph | **new (wraps stores)** | `system_graph.py`, Obsidian tools, per-module JSON stores |
| Working / Long-term Memory | **new + consolidate** | `lesson_synthesis.py`, `reinforcement.py`, `calibration.py`, council memory |
| Reflection Engine | **evolve** | `agentic_workflow.reflect`, `lesson_synthesis.py`, OX cognitive modules |
| Observability | **consolidate** | `telemetry.py`, `observability.py`, `reliability_dashboard.py`, `/api/system/graph` |

**Nothing in the table is greenfield rewrite.** V2 = formalize boundaries + add the
Mission/Knowledge-Graph/Memory layers + make the dashboard mission-first.

## 4. Design principles (how, concretely)
- **SOLID + DI**: each engine is a class with an explicit interface; dependencies
  (kernel, ipc, governance, memory) are **injected** at construction (see the
  `GenesisOS` facade pattern already used). No global singletons inside engines.
- **Event-driven**: engines never call each other directly for side-effects — they
  publish to `os_ipc.EventBus` (`mission.*`, `council.*`, `agent.*`, `governance.*`,
  `memory.*`). Subscribers (telemetry, dashboard, reflection) react.
- **Plugin architecture**: runtimes (`runtime_plugins/`), apps (`plugins/apps/`),
  skills (`skills/*/SKILL.md`), workflow nodes (`@node`), tools — all discovered,
  none hardcoded. Adding one = drop a file, zero engine change.
- **Replaceable**: every engine sits behind an interface + a feature flag, so V2
  engines can be switched on per-subsystem (see [MigrationPlan](MigrationPlan.md)).
- **Observable**: every engine emits telemetry spans; nothing is invisible.
- **Anti-overengineering**: no microservices, no message broker, no k8s. One
  process, in-proc event bus, SQLite stores, optional external runtimes. Scale-out
  is a *later* concern handled by the same interfaces (the bus/store become network).

## 5. Cross-cutting kernels
### Governance (mandatory path) → [details](MigrationPlan.md)
`Mission → Risk → Security → Approval → Execution → Audit → Reflection`. Implemented
as a middleware every privileged action passes: `os_permissions.require()` +
`governance.GPS2Gate` (deny-by-default, human gate on irreversible tools) +
`skynetclaw_meta.shadow_gate` (anti-hallucination / anti-loop). No tool call,
runtime call, or memory write bypasses it.

### Observability
Single `Telemetry` facade emits spans to a ring buffer + SQLite (`runtime_metrics.db`,
`telemetry`). Metrics: mission duration, agent utilization & state, token usage,
tool latency, memory hit-ratio, reasoning depth, execution graph, cost, failure
analysis. Surfaced at `/api/observability/*` and the dashboard.

### Memory tiers
- **Working memory** (RAM, auto-expiring): context window, recent decisions,
  temp facts, open questions, pending tasks, current assumptions. TTL per item.
- **Long-term memory** (durable, versioned): mission history, architecture
  decisions, lessons, patterns, failure cases, successful strategies.
- Both indexed into the **Knowledge Graph** for semantic/graph/timeline/mission
  retrieval. See [KnowledgeGraph](KnowledgeGraph.md).

## 6. The one-paragraph mental model
A **Mission** is admitted, the **Governance** kernel risk-rates it, a **Council**
deliberates and produces a plan, the **Execution Engine** runs that plan as a
workflow DAG of agents (each a state machine) that call **skills/tools** through
the **Runtime Orchestrator** (which routes to the best model with fallback), every
step is **governed** and **observed**, results are written to **memory + the
knowledge graph**, and on completion the **Reflection Engine** asks what to learn,
forget, and evolve — closing the loop. The dashboard shows the Mission first.
