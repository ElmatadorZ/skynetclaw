"""
logic/parser.py — bounded NL/DSL → structured constraints
=========================================================
Single responsibility: convert statements in a DOCUMENTED, bounded grammar into
structured Relations, and (given a graph's variables) into Constraints. It NEVER
silently drops information: anything it cannot parse is returned in `unparsed` and
lowers the engine's confidence. Open-domain English is out of scope by design — the
model frames NL into these forms; the engine does the exact reasoning.

Grammar (case-insensitive; A, B are identifiers):
    A is B            | A = B    | A equals B          → Relation(equal, A, B)
    A is not B        | A != B   | A isn't B           → Relation(not_equal, A, B)
    A left of B       | A left_of B | A before B | A < B → Relation(left_of, A, B)
    A right of B      | A after B | A > B                → Relation(left_of, B, A)
    A is <value>                                         → Relation(equal_value, A, <value>)

Example (from the mission):
    "Alice is left of Bob"  →  Relation(left_of, Alice, Bob)

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .constraint_graph import ConstraintGraph, Constraint, Eq, Ne, Lt


@dataclass(frozen=True)
class Relation:
    predicate: str          # equal | not_equal | left_of | equal_value
    a: str
    b: Any

    def __repr__(self) -> str:
        return f"Relation({self.predicate}, {self.a}, {self.b})"


_ID = r"[A-Za-z_][A-Za-z0-9_]*"
_RULES: List[Tuple[re.Pattern, str, bool]] = [
    # (pattern, predicate, swap?)  — capture groups (1)=a (2)=b
    (re.compile(rf"^\s*({_ID})\s+is\s+not\s+({_ID})\s*$", re.I), "not_equal", False),
    (re.compile(rf"^\s*({_ID})\s+isn't\s+({_ID})\s*$", re.I), "not_equal", False),
    (re.compile(rf"^\s*({_ID})\s*!=\s*({_ID})\s*$"), "not_equal", False),
    (re.compile(rf"^\s*({_ID})\s+(?:is\s+)?(?:left[ _]of|before)\s+({_ID})\s*$", re.I), "left_of", False),
    (re.compile(rf"^\s*({_ID})\s*<\s*({_ID})\s*$"), "left_of", False),
    (re.compile(rf"^\s*({_ID})\s+(?:is\s+)?(?:right[ _]of|after)\s+({_ID})\s*$", re.I), "left_of", True),
    (re.compile(rf"^\s*({_ID})\s*>\s*({_ID})\s*$"), "left_of", True),
    (re.compile(rf"^\s*({_ID})\s+(?:is|=|equals)\s+({_ID})\s*$", re.I), "equal", False),
]


def parse_line(line: str) -> Optional[Relation]:
    for pat, pred, swap in _RULES:
        m = pat.match(line)
        if m:
            a, b = m.group(1), m.group(2)
            if swap:
                a, b = b, a
            return Relation(pred, a, b)
    return None


@dataclass
class ParseResult:
    relations: List[Relation]
    unparsed: List[str]

    @property
    def complete(self) -> bool:
        return not self.unparsed


def parse(text: str) -> ParseResult:
    """Parse newline- or semicolon-separated statements. Comments (#) and blanks skip."""
    rels: List[Relation] = []
    unparsed: List[str] = []
    for raw in re.split(r"[\n;]+", text or ""):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        r = parse_line(line)
        (rels if r else unparsed).append(r if r else line)
    return ParseResult(rels, unparsed)


def to_constraints(relations: List[Relation], graph: ConstraintGraph) -> Tuple[List[Constraint], List[str]]:
    """Map recognized Relations to Constraints against the graph's variables. A
    relation referencing an unknown variable is reported (never silently dropped)."""
    out: List[Constraint] = []
    problems: List[str] = []
    for r in relations:
        if r.predicate == "equal_value":
            if r.a in graph.variables:
                out.append(Eq(r.a, value=r.b))
            else:
                problems.append(f"unknown variable: {r.a}")
            continue
        # relations over two variables
        if r.a not in graph.variables or r.b not in graph.variables:
            problems.append(f"relation references unknown variable(s): {r}")
            continue
        if r.predicate == "equal":
            out.append(Eq(r.a, b=r.b))
        elif r.predicate == "not_equal":
            out.append(Ne(r.a, b=r.b))
        elif r.predicate == "left_of":
            out.append(Lt(r.a, r.b))
        else:
            problems.append(f"unmapped predicate: {r}")
    return out, problems
