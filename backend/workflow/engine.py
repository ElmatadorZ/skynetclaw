"""
workflow/engine.py — OX-WORKFLOW-ENGINE-1 · Engine + Runtime + subsystems
=========================================================================
The single orchestration layer. Compiles a workflow to an optimized DAG and
executes it through the Runtime Kernel — sequential / parallel (levels) /
conditional (gating) / loop / nested / recursive — emitting events on the IPC
bus, checkpointing each node (pause/resume/rollback/replay), versioning artifacts
and collecting metrics. NO direct runtime/model/endpoint/provider references.

Bundles the deliverable subsystems: ArtifactManager, MetricsCollector,
CheckpointStore, WorkflowRegistry, WorkflowScheduler, WorkflowDebugger.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

from workflow.ir import WorkflowIR, parse
from workflow.compiler import compile as compile_ir, ExecGraph
from workflow.context import WorkflowContext
from workflow.nodes import get_node, safe_eval


class WorkflowPause(Exception):
    def __init__(self, node_id: str, message: str = ""):
        super().__init__(message); self.node_id = node_id; self.message = message


# ── Artifact Manager (Phase 10) ───────────────────────────────────────────────
class ArtifactManager:
    def __init__(self):
        self._store: Dict[str, List[Dict[str, Any]]] = {}     # key → versions
    def store(self, run_id: str, node_id: str, kind: str, data: Any) -> Dict[str, Any]:
        key = f"{run_id}:{node_id}"
        versions = self._store.setdefault(key, [])
        art = {"key": key, "version": len(versions) + 1, "kind": kind,
               "data": data, "ts": time.time()}
        versions.append(art); return art
    def get(self, run_id: str, node_id: str) -> List[Dict[str, Any]]:
        return self._store.get(f"{run_id}:{node_id}", [])
    def list(self, run_id: str) -> List[Dict[str, Any]]:
        return [v[-1] for k, v in self._store.items() if k.startswith(run_id + ":")]


# ── Metrics Collector (Phase 13) ──────────────────────────────────────────────
class MetricsCollector:
    def __init__(self):
        self._m: Dict[str, List[Dict[str, Any]]] = {}
    def record(self, run_id: str, node_id: str, **kv):
        self._m.setdefault(run_id, []).append({"node": node_id, **kv})
    def summary(self, run_id: str) -> Dict[str, Any]:
        rows = self._m.get(run_id, [])
        durs = [r.get("duration_s", 0) for r in rows]
        return {"nodes": len(rows), "total_s": round(sum(durs), 3),
                "errors": sum(1 for r in rows if r.get("error")),
                "retries": sum(r.get("retries", 0) for r in rows),
                "per_node": rows}


# ── Checkpoint Store (Phase 9) ────────────────────────────────────────────────
class CheckpointStore:
    def __init__(self):
        self._cp: Dict[str, List[Dict[str, Any]]] = {}
    def save(self, run_id: str, snapshot: Dict[str, Any], label: str = "") -> int:
        chain = self._cp.setdefault(run_id, [])
        chain.append({"label": label, "ts": time.time(), "snapshot": snapshot})
        return len(chain) - 1
    def latest(self, run_id: str) -> Optional[Dict[str, Any]]:
        chain = self._cp.get(run_id) or []
        return chain[-1]["snapshot"] if chain else None
    def at(self, run_id: str, index: int) -> Optional[Dict[str, Any]]:
        chain = self._cp.get(run_id) or []
        return chain[index]["snapshot"] if -len(chain) <= index < len(chain) else None
    def history(self, run_id: str) -> List[Dict[str, Any]]:
        return [{"index": i, "label": c["label"], "ts": c["ts"]}
                for i, c in enumerate(self._cp.get(run_id) or [])]


# ── Workflow Registry (Phase 12) ──────────────────────────────────────────────
class WorkflowRegistry:
    def __init__(self):
        self._wf: Dict[str, Dict[str, Any]] = {}      # "id@version" → record
    def register(self, ir: WorkflowIR, owner: str = "", permissions: List[str] = None,
                 tags: List[str] = None) -> Dict[str, Any]:
        key = f"{ir.id}@{ir.version}"
        rec = {"id": ir.id, "version": ir.version, "owner": owner,
               "permissions": permissions or [], "tags": tags or [],
               "inputs": list(ir.inputs.keys()), "outputs": ir.outputs,
               "nodes": len(ir.nodes), "definition": ir.to_dict(), "metrics": {}}
        self._wf[key] = rec; return {k: v for k, v in rec.items() if k != "definition"}
    def get(self, wf_id: str, version: str = None) -> Optional[Dict[str, Any]]:
        if version: return self._wf.get(f"{wf_id}@{version}")
        cands = [r for k, r in self._wf.items() if r["id"] == wf_id]
        return sorted(cands, key=lambda r: r["version"])[-1] if cands else None
    def list(self) -> List[Dict[str, Any]]:
        return [{k: v for k, v in r.items() if k != "definition"} for r in self._wf.values()]


# ── Debugger (Phase 14) ───────────────────────────────────────────────────────
class WorkflowDebugger:
    def __init__(self):
        self.breakpoints: set = set()
        self.step_mode = False
        self._timeline: Dict[str, List[Dict[str, Any]]] = {}
    def set_breakpoint(self, node_id: str): self.breakpoints.add(node_id)
    def clear(self): self.breakpoints.clear(); self.step_mode = False
    def trace(self, run_id: str, event: str, node_id: str, **kv):
        self._timeline.setdefault(run_id, []).append(
            {"event": event, "node": node_id, "t": time.time(), **kv})
    def timeline(self, run_id: str) -> List[Dict[str, Any]]:
        return self._timeline.get(run_id, [])


# ── Scheduler (Phase 11) ──────────────────────────────────────────────────────
class WorkflowScheduler:
    def __init__(self, engine: "WorkflowEngine"):
        self.engine = engine
        self.jobs: Dict[str, Dict[str, Any]] = {}
    def run_now(self, definition: Any, inputs: Dict[str, Any] = None):
        return asyncio.get_event_loop().create_task(self.engine.run(definition, inputs or {}))
    def schedule(self, name: str, definition: Any, every_s: float = None,
                 on_event: str = None, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        self.jobs[name] = {"definition": definition, "every_s": every_s, "on_event": on_event,
                           "inputs": inputs or {}, "last": 0.0}
        if on_event and self.engine.ipc:
            self.engine.ipc.subscribe(on_event,
                lambda t, p: self.engine.scheduler.run_now(definition, inputs), owner=f"sched:{name}")
        return {"scheduled": name, "every_s": every_s, "on_event": on_event}
    def tick(self):
        now = time.time()
        for name, j in self.jobs.items():
            if j["every_s"] and now - j["last"] >= j["every_s"]:
                j["last"] = now; self.run_now(j["definition"], j["inputs"])


# ── Runtime executor ──────────────────────────────────────────────────────────
class WorkflowEngine:
    def __init__(self, runtime=None, ipc=None, tool_executor=None):
        self._runtime = runtime
        self.ipc = ipc
        self.tool_executor = tool_executor
        self.artifacts = ArtifactManager()
        self.metrics = MetricsCollector()
        self.checkpoints = CheckpointStore()
        self.registry = WorkflowRegistry()
        self.debugger = WorkflowDebugger()
        self.scheduler = WorkflowScheduler(self)
        self.runs: Dict[str, Dict[str, Any]] = {}

    def runtime(self):
        if self._runtime is not None:
            return self._runtime
        import runtime_kernel as rk
        return rk.get_kernel(rediscover=False)

    def compile(self, definition: Any) -> ExecGraph:
        return compile_ir(parse(definition))

    async def run(self, definition: Any, inputs: Dict[str, Any] = None,
                  run_id: str = None, _resume_ctx: WorkflowContext = None,
                  _nested: bool = False) -> Dict[str, Any]:
        graph = self.compile(definition)
        ir = graph.ir
        run_id = run_id or f"{ir.id}-{uuid.uuid4().hex[:8]}"
        ctx = _resume_ctx or WorkflowContext(run_id, inputs={**ir.inputs, **(inputs or {})},
                                             runtime=self.runtime(), ipc=self.ipc)
        ctx.tool_executor = self.tool_executor
        self.runs[run_id] = {"id": ir.id, "status": "running", "started": time.time(), "ctx": ctx}
        ctx.record("WorkflowStarted", workflow=ir.id, run_id=run_id)

        try:
            for level in graph.levels:
                runnable = [nid for nid in level if nid not in ctx.node_outputs]
                await asyncio.gather(*[self._run_node(ir, nid, ctx, run_id) for nid in runnable])
            status = "completed"
        except WorkflowPause as wp:
            self.checkpoints.save(run_id, ctx.snapshot(), label=f"paused@{wp.node_id}")
            self.runs[run_id]["status"] = "paused"
            ctx.record("WorkflowPaused", node=wp.node_id, message=wp.message)
            return self._result(run_id, ir, ctx, "paused", paused_at=wp.node_id)
        except Exception as e:
            self.runs[run_id]["status"] = "failed"
            ctx.record("WorkflowFailed", error=str(e)[:200])
            return self._result(run_id, ir, ctx, "failed", error=str(e)[:200])

        self.runs[run_id]["status"] = status
        ctx.record("WorkflowFinished", run_id=run_id)
        return self._result(run_id, ir, ctx, status)

    async def _run_node(self, ir: WorkflowIR, nid: str, ctx: WorkflowContext, run_id: str):
        nd = ir.node(nid)
        # gating: skip if all deps skipped, or own 'when' is false
        deps_skipped = [d for d in nd.deps if d in ctx.skipped]
        if nd.deps and len(deps_skipped) == len(nd.deps):
            ctx.skipped.add(nid); ctx.record("NodeSkipped", node=nid, reason="deps_skipped"); return
        if nd.when and not safe_eval(ctx.resolve(nd.when) if "${" in str(nd.when) else nd.when, ctx):
            ctx.skipped.add(nid); ctx.record("NodeSkipped", node=nid, reason="when_false"); return
        if nid in self.debugger.breakpoints:
            ctx.record("Breakpoint", node=nid)
        self.debugger.trace(run_id, "NodeStarted", nid)
        ctx.record("NodeStarted", node=nid, type=nd.type)
        t0 = time.time(); attempts = 0
        while True:
            try:
                out = await get_node(nd.type).execute(ctx, nd)
                ctx.set_output(nid, out)
                self.artifacts.store(run_id, nid, _kind(out), out)
                dt = round(time.time() - t0, 3)
                self.metrics.record(run_id, nid, duration_s=dt, retries=attempts, type=nd.type)
                self.checkpoints.save(run_id, ctx.snapshot(), label=f"after:{nid}")
                self.debugger.trace(run_id, "NodeFinished", nid, duration_s=dt)
                ctx.record("NodeFinished", node=nid, duration_s=dt)
                return
            except WorkflowPause:
                raise
            except Exception as e:
                if attempts < nd.retries:
                    attempts += 1; await asyncio.sleep(0.1 * attempts); continue
                self.metrics.record(run_id, nid, error=str(e)[:160], retries=attempts)
                self.debugger.trace(run_id, "NodeFailed", nid, error=str(e)[:160])
                ctx.record("NodeFailed", node=nid, error=str(e)[:160])
                raise

    def _result(self, run_id, ir, ctx, status, **extra):
        outputs = {o: ctx._lookup(o) for o in ir.outputs} if ir.outputs else ctx.node_outputs
        return {"run_id": run_id, "workflow": ir.id, "status": status,
                "outputs": outputs, "metrics": self.metrics.summary(run_id),
                "history": ctx.history, **extra}

    # — checkpoint operations (Phase 9) —
    async def resume(self, run_id: str, approvals: Dict[str, bool] = None,
                     definition: Any = None) -> Dict[str, Any]:
        snap = self.checkpoints.latest(run_id)
        run = self.runs.get(run_id)
        if not snap or not run:
            return {"error": f"no checkpoint for {run_id}"}
        ctx = run["ctx"]; ctx.restore(snap)
        for nid, ok in (approvals or {}).items():
            ctx.variables[f"__approved__{nid}"] = ok
        defn = definition or self.registry.get(run["id"])
        defn = defn["definition"] if isinstance(defn, dict) and "definition" in defn else defn
        return await self.run(defn, run_id=run_id, _resume_ctx=ctx)

    def rollback(self, run_id: str, to_index: int) -> Dict[str, Any]:
        snap = self.checkpoints.at(run_id, to_index)
        if snap is None:
            return {"error": "no such checkpoint"}
        run = self.runs.get(run_id)
        if run:
            run["ctx"].restore(snap)
        return {"rolledback": run_id, "to": to_index, "node_outputs": list(snap.get("node_outputs", {}))}

    def status(self, run_id: str) -> Dict[str, Any]:
        run = self.runs.get(run_id)
        if not run:
            return {"error": "unknown run"}
        return {"run_id": run_id, "workflow": run["id"], "status": run["status"],
                "checkpoints": self.checkpoints.history(run_id),
                "metrics": self.metrics.summary(run_id),
                "timeline": self.debugger.timeline(run_id)}


def _kind(out: Any) -> str:
    if isinstance(out, dict) and "vectors" in out: return "vector"
    if isinstance(out, dict): return "json"
    if isinstance(out, (list, tuple)): return "table"
    return "text"


_ENGINE: Optional[WorkflowEngine] = None


def get_engine() -> WorkflowEngine:
    global _ENGINE
    if _ENGINE is None:
        try:
            import os_ipc, genesis_os
            ipc = genesis_os.get_os().ipc
        except Exception:
            ipc = None
        _ENGINE = WorkflowEngine(ipc=ipc)
    return _ENGINE
