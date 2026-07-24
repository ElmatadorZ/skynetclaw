"""
engines/decision_selection_engine.py — Decision Selection Engine
================================================================
Single responsibility: turn scored candidates into a Decision — RANK, COMPARE, REJECT
invalid candidates, CHOOSE the best, and GENERATE an explanation. It does not compute
utility (Utility engine) nor review the choice (Review engine).

Selection policies are pluggable (RL-ready): a policy is a pure function
    (scores, pareto_front) -> chosen_action_id
Two built-ins: `max_utility` (highest scalar on the Pareto front) and `pareto_then_utility`
(restrict to the front, then max scalar) — plus room for a learned policy.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from ..contracts import ActionCandidate, Decision, UtilityScore

Policy = Callable[[List[UtilityScore], List[str]], Optional[str]]


def policy_max_utility(scores: List[UtilityScore], pareto_front: List[str]) -> Optional[str]:
    feasible = [s for s in scores if s.feasible]
    pool = feasible or scores
    if not pool:
        return None
    best = max(pool, key=lambda s: (s.scalar, s.action_id))
    return best.action_id


def policy_pareto_then_utility(scores: List[UtilityScore], pareto_front: List[str]) -> Optional[str]:
    front = [s for s in scores if s.action_id in set(pareto_front) and s.feasible]
    pool = front or [s for s in scores if s.feasible] or scores
    if not pool:
        return None
    return max(pool, key=lambda s: (s.scalar, s.action_id)).action_id


class DecisionSelectionEngine:
    name = "default"

    def __init__(self, policy: Policy = policy_max_utility, policy_name: str = "max_utility"):
        self._policy = policy
        self._policy_name = policy_name

    def select(self, scores: List[UtilityScore], actions: Dict[str, ActionCandidate],
               pareto_front: List[str]) -> Decision:
        ranked = sorted(((s.action_id, s.scalar) for s in scores),
                        key=lambda t: (-t[1], t[0]))
        rejected = [(s.action_id, "infeasible: constraint penalty > 0")
                    for s in scores if not s.feasible]
        chosen_id = self._policy(scores, pareto_front)
        chosen = actions.get(chosen_id) if chosen_id else None
        explanation = self._explain(chosen, scores, ranked, rejected, pareto_front)
        return Decision(chosen=chosen, ranked=ranked, rejected=rejected,
                        pareto_front=sorted(pareto_front), explanation=explanation)

    def _explain(self, chosen, scores, ranked, rejected, pareto_front) -> str:
        if not chosen:
            return ("No candidate was selected: all candidates were infeasible or the pool "
                    "was empty. Refusing to choose an invalid plan.")
        smap = {s.action_id: s for s in scores}
        s = smap.get(chosen.id)
        parts = [f"Chose '{chosen.id}' via policy '{self._policy_name}'."]
        if s:
            top = sorted(s.objective_map().items(), key=lambda t: -t[1])[:3]
            parts.append("Top objective contributions: "
                         + ", ".join(f"{k}={v:.3f}" for k, v in top) + ".")
            if s.constraint_penalty:
                parts.append(f"Constraint penalty {s.constraint_penalty:.3f} was outweighed.")
        if chosen.id in set(pareto_front):
            parts.append("It is on the Pareto front (not dominated by any alternative).")
        if len(ranked) > 1:
            runner = next((aid for aid, _ in ranked if aid != chosen.id), None)
            if runner:
                parts.append(f"Runner-up was '{runner}'.")
        if rejected:
            parts.append(f"Rejected {len(rejected)} infeasible candidate(s).")
        return " ".join(parts)
