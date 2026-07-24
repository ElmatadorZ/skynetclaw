"""
workflow/nodes.py — OX-WORKFLOW-ENGINE-1 · Node Types
=====================================================
Every node implements `async execute(ctx, node) -> output`. LLM / embedding /
agent nodes route through the Runtime Kernel ONLY (capability, never a model
name). New node types register with @node("type") — zero engine changes.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from typing import Any, Callable, Dict

NODE_REGISTRY: Dict[str, "Node"] = {}


def node(type_name: str):
    def deco(cls):
        NODE_REGISTRY[type_name] = cls()
        cls.type = type_name
        return cls
    return deco


def get_node(type_name: str) -> "Node":
    n = NODE_REGISTRY.get(type_name)
    if n is None:
        raise KeyError(f"unknown node type '{type_name}'")
    return n


def safe_eval(expr: str, ctx) -> Any:
    # node outputs first, then variables override (variables are the primary
    # namespace; a node id must never shadow a same-named variable).
    env = {k: v for k, v in ctx.node_outputs.items()}
    env.update(ctx.variables)
    try:
        return eval(expr, {"__builtins__": {}}, env)   # trusted workflow authors
    except Exception:
        return None


class Node:
    type = "base"
    async def execute(self, ctx, node) -> Any:          # pragma: no cover
        raise NotImplementedError


@node("set")
class SetNode(Node):
    async def execute(self, ctx, node):
        out = {}
        for k, v in ctx.resolve(node.params).items():
            ctx.set(k, v); out[k] = v
        return out


@node("llm")
class LLMNode(Node):
    async def execute(self, ctx, node):
        p = ctx.resolve(node.params)
        role = p.get("role", "Execution")
        messages = p.get("messages") or [{"role": "user", "content": str(p.get("prompt", ""))}]
        tools = p.get("tools")
        def _collect():
            text, calls = [], []
            for raw in ctx.runtime.infer(required={"role": role, "tool_calling": bool(tools)},
                                         messages=messages, tools=tools, stream=True,
                                         options=p.get("options", {"temperature": 0.2})):
                ev = json.loads(raw)
                if ev.get("type") == "text": text.append(ev.get("text", ""))
                elif ev.get("type") == "__tool_calls__": calls.extend(ev.get("calls", []))
            return {"text": "".join(text), "tool_calls": calls}
        return await asyncio.to_thread(_collect)


@node("embedding")
class EmbeddingNode(Node):
    async def execute(self, ctx, node):
        p = ctx.resolve(node.params)
        texts = p.get("texts") or [p.get("text", "")]
        return await asyncio.to_thread(lambda: {"vectors": ctx.runtime.embeddings(texts)})


@node("agent")
class AgentNode(LLMNode):
    """An agent step = execution-role LLM with tools — through the kernel."""
    async def execute(self, ctx, node):
        node.params.setdefault("role", "Execution")
        return await super().execute(ctx, node)


@node("tool")
class ToolNode(Node):
    async def execute(self, ctx, node):
        p = ctx.resolve(node.params)
        name, args = p.get("name"), p.get("args", {})
        executor: Callable = getattr(ctx, "tool_executor", None)
        if executor is None:
            import main  # lazy: tool execution lives in the host
            executor = lambda n, a: asyncio.get_event_loop().run_until_complete(main.exec_tool(n, a))
        try:
            res = executor(name, args)
            if asyncio.iscoroutine(res):
                res = await res
            return {"tool": name, "result": res}
        except Exception as e:
            return {"tool": name, "error": str(e)[:200]}


@node("condition")
class ConditionNode(Node):
    async def execute(self, ctx, node):
        expr = ctx.resolve(node.params).get("expr") or node.when or "True"
        return {"value": bool(safe_eval(expr, ctx))}


@node("merge")
class MergeNode(Node):
    async def execute(self, ctx, node):
        return {"merged": {d: ctx.node_outputs.get(d) for d in node.deps}}


@node("delay")
class DelayNode(Node):
    async def execute(self, ctx, node):
        secs = float(ctx.resolve(node.params).get("seconds", 0))
        await asyncio.sleep(min(secs, 30))
        return {"delayed_s": secs}


@node("python")
class PythonNode(Node):
    async def execute(self, ctx, node):
        return {"value": safe_eval(ctx.resolve(node.params).get("expr", "None"), ctx)}


@node("http")
class HTTPNode(Node):
    async def execute(self, ctx, node):
        p = ctx.resolve(node.params)
        def _req():
            data = json.dumps(p["body"]).encode() if p.get("body") else None
            req = urllib.request.Request(p["url"], data=data, method=p.get("method", "GET"),
                                         headers=p.get("headers", {}))
            with urllib.request.urlopen(req, timeout=p.get("timeout", 20)) as r:
                return {"status": r.status, "body": r.read().decode("utf-8", "replace")[:5000]}
        return await asyncio.to_thread(_req)


@node("memory")
class MemoryNode(Node):
    async def execute(self, ctx, node):
        p = ctx.resolve(node.params)
        if p.get("op") == "write":
            ctx.session[p["key"]] = p.get("value"); return {"wrote": p["key"]}
        return {"value": ctx.session.get(p.get("key"))}


@node("loop")
class LoopNode(Node):
    """Map a template node-params over a list, collecting per-item outputs."""
    async def execute(self, ctx, node):
        p = ctx.resolve(node.params)
        items = p.get("items", [])
        inner_type = p.get("node", "python")
        results = []
        for i, item in enumerate(items):
            ctx.set("item", item); ctx.set("index", i)
            sub = type(node)(id=f"{node.id}#{i}", type=inner_type, params=p.get("params", {}))
            results.append(await get_node(inner_type).execute(ctx, sub))
        return {"results": results, "count": len(results)}


@node("approval")
class ApprovalNode(Node):
    """Pause point: raises a Pause the runtime catches → checkpoint + WorkflowPaused."""
    async def execute(self, ctx, node):
        from workflow.engine import WorkflowPause
        if ctx.variables.get(f"__approved__{node.id}"):
            return {"approved": True}
        raise WorkflowPause(node.id, ctx.resolve(node.params).get("message", "approval required"))


@node("workflow")
class SubWorkflowNode(Node):
    """Nested / recursive workflow — runs another definition via the engine."""
    async def execute(self, ctx, node):
        from workflow.engine import get_engine
        p = ctx.resolve(node.params)
        depth = int(ctx.variables.get("__depth__", 0))
        if depth >= int(p.get("max_depth", 8)):
            return {"error": "max recursion depth"}
        eng = get_engine()
        res = await eng.run(p["definition"], inputs={**p.get("inputs", {}),
                            "__depth__": depth + 1}, _nested=True)
        return {"workflow": res.get("run_id"), "outputs": res.get("outputs"),
                "status": res.get("status")}
