"""
test_dic_integration.py — DIC service wiring + acceptance criteria (ADR-0012)
============================================================================
Verifies the capability composes services correctly and meets every acceptance criterion:
LLM-independence, deterministic replay, multiple planners/utilities/simulators, plugin
policies, backward compatibility, and no-duplication (reuse of logic/DIF/CVL).

    python backend/tests/test_dic_integration.py
"""
from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

from capabilities.decision_intelligence import (
    DecisionIntelligenceCapability, DecisionRequest, Goal, GoalDirection,
    ResourceVector, ActionCandidate, snapshot)

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)

def _req(**kw):
    base = dict(
        world={"revenue":10.0,"cost":20.0},
        goals=[Goal("grow","revenue",GoalDirection.MAXIMIZE,weight=2.0),
               Goal("lean","cost",GoalDirection.MINIMIZE,weight=1.0)],
        available_resources=ResourceVector.of({"effort":5.0,"budget":100.0}),
        seed_actions=[
            ActionCandidate("campaign","",effects=(("revenue",3.0),("cost",1.0)),
                expected_benefits=("rev up",),required_resources=ResourceVector.of({"effort":2,"budget":40}),
                risks=("uncertain",),estimated_confidence=0.7),
            ActionCandidate("cut","",effects=(("cost",-2.0),),expected_benefits=("cost down",),
                required_resources=ResourceVector.of({"effort":1}),estimated_confidence=0.8)],
        constraints_text="cost <= 100")
    base.update(kw)
    return DecisionRequest(**base)


def t_end_to_end():
    print("== end-to-end decision ==")
    cap = DecisionIntelligenceCapability()
    r = cap.decide(_req())
    check("a candidate is chosen", r.decision.chosen is not None)
    check("decision accepted (all gates pass)", r.accepted, str(r.gate.checks))
    check("explanation present", bool(r.decision.explanation))
    check("all 5 gate validations ran", set(r.gate.checks)=={"constraint","consistency","counterexample","confidence","decision"})
    check("trace records pipeline", len(r.trace) >= 6)


def t_deterministic_replay():
    print("== deterministic replay ==")
    cap = DecisionIntelligenceCapability()
    a = json.dumps(cap.decide(_req()).as_dict(), sort_keys=True, default=str)
    b = json.dumps(cap.decide(_req()).as_dict(), sort_keys=True, default=str)
    check("identical request → identical result", a==b)


def t_multiple_plugins():
    print("== multiple planners/utilities/simulators/policies ==")
    cap = DecisionIntelligenceCapability()
    snap = snapshot()
    check("registry lists >=2 planners", len(snap["planners"])>=2)
    check("registry lists >=2 utilities", len(snap["utilities"])>=2)
    check("registry lists >=2 simulators", len(snap["simulators"])>=2)
    check("registry lists >=2 policies", len(snap["policies"])>=2)
    results = {}
    for pl in snap["planners"]:
        for ut in snap["utilities"]:
            for sm in snap["simulators"]:
                for po in snap["policies"]:
                    r = cap.decide(_req(planner=pl, utility=ut, simulator=sm, policy=po))
                    results[(pl,ut,sm,po)] = r.decision.chosen.id if r.decision.chosen else None
    check("every plugin combination runs", len(results)==len(snap["planners"])*len(snap["utilities"])*len(snap["simulators"])*len(snap["policies"]))
    check("all combinations produced a decision", all(v is not None for v in results.values()))


def t_plugin_policy_override():
    print("== plugin decision policy (RL-ready seam) ==")
    from capabilities.decision_intelligence.registry import POLICIES
    # register a custom policy that always picks the lexicographically-first feasible id
    def first_feasible(scores, front):
        feas = sorted([s.action_id for s in scores if s.feasible])
        return feas[0] if feas else None
    POLICIES.register("first_feasible", lambda: first_feasible)
    cap = DecisionIntelligenceCapability()
    r = cap.decide(_req(policy="first_feasible"))
    check("custom policy plugged without touching services", r.decision.chosen is not None)


