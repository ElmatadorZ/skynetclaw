"""
test_dic_scenario.py — DIC end-to-end SCENARIO tests (ADR-0012)
==============================================================
Realistic decision scenarios exercising the whole capability: trade-offs, resource limits,
adaptive re-planning after a world change, and a full mission → learning loop.

    python backend/tests/test_dic_scenario.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

from capabilities.decision_intelligence import (
    DecisionIntelligenceCapability, DecisionRequest, Goal, GoalDirection,
    ResourceVector, ActionCandidate)
from capabilities.decision_intelligence.contracts import Plan

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)


def t_scenario_growth_vs_cost():
    print("== scenario: growth under a budget ==")
    cap = DecisionIntelligenceCapability()
    r = cap.decide(DecisionRequest(
        world={"revenue":100.0,"cost":50.0},
        goals=[Goal("grow","revenue",GoalDirection.MAXIMIZE,weight=3.0),
               Goal("lean","cost",GoalDirection.MINIMIZE,weight=1.0)],
        available_resources=ResourceVector.of({"budget":100.0,"effort":10.0}),
        seed_actions=[
            ActionCandidate("ads","Paid ads",effects=(("revenue",4.0),("cost",2.0)),
                expected_benefits=("fast growth",),required_resources=ResourceVector.of({"budget":60,"effort":3}),
                risks=("CAC may rise",),estimated_confidence=0.65),
            ActionCandidate("seo","Organic SEO",effects=(("revenue",1.5),),
                expected_benefits=("durable growth",),required_resources=ResourceVector.of({"effort":4}),
                estimated_confidence=0.8),
            ActionCandidate("layoff","Cut team",effects=(("cost",-3.0),("revenue",-1.0)),
                expected_benefits=("lower cost",),required_resources=ResourceVector.of({"effort":1}),
                risks=("morale, capacity",),estimated_confidence=0.7)],
        constraints_text="cost <= 200", horizons=(5,10,20,30)))
    check("a decision is made and accepted", r.decision.chosen is not None and r.accepted)
    check("explanation cites objective contributions", "objective" in r.decision.explanation.lower())
    check("pareto front computed", isinstance(r.decision.pareto_front, list) and r.decision.pareto_front)
    check("every candidate simulated over 4 horizons",
          all(len(oc.predictions)==4 for oc in r.outcomes.values()))


def t_scenario_all_paths_risky():
    print("== scenario: low-confidence options get challenged ==")
    cap = DecisionIntelligenceCapability()
    r = cap.decide(DecisionRequest(
        world={"metric":0.0},
        goals=[Goal("g","metric",GoalDirection.MAXIMIZE)],
        seed_actions=[ActionCandidate("gamble","",effects=(("metric",9.0),),
            expected_benefits=("big if it works",),estimated_confidence=0.15,risks=("very uncertain",))],
        confidence_threshold=0.5))
    check("weak-confidence decision is not accepted", not r.accepted)
    check("review raised challenges", len(r.verdict.challenges) >= 1)


def t_scenario_adapt_then_decide():
    print("== scenario: world changes → adapt plan minimally ==")
    cap = DecisionIntelligenceCapability()
    sA = ActionCandidate("A","",effects=(("supply",2.0),))
    sB = ActionCandidate("B","",effects=(("demand",1.0),))
    plan = Plan("launch",(sA,sB))
    patch = cap.adapt(plan, {"supply":10.0,"demand":5.0}, {"supply":3.0,"demand":5.0},
                      [Goal("g","supply")], ResourceVector.of({"effort":5}))
    check("supply-shock patches only the supply step", patch.changed_steps==["A"] and patch.kept_steps==["B"])
    check("patch explains the change", "supply" in patch.reason)


def t_scenario_mission_to_learning():
    print("== scenario: mission outcomes → learning ==")
    cap = DecisionIntelligenceCapability()
    # simulate three executed decisions with observed outcomes
    for item in [
        {"action_id":"ads","accepted":True,"predicted":20,"actual":22,"confidence":0.65,"policy":"max_utility"},
        {"action_id":"seo","accepted":True,"predicted":15,"actual":16,"confidence":0.8,"policy":"max_utility"},
        {"action_id":"promo","accepted":True,"predicted":30,"actual":5,"confidence":0.85,"policy":"max_utility"}]:
        cap.record_outcome(item)
    rep = cap.learn()
    check("successful patterns identified", set(["ads","seo"]).issubset(set(rep.successful_patterns)))
    check("failed pattern identified", "promo" in rep.failed_patterns)
    check("trade-off analysis surfaces the miscalibration", any("promo" in t for t in rep.tradeoff_analysis))
    check("policy improvement proposed", isinstance(rep.policy_improvements, list))


def main():
    for fn in (t_scenario_growth_vs_cost, t_scenario_all_paths_risky,
               t_scenario_adapt_then_decide, t_scenario_mission_to_learning):
        try: fn()
        except Exception as ex:
            check(fn.__name__, False, f"harness error: {type(ex).__name__}: {ex}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1

def test_scenario():
    assert main()==0

if __name__ == "__main__":
    raise SystemExit(main())
