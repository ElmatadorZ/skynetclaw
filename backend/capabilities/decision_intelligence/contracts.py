"""
contracts.py — shared data contracts for the Decision Intelligence Capability
=============================================================================
Single source of truth for the types that cross service/engine boundaries. Keeping them
here (not scattered across engines) is what lets engines stay decoupled and lets plugins
conform to one shape. Pure dataclasses; deterministic `as_dict()` for auditable replay.

No behaviour lives here beyond trivial derived helpers — engines compute, contracts carry.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# A world state is a flat mapping of variable → numeric/discrete value. Numeric variables
# are what the simulator projects over time; discrete variables are carried as-is.
WorldVars = Dict[str, Any]


# ──────────────────────────────────────────────────────────────────────────────
# Goals
# ──────────────────────────────────────────────────────────────────────────────
class GoalDirection(str, Enum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    TARGET = "target"          # reach `target_value` (within tolerance)


@dataclass(frozen=True)
class Goal:
    """A single objective over a world-state variable. `weight` feeds the utility engine;
    priorities are NEVER hardcoded — they live here as configurable weights."""
    id: str
    variable: str
    direction: GoalDirection = GoalDirection.MAXIMIZE
    weight: float = 1.0
    target_value: Optional[float] = None
    tolerance: float = 0.0
    deadline_horizon: Optional[int] = None    # days; None = no deadline

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "variable": self.variable, "direction": self.direction.value,
                "weight": self.weight, "target_value": self.target_value,
                "tolerance": self.tolerance, "deadline_horizon": self.deadline_horizon}


# ──────────────────────────────────────────────────────────────────────────────
# Resources
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ResourceVector:
    """Named resources → amounts (budget, time, compute, people, ...)."""
    amounts: Tuple[Tuple[str, float], ...] = ()

    @staticmethod
    def of(d: Dict[str, float]) -> "ResourceVector":
        return ResourceVector(tuple(sorted((k, float(v)) for k, v in d.items())))

    def get(self, name: str) -> float:
        for k, v in self.amounts:
            if k == name:
                return v
        return 0.0

    def covers(self, need: "ResourceVector") -> bool:
        return all(self.get(k) >= v for k, v in need.amounts)

    def minus(self, need: "ResourceVector") -> "ResourceVector":
        keys = {k for k, _ in self.amounts} | {k for k, _ in need.amounts}
        return ResourceVector.of({k: self.get(k) - need.get(k) for k in keys})

    def as_dict(self) -> Dict[str, float]:
        return {k: v for k, v in self.amounts}


# ──────────────────────────────────────────────────────────────────────────────
# Action candidates (the Planner's unit of output)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ActionCandidate:
    """A candidate action. The Planner emits SEVERAL of these — never one. Every field the
    mission requires is mandatory-by-shape (`effects` drives the deterministic simulator)."""
    id: str
    description: str
    effects: Tuple[Tuple[str, float], ...] = ()     # per-day delta applied to world vars
    expected_benefits: Tuple[str, ...] = ()
    expected_costs: Tuple[str, ...] = ()
    required_resources: ResourceVector = field(default_factory=ResourceVector)
    risks: Tuple[str, ...] = ()
    dependencies: Tuple[str, ...] = ()              # ids of prerequisite actions
    estimated_confidence: float = 0.5

    def effect_map(self) -> Dict[str, float]:
        return {k: v for k, v in self.effects}

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "description": self.description,
                "effects": self.effect_map(),
                "expected_benefits": list(self.expected_benefits),
                "expected_costs": list(self.expected_costs),
                "required_resources": self.required_resources.as_dict(),
                "risks": list(self.risks), "dependencies": list(self.dependencies),
                "estimated_confidence": self.estimated_confidence}


@dataclass(frozen=True)
class Plan:
    """An ordered sequence of action candidates (a strategy). A decision point may compare
    several Plans; the Adaptive engine patches a Plan in place."""
    id: str
    steps: Tuple[ActionCandidate, ...] = ()

    def action_ids(self) -> List[str]:
        return [a.id for a in self.steps]

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "steps": [a.as_dict() for a in self.steps]}


# ──────────────────────────────────────────────────────────────────────────────
# Simulation
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_HORIZONS: Tuple[int, ...] = (5, 10, 20, 30)


@dataclass(frozen=True)
class HorizonPrediction:
    horizon: int
    expected: WorldVars
    low: WorldVars                # lower uncertainty bound
    high: WorldVars               # upper uncertainty bound

    def as_dict(self) -> Dict[str, Any]:
        return {"horizon": self.horizon, "expected": self.expected,
                "low": self.low, "high": self.high}


@dataclass(frozen=True)
class SimOutcome:
    action_id: str
    predictions: Tuple[HorizonPrediction, ...] = ()

    def at(self, horizon: int) -> Optional[HorizonPrediction]:
        for p in self.predictions:
            if p.horizon == horizon:
                return p
        return None

    def as_dict(self) -> Dict[str, Any]:
        return {"action_id": self.action_id,
                "predictions": [p.as_dict() for p in self.predictions]}


# ──────────────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class UtilityScore:
    action_id: str
    scalar: float                                   # weighted scalarisation
    objective_scores: Tuple[Tuple[str, float], ...] = ()   # per-goal contribution
    constraint_penalty: float = 0.0
    feasible: bool = True

    def objective_map(self) -> Dict[str, float]:
        return {k: v for k, v in self.objective_scores}

    def as_dict(self) -> Dict[str, Any]:
        return {"action_id": self.action_id, "scalar": round(self.scalar, 6),
                "objective_scores": self.objective_map(),
                "constraint_penalty": self.constraint_penalty, "feasible": self.feasible}


# ──────────────────────────────────────────────────────────────────────────────
# Decision + review + learning
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Decision:
    chosen: Optional[ActionCandidate]
    ranked: List[Tuple[str, float]] = field(default_factory=list)   # (action_id, scalar) desc
    rejected: List[Tuple[str, str]] = field(default_factory=list)   # (action_id, reason)
    pareto_front: List[str] = field(default_factory=list)
    explanation: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"chosen": self.chosen.as_dict() if self.chosen else None,
                "ranked": self.ranked, "rejected": self.rejected,
                "pareto_front": self.pareto_front, "explanation": self.explanation}


@dataclass
class ReviewVerdict:
    accepted: bool
    challenges: List[str] = field(default_factory=list)
    counterexample: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"accepted": self.accepted, "challenges": self.challenges,
                "counterexample": self.counterexample, "confidence": round(self.confidence, 4),
                "reasons": self.reasons}


@dataclass
class PlanPatch:
    """Result of adaptive re-planning: what changed, not a whole new plan."""
    plan: Plan
    changed_steps: List[str] = field(default_factory=list)
    kept_steps: List[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"plan": self.plan.as_dict(), "changed_steps": self.changed_steps,
                "kept_steps": self.kept_steps, "reason": self.reason}


@dataclass
class Lesson:
    kind: str                       # "successful_pattern" | "failed_pattern" | "tradeoff" | "policy"
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "summary": self.summary, "evidence": self.evidence}


@dataclass
class LearningReport:
    lessons: List[Lesson] = field(default_factory=list)
    successful_patterns: List[str] = field(default_factory=list)
    failed_patterns: List[str] = field(default_factory=list)
    tradeoff_analysis: List[str] = field(default_factory=list)
    policy_improvements: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"lessons": [l.as_dict() for l in self.lessons],
                "successful_patterns": self.successful_patterns,
                "failed_patterns": self.failed_patterns,
                "tradeoff_analysis": self.tradeoff_analysis,
                "policy_improvements": self.policy_improvements}


# ──────────────────────────────────────────────────────────────────────────────
# Top-level request / result (deterministic replay unit)
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class DecisionRequest:
    world: WorldVars
    goals: List[Goal]
    available_resources: ResourceVector = field(default_factory=ResourceVector)
    horizons: Tuple[int, ...] = DEFAULT_HORIZONS
    weights: Dict[str, float] = field(default_factory=dict)     # goal_id → weight override
    planner: str = "default"
    utility: str = "weighted"
    simulator: str = "trend"
    policy: str = "max_utility"
    confidence_threshold: float = 0.35
    constraints_text: str = ""                                  # optional logic/DSL constraints
    seed_actions: List[ActionCandidate] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"world": self.world, "goals": [g.as_dict() for g in self.goals],
                "available_resources": self.available_resources.as_dict(),
                "horizons": list(self.horizons), "weights": self.weights,
                "planner": self.planner, "utility": self.utility,
                "simulator": self.simulator, "policy": self.policy,
                "confidence_threshold": self.confidence_threshold,
                "constraints_text": self.constraints_text,
                "seed_actions": [a.as_dict() for a in self.seed_actions]}
