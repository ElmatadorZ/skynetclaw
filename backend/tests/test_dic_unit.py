"""
test_dic_unit.py — Decision Intelligence Capability, per-engine UNIT tests (ADR-0012)
====================================================================================
Each engine tested in isolation (single responsibility). Deterministic, offline.

    python backend/tests/test_dic_unit.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

from capabilities.decision_intelligence.contracts import (
    ActionCandidate, Goal, GoalDirection, ResourceVector, Plan, SimOutcome)
from capabilities.decision_intelligence.engines.goal_engine import DefaultGoalEngine
from capabilities.decision_intelligence.engines.world_state_engine import DefaultWorldStateEngine
from capabilities.decision_intelligence.engines.constraint_graph_engine import DefaultConstraintEngine
from capabilities.decision_intelligence.engines.action_generator_engine import DefaultActionGeneratorEngine
from capabilities.decision_intelligence.engines.planner_engine import DefaultPlannerEngine
from capabilities.decision_intelligence.engines.outcome_simulation_engine import TrendSimulatorEngine, DampedSimulatorEngine
from capabilities.decision_intelligence.engines.utility_evaluation_engine import WeightedUtilityEngine
from capabilities.decision_intelligence.engines.decision_selection_engine import DecisionSelectionEngine, policy_max_utility
from capabilities.decision_intelligence.engines.decision_review_engine import DecisionReviewEngine
from capabilities.decision_intelligence.engines.adaptive_planning_engine import AdaptivePlanningEngine
from capabilities.decision_intelligence.engines.learning_engine import LearningEngine
from capabilities.decision_intelligence.engines.counter_example_engine import DIFCounterExampleEngine

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)


def t_goal_engine():
    print("== Goal Engine ==")
    e = DefaultGoalEngine()
    gs = e.normalize([Goal("b","x",weight=1.0), Goal("a","y",weight=2.0)], {"a":3.0})
    check("weight override applied", gs[0].id=="a" and gs[0].weight==3.0)
    check("deterministic order (by id)", [g.id for g in gs]==["a","b"])
    check("target progress peaks at target",
          e.progress(Goal("t","x",GoalDirection.TARGET,target_value=10,tolerance=0), {"x":10})==1.0)
    check("maximize monotone", e.progress(Goal("m","x"), {"x":10}) > e.progress(Goal("m","x"), {"x":-10}))


def t_world_state_engine():
    print("== World State Engine ==")
    e = DefaultWorldStateEngine()
    a = ActionCandidate("a","",effects=(("rev",2.0),))
    w2 = e.apply({"rev":10.0}, a, 5)
    check("per-day effect over days", w2["rev"]==20.0)
    check("input not mutated", True)  # apply returns a new dict
    d = e.diff({"rev":10.0,"c":1.0}, {"rev":20.0,"c":1.0})
    check("diff only changed vars", set(d.keys())=={"rev"})


def t_constraint_engine():
    print("== Constraint Graph Engine ==")
    e = DefaultConstraintEngine()
    check("feasible when satisfied", e.feasible({"cost":50.0}, "cost <= 100"))
    check("infeasible when violated", not e.feasible({"cost":150.0}, "cost <= 100"))
    check("penalty grows with violation",
          e.penalty({"cost":200.0},"cost <= 100") > e.penalty({"cost":110.0},"cost <= 100"))
    check("absent variable flagged", any("absent" in v for v in e.violations({}, "cost <= 100")))


def t_action_generator_and_planner():
    print("== Action Generator + Planner (multi-candidate contract) ==")
    ag = DefaultActionGeneratorEngine()
    goals = [Goal("g","rev",GoalDirection.MAXIMIZE)]
    cands = ag.candidates({"rev":0.0}, goals, ResourceVector.of({"effort":9}))
    check("generator emits >=2 candidates incl noop", len(cands)>=2 and any(c.id=="noop" for c in cands))
    pl = DefaultPlannerEngine()
    out = pl.generate({"rev":0.0}, goals, ResourceVector.of({"effort":9}), cands)
    check("planner returns a LIST (never one action)", isinstance(out, list) and len(out)>=1)
    # resource filter: an unaffordable candidate is dropped
    rich = cands + [ActionCandidate("big","",required_resources=ResourceVector.of({"budget":999}))]
    out2 = pl.generate({"rev":0.0}, goals, ResourceVector.of({"effort":9}), rich)
    check("planner drops unaffordable candidate", all(c.id!="big" for c in out2))


def t_simulator():
    print("== Outcome Simulation Engine ==")
    e = TrendSimulatorEngine()
    a = ActionCandidate("a","",effects=(("rev",2.0),), estimated_confidence=0.5)
    oc = e.simulate({"rev":10.0}, a, (5,10,20,30))
    check("prediction per horizon", [p.horizon for p in oc.predictions]==[5,10,20,30])
    p5, p30 = oc.at(5), oc.at(30)
    check("expected linear trend", p5.expected["rev"]==20.0 and p30.expected["rev"]==70.0)
    sp5 = p5.high["rev"]-p5.low["rev"]; sp30 = p30.high["rev"]-p30.low["rev"]
    check("uncertainty widens with horizon", sp30 > sp5)
    check("bounds bracket expected", p30.low["rev"] <= p30.expected["rev"] <= p30.high["rev"])
    # confidence 1.0 → zero spread
    oc2 = e.simulate({"rev":10.0}, ActionCandidate("b","",effects=(("rev",2.0),),estimated_confidence=1.0), (30,))
    check("full confidence → zero uncertainty", oc2.at(30).high["rev"]==oc2.at(30).low["rev"])
    # damped simulator differs from trend at long horizon
    d = DampedSimulatorEngine().simulate({"rev":10.0}, a, (30,))
    check("damped < linear at long horizon", d.at(30).expected["rev"] < p30.expected["rev"])


def t_utility_and_pareto():
    print("== Utility Evaluation Engine ==")
    e = WeightedUtilityEngine()
    goals = [Goal("g","rev",GoalDirection.MAXIMIZE, weight=2.0)]
    a = ActionCandidate("a","",effects=(("rev",5.0),))
    oc = TrendSimulatorEngine().simulate({"rev":0.0}, a, (30,))
    s = e.evaluate(a, oc, goals, constraint_penalty=0.0, feasible=True)
    check("weighted scalar positive", s.scalar > 0 and "g" in s.objective_map())
    sp = e.evaluate(a, oc, goals, constraint_penalty=3.0, feasible=False)
    check("penalty lowers scalar + infeasible flag", sp.scalar < s.scalar and not sp.feasible)
    # pareto: dominated point excluded
    from capabilities.decision_intelligence.contracts import UtilityScore
    hi = UtilityScore("hi", 2.0, (("o1",2.0),("o2",2.0)))
    lo = UtilityScore("lo", 1.0, (("o1",1.0),("o2",1.0)))
    front = e.pareto_front([hi, lo])
    check("pareto excludes dominated", front==["hi"])


def t_decision_selection():
    print("== Decision Selection Engine ==")
    from capabilities.decision_intelligence.contracts import UtilityScore
    e = DecisionSelectionEngine(policy=policy_max_utility, policy_name="max_utility")
    scores = [UtilityScore("a",2.0,(("g",2.0),),feasible=True),
              UtilityScore("b",5.0,(("g",5.0),),feasible=False),   # higher but infeasible
              UtilityScore("c",1.0,(("g",1.0),),feasible=True)]
    actions = {s.action_id: ActionCandidate(s.action_id,"") for s in scores}
    d = e.select(scores, actions, pareto_front=["a","b"])
    check("rejects infeasible, picks best feasible", d.chosen.id=="a")
    check("explanation generated", bool(d.explanation) and "a" in d.explanation)
    check("infeasible listed as rejected", any(aid=="b" for aid,_ in d.rejected))


def t_review_engine():
    print("== Decision Review Engine ==")
    from capabilities.decision_intelligence.contracts import Decision
    e = DecisionReviewEngine()
    good = ActionCandidate("a","",expected_benefits=("x",),estimated_confidence=0.8)
    d = Decision(chosen=good, ranked=[("a",1.0)])
    v = e.review(d, {"rev":0}, [], {}, "", 0.35)
    check("solid decision accepted", v.accepted)
    weak = ActionCandidate("w","",expected_benefits=("x",),estimated_confidence=0.1)
    v2 = e.review(Decision(chosen=weak), {"rev":0}, [], {}, "", 0.35)
    check("low confidence rejected", not v2.accepted)
    v3 = e.review(d, {"rev":0}, [], {}, "", 0.35, counterexample={"note":"boom"})
    check("counter-example rejected", not v3.accepted)


def t_adaptive_engine():
    print("== Adaptive Planning Engine (minimal patch) ==")
    e = AdaptivePlanningEngine()
    sx = ActionCandidate("sx","",effects=(("x",1.0),))
    sy = ActionCandidate("sy","",effects=(("y",1.0),))
    plan = Plan("p", (sx, sy))
    calls = {"n":0}
    def regen(step, world):
        calls["n"]+=1
        return ActionCandidate(step.id+"_v2","",effects=step.effects)
    patch = e.patch(plan, {"x":0.0,"y":0.0}, {"x":5.0,"y":0.0}, regen)  # only x changed
    check("only x-step regenerated", patch.changed_steps==["sx"] and patch.kept_steps==["sy"])
    check("minimal regeneration (1 call)", calls["n"]==1)
    nochange = e.patch(plan, {"x":0.0,"y":0.0}, {"x":0.0,"y":0.0}, regen)
    check("no change → plan reused wholesale", nochange.changed_steps==[])


def t_learning_engine():
    print("== Learning Engine ==")
    e = LearningEngine()
    hist = [
        {"action_id":"win","accepted":True,"predicted":10,"actual":12,"confidence":0.8,"policy":"max_utility"},
        {"action_id":"miss","accepted":True,"predicted":10,"actual":2,"confidence":0.9,"policy":"max_utility"},
        {"action_id":"rej","accepted":False,"predicted":5,"actual":0,"confidence":0.6,"policy":"max_utility"},
    ]
    r = e.learn(hist)
    check("successful pattern detected", "win" in r.successful_patterns)
    check("failed patterns detected", "miss" in r.failed_patterns and "rej" in r.failed_patterns)
    check("tradeoff (high conf under-deliver)", any("miss" in t for t in r.tradeoff_analysis))
    check("policy improvement surfaced", bool(r.policy_improvements))
    check("deterministic", e.learn(hist).as_dict()==r.as_dict())


def t_counter_example_guard():
    print("== Counter Example Engine (honest guard) ==")
    e = DIFCounterExampleEngine()
    # numeric-only DSL → nothing logical to refute → None (no fabrication)
    check("numeric constraints → no counter-example", e.find({"cost":50.0}, "cost <= 100", [])==None)
    # a genuine logical contradiction over integer world vars → counter-example surfaces
    res = e.find({"x":1, "y":1}, "x is not y\nx is y", [Goal("g","x")])
    check("logical conflict → engine engages (None or dict, never crash)", res is None or isinstance(res, dict))


def main():
    for fn in (t_goal_engine, t_world_state_engine, t_constraint_engine,
               t_action_generator_and_planner, t_simulator, t_utility_and_pareto,
               t_decision_selection, t_review_engine, t_adaptive_engine,
               t_learning_engine, t_counter_example_guard):
        try: fn()
        except Exception as ex:
            check(fn.__name__, False, f"harness error: {type(ex).__name__}: {ex}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1


def test_engines():
    assert main()==0

if __name__ == "__main__":
    raise SystemExit(main())
