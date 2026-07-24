"""
test_di_framework.py — Decision Intelligence Framework (ADR-0011) unit + integration
====================================================================================
Deterministic, offline (formal models — no LLM). Locks the service layer over the
Cognitive Logic Engine: analyzer guard, verifier, counter-example, confidence gates,
score rubric, the engine's classification + self-check, and determinism.

    python backend/tests/test_di_framework.py
"""
from __future__ import annotations
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

import logic
from logic import ConstraintGraph, Eq, Ne, Lt, AllDifferent
import decision_intelligence as DI
from decision_intelligence.constraint_analyzer import (
    analyze, validate_model, AnalysisModel, ConstraintSpec, Fact)
from decision_intelligence.counter_example import search_counter_example
from decision_intelligence.confidence_engine import assess_confidence
from decision_intelligence.decision_score import Telemetry, score_decision
from decision_intelligence.decision_verifier import verify_decision

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)


# ── Phase 1: analyzer + anti-fabrication guard ────────────────────────────────
def _fake_llm(_prompt):
    # one grounded constraint (span present) + one hallucinated (span absent)
    return json.dumps({
        "variables": [{"name": "x", "domain": [1, 2, 3]}],
        "constraints": [
            {"type": "eq", "a": "x", "b": None, "value": 2, "text": "x is 2",
             "source_span": "x is 2"},                       # grounded
            {"type": "ne", "a": "x", "b": None, "value": 3, "text": "x is not 3",
             "source_span": "x can never equal three"},       # NOT in source → ungrounded
        ],
        "goals": ["x"], "missing_information": [],
    })

def t_analyzer_guard():
    print("== analyzer: never invents facts ==")
    m = analyze("We know x is 2.", llm=_fake_llm)
    grounded = [f for f in m.facts if f.grounded]
    ungrounded = [f for f in m.facts if not f.grounded]
    check("grounded fact admitted as hard constraint",
          len(m.constraints) == 1 and any("2" in c.description for c in m.constraints))
    check("ungrounded fact demoted to assumption",
          len(m.assumptions) == 1 and len(ungrounded) == 1)
    check("ungrounded flagged in missing_information",
          any("ungrounded" in mi.lower() for mi in m.missing_information))

def t_analyzer_validation():
    print("== analyzer: validation ==")
    g = ConstraintGraph(); g.add_var("x", [1, 2])
    m = analyze(graph=g, goals=["nonexistent"])
    check("undeclared goal flagged", any("goal" in i for i in validate_model(m)))
    m2 = analyze(graph=(ConstraintGraph().add_var("x", [1, 2]).add(Eq("x", value=1))))
    check("clean model → no issues", validate_model(m2) == [])


# ── Phase 3: counter-example ──────────────────────────────────────────────────
def t_counter_example():
    print("== counter-example: active invalidation ==")
    # unique answer → no counter-example
    g = ConstraintGraph(); g.add_var("x",[1,2,3]).add_var("y",[1,2,3])
    g.add(Eq("x", value=2)).add(Ne("x", b="y")).add(Ne("y", value=3))
    m = analyze(graph=g, goals=["y"])
    ce = search_counter_example(m, {"x":2,"y":1}, ["y"])
    check("unique answer → no counter-example", not ce.found, ce.note)
    # ambiguous → verified goal-differing counter-example
    g2 = ConstraintGraph(); g2.add_var("a",["R","G"]).add_var("b",["R","G"]); g2.add(Ne("a", b="b"))
    m2 = analyze(graph=g2, goals=["a"])
    ce2 = search_counter_example(m2, {"a":"R","b":"G"}, ["a"])
    check("ambiguous → verified counter-example found", ce2.found and ce2.verified,
          f"alt={ce2.alternative}")


# ── Phase 4: verifier ─────────────────────────────────────────────────────────
def t_verifier():
    print("== verifier: every constraint + assumptions ==")
    g = ConstraintGraph(); g.add_var("x",[1,2,3]); g.add(Eq("x", value=2))
    m = analyze(graph=g, goals=["x"])
    good = verify_decision(m, {"x":2})
    bad = verify_decision(m, {"x":3})
    check("valid assignment PASSES", good.ok and good.passed == 1)
    check("invalid assignment FAILS", not bad.ok and bad.failed >= 1)
    # assumption tracking
    assum = ConstraintSpec(Ne("x", value=1), "x != 1", is_assumption=True)
    m2 = analyze(graph=(ConstraintGraph().add_var("x",[1,2,3]).add(Eq("x",value=2)).add(assum.constraint)),
                 assumptions=[assum], goals=["x"])
    v = verify_decision(m2, {"x":2})
    check("assumption line flagged", any(l.is_assumption for l in v.lines))


