"""
test_dic_stress.py — DIC stress + benchmark (ADR-0012)
======================================================
Scale: many candidates, many goals, large world state — still deterministic and bounded in
time. Doubles as a lightweight benchmark (records wall time; asserts a generous ceiling so
it is stable on the House's CPU-only runtime).

    python backend/tests/test_dic_stress.py
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

from capabilities.decision_intelligence import (
    DecisionIntelligenceCapability, DecisionRequest, Goal, GoalDirection,
    ResourceVector, ActionCandidate)

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)


def _big_request(n_actions=200, n_goals=20):
    world = {f"v{i}": float(i) for i in range(n_goals)}
    goals = [Goal(f"g{i}", f"v{i}", GoalDirection.MAXIMIZE, weight=1.0 + (i % 3))
             for i in range(n_goals)]
    seed = []
    for k in range(n_actions):
        i = k % n_goals
        seed.append(ActionCandidate(
            f"a{k}", f"action {k}", effects=((f"v{i}", 1.0 + (k % 5) * 0.1),),
            expected_benefits=(f"advance v{i}",),
            required_resources=ResourceVector.of({"effort": 1.0}),
            estimated_confidence=0.3 + (k % 7) * 0.1))
    return DecisionRequest(world=world, goals=goals,
                           available_resources=ResourceVector.of({"effort": 10_000.0}),
                           seed_actions=seed, horizons=(5, 10, 20, 30))


def t_scale():
    print("== stress: 200 candidates × 20 goals × 4 horizons ==")
    cap = DecisionIntelligenceCapability()
    req = _big_request()
    t0 = time.perf_counter()
    r = cap.decide(req)
    dt = time.perf_counter() - t0
    check("produces a decision at scale", r.decision.chosen is not None)
    check("all candidates scored", len(r.decision.ranked) >= 200)
    check("pareto front computed at scale", isinstance(r.decision.pareto_front, list))
    check(f"completes under 5s (took {dt:.2f}s)", dt < 5.0)


def t_scale_deterministic():
    print("== stress: deterministic at scale ==")
    cap = DecisionIntelligenceCapability()
    req = _big_request(120, 12)
    a = json.dumps(cap.decide(req).as_dict(), sort_keys=True, default=str)
    b = json.dumps(cap.decide(req).as_dict(), sort_keys=True, default=str)
    check("identical large request → identical result", a == b)


def t_learning_scale():
    print("== stress: learning over a long history ==")
    cap = DecisionIntelligenceCapability()
    for k in range(500):
        cap.record_outcome({"action_id": f"a{k%25}", "accepted": (k % 4 != 0),
                            "predicted": 10.0, "actual": 10.0 if k % 3 else 1.0,
                            "confidence": 0.5 + (k % 5) * 0.1, "policy": "max_utility"})
    t0 = time.perf_counter()
    rep = cap.learn()
    dt = time.perf_counter() - t0
    check("learning returns a report over 500 records", rep is not None)
    check(f"learning under 2s (took {dt:.2f}s)", dt < 2.0)
    check("deterministic learning at scale", cap.learn().as_dict() == rep.as_dict())


def main():
    for fn in (t_scale, t_scale_deterministic, t_learning_scale):
        try: fn()
        except Exception as ex:
            check(fn.__name__, False, f"harness error: {type(ex).__name__}: {ex}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1

def test_stress():
    assert main()==0

if __name__ == "__main__":
    raise SystemExit(main())
