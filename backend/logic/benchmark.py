"""
logic/benchmark.py — the Cognitive Logic Engine benchmark suite
===============================================================
Each case builds a ConstraintGraph and asserts the ENGINE's status (+ proof
re-verifies). No benchmark-specific prompt engineering — pure architecture.

Cases: logic-grid · knight&knave · graph-coloring · sudoku(4x4) · scheduling ·
SAT · UNSAT · under-constrained · contradictory-instructions.

Run:  python -m logic.benchmark
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from .constraint_graph import ConstraintGraph, Eq, Ne, Lt, AllDifferent, Implies, Xor, Predicate
from .solver import Status
from .engine import reason


# ── builders ──────────────────────────────────────────────────────────────────
def logic_grid() -> ConstraintGraph:
    # 3 people at positions 1..3: Alice left of Bob; Carol is at 3. → unique.
    g = ConstraintGraph()
    for p in ("Alice", "Bob", "Carol"):
        g.add_var(p, [1, 2, 3])
    g.add(AllDifferent(("Alice", "Bob", "Carol")))
    g.add(Lt("Alice", "Bob"))
    g.add(Eq("Carol", value=3))
    return g


def knights_and_knaves() -> ConstraintGraph:
    # Determinate classic: A says "At least one of us is a knave."
    # Knight(1)=truth-teller, Knave(0)=liar.
    #   A knight ⇒ statement TRUE  ⇒ (A is knave OR B is knave)
    #   A knave  ⇒ statement FALSE ⇒ (A is knight AND B is knight)  [impossible if A is knave]
    # → forces A=knight, B=knave (unique). If A were a knave, its own statement about
    #   a knave existing would be true, but a knave cannot speak truth — contradiction.
    g = ConstraintGraph()
    g.add_var("A", [0, 1]).add_var("B", [0, 1])
    at_least_one_knave = Predicate(("A", "B"), lambda x: x["A"] == 0 or x["B"] == 0, "≥1 knave")
    no_knave = Predicate(("A", "B"), lambda x: x["A"] == 1 and x["B"] == 1, "no knave")
    g.add(Implies(Eq("A", value=1), at_least_one_knave))
    g.add(Implies(Eq("A", value=0), no_knave))
    return g


def knights_and_knaves_paradox() -> ConstraintGraph:
    # The liar: A says "I am a knave." Knight⇒true⇒A is a knave (contra); Knave⇒false⇒
    # A is a knight (contra). → UNSATISFIABLE (impossible).
    g = ConstraintGraph()
    g.add_var("A", [0, 1])
    g.add(Implies(Eq("A", value=1), Eq("A", value=0)))   # knight ⇒ statement true ⇒ A knave
    g.add(Implies(Eq("A", value=0), Eq("A", value=1)))   # knave  ⇒ statement false ⇒ A knight
    return g


def graph_coloring() -> ConstraintGraph:
    # triangle A-B-C, 3 colors → 6 proper colorings (MULTIPLE)
    g = ConstraintGraph()
    for v in ("A", "B", "C"):
        g.add_var(v, ["red", "green", "blue"])
    g.add(Ne("A", "B")).add(Ne("B", "C")).add(Ne("A", "C"))
    return g


def graph_coloring_unsat() -> ConstraintGraph:
    # triangle with only 2 colors → impossible
    g = ConstraintGraph()
    for v in ("A", "B", "C"):
        g.add_var(v, ["red", "green"])
    g.add(Ne("A", "B")).add(Ne("B", "C")).add(Ne("A", "C"))
    return g


def sudoku_4x4() -> ConstraintGraph:
    # 4x4 Latin-square-ish sudoku with a few givens → unique.
    g = ConstraintGraph()
    cells = [(r, c) for r in range(4) for c in range(4)]
    for (r, c) in cells:
        g.add_var(f"c{r}{c}", [1, 2, 3, 4])
    for r in range(4):
        g.add(AllDifferent(tuple(f"c{r}{c}" for c in range(4))))
    for c in range(4):
        g.add(AllDifferent(tuple(f"c{r}{c}" for r in range(4))))
    for br in (0, 2):
        for bc in (0, 2):
            box = tuple(f"c{br+i}{bc+j}" for i in range(2) for j in range(2))
            g.add(AllDifferent(box))
    # Givens taken from a VALID solved grid (so the puzzle is genuinely solvable):
    #   1 2 | 3 4
    #   3 4 | 1 2
    #   ----+----
    #   2 1 | 4 3
    #   4 3 | 2 1
    givens = {"c00": 1, "c01": 2, "c02": 3,
              "c10": 3, "c13": 2,
              "c21": 1, "c22": 4,
              "c30": 4, "c33": 1}
    for k, v in givens.items():
        g.add(Eq(k, value=v))
    return g


def scheduling() -> ConstraintGraph:
    # 3 talks in 3 slots; Keynote before Workshop; Panel is slot 2. → unique.
    g = ConstraintGraph()
    for t in ("Keynote", "Workshop", "Panel"):
        g.add_var(t, [1, 2, 3])
    g.add(AllDifferent(("Keynote", "Workshop", "Panel")))
    g.add(Lt("Keynote", "Workshop"))
    g.add(Eq("Panel", value=2))
    return g


def plain_sat() -> ConstraintGraph:
    g = ConstraintGraph()
    g.add_var("x", [0, 1]).add_var("y", [0, 1])
    g.add(Eq("x", value=1)).add(Ne("x", "y"))     # x=1, y=0 → unique
    return g


def plain_unsat() -> ConstraintGraph:
    g = ConstraintGraph()
    g.add_var("x", [1, 2]).add_var("y", [1, 2])
    g.add(Lt("x", "y")).add(Lt("y", "x"))          # x<y and y<x
    return g


def under_constrained() -> ConstraintGraph:
    g = ConstraintGraph()
    g.add_var("a", [1, 2]).add_var("b", [1, 2]).add_var("free", [7, 8, 9])
    g.add(Ne("a", "b"))                            # 'free' touched by nothing
    return g


def contradictory_instructions() -> ConstraintGraph:
    # "Room must be A"; "Room must not be A"; "Room must be A or B" → UNSAT (A vs not-A)
    g = ConstraintGraph()
    g.add_var("Room", ["A", "B", "C"])
    g.add(Eq("Room", value="A"))
    g.add(Ne("Room", value="A"))
    return g


# ── the suite ─────────────────────────────────────────────────────────────────
CASES: List[Tuple[str, Callable[[], ConstraintGraph], Status]] = [
    ("logic_grid",                logic_grid,                Status.SATISFIABLE),
    ("knights_and_knaves",        knights_and_knaves,        Status.SATISFIABLE),
    ("knights_paradox_unsat",     knights_and_knaves_paradox,Status.UNSATISFIABLE),
    ("graph_coloring_3col",       graph_coloring,            Status.MULTIPLE_SOLUTIONS),
    ("graph_coloring_2col_unsat", graph_coloring_unsat,      Status.UNSATISFIABLE),
    ("sudoku_4x4",                sudoku_4x4,                Status.SATISFIABLE),
    ("scheduling",                scheduling,                Status.SATISFIABLE),
    ("plain_sat",                 plain_sat,                 Status.SATISFIABLE),
    ("plain_unsat",               plain_unsat,               Status.UNSATISFIABLE),
    ("under_constrained",         under_constrained,         Status.UNDERCONSTRAINED),
    ("contradictory_instructions",contradictory_instructions,Status.UNSATISFIABLE),
]


def run() -> Dict[str, object]:
    rows = []
    ok = 0
    for name, build, expect in CASES:
        g = build()
        rep = reason(g)
        status_ok = rep.status == expect
        # every produced proof must re-verify (SAT model verified; UNSAT core; etc.)
        proof_ok = rep.proof.verified or rep.status in (Status.UNKNOWN,)
        # determinism: same input twice → identical status + solution
        rep2 = reason(build())
        deterministic = (rep2.status == rep.status and rep2.solution == rep.solution)
        passed = status_ok and proof_ok and deterministic
        ok += bool(passed)
        rows.append({"case": name, "expect": expect.value, "got": rep.status.value,
                     "proof_verified": rep.proof.verified, "deterministic": deterministic,
                     "answer_conf": round(rep.answer_confidence, 2), "pass": passed})
    return {"passed": ok, "total": len(CASES), "rows": rows}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    res = run()
    for r in res["rows"]:
        mark = "OK " if r["pass"] else "XX "
        print(f"  {mark}{r['case']:28} expect={r['expect']:18} got={r['got']:18} "
              f"proof={r['proof_verified']} det={r['deterministic']} conf={r['answer_conf']}")
    print(f"\nBENCHMARK {res['passed']}/{res['total']} passed")
