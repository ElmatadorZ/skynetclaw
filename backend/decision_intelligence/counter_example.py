"""
decision_intelligence/counter_example.py — Phase 3: active invalidation
=======================================================================
Single responsibility: try to PROVE A CANDIDATE ANSWER WRONG. Given a candidate
assignment and the goal variable(s), search for a DIFFERENT solution in which the
GOAL takes a different value — a genuine counter-example to a "unique answer" claim.

This is stronger than merely exhibiting `solutions[1]`: two full solutions can share
the same goal value (the answer is still unique even if incidental variables vary). We
specifically hunt for a solution whose *goal tuple differs*, by adding one deterministic
`Predicate` — "goal ≠ candidate's goal" — to a copy of the graph and asking the engine
for any solution.

If the goal set is empty, we fall back to "any structurally distinct second solution",
which invalidates a claim of a unique full assignment.

Every returned counter-example is INDEPENDENTLY VERIFIED before it is trusted.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import logic
from logic import ConstraintGraph, Predicate
from .constraint_analyzer import AnalysisModel


@dataclass
class CounterExample:
    found: bool
    alternative: Optional[Dict[str, Any]] = None
    differing_goals: List[str] = field(default_factory=list)
    candidate_goal: Optional[Dict[str, Any]] = None
    alternative_goal: Optional[Dict[str, Any]] = None
    verified: bool = False
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"found": self.found, "verified": self.verified,
                "alternative": self.alternative, "differing_goals": self.differing_goals,
                "candidate_goal": self.candidate_goal,
                "alternative_goal": self.alternative_goal, "note": self.note}


def search_counter_example(model: AnalysisModel,
                           candidate: Optional[Dict[str, Any]],
                           goals: Optional[List[str]] = None) -> CounterExample:
    """Return a CounterExample. `found=True` means the candidate's ANSWER is not unique."""
    if candidate is None:
        return CounterExample(found=False, note="no candidate to invalidate")

    goals = [g for g in (goals if goals is not None else model.goals)
             if g in candidate]

    graph = model.graph()

    if goals:
        candidate_goal = {g: candidate[g] for g in goals}
        cand_tuple = tuple(candidate_goal[g] for g in goals)

        def _goal_differs(a: Dict[str, Any], _goals=tuple(goals), _ct=cand_tuple) -> bool:
            return tuple(a[g] for g in _goals) != _ct

        probe = ConstraintGraph(variables=dict(graph.variables),
                                constraints=list(graph.constraints))
        probe.add(Predicate(scope_=tuple(goals), fn=_goal_differs,
                            label=f"goal != {candidate_goal}"))
        res = logic.solve(probe, max_solutions=1)
        if res.status == logic.Status.SATISFIABLE or res.solutions:
            alt = res.solutions[0]
            verified = logic.verify(graph, alt).ok    # verify against the ORIGINAL model
            alt_goal = {g: alt[g] for g in goals}
            return CounterExample(
                found=True, alternative=alt, differing_goals=list(goals),
                candidate_goal=candidate_goal, alternative_goal=alt_goal,
                verified=verified,
                note=("a distinct, verified solution assigns the goal differently — "
                      "the answer is NOT unique"))
        return CounterExample(found=False, candidate_goal=candidate_goal,
                              note="no solution assigns the goal differently — answer is unique")

    # No goal: look for any structurally distinct verified second solution.
    def _differs(a: Dict[str, Any], _cand=dict(candidate)) -> bool:
        return any(a.get(k) != v for k, v in _cand.items())

    probe = ConstraintGraph(variables=dict(graph.variables),
                            constraints=list(graph.constraints))
    probe.add(Predicate(scope_=tuple(sorted(graph.variables)), fn=_differs,
                        label="assignment != candidate"))
    res = logic.solve(probe, max_solutions=1)
    if res.solutions:
        alt = res.solutions[0]
        verified = logic.verify(graph, alt).ok
        return CounterExample(found=True, alternative=alt, verified=verified,
                              note="a second, distinct verified solution exists")
    return CounterExample(found=False, note="no distinct second solution — assignment is unique")


def invalidates_unique(ce: CounterExample) -> bool:
    """A candidate's uniqueness is refuted only by a VERIFIED differing counter-example."""
    return bool(ce.found and ce.verified)
