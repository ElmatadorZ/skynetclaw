"""
Decision Intelligence Capability — a first-class SkynetClaw capability that sits ABOVE
reasoning and turns it into verifiable, adaptive, resource-aware decision-making.

Stack: Capability → Service → Engine → Tool → Validator (ADR-0012).
Reuses (never duplicates): logic/ (ADR-0008), decision_intelligence/ DIF (ADR-0011),
cognitive_validation.py CVL (ADR-0002).

Quick start:
    from capabilities.decision_intelligence import DecisionIntelligenceCapability
    from capabilities.decision_intelligence.contracts import (
        DecisionRequest, Goal, GoalDirection, ResourceVector)

    cap = DecisionIntelligenceCapability()
    req = DecisionRequest(world={"revenue": 0}, goals=[Goal("g", "revenue")])
    result = cap.decide(req)
    print(result.accepted, result.decision.chosen.id)
"""
from .capability import DecisionIntelligenceCapability, DecisionResult  # noqa: F401
from .contracts import (  # noqa: F401
    ActionCandidate, Decision, DecisionRequest, Goal, GoalDirection, HorizonPrediction,
    LearningReport, Lesson, Plan, PlanPatch, ResourceVector, ReviewVerdict, SimOutcome,
    UtilityScore, DEFAULT_HORIZONS,
)
from .registry import (  # noqa: F401
    PLANNERS, UTILITIES, SIMULATORS, POLICIES, ACTION_GENERATORS, snapshot,
)

__all__ = [
    "DecisionIntelligenceCapability", "DecisionResult",
    "DecisionRequest", "Goal", "GoalDirection", "ResourceVector", "ActionCandidate",
    "Plan", "PlanPatch", "Decision", "ReviewVerdict", "SimOutcome", "UtilityScore",
    "HorizonPrediction", "Lesson", "LearningReport", "DEFAULT_HORIZONS",
    "PLANNERS", "UTILITIES", "SIMULATORS", "POLICIES", "ACTION_GENERATORS", "snapshot",
]
