# WORKFLOW_ENGINE.md — OX-WORKFLOW-ENGINE-1

The single orchestration layer. Every LLM/agent/embedding execution passes the
Runtime Kernel by **capability** — never a model/endpoint/provider name.

## Pipeline
```
Definition (dict | JSON | YAML)
      │  workflow.ir.parse  →  WorkflowIR   (never execute YAML directly)
      ▼
Workflow Compiler (workflow.compiler)
      │  dependency analysis · cycle detection · validation
      │  topological order → parallel LEVELS (optimized DAG)
      ▼
Workflow Runtime (workflow.engine.WorkflowEngine)
      │  per level: gather() runnable nodes  (parallel)
      │  gating: skip if all deps skipped or `when` false  (conditional)
      │  node.execute(ctx)  ── LLM/agent/embedding ──►  Runtime Kernel.infer(role)
      │                                                    └─► Driver ─► Runtime ─► Model
      ▼
Result + outputs + metrics + artifacts + checkpoints + event history
```

## Modules
| File | Role |
|---|---|
| `workflow/ir.py` | Definition → IR (`NodeDef`/`WorkflowIR`), parse (dict/JSON/YAML), validate |
| `workflow/compiler.py` | IR → `ExecGraph` (cycle detection, topo order, parallel levels) |
| `workflow/context.py` | `WorkflowContext` — variables/outputs/artifacts/metrics/history; `${var}`/`${node.field}` resolution; snapshot/restore (no globals) |
| `workflow/nodes.py` | Node registry + types; `@node("type")` to extend with zero engine changes |
| `workflow/engine.py` | Runtime executor + Registry + Scheduler + Checkpoint + Artifacts + Metrics + Debugger + facade |

## Node types (registry, extensible)
`set · llm · agent · embedding · tool · condition · merge · delay · python · http
· memory · loop(map) · approval · workflow(nested/recursive)`. Each implements
`async execute(ctx, node)`. **llm/agent/embedding call `ctx.runtime.infer/embeddings`
(the kernel) only** — no model names anywhere (enforced by a test).

## Execution modes (all validated)
Sequential · Parallel (levels) · Conditional (gating + branch skip) · Loop/Map ·
Nested · Recursive (depth-limited) · Event-driven & Scheduled (Scheduler).

## Checkpoint / control
A checkpoint snapshot (variables + node_outputs + skipped + history) is saved
after every node and on pause. Supports **pause** (Approval node → `WorkflowPause`),
**resume** (restore + approvals + continue, completed nodes skipped), **rollback**
(restore to a checkpoint index), **retry** (per-node `retries`), **replay**.

## Events (IPC bus)
`WorkflowStarted/Finished/Paused/Failed`, `NodeStarted/Finished/Failed/Skipped`,
`Breakpoint` — published to the OS IPC bus and recorded in run history + the
debugger timeline.

## Subsystems (deliverables)
- **ArtifactManager** — every node output → versioned artifact (kind: text/json/table/vector).
- **MetricsCollector** — per-node duration/retries/errors + run summary.
- **CheckpointStore** — snapshot chain per run (pause/resume/rollback/replay).
- **WorkflowRegistry** — versioned workflows (owner/permissions/tags/inputs/outputs).
- **WorkflowScheduler** — run-now / interval / event (IPC subscription) triggers.
- **WorkflowDebugger** — breakpoints, step, timeline, node/variable inspection.

## API (Phase 15)
REST: `POST /api/workflow/{compile,run,resume,rollback,register}` ·
`GET /api/workflow/runs/{id}` · `/runs/{id}/artifacts` · `/registry`.
WebSocket: `GET /ws/workflow/{run_id}` streams the live timeline until terminal.
Plugin/Desktop API = the same `workflow.get_engine()` facade + `@node` registry.

## Constraints honored
Never calls a runtime directly; never hardcodes a model/endpoint/provider. All
execution flows Workflow → Kernel → Driver → Runtime. Reuses Kernel/Boot/OS/IPC —
no duplicate logic, no redesign.
```
