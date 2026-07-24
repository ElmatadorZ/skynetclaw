"""
test_di_benchmark.py — Decision Intelligence Framework benchmark suite (ADR-0011)
================================================================================
The mission's benchmark families, built as FORMAL models (deterministic, no LLM), each
asserting an acceptance criterion:

    Logic Grid · Scheduling · Constraint Satisfaction · Knight and Knave · Salary ·
    Graph Reasoning · Impossible · Contradictory · Underconstrained · Multiple-valid

Acceptance criteria exercised:
    ✓ detect impossible      ✓ detect contradictions     ✓ detect ambiguous / multiple
    ✓ refuse unsupported     ✓ deterministic output      ✓ confidence from evidence

    python backend/tests/test_di_benchmark.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

from logic import ConstraintGraph, Eq, Ne, Lt, AllDifferent, Predicate
import decision_intelligence as DI

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)

def _g(*vars_):
    g = ConstraintGraph()
    for name, dom in vars_:
        g.add_var(name, dom)
    return g


# 1 ── LOGIC GRID: unique arrangement ─────────────────────────────────────────
def t_logic_grid():
    # 3 people at positions 1..3; Carol=3, Alice<Bob, all distinct ⇒ Alice=1,Bob=2,Carol=3
    g = _g(("Alice",[1,2,3]), ("Bob",[1,2,3]), ("Carol",[1,2,3]))
    g.add(AllDifferent(("Alice","Bob","Carol"))).add(Eq("Carol", value=3)).add(Lt("Alice","Bob"))
    r = DI.decide(graph=g, goals=["Alice","Bob","Carol"],
                  problem="Alice left of Bob; Carol is third; all in distinct seats 1-3.")
    check("logic-grid SATISFIABLE unique",
          r.classification.value=="SATISFIABLE" and r.answer=={"Alice":1,"Bob":2,"Carol":3},
          str(r.answer))
    check("logic-grid confident", r.confidence.answer_confidence > 0.9)


# 2 ── SCHEDULING: multiple valid schedules ───────────────────────────────────
def t_scheduling():
    # 3 tasks into 3 distinct slots, t1 before t2 — several valid schedules exist
    g = _g(("t1",[1,2,3]), ("t2",[1,2,3]), ("t3",[1,2,3]))
    g.add(AllDifferent(("t1","t2","t3"))).add(Lt("t1","t2"))
    r = DI.decide(graph=g, goals=["t3"], problem="Schedule t1 before t2 in 3 distinct slots.")
    check("scheduling MULTIPLE (t3 not determined)",
          r.classification.value=="MULTIPLE_SOLUTIONS" and r.answer is None, r.classification.value)


# 3 ── CONSTRAINT SATISFACTION: proper 3-colouring of a triangle (multiple) ────
def t_csp_coloring():
    g = _g(("A",["r","g","b"]), ("B",["r","g","b"]), ("C",["r","g","b"]))
    g.add(Ne("A", b="B")).add(Ne("B", b="C")).add(Ne("A", b="C"))
    r = DI.decide(graph=g, problem="Colour a triangle with 3 colours, adjacent differ.")
    check("triangle/3-colours → MULTIPLE", r.classification.value=="MULTIPLE_SOLUTIONS")
    check("triangle/3-colours → verified counter-example", r.counter_example.found and r.counter_example.verified)


# 4 ── KNIGHT AND KNAVE: unique identities ────────────────────────────────────
def t_knight_knave():
    # A says "we are both knaves". 1=knight (truth), 0=knave (lies).
    # truth(A) ⟺ statement;  statement = (A==knave AND B==knave)
    g = _g(("A",[0,1]), ("B",[0,1]))
    def truth(a): return (a["A"]==1) == (a["A"]==0 and a["B"]==0)
    g.add(Predicate(scope_=("A","B"), fn=truth, label='A: "we are both knaves"'))
    r = DI.decide(graph=g, goals=["A","B"], problem='A says: we are both knaves.')
    check("knight-knave SATISFIABLE unique",
          r.classification.value=="SATISFIABLE" and r.answer=={"A":0,"B":1}, str(r.answer))


# 5 ── SALARY: unique ordering ────────────────────────────────────────────────
def t_salary():
    # sA<sB<sC distinct from {50,60,70}, sB=60 ⇒ sA=50, sC=70
    g = _g(("sA",[50,60,70]), ("sB",[50,60,70]), ("sC",[50,60,70]))
    g.add(AllDifferent(("sA","sB","sC"))).add(Lt("sA","sB")).add(Lt("sB","sC")).add(Eq("sB", value=60))
    r = DI.decide(graph=g, goals=["sA","sC"], problem="A<B<C salaries; B earns 60.")
    check("salary SATISFIABLE unique", r.classification.value=="SATISFIABLE" and r.answer=={"sA":50,"sC":70},
          str(r.answer))


# 6 ── GRAPH REASONING: 2-colour a path with one endpoint fixed → unique ───────
def t_graph_reasoning():
    # path a-b-c, 2 colours, a fixed ⇒ b, c forced
    g = _g(("a",[0,1]), ("b",[0,1]), ("c",[0,1]))
    g.add(Ne("a", b="b")).add(Ne("b", b="c")).add(Eq("a", value=0))
    r = DI.decide(graph=g, goals=["a","b","c"], problem="2-colour path a-b-c with a=0.")
    check("graph SATISFIABLE unique", r.classification.value=="SATISFIABLE" and r.answer=={"a":0,"b":1,"c":0},
          str(r.answer))


# 7 ── IMPOSSIBLE: pigeonhole (UNSAT, NOT a contradiction) ─────────────────────
def t_impossible():
    g = _g(("p",[1,2]), ("q",[1,2]), ("r",[1,2]))
    g.add(AllDifferent(("p","q","r")))   # 3 distinct values into 2 slots — impossible
    r = DI.decide(graph=g, problem="Assign 3 distinct values from a 2-value domain.")
    check("pigeonhole → UNSATISFIABLE", r.classification.value=="UNSATISFIABLE")
    check("pigeonhole → NOT flagged contradiction", r.contradiction is False)
    check("impossible → high status confidence", r.confidence.status_confidence >= 0.9)


# 8 ── CONTRADICTORY: directly conflicting facts (UNSAT + contradiction) ───────
def t_contradictory():
    g = _g(("x",[1,2,3]))
    g.add(Eq("x", value=1)).add(Eq("x", value=2))
    r = DI.decide(graph=g, goals=["x"], problem="x is 1 and x is 2.")
    check("x=1 ∧ x=2 → UNSATISFIABLE + contradiction", r.classification.value=="UNSATISFIABLE" and r.contradiction)
    check("contradiction → minimal core surfaced", len(r.unsat_core) >= 2, str(r.unsat_core))
    # eq/ne conflict on a pair
    g2 = _g(("u",[1,2]), ("v",[1,2]))
    g2.add(Eq("u", b="v")).add(Ne("u", b="v"))
    r2 = DI.decide(graph=g2, problem="u=v and u!=v.")
    check("u=v ∧ u!=v → contradiction", r2.classification.value=="UNSATISFIABLE" and r2.contradiction)


# 9 ── UNDERCONSTRAINED: goal not determined by any constraint ─────────────────
def t_underconstrained():
    g = _g(("x",[1,2]), ("z",[1,2]))
    g.add(Eq("x", value=1))            # z is free; asked to determine z
    r = DI.decide(graph=g, goals=["z"], problem="x=1; determine z (nothing constrains z).")
    check("free goal → UNDERCONSTRAINED", r.classification.value=="UNDERCONSTRAINED" and r.answer is None,
          r.classification.value)
    check("underconstrained → refuses answer, low answer-confidence", r.confidence.answer_confidence <= 0.5)


# 10 ── MULTIPLE VALID ANSWERS surfaced honestly (goal genuinely varies) ───────
def t_multiple_answers():
    g = _g(("a",["R","G"]), ("b",["R","G"]))
    g.add(Ne("a", b="b"))
    r = DI.decide(graph=g, goals=["a"], problem="a≠b over {R,G}; find a.")
    vals = sorted({s["a"] for s in r.candidate_solutions})
    check("both answers exist, none forced", r.answer is None and vals==["G","R"], str(vals))


# 11 ── DETERMINISM across the whole suite ─────────────────────────────────────
def t_determinism_suite():
    import json
    def run():
        g = _g(("Alice",[1,2,3]), ("Bob",[1,2,3]), ("Carol",[1,2,3]))
        g.add(AllDifferent(("Alice","Bob","Carol"))).add(Eq("Carol", value=3)).add(Lt("Alice","Bob"))
        return json.dumps(DI.decide(graph=g, goals=["Alice","Bob","Carol"]).as_dict(),
                          sort_keys=True, default=str)
    check("benchmark determinism", run()==run())


def main():
    for fn in (t_logic_grid, t_scheduling, t_csp_coloring, t_knight_knave, t_salary,
               t_graph_reasoning, t_impossible, t_contradictory, t_underconstrained,
               t_multiple_answers, t_determinism_suite):
        print(f"== {fn.__name__} ==")
        try: fn()
        except Exception as e:
            check(fn.__name__, False, f"harness error: {type(e).__name__}: {e}")
    print(f"\n{'ALL BENCHMARKS PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1


# pytest entry points
def test_impossible(): t_impossible(); assert not FAILED
def test_contradictory(): t_contradictory(); assert not FAILED
def test_multiple(): t_multiple_answers(); assert not FAILED
def test_underconstrained(): t_underconstrained(); assert not FAILED

if __name__ == "__main__":
    raise SystemExit(main())
