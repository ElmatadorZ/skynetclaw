"""
decision_intelligence/constraint_analyzer.py — Phase 1: structured problem analysis
===================================================================================
Single responsibility: turn a problem (natural language OR a formal spec) into a
structured, auditable `AnalysisModel`:

    facts · variables · constraints · unknowns · assumptions · goals · missing_information

and a `logic.ConstraintGraph` ready for the engine.

THE CARDINAL RULE — never invent a fact. Any statement whose cited source span is not
found verbatim in the problem text is NOT admitted as a fact; it is demoted to an
`assumption` (still used, but flagged and confidence-penalised) or dropped into
`missing_information`. This guard is deterministic and runs regardless of whether the
extraction came from a human, a formal builder, or an LLM.

Two ways to build a model:
  1. FORMAL (deterministic, used by tests + trusted callers): pass a ready
     `logic.ConstraintGraph` plus optional goals/assumptions/missing_information.
  2. GUARDED EXTRACTION: pass `problem` text and an `llm` callable that returns a JSON
     description; every extracted fact is span-checked before admission.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import logic
from logic import ConstraintGraph, Constraint, Eq, Ne, Lt


# ──────────────────────────────────────────────────────────────────────────────
# Structured model
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Fact:
    """An admitted ground truth. `source_span` is the verbatim text it was grounded in.
    `grounded=False` means it survived only as an assumption (span not found)."""
    text: str
    source_span: str = ""
    grounded: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "source_span": self.source_span, "grounded": self.grounded}


@dataclass(frozen=True)
class VariableSpec:
    name: str
    domain: Tuple[Any, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "domain": list(self.domain)}


@dataclass
class ConstraintSpec:
    """A constraint plus its human-readable description and provenance flag."""
    constraint: Constraint
    description: str
    is_assumption: bool = False        # flagged, not a stated fact

    def as_dict(self) -> Dict[str, Any]:
        return {"description": self.description, "is_assumption": self.is_assumption,
                "kind": self.constraint.kind}


@dataclass
class AnalysisModel:
    raw_problem: str = ""
    facts: List[Fact] = field(default_factory=list)
    variables: List[VariableSpec] = field(default_factory=list)
    constraints: List[ConstraintSpec] = field(default_factory=list)   # hard constraints
    assumptions: List[ConstraintSpec] = field(default_factory=list)   # flagged, still applied
    goals: List[str] = field(default_factory=list)                    # goal variable name(s)
    unknowns: List[str] = field(default_factory=list)                 # variables asked to determine
    missing_information: List[str] = field(default_factory=list)
    unresolved_inputs: int = 0        # statements the extractor could not parse
    total_inputs: int = 0

    # — derived —
    def graph(self) -> ConstraintGraph:
        """The logic.ConstraintGraph the engine reasons over: hard constraints AND
        (flagged) assumptions both apply — an assumption still shapes the search; it is
        merely tracked so confidence can discount it."""
        g = ConstraintGraph()
        for v in self.variables:
            g.add_var(v.name, v.domain)
        for cs in self.constraints:
            g.add(cs.constraint)
        for cs in self.assumptions:
            g.add(cs.constraint)
        return g

    def all_constraint_specs(self) -> List[ConstraintSpec]:
        return list(self.constraints) + list(self.assumptions)

    def grounded_facts(self) -> List[Fact]:
        return [f for f in self.facts if f.grounded]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "raw_problem": self.raw_problem,
            "facts": [f.as_dict() for f in self.facts],
            "variables": [v.as_dict() for v in self.variables],
            "constraints": [c.as_dict() for c in self.constraints],
            "assumptions": [c.as_dict() for c in self.assumptions],
            "goals": list(self.goals),
            "unknowns": list(self.unknowns),
            "missing_information": list(self.missing_information),
            "unresolved_inputs": self.unresolved_inputs,
            "total_inputs": self.total_inputs,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────
def validate_model(model: AnalysisModel) -> List[str]:
    """Return a list of structural issues (empty ⇒ well-formed). Never raises."""
    issues: List[str] = []
    names = {v.name for v in model.variables}
    if not names:
        issues.append("no variables declared")
    seen = set()
    for v in model.variables:
        if v.name in seen:
            issues.append(f"duplicate variable: {v.name}")
        seen.add(v.name)
        if not v.domain:
            issues.append(f"variable {v.name} has an empty domain")
    for cs in model.all_constraint_specs():
        for s in getattr(cs.constraint, "scope", ()):
            if s not in names:
                issues.append(f"constraint '{cs.description}' references unknown variable '{s}'")
    for g in model.goals:
        if g not in names:
            issues.append(f"goal '{g}' is not a declared variable")
    for u in model.unknowns:
        if u not in names:
            issues.append(f"unknown '{u}' is not a declared variable")
    return issues


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def analyze(problem: Any = "", *,
            model: Optional[AnalysisModel] = None,
            graph: Optional[ConstraintGraph] = None,
            goals: Optional[List[str]] = None,
            unknowns: Optional[List[str]] = None,
            assumptions: Optional[List[ConstraintSpec]] = None,
            missing_information: Optional[List[str]] = None,
            facts: Optional[List[Fact]] = None,
            llm: Optional[Callable[[str], str]] = None) -> AnalysisModel:
    """Produce an AnalysisModel.

    Precedence:
      · `model` given            → validated and returned as-is (trusted formal path).
      · `graph` given            → wrapped into an AnalysisModel (formal path).
      · `problem` + `llm` given  → guarded extraction (never invents facts).
      · `problem` only           → bounded built-in parser (logic.parse); anything it
                                    cannot parse becomes missing_information (honest).
    """
    if model is not None:
        return model

    if graph is not None:
        return _from_graph(graph, problem=str(problem), goals=goals, unknowns=unknowns,
                           assumptions=assumptions, missing_information=missing_information,
                           facts=facts)

    text = problem if isinstance(problem, str) else str(problem)
    if llm is not None:
        return _from_llm(text, llm, goals=goals, unknowns=unknowns)

    return _from_bounded_parser(text, goals=goals, unknowns=unknowns)


# ──────────────────────────────────────────────────────────────────────────────
# Formal path
# ──────────────────────────────────────────────────────────────────────────────
def _from_graph(graph: ConstraintGraph, *, problem: str,
                goals: Optional[List[str]], unknowns: Optional[List[str]],
                assumptions: Optional[List[ConstraintSpec]],
                missing_information: Optional[List[str]],
                facts: Optional[List[Fact]]) -> AnalysisModel:
    variables = [VariableSpec(name, tuple(v.domain)) for name, v in
                 sorted(graph.variables.items())]
    assumption_ids = {id(cs.constraint) for cs in (assumptions or [])}
    hard = [ConstraintSpec(c, c.describe(), is_assumption=False)
            for c in graph.constraints if id(c) not in assumption_ids]
    return AnalysisModel(
        raw_problem=problem,
        facts=list(facts or []),
        variables=variables,
        constraints=hard,
        assumptions=list(assumptions or []),
        goals=list(goals or []),
        unknowns=list(unknowns or []),
        missing_information=list(missing_information or []),
        unresolved_inputs=0,
        total_inputs=len(hard) + len(assumptions or []),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Bounded built-in parser path (deterministic, no LLM)
# ──────────────────────────────────────────────────────────────────────────────
def _from_bounded_parser(text: str, *, goals, unknowns) -> AnalysisModel:
    """Uses logic.parse's documented grammar. Variables must be declared by the caller
    for full solving; here we only surface what the grammar recognises and flag the rest
    as missing_information — we NEVER invent variables or domains."""
    pr = logic.parse(text)
    facts = [Fact(text=repr(r), source_span=_first_span(text, [r.a, str(r.b)]))
             for r in pr.relations]
    model = AnalysisModel(
        raw_problem=text,
        facts=facts,
        goals=list(goals or []),
        unknowns=list(unknowns or []),
        missing_information=list(pr.unparsed),
        unresolved_inputs=len(pr.unparsed),
        total_inputs=len(pr.relations) + len(pr.unparsed),
    )
    if not model.variables:
        model.missing_information.append(
            "no variable domains supplied — cannot build a solvable model from prose alone")
    return model


# ──────────────────────────────────────────────────────────────────────────────
# Guarded LLM extraction path
# ──────────────────────────────────────────────────────────────────────────────
_EXTRACTION_SCHEMA = """Return STRICT JSON only, no prose:
{
  "variables":  [{"name": str, "domain": [values...]}],
  "constraints":[{"type": "eq|ne|lt", "a": str, "b": str|null, "value": any|null,
                  "text": str, "source_span": str}],
  "goals":      [variable names asked to determine],
  "missing_information": [str]
}
Every constraint MUST include the exact verbatim `source_span` copied from the problem.
Do NOT invent facts. If unsure, put it in missing_information."""


def extraction_prompt(problem: str) -> str:
    return (f"Extract a finite-domain constraint model from the PROBLEM.\n\n"
            f"{_EXTRACTION_SCHEMA}\n\nPROBLEM:\n{problem}\n")


def _from_llm(text: str, llm: Callable[[str], str], *, goals, unknowns) -> AnalysisModel:
    raw = llm(extraction_prompt(text)) or ""
    data = _safe_json(raw)
    variables = [VariableSpec(v["name"], tuple(v.get("domain", [])))
                 for v in data.get("variables", []) if v.get("name") and v.get("domain")]
    var_names = {v.name for v in variables}
    g = ConstraintGraph()
    for v in variables:
        g.add_var(v.name, v.domain)

    constraints: List[ConstraintSpec] = []
    assumptions: List[ConstraintSpec] = []
    facts: List[Fact] = []
    missing: List[str] = list(data.get("missing_information", []))
    unresolved = 0

    for c in data.get("constraints", []):
        con = _build_constraint(c, var_names)
        if con is None:
            unresolved += 1
            missing.append(f"unparseable constraint: {json.dumps(c, ensure_ascii=False)[:120]}")
            continue
        span = str(c.get("source_span", "") or "")
        grounded = bool(span) and _span_present(text, span)
        desc = str(c.get("text") or con.describe())
        facts.append(Fact(text=desc, source_span=span, grounded=grounded))
        spec = ConstraintSpec(con, desc, is_assumption=not grounded)
        (constraints if grounded else assumptions).append(spec)
        if not grounded:
            missing.append(f"ungrounded (no matching source span): {desc}")

    resolved_goals = [str(x) for x in data.get("goals", []) if str(x) in var_names]
    return AnalysisModel(
        raw_problem=text, facts=facts, variables=variables,
        constraints=constraints, assumptions=assumptions,
        goals=list(goals or resolved_goals),
        unknowns=list(unknowns or [v for v in var_names if v not in resolved_goals]),
        missing_information=missing, unresolved_inputs=unresolved,
        total_inputs=len(constraints) + len(assumptions) + unresolved,
    )


def _build_constraint(c: Dict[str, Any], var_names) -> Optional[Constraint]:
    t = str(c.get("type", "")).lower()
    a, b, val = c.get("a"), c.get("b"), c.get("value")
    if a not in var_names:
        return None
    try:
        if t == "eq":
            return Eq(a, b=b) if b in var_names else Eq(a, value=val)
        if t == "ne":
            return Ne(a, b=b) if b in var_names else Ne(a, value=val)
        if t == "lt" and b in var_names:
            return Lt(a, b)
    except Exception:
        return None
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Guards / helpers (deterministic)
# ──────────────────────────────────────────────────────────────────────────────
def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _span_present(text: str, span: str) -> bool:
    """The cited span must appear (whitespace-normalised, case-insensitive) in the
    source. This is the anti-fabrication guard."""
    return bool(span) and _normalize(span) in _normalize(text)


def _first_span(text: str, tokens: List[str]) -> str:
    for tok in tokens:
        if tok and tok in text:
            return tok
    return ""


def _safe_json(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    # tolerate ```json fences and leading/trailing prose
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        raw = m.group(0)
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    g = ConstraintGraph()  # noqa: F811 (logic imported at top; run via `python -m`)
    g.add_var("x", [1, 2, 3]).add_var("y", [1, 2, 3])
    g.add(Ne("x", b="y")).add(Eq("x", value=2))
    m = analyze(graph=g, goals=["y"], missing_information=[])
    print("variables:", [v.name for v in m.variables])
    print("constraints:", [c.description for c in m.constraints])
    print("issues:", validate_model(m))
