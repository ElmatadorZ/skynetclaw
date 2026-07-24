"""
logic/constraint_graph.py — the constraint model + a queryable graph
====================================================================
Single responsibility: REPRESENT variables (finite domains) and constraints as a
queryable graph. No solving happens here.

Every Constraint answers two questions deterministically:
  · violated(assignment)  — True only if the (possibly PARTIAL) assignment ALREADY
                            makes it impossible (used to prune search).
  · satisfied(assignment) — True only if its whole scope is assigned AND it holds
                            (used by the verifier; a missing variable ⇒ NOT satisfied,
                            never an assumption).

Constraint kinds: equality · inequality · ordering (</>) · all-different · implication
· xor · exclusivity (at-most-one) · membership · predicate. Ordering-style relations
("A left_of B") are modelled as integer position variables + Lt (see parser).

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence, Set, Tuple

Assignment = Dict[str, Any]


def _all_assigned(scope: Sequence[str], a: Assignment) -> bool:
    return all(v in a for v in scope)


# ── Variables ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Variable:
    name: str
    domain: Tuple[Any, ...]

    def __post_init__(self):
        if not self.domain:
            raise ValueError(f"variable {self.name!r} has an empty domain")


# ── Constraint base ───────────────────────────────────────────────────────────
class Constraint:
    kind: str = "constraint"
    scope: Tuple[str, ...] = ()

    def violated(self, a: Assignment) -> bool:      # definitely broken by partial a?
        raise NotImplementedError

    def satisfied(self, a: Assignment) -> bool:     # fully assigned AND holds?
        raise NotImplementedError

    def describe(self) -> str:
        return self.kind

    def __repr__(self) -> str:
        return f"<{self.describe()}>"


# ── Concrete constraints ──────────────────────────────────────────────────────
@dataclass
class Eq(Constraint):
    """a == b   (b is another variable) OR a == value (constant)."""
    a: str = ""
    b: str = None            # variable name
    value: Any = None        # or a constant
    kind: str = field(default="equality", init=False)

    def __post_init__(self):
        self.scope = (self.a,) if self.b is None else (self.a, self.b)

    def violated(self, x: Assignment) -> bool:
        if self.b is None:
            return self.a in x and x[self.a] != self.value
        return _all_assigned(self.scope, x) and x[self.a] != x[self.b]

    def satisfied(self, x: Assignment) -> bool:
        if self.b is None:
            return self.a in x and x[self.a] == self.value
        return _all_assigned(self.scope, x) and x[self.a] == x[self.b]

    def describe(self) -> str:
        return f"{self.a} == {self.value if self.b is None else self.b}"


@dataclass
class Ne(Constraint):
    """a != b (variables) OR a != value."""
    a: str = ""
    b: str = None
    value: Any = None
    kind: str = field(default="inequality", init=False)

    def __post_init__(self):
        self.scope = (self.a,) if self.b is None else (self.a, self.b)

    def violated(self, x: Assignment) -> bool:
        if self.b is None:
            return self.a in x and x[self.a] == self.value
        return _all_assigned(self.scope, x) and x[self.a] == x[self.b]

    def satisfied(self, x: Assignment) -> bool:
        if self.b is None:
            return self.a in x and x[self.a] != self.value
        return _all_assigned(self.scope, x) and x[self.a] != x[self.b]

    def describe(self) -> str:
        return f"{self.a} != {self.value if self.b is None else self.b}"


@dataclass
class Lt(Constraint):
    """a < b on the natural order of the (comparable) domain values."""
    a: str = ""
    b: str = ""
    kind: str = field(default="ordering", init=False)

    def __post_init__(self):
        self.scope = (self.a, self.b)

    def violated(self, x: Assignment) -> bool:
        return _all_assigned(self.scope, x) and not (x[self.a] < x[self.b])

    def satisfied(self, x: Assignment) -> bool:
        return _all_assigned(self.scope, x) and x[self.a] < x[self.b]

    def describe(self) -> str:
        return f"{self.a} < {self.b}"


@dataclass
class AllDifferent(Constraint):
    variables: Tuple[str, ...] = ()
    kind: str = field(default="all_different", init=False)

    def __post_init__(self):
        self.scope = tuple(self.variables)

    def violated(self, x: Assignment) -> bool:
        seen = {}
        for v in self.scope:
            if v in x:
                val = x[v]
                if val in seen:
                    return True
                seen[val] = v
        return False

    def satisfied(self, x: Assignment) -> bool:
        if not _all_assigned(self.scope, x):
            return False
        vals = [x[v] for v in self.scope]
        return len(set(vals)) == len(vals)

    def describe(self) -> str:
        return f"all_different({', '.join(self.scope)})"


@dataclass
class Predicate(Constraint):
    """General constraint: fn(assignment)->bool over an explicit scope. Deterministic."""
    scope_: Tuple[str, ...] = ()
    fn: Callable[[Assignment], bool] = None
    label: str = "predicate"
    kind: str = field(default="predicate", init=False)

    def __post_init__(self):
        self.scope = tuple(self.scope_)

    def violated(self, x: Assignment) -> bool:
        # a predicate can only be judged when its scope is fully assigned
        return _all_assigned(self.scope, x) and not self.fn(x)

    def satisfied(self, x: Assignment) -> bool:
        return _all_assigned(self.scope, x) and bool(self.fn(x))

    def describe(self) -> str:
        return self.label


@dataclass
class Implies(Constraint):
    """premise ⇒ conclusion (both Constraints)."""
    premise: Constraint = None
    conclusion: Constraint = None
    kind: str = field(default="implication", init=False)

    def __post_init__(self):
        self.scope = tuple(sorted(set(self.premise.scope) | set(self.conclusion.scope)))

    def violated(self, x: Assignment) -> bool:
        # broken only when the premise definitely holds and the conclusion is broken
        return self.premise.satisfied(x) and self.conclusion.violated(x)

    def satisfied(self, x: Assignment) -> bool:
        if not _all_assigned(self.scope, x):
            return False
        return (not self.premise.satisfied(x)) or self.conclusion.satisfied(x)

    def describe(self) -> str:
        return f"({self.premise.describe()}) => ({self.conclusion.describe()})"


@dataclass
class Xor(Constraint):
    """exactly one of the two constraints holds."""
    left: Constraint = None
    right: Constraint = None
    kind: str = field(default="xor", init=False)

    def __post_init__(self):
        self.scope = tuple(sorted(set(self.left.scope) | set(self.right.scope)))

    def violated(self, x: Assignment) -> bool:
        if not _all_assigned(self.scope, x):
            return False
        return self.left.satisfied(x) == self.right.satisfied(x)  # both same ⇒ not xor

    def satisfied(self, x: Assignment) -> bool:
        if not _all_assigned(self.scope, x):
            return False
        return self.left.satisfied(x) != self.right.satisfied(x)

    def describe(self) -> str:
        return f"xor({self.left.describe()}, {self.right.describe()})"


@dataclass
class AtMostOne(Constraint):
    """At most one of the given constraints may hold (exclusivity)."""
    members: Tuple[Constraint, ...] = ()
    kind: str = field(default="exclusivity", init=False)

    def __post_init__(self):
        s: Set[str] = set()
        for c in self.members:
            s |= set(c.scope)
        self.scope = tuple(sorted(s))

    def violated(self, x: Assignment) -> bool:
        return sum(1 for c in self.members if c.satisfied(x)) > 1

    def satisfied(self, x: Assignment) -> bool:
        if not _all_assigned(self.scope, x):
            return False
        return sum(1 for c in self.members if c.satisfied(x)) <= 1

    def describe(self) -> str:
        return f"at_most_one({', '.join(c.describe() for c in self.members)})"


# ── The graph ─────────────────────────────────────────────────────────────────
@dataclass
class ConstraintGraph:
    variables: Dict[str, Variable] = field(default_factory=dict)
    constraints: List[Constraint] = field(default_factory=list)

    def add_var(self, name: str, domain: Sequence[Any]) -> "ConstraintGraph":
        self.variables[name] = Variable(name, tuple(domain))
        return self

    def add(self, c: Constraint) -> "ConstraintGraph":
        missing = [v for v in c.scope if v not in self.variables]
        if missing:
            raise ValueError(f"constraint {c.describe()} references unknown variables {missing}")
        self.constraints.append(c)
        return self

    # — queryable —
    def scoped_vars(self) -> Set[str]:
        s: Set[str] = set()
        for c in self.constraints:
            s |= set(c.scope)
        return s

    def unconstrained_vars(self) -> List[str]:
        """Variables that no constraint touches — the structural signal of an
        UNDER-constrained problem."""
        scoped = self.scoped_vars()
        return sorted(v for v in self.variables if v not in scoped)

    def constraints_on(self, var: str) -> List[Constraint]:
        return [c for c in self.constraints if var in c.scope]

    def neighbors(self, var: str) -> Set[str]:
        out: Set[str] = set()
        for c in self.constraints_on(var):
            out |= set(c.scope)
        out.discard(var)
        return out

    def by_kind(self, kind: str) -> List[Constraint]:
        return [c for c in self.constraints if c.kind == kind]

    def summary(self) -> Dict[str, Any]:
        return {"variables": len(self.variables), "constraints": len(self.constraints),
                "unconstrained": self.unconstrained_vars(),
                "kinds": sorted({c.kind for c in self.constraints})}
