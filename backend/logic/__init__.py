"""
logic — the Cognitive Logic Engine (deterministic reasoning).
See docs/adr/ADR-0008-cognitive-logic-engine.md.

Public API:
    from logic import ConstraintGraph, Eq, Ne, Lt, AllDifferent, Implies, Xor, AtMostOne
    from logic import reason            # the full pipeline → Report
    from logic import solve, verify     # lower-level
    from logic import parse             # bounded NL/DSL → Relations
"""
from .constraint_graph import (  # noqa: F401
    ConstraintGraph, Variable, Constraint,
    Eq, Ne, Lt, AllDifferent, Predicate, Implies, Xor, AtMostOne,
)
from .solver import Status, SolveResult, solve, solve_all  # noqa: F401
from .verifier import verify, VerifyReport  # noqa: F401
from .proof import build_proof, Proof  # noqa: F401
from .diagnostics import minimal_conflict, Diagnosis  # noqa: F401
from .parser import parse, parse_line, to_constraints, Relation, ParseResult  # noqa: F401
from .engine import reason, Report  # noqa: F401
