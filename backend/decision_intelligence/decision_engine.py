"""
decision_intelligence/decision_engine.py — Phases 2 + Self-check: the orchestrator
==================================================================================
Single responsibility: COMPOSE the framework into one auditable decision act and
render it in the mission's OUTPUT FORMAT.

Pipeline:
    analyze (Phase 1)  → AnalysisModel
    solve   (logic)    → classify: SATISFIABLE / UNSATISFIABLE / UNDERCONSTRAINED /
                         MULTIPLE_SOLUTIONS / UNKNOWN   (+ contradiction diagnosis)
    counter-example (Phase 3) → active invalidation of the candidate answer
    verify  (Phase 4)  → PASS/FAIL for every constraint + assumption
    confidence (Phase 5) → confidence from evidence
    score   (Phase 6)  → /100 auditability rubric

SELF-CHECK loop: before asserting an answer, try to prove it wrong.
  · If the chosen candidate fails independent verification, advance to the next
    verified solution (a real re-derivation), else conclude UNKNOWN.
  · If a VERIFIED goal-differing counter-example exists, the answer is NOT unique —
    reclassify honestly to MULTIPLE_SOLUTIONS / UNDERCONSTRAINED rather than force one.
Because DIF never invents facts, there is nothing to add on a failed check, so the loop
converges to the honest non-unique / UNKNOWN classification rather than looping forever.

CONTRADICTION is a diagnosis on UNSATISFIABLE (a variable forced to two constants, or a
constraint asserted with its negation) — distinct from a mere capacity impossibility.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import logic
from logic import ConstraintGraph, Eq

from .constraint_analyzer import AnalysisModel, analyze
from .counter_example import search_counter_example, CounterExample, invalidates_unique
from .decision_verifier import verify_decision, DecisionVerification
from .confidence_engine import assess_confidence, ConfidenceReport
from .decision_score import Telemetry, score_decision, DecisionScore


class Classification(str, Enum):
    SATISFIABLE = "SATISFIABLE"
    UNSATISFIABLE = "UNSATISFIABLE"
    UNDERCONSTRAINED = "UNDERCONSTRAINED"
    MULTIPLE_SOLUTIONS = "MULTIPLE_SOLUTIONS"
    UNKNOWN = "UNKNOWN"


@dataclass
class DecisionReport:
    classification: Classification
    contradiction: bool
    candidate_solution: Optional[Dict[str, Any]]
    candidate_solutions: List[Dict[str, Any]]
    answer: Optional[Dict[str, Any]]                 # goal→value if a UNIQUE answer, else None
    unsat_core: List[str]
    counter_example: CounterExample
    verification: DecisionVerification
    confidence: ConfidenceReport
    score: DecisionScore
    model: AnalysisModel
    reasoning_trace: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification.value,
            "contradiction": self.contradiction,
            "answer": self.answer,
            "candidate_solution": self.candidate_solution,
            "candidate_solutions": self.candidate_solutions,
            "unsat_core": self.unsat_core,
            "counter_example": self.counter_example.as_dict(),
            "verification": self.verification.as_dict(),
            "confidence": self.confidence.as_dict(),
            "score": self.score.as_dict(),
            "model": self.model.as_dict(),
            "reasoning_trace": self.reasoning_trace,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Contradiction diagnosis (a refinement of UNSATISFIABLE)
# ──────────────────────────────────────────────────────────────────────────────
def _detect_contradiction(model: AnalysisModel, mus_constraints) -> bool:
    """True iff the minimal conflict is a LOGICAL conflict rather than mere capacity.
    Detected structurally: a variable forced (by Eq-to-constant) to two distinct
    constants, or an Eq and a Ne on the same pair/value both present in the core."""
    forced: Dict[str, set] = {}
    eq_pairs = set()
    ne_pairs = set()
    for c in mus_constraints:
        kind = getattr(c, "kind", "")
        if kind == "equality" and getattr(c, "b", None) is None:
            forced.setdefault(c.a, set()).add(c.value)
        if kind == "equality" and getattr(c, "b", None) is not None:
            eq_pairs.add(frozenset((c.a, c.b)))
        if kind == "inequality" and getattr(c, "b", None) is not None:
            ne_pairs.add(frozenset((c.a, c.b)))
    if any(len(vals) >= 2 for vals in forced.values()):
        return True
    if eq_pairs & ne_pairs:
        return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Classification (Phase 2)
# ──────────────────────────────────────────────────────────────────────────────
def _classify(model: AnalysisModel):
    """Return (Classification, solve_result, candidate, candidate_solutions,
    contradiction, unsat_core)."""
    graph = model.graph()
    result = logic.solve(graph, max_solutions=2)
    st = result.status
    solutions = list(result.solutions)

    if st == logic.Status.UNSATISFIABLE:
        diag = logic.minimal_conflict(graph)
        contradiction = _detect_contradiction(model, diag.conflict_constraints)
        return (Classification.UNSATISFIABLE, result, None, [], contradiction,
                list(diag.minimal_conflict))

    if st == logic.Status.UNKNOWN:
        return (Classification.UNKNOWN, result, None, [], False, [])

    if st == logic.Status.SATISFIABLE:
        return (Classification.SATISFIABLE, result, solutions[0], solutions, False, [])

    # MULTIPLE_SOLUTIONS or UNDERCONSTRAINED — the engine already distinguishes them by
    # the presence of a structurally unconstrained variable.
    cls = (Classification.UNDERCONSTRAINED
           if st == logic.Status.UNDERCONSTRAINED else Classification.MULTIPLE_SOLUTIONS)
    return (cls, result, solutions[0] if solutions else None, solutions, False, [])


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────────────
def decide(problem: Any = "", *, model: Optional[AnalysisModel] = None,
           graph: Optional[ConstraintGraph] = None, goals=None, unknowns=None,
           assumptions=None, missing_information=None, facts=None, llm=None,
           max_selfcheck: int = 8) -> DecisionReport:
    """Run the full auditable decision pipeline. Deterministic for a fixed model."""
    model = analyze(problem, model=model, graph=graph, goals=goals, unknowns=unknowns,
                    assumptions=assumptions, missing_information=missing_information,
                    facts=facts, llm=llm)
    trace: List[str] = []

    # Guard: an ill-formed model (e.g. prose with no variables) → UNKNOWN, refuse to guess.
    issues = _fatal_issues(model)
    if issues:
        trace.append("model not solvable: " + "; ".join(issues))
        return _unknown_report(model, trace, reason="; ".join(issues))

    cls, result, candidate, candidate_solutions, contradiction, unsat_core = _classify(model)
    trace.append(f"solve → {cls.value}" + (" (contradiction)" if contradiction else ""))

    goals_eff = list(model.goals)

    # ── SELF-CHECK loop ──────────────────────────────────────────────────────
    counter_example = CounterExample(found=False, note="not applicable")
    verification = verify_decision(model, candidate)
    forced_single = False
    answer: Optional[Dict[str, Any]] = None

    if cls == Classification.SATISFIABLE:
        # (a) the candidate must independently verify; if not, re-derive from the next
        #     verified solution (bounded), else UNKNOWN.
        tries = 0
        pool = list(candidate_solutions)
        while candidate is not None and not verification.ok and tries < max_selfcheck:
            trace.append("self-check: candidate failed verification — re-deriving")
            pool = pool[1:]
            candidate = pool[0] if pool else None
            verification = verify_decision(model, candidate)
            tries += 1
        if candidate is None or not verification.ok:
            trace.append("self-check: no verified candidate — refusing (UNKNOWN)")
            return _unknown_report(model, trace, reason="no candidate survived verification")

        # (b) actively try to prove the answer wrong.
        counter_example = search_counter_example(model, candidate, goals_eff)
        trace.append("counter-example search: " + counter_example.note)
        if invalidates_unique(counter_example):
            # honest reclassification — never force a single answer
            cls = (Classification.UNDERCONSTRAINED
                   if model.graph().unconstrained_vars() else Classification.MULTIPLE_SOLUTIONS)
            trace.append(f"self-check: uniqueness refuted → reclassified {cls.value}")
            answer = None
        else:
            answer = ({g: candidate[g] for g in goals_eff} if goals_eff
                      else dict(candidate))
            forced_single = True
            trace.append("self-check: no counter-example — answer asserted")

    elif cls in (Classification.MULTIPLE_SOLUTIONS, Classification.UNDERCONSTRAINED):
        counter_example = search_counter_example(model, candidate, goals_eff)
        trace.append("counter-example search: " + counter_example.note)
        # If a goal is specified and it is in fact identical across solutions, the ANSWER
        # is unique even though full assignments differ → upgrade to SATISFIABLE-answer.
        if goals_eff and counter_example.found is False and candidate is not None:
            answer = {g: candidate[g] for g in goals_eff}
            cls = Classification.SATISFIABLE
            forced_single = True
            verification = verify_decision(model, candidate)
            trace.append("goal determined across all solutions → answer is unique")
        else:
            answer = None

    # proof (for confidence + report)
    proof = logic.build_proof(model.graph(), result,
                              mus=unsat_core if unsat_core else None)

    # ── Confidence (Phase 5) ──
    confidence = assess_confidence(
        classification=cls.value,
        verification=(verification if cls == Classification.SATISFIABLE else
                      (verification if verification.total_constraints else None)),
        counter_example=counter_example,
        exhaustive=result.exhausted,
        proof_verified=proof.verified,
        grounded_facts=len(model.grounded_facts()),
        missing_information=len(model.missing_information),
        distinct_answer_count=_distinct_goal_values(candidate_solutions, goals_eff),
    )
    trace.append(f"confidence → answer={confidence.answer_confidence:.2f} "
                 f"status={confidence.status_confidence:.2f}")

    # ── Score (Phase 6) ──
    telem = Telemetry(
        classification=cls.value,
        verifier_ran=(candidate is not None),
        verifier_ok=verification.ok,
        constraints_total=len(model.all_constraint_specs()),
        constraints_checked=verification.total_constraints,
        counter_example_ran=(cls != Classification.UNSATISFIABLE and cls != Classification.UNKNOWN),
        counter_example_found=counter_example.found,
        counter_example_verified=counter_example.verified,
        forced_single_answer=forced_single,
        grounded_facts=len(model.grounded_facts()),
        ungrounded_statements=len(model.assumptions),
        ungrounded_flagged=len(model.assumptions),   # every assumption is flagged by construction
        answer_confidence=confidence.answer_confidence,
        status_confidence=confidence.status_confidence,
        exhaustive=result.exhausted,
        proof_verified=proof.verified,
    )
    score = score_decision(telem)

    return DecisionReport(
        classification=cls, contradiction=contradiction,
        candidate_solution=candidate, candidate_solutions=candidate_solutions,
        answer=answer, unsat_core=unsat_core, counter_example=counter_example,
        verification=verification, confidence=confidence, score=score,
        model=model, reasoning_trace=trace,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _fatal_issues(model: AnalysisModel) -> List[str]:
    from .constraint_analyzer import validate_model
    issues = validate_model(model)
    # only STRUCTURAL impossibilities are fatal; missing_information is honest, not fatal
    return [i for i in issues if "unknown variable" in i or "empty domain" in i
            or i == "no variables declared"]


def _distinct_goal_values(solutions: List[Dict[str, Any]], goals: List[str]) -> int:
    if not goals or not solutions:
        return max(len(solutions), 1)
    seen = {tuple(s[g] for g in goals) for s in solutions if all(g in s for g in goals)}
    return max(len(seen), 1)


def _unknown_report(model: AnalysisModel, trace: List[str], reason: str) -> DecisionReport:
    verification = DecisionVerification(ok=False)
    counter_example = CounterExample(found=False, note="not applicable (UNKNOWN)")
    confidence = assess_confidence(
        classification="UNKNOWN", verification=None, counter_example=counter_example,
        exhaustive=False, proof_verified=False,
        grounded_facts=len(model.grounded_facts()),
        missing_information=len(model.missing_information) or 1,
    )
    telem = Telemetry(classification="UNKNOWN", answer_confidence=0.0,
                      constraints_total=len(model.all_constraint_specs()),
                      grounded_facts=len(model.grounded_facts()),
                      ungrounded_statements=len(model.assumptions),
                      ungrounded_flagged=len(model.assumptions))
    score = score_decision(telem)
    return DecisionReport(
        classification=Classification.UNKNOWN, contradiction=False,
        candidate_solution=None, candidate_solutions=[], answer=None,
        unsat_core=[], counter_example=counter_example, verification=verification,
        confidence=confidence, score=score, model=model, reasoning_trace=trace,
    )


# ──────────────────────────────────────────────────────────────────────────────
# OUTPUT FORMAT rendering
# ──────────────────────────────────────────────────────────────────────────────
def render_report(r: DecisionReport) -> str:
    m = r.model
    L: List[str] = []
    add = L.append

    add("=" * 66)
    add("DECISION INTELLIGENCE REPORT")
    add("=" * 66)

    add("\n## Problem Analysis")
    add((m.raw_problem.strip() or "(formal model — no prose supplied)"))

    add("\n## Facts")
    if m.facts:
        for f in m.facts:
            flag = "" if f.grounded else "  [UNGROUNDED → assumption]"
            add(f"  - {f.text}{flag}")
    else:
        add("  (none extracted)")

    add("\n## Variables")
    for v in m.variables:
        add(f"  - {v.name} ∈ {{{', '.join(str(x) for x in v.domain)}}}")
    if not m.variables:
        add("  (none)")

    add("\n## Constraints")
    for cs in m.constraints:
        add(f"  - {cs.description}")
    if not m.constraints:
        add("  (none)")

    add("\n## Assumptions")
    if m.assumptions:
        for cs in m.assumptions:
            add(f"  - {cs.description}  [flagged, not a stated fact]")
    else:
        add("  (none — no unsupported facts admitted)")

    add("\n## Missing Information")
    if m.missing_information:
        for mi in m.missing_information:
            add(f"  - {mi}")
    else:
        add("  (none)")

    add("\n## Candidate Solutions")
    if r.candidate_solutions:
        for i, s in enumerate(r.candidate_solutions, 1):
            add(f"  {i}. {_fmt(s)}")
    elif r.classification == Classification.UNSATISFIABLE:
        add("  (none — the problem is impossible)")
    else:
        add("  (none)")

    add("\n## Decision")
    add(f"  Classification: {r.classification.value}"
        + ("  [CONTRADICTION]" if r.contradiction else ""))
    if r.answer is not None:
        add(f"  Answer: {_fmt(r.answer)}")
    elif r.classification == Classification.UNSATISFIABLE:
        add("  No solution exists. Minimal conflict:")
        for c in r.unsat_core:
            add(f"    · {c}")
    elif r.classification in (Classification.MULTIPLE_SOLUTIONS,
                              Classification.UNDERCONSTRAINED):
        add("  Uniqueness REFUSED — multiple valid solutions exist (no single answer asserted).")
    else:
        add("  UNKNOWN — insufficient/unresolvable information; refusing to guess.")

    add("\n## Counter Example")
    ce = r.counter_example
    if ce.found:
        add(f"  Found (verified={ce.verified}): {_fmt(ce.alternative)}")
        if ce.differing_goals:
            add(f"  Goal differs: {ce.candidate_goal} vs {ce.alternative_goal}")
        add(f"  → {ce.note}")
    else:
        add(f"  None found — {ce.note}")

    add("\n## Verification")
    v = r.verification
    add(f"  Overall: {'PASS' if v.ok else 'FAIL'}  ({v.passed} pass / {v.failed} fail)")
    for line in v.lines:
        tag = " [assumption]" if line.is_assumption else ""
        add(f"    [{line.result}] {line.description}{tag}"
            + (f" — {line.detail}" if line.detail else ""))
    if v.load_bearing_assumptions:
        add(f"  Load-bearing assumptions: {', '.join(v.load_bearing_assumptions)}")

    add("\n## Confidence")
    cf = r.confidence
    add(f"  Answer confidence: {cf.answer_confidence:.2f}   "
        f"Status confidence: {cf.status_confidence:.2f}")
    add("  Components (evidence, not heuristic):")
    for k, val in cf.components.as_dict().items():
        add(f"    · {k}: {val}")
    for n in cf.calibration_notes:
        add(f"  note: {n}")

    add("\n## Decision Score")
    add(r.score.render())
    for n in r.score.notes:
        add(f"  note: {n}")

    add("\n" + "=" * 66)
    return "\n".join(L)


def _fmt(sol: Optional[Dict[str, Any]]) -> str:
    if not sol:
        return "{}"
    return "{" + ", ".join(f"{k}={sol[k]}" for k in sorted(sol)) + "}"
