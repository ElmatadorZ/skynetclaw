"""
decision_intelligence — the Decision Intelligence Framework (DIF)
================================================================
An auditable decision-making SERVICE layered over the Cognitive Logic Engine
(`backend/logic/`, ADR-0008). DIF does not re-implement solving; it composes the
engine into a single auditable act and adds what the engine does not:

    Phase 1  constraint_analyzer   NL/formal → structured AnalysisModel (no fabrication)
    Phase 2  decision_engine       classify (SAT/UNSAT/UNDER/MULTIPLE/UNKNOWN)
    Phase 3  counter_example       ACTIVE invalidation (prove the answer wrong)
    Phase 4  decision_verifier     PASS/FAIL for every constraint + assumption
    Phase 5  confidence_engine     confidence COMPUTED from five evidence components
    Phase 6  decision_score        deterministic /100 auditability rubric

See docs/adr/ADR-0011-decision-intelligence-framework.md.

Public API:
    from decision_intelligence import decide, render_report, AnalysisModel
    report = decide(model=<AnalysisModel or logic.ConstraintGraph>)   # deterministic
    report = decide(problem="...", llm=<callable>)                    # guarded extraction
    print(render_report(report))                                     # the audit report

License: Apache-2.0 — ElmatadorZ
"""
from .constraint_analyzer import (  # noqa: F401
    AnalysisModel, Fact, VariableSpec, ConstraintSpec, analyze, validate_model,
)
from .decision_verifier import verify_decision, DecisionVerification  # noqa: F401
from .counter_example import search_counter_example, CounterExample  # noqa: F401
from .confidence_engine import assess_confidence, ConfidenceReport  # noqa: F401
from .decision_score import score_decision, DecisionScore  # noqa: F401
from .decision_engine import (  # noqa: F401
    decide, render_report, DecisionReport, Classification,
)

__all__ = [
    "decide", "render_report", "DecisionReport", "Classification",
    "AnalysisModel", "Fact", "VariableSpec", "ConstraintSpec", "analyze",
    "validate_model", "verify_decision", "DecisionVerification",
    "search_counter_example", "CounterExample", "assess_confidence",
    "ConfidenceReport", "score_decision", "DecisionScore",
]
