"""
engines — the 12 single-responsibility engines of the Decision Intelligence Capability.
Each engine imports only `contracts`, `interfaces`, and reused substrate (logic/DIF) —
never another engine. Importing this package registers the built-in pluggable engines
(planners, utilities, simulators, decision policies) into `registry`.
"""
from ..registry import PLANNERS, UTILITIES, SIMULATORS, POLICIES, ACTION_GENERATORS

from .goal_engine import DefaultGoalEngine  # noqa: F401
from .world_state_engine import DefaultWorldStateEngine  # noqa: F401
from .constraint_graph_engine import DefaultConstraintEngine  # noqa: F401
from .action_generator_engine import DefaultActionGeneratorEngine
from .planner_engine import DefaultPlannerEngine, ConservativePlannerEngine
from .outcome_simulation_engine import TrendSimulatorEngine, DampedSimulatorEngine
from .utility_evaluation_engine import WeightedUtilityEngine, RiskAverseUtilityEngine
from .decision_selection_engine import (
    DecisionSelectionEngine, policy_max_utility, policy_pareto_then_utility)
from .decision_review_engine import DecisionReviewEngine  # noqa: F401
from .counter_example_engine import DIFCounterExampleEngine  # noqa: F401
from .adaptive_planning_engine import AdaptivePlanningEngine  # noqa: F401
from .learning_engine import LearningEngine  # noqa: F401

# ── Register built-in pluggable engines (idempotent) ──
PLANNERS.register("default", DefaultPlannerEngine)
PLANNERS.register("conservative", ConservativePlannerEngine)
UTILITIES.register("weighted", WeightedUtilityEngine)
UTILITIES.register("risk_averse", RiskAverseUtilityEngine)
SIMULATORS.register("trend", TrendSimulatorEngine)
SIMULATORS.register("damped", DampedSimulatorEngine)
ACTION_GENERATORS.register("default", DefaultActionGeneratorEngine)
# decision-selection policies are pure functions → factory returns the callable
POLICIES.register("max_utility", lambda: policy_max_utility)
POLICIES.register("pareto_then_utility", lambda: policy_pareto_then_utility)
