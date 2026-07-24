"""
workflow/compiler.py — OX-WORKFLOW-ENGINE-1 · Workflow Compiler
===============================================================
Workflow IR → Workflow Graph → Execution Graph (optimized DAG).

Responsibilities: dependency analysis · cycle detection · variable-binding
validation · topological ordering into parallel LEVELS (the optimization: nodes
in the same level have no inter-dependency and may run concurrently).

Dependency-free.
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from workflow.ir import WorkflowIR, validate_ir


class CompileError(Exception):
    pass


@dataclass
class ExecGraph:
    ir: WorkflowIR
    adjacency: Dict[str, List[str]]       # node → downstream nodes
    indegree: Dict[str, int]
    order: List[str]                       # topological order
    levels: List[List[str]]                # parallel execution levels
    entry: List[str]                       # nodes with no deps

    def to_dict(self):
        return {"order": self.order, "levels": self.levels, "entry": self.entry,
                "edges": self.adjacency}


def _detect_cycle(nodes: List[str], adjacency: Dict[str, List[str]]) -> List[str]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    stack: List[str] = []

    def dfs(u: str) -> List[str]:
        color[u] = GRAY; stack.append(u)
        for v in adjacency.get(u, []):
            if color[v] == GRAY:
                i = stack.index(v)
                return stack[i:] + [v]
            if color[v] == WHITE:
                r = dfs(v)
                if r:
                    return r
        color[u] = BLACK; stack.pop()
        return []

    for n in nodes:
        if color[n] == WHITE:
            r = dfs(n)
            if r:
                return r
    return []


def compile(ir: WorkflowIR) -> ExecGraph:
    errs = validate_ir(ir)
    if errs:
        raise CompileError("; ".join(errs))

    ids = [n.id for n in ir.nodes]
    adjacency: Dict[str, List[str]] = {i: [] for i in ids}
    indegree: Dict[str, int] = {i: 0 for i in ids}
    for n in ir.nodes:
        for d in n.deps:                       # edge d → n
            adjacency[d].append(n.id)
            indegree[n.id] += 1

    cycle = _detect_cycle(ids, adjacency)
    if cycle:
        raise CompileError(f"cycle detected: {' -> '.join(cycle)}")

    # Kahn topological sort, grouped into parallel levels
    indeg = dict(indegree)
    frontier = sorted([i for i in ids if indeg[i] == 0])
    order: List[str] = []
    levels: List[List[str]] = []
    while frontier:
        levels.append(list(frontier))
        nxt: List[str] = []
        for u in frontier:
            order.append(u)
            for v in adjacency[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    nxt.append(v)
        frontier = sorted(nxt)
    if len(order) != len(ids):
        raise CompileError("unreachable nodes or residual cycle")

    return ExecGraph(ir=ir, adjacency=adjacency, indegree=indegree,
                     order=order, levels=levels,
                     entry=[i for i in ids if indegree[i] == 0])