# ── Phase 5: confidence gates ─────────────────────────────────────────────────
def t_confidence_gates():
    print("== confidence: evidence + gates ==")
    class V:  # minimal stand-in
        ok=True; passed=3; failed=0; total_constraints=3
        load_bearing_assumptions=[]; unverified_assumptions=[]
    class CEyes: found=True; verified=True
    class CEno: found=False; verified=False
    hi = assess_confidence(classification="SATISFIABLE", verification=V(), counter_example=CEno(),
                           exhaustive=True, proof_verified=True, grounded_facts=3, missing_information=0)
    check("clean SAT → high confidence", hi.answer_confidence > 0.9, str(hi.answer_confidence))
    unk = assess_confidence(classification="UNKNOWN", verification=None, counter_example=CEno(),
                            exhaustive=False, proof_verified=False, grounded_facts=0, missing_information=1)
    check("UNKNOWN gate → 0", unk.answer_confidence == 0.0)
    amb = assess_confidence(classification="MULTIPLE_SOLUTIONS", verification=V(), counter_example=CEyes(),
                            exhaustive=True, proof_verified=True, grounded_facts=1, missing_information=0,
                            distinct_answer_count=2)
    check("alternatives → answer confidence collapses", amb.answer_confidence <= 0.5, str(amb.answer_confidence))


# ── Phase 6: score rubric ─────────────────────────────────────────────────────
def t_score():
    print("== score: /100 rubric ==")
    perfect = Telemetry(classification="SATISFIABLE", verifier_ran=True, verifier_ok=True,
                        constraints_total=3, constraints_checked=3, counter_example_ran=True,
                        counter_example_found=False, forced_single_answer=True,
                        grounded_facts=3, ungrounded_statements=0, ungrounded_flagged=0,
                        answer_confidence=1.0, status_confidence=1.0, exhaustive=True, proof_verified=True)
    s = score_decision(perfect)
    check("clean SAT scores high", s.total >= 95, f"{s.total}/100")
    check("total never exceeds 100", s.total <= 100)
    # forcing a single answer against a verified counter-example tanks consistency
    bad = Telemetry(classification="MULTIPLE_SOLUTIONS", forced_single_answer=True,
                    counter_example_ran=True, counter_example_found=True, counter_example_verified=True,
                    constraints_total=1, constraints_checked=1)
    sb = score_decision(bad)
    check("forcing answer vs counter-example → consistency 0", sb.breakdown["consistency"] == 0)
    check("forcing answer when MULTIPLE → decision_quality 0", sb.breakdown["decision_quality"] == 0)


# ── Phase 2 + self-check: engine classification ───────────────────────────────
def t_engine_classes():
    print("== engine: 5-way classification + self-check ==")
    # SAT unique
    g = ConstraintGraph(); g.add_var("x",[1,2,3]).add_var("y",[1,2,3])
    g.add(Eq("x",value=2)).add(Ne("x",b="y")).add(Ne("y",value=3))
    r = DI.decide(graph=g, goals=["y"])
    check("SAT unique + answer asserted", r.classification.value=="SATISFIABLE" and r.answer=={"y":1})
    # MULTIPLE — never forces a single answer
    g2 = ConstraintGraph(); g2.add_var("a",["R","G"]).add_var("b",["R","G"]); g2.add(Ne("a",b="b"))
    r2 = DI.decide(graph=g2, goals=["a"])
    check("MULTIPLE → refuses single answer", r2.classification.value=="MULTIPLE_SOLUTIONS" and r2.answer is None)
    # UNSAT contradiction
    g3 = ConstraintGraph(); g3.add_var("x",[1,2,3]); g3.add(Eq("x",value=1)).add(Eq("x",value=2))
    r3 = DI.decide(graph=g3, goals=["x"])
    check("UNSAT + contradiction detected", r3.classification.value=="UNSATISFIABLE" and r3.contradiction)
    # UNKNOWN — prose with no variables → refuse
    r4 = DI.decide(problem="Should we expand to Europe next year?")
    check("prose w/o model → UNKNOWN (refuse)", r4.classification.value=="UNKNOWN" and r4.confidence.answer_confidence==0.0)


def t_determinism():
    print("== determinism: identical model → identical report ==")
    def build():
        g = ConstraintGraph(); g.add_var("x",[1,2,3]).add_var("y",[1,2,3])
        g.add(Eq("x",value=2)).add(Ne("x",b="y")).add(Ne("y",value=3))
        return DI.decide(graph=g, goals=["y"])
    a, b = build().as_dict(), build().as_dict()
    check("two runs byte-identical", json.dumps(a, sort_keys=True, default=str)==json.dumps(b, sort_keys=True, default=str))


def main():
    for fn in (t_analyzer_guard, t_analyzer_validation, t_counter_example, t_verifier,
               t_confidence_gates, t_score, t_engine_classes, t_determinism):
        try: fn()
        except Exception as e:
            check(fn.__name__, False, f"harness error: {type(e).__name__}: {e}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1


# pytest entry points
def test_analyzer_guard(): t_analyzer_guard(); assert not FAILED
def test_engine_classes(): t_engine_classes(); assert not FAILED
def test_determinism(): t_determinism(); assert not FAILED

if __name__ == "__main__":
    raise SystemExit(main())
