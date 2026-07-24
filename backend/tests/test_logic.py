"""
test_logic.py — unit + integration tests for the Cognitive Logic Engine (ADR-0008).
Deterministic, model-free. Run: python -m pytest tests/test_logic.py
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logic import (ConstraintGraph, Eq, Ne, Lt, AllDifferent, Implies, Xor, AtMostOne,
                   Predicate, solve, verify, reason, parse, to_constraints, Status)
from logic.diagnostics import minimal_conflict
from logic import benchmark


# ── UNIT: parser (never loses information) ───────────────────────────────────
def test_parse_left_of_example():
    r = parse("Alice is left of Bob")
    rel = r.relations[0]
    assert (rel.predicate, rel.a, rel.b) == ("left_of", "Alice", "Bob")
    assert r.complete


def test_parse_flags_unparsed_never_drops():
    r = parse("Alice left of Bob\nthe weather is nice today")
    assert len(r.relations) == 1
    assert r.unparsed == ["the weather is nice today"]   # surfaced, not silently dropped
    assert not r.complete


def test_parse_variants_and_swap():
    assert parse("A != B").relations[0].predicate == "not_equal"
    assert parse("A is not B").relations[0].predicate == "not_equal"
    # "A after B" and "B before A" are the same left_of relation
    assert parse("A after B").relations[0] == parse("B before A").relations[0]


# ── UNIT: constraint semantics + verifier (no silent assumption) ─────────────
def test_no_silent_assumption():
    g = ConstraintGraph().add_var("A", [1]).add_var("B", [1, 2]).add(Eq("A", value=1))
    vr = verify(g, {"A": 1})            # B deliberately missing
    assert not vr.ok and "B" in vr.missing_assignments


def test_verify_rejects_out_of_domain():
    g = ConstraintGraph().add_var("A", [1, 2])
    assert not verify(g, {"A": 9}).ok


def test_constraint_violated_vs_satisfied():
    assert Lt("a", "b").violated({"a": 5, "b": 2})
    assert Lt("a", "b").satisfied({"a": 1, "b": 2})
    assert not Lt("a", "b").satisfied({"a": 1})     # partial ⇒ not satisfied (no assumption)


# ── UNIT: solver — the five honest statuses ──────────────────────────────────
def test_status_satisfiable_unique():
    g = ConstraintGraph().add_var("x", [0, 1]).add_var("y", [0, 1]).add(Eq("x", value=1)).add(Ne("x", "y"))
    r = solve(g)
    assert r.status == Status.SATISFIABLE and r.solutions[0] == {"x": 1, "y": 0}


def test_status_unsatisfiable():
    g = ConstraintGraph().add_var("x", [1, 2]).add_var("y", [1, 2]).add(Lt("x", "y")).add(Lt("y", "x"))
    assert solve(g).status == Status.UNSATISFIABLE


def test_status_multiple():
    g = ConstraintGraph().add_var("A", ["r", "g"]).add_var("B", ["r", "g"]).add(Ne("A", "B"))
    assert solve(g).status == Status.MULTIPLE_SOLUTIONS


def test_status_underconstrained():
    g = ConstraintGraph().add_var("a", [1, 2]).add_var("b", [1, 2]).add_var("free", [7, 8]).add(Ne("a", "b"))
    assert solve(g).status == Status.UNDERCONSTRAINED


def test_status_unknown_refuses_to_guess():
    g = ConstraintGraph()
    for v in "abcdef":
        g.add_var(v, list(range(6)))
    g.add(AllDifferent(tuple("abcdef")))
    r = solve(g, node_budget=1)
    assert r.status == Status.UNKNOWN            # refused to guess under budget


def test_determinism():
    def build():
        g = ConstraintGraph().add_var("A", [1, 2, 3]).add_var("B", [1, 2, 3]).add_var("C", [1, 2, 3])
        return g.add(AllDifferent(("A", "B", "C"))).add(Lt("A", "B")).add(Lt("B", "C"))
    assert solve(build()).solutions == solve(build()).solutions


# ── UNIT: diagnostics — minimal conflict set ─────────────────────────────────
def test_minimal_conflict_isolates_the_cause():
    g = ConstraintGraph().add_var("x", [1, 2]).add_var("y", [1, 2]).add_var("z", [1, 2])
    g.add(Lt("x", "y")).add(Lt("y", "x")).add(Eq("z", value=1))   # z-constraint is irrelevant
    d = minimal_conflict(g)
    assert len(d.minimal_conflict) == 2
    assert all("z" not in m for m in d.minimal_conflict)
    assert d.repair


# ── INTEGRATION: reason() pipeline + computed confidence ─────────────────────
def test_reason_sat_full_confidence_and_verified():
    g = ConstraintGraph().add_var("x", [0, 1]).add(Eq("x", value=1))
    rep = reason(g)
    assert rep.status == Status.SATISFIABLE
    assert rep.answer_confidence == 1.0 and rep.verification.ok and rep.proof.verified


def test_reason_refuses_ambiguous_with_counter_example():
    g = ConstraintGraph().add_var("A", ["r", "g"]).add_var("B", ["r", "g"]).add(Ne("A", "B"))
    rep = reason(g)
    assert rep.answer_confidence == 0.0            # refuses to assert a unique answer
    assert rep.counter_example is not None         # exhibits the second model


def test_reason_unsat_has_diagnosis_and_verified_proof():
    g = ConstraintGraph().add_var("x", [1, 2]).add_var("y", [1, 2]).add(Lt("x", "y")).add(Lt("y", "x"))
    rep = reason(g)
    assert rep.status == Status.UNSATISFIABLE
    assert rep.diagnosis and rep.diagnosis.minimal_conflict and rep.proof.verified


def test_proof_is_reproducible():
    a = reason(benchmark.logic_grid()).proof.as_dict()
    b = reason(benchmark.logic_grid()).proof.as_dict()
    assert a == b                                   # deterministic, reproducible


def test_parse_to_reason_pipeline():
    g = ConstraintGraph()
    for p in ("Alice", "Bob", "Carol"):
        g.add_var(p, [1, 2, 3])
    pr = parse("Alice left of Bob")
    cons, problems = to_constraints(pr.relations, g)
    assert not problems
    for c in cons:
        g.add(c)
    g.add(AllDifferent(("Alice", "Bob", "Carol"))).add(Eq("Carol", value=3))
    rep = reason(g, unresolved_inputs=len(pr.unparsed), total_inputs=1)
    assert rep.status == Status.SATISFIABLE and rep.solution == {"Alice": 1, "Bob": 2, "Carol": 3}


# ── the whole benchmark must pass, deterministically ─────────────────────────
def test_benchmark_suite_all_pass():
    res = benchmark.run()
    assert res["passed"] == res["total"], res["rows"]