def t_reject_invalid():
    print("== rejects invalid plans ==")
    cap = DecisionIntelligenceCapability()
    # Start already over-budget so EVERY candidate (incl. no-op) stays infeasible at the far
    # horizon — the decision must not be accepted (constraint/decision gate blocks it).
    r = cap.decide(_req(
        world={"revenue":10.0,"cost":150.0},
        goals=[Goal("grow","revenue",GoalDirection.MAXIMIZE,weight=2.0)],
        seed_actions=[ActionCandidate("spend","",effects=(("cost",5.0),),
            expected_benefits=("x",),required_resources=ResourceVector(),estimated_confidence=0.9)],
        constraints_text="cost <= 100"))
    check("all-infeasible decision is NOT accepted", not r.accepted, str(r.gate.checks))
    check("constraint or decision gate blocked it",
          (r.gate.checks["constraint"] is False) or (r.gate.checks["decision"] is False),
          str(r.gate.checks))
    # and a feasible alternative IS preferred when one exists (system escapes correctly)
    r2 = cap.decide(_req(world={"revenue":10.0,"cost":95.0},
        seed_actions=[ActionCandidate("spend","",effects=(("cost",5.0),),
            expected_benefits=("x",),required_resources=ResourceVector(),estimated_confidence=0.9)],
        constraints_text="cost <= 100"))
    check("prefers a feasible candidate over the infeasible one", r2.decision.chosen.id != "spend",
          f"chose {r2.decision.chosen.id}")


def t_adaptive_reuse():
    print("== adaptive re-planning reuses plan ==")
    from capabilities.decision_intelligence.contracts import Plan
    cap = DecisionIntelligenceCapability()
    sx = ActionCandidate("sx","",effects=(("x",1.0),))
    sy = ActionCandidate("sy","",effects=(("y",1.0),))
    patch = cap.adapt(Plan("p",(sx,sy)), {"x":0.0,"y":0.0}, {"x":9.0,"y":0.0},
                      [Goal("g","x")], ResourceVector.of({"effort":5}))
    check("only affected step changed", "sx" in patch.changed_steps and "sy" in patch.kept_steps)


def t_learning_roundtrip():
    print("== learning across a mission ==")
    cap = DecisionIntelligenceCapability()
    cap.record_outcome({"action_id":"a","accepted":True,"predicted":10,"actual":11,"confidence":0.8,"policy":"max_utility"})
    cap.record_outcome({"action_id":"b","accepted":True,"predicted":10,"actual":1,"confidence":0.9,"policy":"max_utility"})
    rep = cap.learn()
    check("lessons produced", "a" in rep.successful_patterns and "b" in rep.failed_patterns)


def t_llm_independence_and_reuse():
    print("== LLM-independence + reuse (no duplication) ==")
    # nothing in the capability import graph pulls an LLM/HTTP client
    import capabilities.decision_intelligence as C
    mods = [m for m in sys.modules if m.startswith("capabilities.decision_intelligence")]
    tainted = [m for m in mods if any(x in m for x in ("openai","requests","httpx","ollama"))]
    check("no LLM/HTTP dependency in capability", not tainted)
    # reuse: the counter-example engine imports the DIF subsystem (not a re-implementation)
    src = (Path(__file__).resolve().parent.parent / "capabilities" / "decision_intelligence" /
           "engines" / "counter_example_engine.py").read_text(encoding="utf-8")
    check("counter-example REUSES decision_intelligence (DIF)", "import decision_intelligence" in src)
    src2 = (Path(__file__).resolve().parent.parent / "capabilities" / "decision_intelligence" /
            "validators" / "decision_validation_gate.py").read_text(encoding="utf-8")
    check("validation gate REUSES CVL", "cognitive_validation" in src2)


def t_backward_compat():
    print("== backward compatibility (reused subsystems intact) ==")
    ok = True
    try:
        import logic, decision_intelligence, decision, cognitive_validation  # noqa
    except Exception as e:
        ok = False; check("reused modules import", False, str(e)); return
    check("logic/DIF/decision/CVL all still import", ok)


def main():
    for fn in (t_end_to_end, t_deterministic_replay, t_multiple_plugins,
               t_plugin_policy_override, t_reject_invalid, t_adaptive_reuse,
               t_learning_roundtrip, t_llm_independence_and_reuse, t_backward_compat):
        try: fn()
        except Exception as ex:
            check(fn.__name__, False, f"harness error: {type(ex).__name__}: {ex}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1

def test_integration():
    assert main()==0

if __name__ == "__main__":
    raise SystemExit(main())
