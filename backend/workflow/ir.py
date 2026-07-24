"""
workflow/ir.py — OX-WORKFLOW-ENGINE-1 · Workflow Definition + IR
===============================================================
A workflow may be authored as a dict (visual graph), a JSON string, or YAML.
Everything is parsed into ONE Intermediate Representation (WorkflowIR) — the
engine never executes YAML/JSON directly, only the IR.

Dependency-free (YAML is optional; used only if PyYAML is installed).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NodeDef:
    id: str
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    deps: List[str] = field(default_factory=list)     # upstream node ids
    when: Optional[str] = None                          # condition expr (gates the node)
    iterate: Optional[str] = None                       # ${var} list → loop/map
    retries: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "type": self.type, "params": self.params,
                "deps": self.deps, "when": self.when, "iterate": self.iterate,
                "retries": self.retries}


@dataclass
class WorkflowIR:
    id: str
    name: str = ""
    version: str = "1.0.0"
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    nodes: List[NodeDef] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def node(self, nid: str) -> Optional[NodeDef]:
        return next((n for n in self.nodes if n.id == nid), None)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "version": self.version,
                "inputs": self.inputs, "outputs": self.outputs,
                "nodes": [n.to_dict() for n in self.nodes], "metadata": self.metadata}


def _coerce(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("utf-8", "replace")
    if isinstance(obj, str):
        s = obj.strip()
        if s.startswith("{") or s.startswith("["):
            return json.loads(s)
        try:
            import yaml  # optional
            return yaml.safe_load(s)
        except Exception as e:
            raise ValueError(f"cannot parse workflow (install PyYAML for YAML): {e}")
    raise ValueError("workflow definition must be dict | JSON | YAML")


def parse(definition: Any) -> WorkflowIR:
    """dict / JSON / YAML → WorkflowIR. The single front door to the engine."""
    d = _coerce(definition)
    nodes = []
    for n in d.get("nodes", []):
        nodes.append(NodeDef(
            id=n["id"], type=n["type"], params=n.get("params", {}) or {},
            deps=list(n.get("deps", []) or []), when=n.get("when"),
            iterate=n.get("iterate"), retries=int(n.get("retries", 0) or 0)))
    return WorkflowIR(
        id=d.get("id") or d.get("name") or "workflow",
        name=d.get("name", d.get("id", "workflow")),
        version=str(d.get("version", "1.0.0")),
        inputs=d.get("inputs", {}) or {}, outputs=d.get("outputs", []) or [],
        nodes=nodes, metadata=d.get("metadata", {}) or {})


def validate_ir(ir: WorkflowIR) -> List[str]:
    errors: List[str] = []
    ids = [n.id for n in ir.nodes]
    if not ir.nodes:
        errors.append("workflow has no nodes")
    if len(ids) != len(set(ids)):
        errors.append("duplicate node ids")
    idset = set(ids)
    for n in ir.nodes:
        for d in n.deps:
            if d not in idset:
                errors.append(f"node '{n.id}' depends on unknown node '{d}'")
    return errors
