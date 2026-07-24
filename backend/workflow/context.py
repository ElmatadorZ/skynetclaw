"""
workflow/context.py — OX-WORKFLOW-ENGINE-1 · WorkflowContext
============================================================
One context object threads through a run — NO globals. Holds variables, node
outputs, artifacts, metrics, history, permissions, workspace and the runtime
handle (the Runtime Kernel). Templates `${var}` / `${node_id}` / `${node.field}`
resolve against variables + upstream outputs.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

_TPL = re.compile(r"\$\{([^}]+)\}")


class WorkflowContext:
    def __init__(self, run_id: str, inputs: Dict[str, Any] = None,
                 runtime: Any = None, ipc: Any = None, permissions: Any = None,
                 artifacts: Any = None, metrics: Any = None, workspace: Any = None,
                 owner: str = "workflow"):
        self.run_id = run_id
        self.variables: Dict[str, Any] = dict(inputs or {})
        self.node_outputs: Dict[str, Any] = {}
        self.runtime = runtime                # Runtime Kernel (the ONLY exec path)
        self.ipc = ipc
        self.permissions = permissions
        self.artifacts = artifacts
        self.metrics = metrics
        self.workspace = workspace
        self.owner = owner
        self.history: List[Dict[str, Any]] = []
        self.session: Dict[str, Any] = {}
        self.skipped: set = set()
        self.created = time.time()

    # — variables / outputs —
    def get(self, name: str, default=None):
        return self.variables.get(name, default)

    def set(self, name: str, value: Any):
        self.variables[name] = value

    def set_output(self, node_id: str, value: Any):
        self.node_outputs[node_id] = value

    def resolve(self, value: Any) -> Any:
        """Substitute ${...} references. A whole-string single ref keeps its
        native type (e.g. a list/dict); embedded refs stringify."""
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        if not isinstance(value, str):
            return value
        m = _TPL.fullmatch(value.strip())
        if m:
            return self._lookup(m.group(1).strip())
        return _TPL.sub(lambda mo: str(self._lookup(mo.group(1).strip())), value)

    def _lookup(self, ref: str) -> Any:
        if ref in self.variables:
            return self.variables[ref]
        head, _, tail = ref.partition(".")
        base = self.node_outputs.get(head, self.variables.get(head))
        if tail and isinstance(base, dict):
            for part in tail.split("."):
                if isinstance(base, dict):
                    base = base.get(part)
                else:
                    return None
            return base
        return base

    # — observability —
    def record(self, event: str, **detail):
        ev = {"event": event, "t": round(time.time() - self.created, 3), **detail}
        self.history.append(ev)
        if self.ipc:
            try: self.ipc.publish(f"workflow.{event}", {"run": self.run_id, **detail},
                                  source=f"workflow:{self.run_id}")
            except Exception: pass

    def snapshot(self) -> Dict[str, Any]:
        return {"run_id": self.run_id, "variables": self.variables,
                "node_outputs": self.node_outputs, "skipped": list(self.skipped),
                "history": self.history}

    def restore(self, snap: Dict[str, Any]):
        self.variables = dict(snap.get("variables", {}))
        self.node_outputs = dict(snap.get("node_outputs", {}))
        self.skipped = set(snap.get("skipped", []))
        self.history = list(snap.get("history", []))
