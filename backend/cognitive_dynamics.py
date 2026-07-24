"""
cognitive_dynamics.py — SYSTEM DYNAMICS of THE HOUSE (read-model)
=================================================================
Models the House as a stock-and-flow system so it can reason about its OWN
improvement, not just a single mission. Everything is derived from existing
sources (knowledge_frontier + learning_engine + agent_runs); no new state.

STOCKS (levels that accumulate)
  knowledge        — verified facts known
  knowledge_debt   — unresolved unknowns + blind spots
  capability       — skills the House can execute
  capability_debt  — mined candidate skills NOT yet promoted

FLOWS (rates that change stocks)
  discovery_velocity — knowns gained / recent runs
  learning_velocity  — lessons recorded
  skill_creation     — candidate skills surfaced

FEEDBACK LOOPS
  R1 (reinforcing): missions → discoveries → richer frontier → better skills →
     better execution → more successful missions.   (growth engine)
  B1 (balancing):  more information → more complexity → more uncertainty →
     need abstraction → knowledge-asset generation → complexity bounded.

BOTTLENECK = the stock with the highest debt relative to its flow — the single
constraint most limiting uncertainty reduction right now.

Deterministic, model-free.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def model(frontier_metrics: Optional[Dict[str, Any]] = None,
          learning_stats: Optional[Dict[str, Any]] = None,
          run_stats: Optional[Dict[str, Any]] = None,
          capability: int = 0, capability_debt: int = 0) -> Dict[str, Any]:
    """Assemble the live system-dynamics view from already-computed inputs."""
    fm = frontier_metrics or {}
    ls = learning_stats or {}
    rs = run_stats or {}

    def _i(v) -> int:
        if isinstance(v, dict):          # stats by_status values are {count, ...}
            v = v.get("count", 0)
        try:
            return int(v or 0)
        except Exception:
            return 0

    knowledge = _i(fm.get("known_count", 0))
    knowledge_debt = _i(fm.get("knowledge_debt", 0))
    learning_velocity = _i(fm.get("learning_velocity", ls.get("lessons", 0)))
    # discovery velocity proxy: knowns per successful run in the window
    by = rs.get("by_status", {}) or {}
    succ = _i(by.get("TASK_COMPLETE")) + _i(by.get("success")) or _i(rs.get("success", 0))
    discovery_velocity = round(knowledge / succ, 3) if succ else float(knowledge)

    stocks = {
        "knowledge": knowledge,
        "knowledge_debt": knowledge_debt,
        "capability": int(capability),
        "capability_debt": int(capability_debt),
    }
    flows = {
        "discovery_velocity": discovery_velocity,
        "learning_velocity": learning_velocity,
        "skill_creation": int(capability_debt),     # candidates waiting to become skills
        "assumption_load": int(fm.get("assumption_load", 0)),
    }

    # ── loop health (qualitative, from real signals) ──
    r1_active = knowledge > 0 and (learning_velocity > 0 or succ > 0)
    b1_pressure = knowledge_debt > max(3, knowledge)      # complexity outrunning structure
    loops = [
        {"id": "R1", "type": "reinforcing", "name": "growth engine",
         "path": "missions→discoveries→frontier→skills→execution→missions",
         "status": "engaged" if r1_active else "idle",
         "evidence": f"knowledge={knowledge}, learning_velocity={learning_velocity}, successes={succ}"},
        {"id": "B1", "type": "balancing", "name": "complexity governor",
         "path": "information→complexity→uncertainty→abstraction→asset-generation",
         "status": "under pressure" if b1_pressure else "stable",
         "evidence": f"knowledge_debt={knowledge_debt} vs knowledge={knowledge}"},
    ]

    # ── bottleneck: the most binding constraint ──
    candidates = [
        ("knowledge_debt", knowledge_debt, "unresolved unknowns dominate — prioritise DISCOVERY"),
        ("capability_debt", capability_debt, "skills are being re-derived, not reused — PROMOTE candidates"),
        ("assumption_load", flows["assumption_load"], "too many unverified beliefs — VALIDATE assumptions"),
    ]
    name, val, advice = max(candidates, key=lambda c: c[1])
    bottleneck = {"constraint": name, "magnitude": val, "advice": advice} if val > 0 else \
                 {"constraint": "none", "magnitude": 0, "advice": "system is balanced — push frontier wider"}

    return {
        "stocks": stocks,
        "flows": flows,
        "loops": loops,
        "bottleneck": bottleneck,
        "debts": {"knowledge_debt": knowledge_debt, "capability_debt": int(capability_debt)},
        "health": "growing" if (r1_active and not b1_pressure) else
                  ("constrained" if b1_pressure else "warming up"),
    }


def render(m: Dict[str, Any]) -> str:
    if not m:
        return ""
    s, f, b = m["stocks"], m["flows"], m["bottleneck"]
    L = ["## COGNITIVE DYNAMICS (the House reasoning about its own growth):",
         f"  STOCKS   knowledge={s['knowledge']} · debt={s['knowledge_debt']} · "
         f"capability={s['capability']} · cap-debt={s['capability_debt']}",
         f"  FLOWS    discovery={f['discovery_velocity']} · learning={f['learning_velocity']} · "
         f"skill-creation={f['skill_creation']}",
         f"  BOTTLENECK  {b['constraint']} ({b['magnitude']}) → {b['advice']}",
         f"  HEALTH   {m['health']}"]
    for lp in m["loops"]:
        L.append(f"  {lp['id']} {lp['type']}: {lp['status']} — {lp['name']}")
    return "\n".join(L)
