# Execution Engine & Agent State Machine

> Replaces opaque single-shot execution with an explicit per-agent **state machine**
> running over a workflow DAG. Every agent exposes its current state.
> Parent: [Architecture](Architecture.md) · Built on `workflow/` (ir, compiler,
> context, nodes, engine) and the agent loop in `main.py`.

## 1. Why a state machine
V1 runs an agent loop with no externally visible phase — the UI can't tell "thinking"
from "stuck". V2 gives every agent a typed state, emitted on every transition, so the
dashboard shows a live execution timeline and the mission engine can detect BLOCKED.

## 2. Agent states
```
PLANNING → RESEARCHING → THINKING → CODING → TESTING → REVIEWING → FINISHED
   ↑            ↓            ↓         ↓        ↓
   └──────── BLOCKED ⇄ PAUSED ────────┘                 → FAILED
```
| State | Meaning | Typical activity |
|---|---|---|
| PLANNING | decomposing the assigned task | build sub-graph |
| RESEARCHING | gathering live data | search/news/read tools |
| THINKING | reasoning over gathered context | LLM call (no side effects) |
| CODING | producing artifacts | write_file / build tools |
| TESTING | verifying artifacts | run/checks/success-criteria |
| REVIEWING | self/auditor review | shadow_gate, auditor |
| BLOCKED | missing input/resource/gate denied | awaiting unblock |
| PAUSED | operator/governance hold | — |
| FINISHED | node success criteria met | emit result |
| FAILED | unrecoverable / budget out | emit error |

Each transition emits `agent.state` `{agent, mission, node, from, to, ts}`.

## 3. Execution = workflow DAG of stateful nodes
The council's plan (mission graph) compiles to a workflow via the **existing**
pipeline: `workflow/ir.py` (intermediate representation) → `compiler.py` (level the
DAG) → `engine.py` (run levels) → `nodes.py` (`@node` plugins) → `context.py` (shared
run context). Each node hosts an agent running the state machine above. Independent
nodes in a level run concurrently; dependent levels run in order.

```python
class WorkflowNode(Protocol):          # plugin — discovered via @node
    name: str; needs: list[str]
    def run(self, ctx: RunContext) -> NodeResult: ...

class ExecutionEngine:
    def __init__(self, compiler: Compiler, runtime: RuntimeOrchestrator,
                 governance: GovernanceGate, memory: MemoryService,
                 bus: EventBus, telemetry: Telemetry): ...
    def run(self, mission: Mission) -> ExecutionResult
    def pause(self, mid): ...; def resume(self, mid): ...
```

## 4. Governance on every step
Before any side-effecting node action (tool, write, runtime call, egress) the engine
calls the [Governance](Architecture.md#5-cross-cutting-kernels) gate
(`os_permissions.require` + `GPS2Gate` + `shadow_gate`). Denied → node goes BLOCKED
with a reason, not a silent skip. This preserves the V1 fix where writes were wrongly
deduped/blocked: the gate decision is explicit and logged.

## 5. Blocking, retries, idempotency
- **BLOCKED** is a first-class state with a reason and an unblock condition (input
  arrives, resource freed, human approves). The mission engine surfaces it.
- **Retries**: transient runtime errors retry via orchestrator fallback (§ RuntimeArch);
  node-level retry budget is bounded to avoid loops (`shadow_gate` anti-loop).
- **Idempotency**: nodes declare effects; re-running a FINISHED node is a no-op
  (result cached in `RunContext`), so resume after PAUSE/crash is safe.

## 6. Observability
Per node/agent: state durations, token usage, tool latency, retries, reasoning depth
(THINKING iterations). These render as the **Execution Timeline** in the
[Dashboard](DashboardArchitecture.md) and feed failure analysis.

## 7. Events & compatibility
Events: `agent.state`, `mission.node.started/finished`, `execution.blocked`,
`execution.paused/resumed`. The `workflow/` engine already exists and is exposed at
`/api/wfe/*`; V2 wires it as the execution path behind the `execution_engine` flag,
with the V1 in-line agent loop as fallback when off.
