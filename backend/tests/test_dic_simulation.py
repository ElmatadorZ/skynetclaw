"""
test_dic_simulation.py — DIC simulation properties (ADR-0012)
============================================================
Multi-horizon determinism, uncertainty monotonicity, and multi-simulator support.

    python backend/tests/test_dic_simulation.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

from capabilities.decision_intelligence.contracts import ActionCandidate, DEFAULT_HORIZONS
from capabilities.decision_intelligence.services.simulation_service import SimulationService

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)


def t_horizons_present():
    print("== all requested horizons predicted ==")
    s = SimulationService("trend")
    a = ActionCandidate("a","",effects=(("v",1.0),),estimated_confidence=0.6)
    oc = s.simulate({"v":0.0}, a, DEFAULT_HORIZONS)
    check("5/10/20/30 all present", [p.horizon for p in oc.predictions]==[5,10,20,30])


def t_uncertainty_monotonic():
    print("== uncertainty widens monotonically ==")
    s = SimulationService("trend")
    a = ActionCandidate("a","",effects=(("v",2.0),),estimated_confidence=0.5)
    oc = s.simulate({"v":0.0}, a, (5,10,20,30))
    spreads = [oc.at(h).high["v"]-oc.at(h).low["v"] for h in (5,10,20,30)]
    check("spreads non-decreasing", all(spreads[i] <= spreads[i+1] for i in range(len(spreads)-1)),
          str(spreads))
    check("bounds bracket expected at every horizon",
          all(oc.at(h).low["v"] <= oc.at(h).expected["v"] <= oc.at(h).high["v"] for h in (5,10,20,30)))


def t_determinism():
    print("== simulation deterministic ==")
    s = SimulationService("trend")
    a = ActionCandidate("a","",effects=(("v",1.5),),estimated_confidence=0.4)
    o1 = s.simulate({"v":3.0}, a, (5,10,20,30)).as_dict()
    o2 = s.simulate({"v":3.0}, a, (5,10,20,30)).as_dict()
    check("identical inputs → identical outcome", o1==o2)


def t_multiple_simulators():
    print("== multiple simulators via service ==")
    a = ActionCandidate("a","",effects=(("v",2.0),),estimated_confidence=0.7)
    trend = SimulationService("trend").simulate({"v":0.0}, a, (30,)).at(30).expected["v"]
    damped = SimulationService("damped").simulate({"v":0.0}, a, (30,)).at(30).expected["v"]
    check("trend vs damped diverge at long horizon", trend != damped and damped < trend,
          f"trend={trend} damped={damped}")


def t_confidence_shrinks_uncertainty():
    print("== higher confidence → tighter bounds ==")
    s = SimulationService("trend")
    lo = s.simulate({"v":0.0}, ActionCandidate("l","",effects=(("v",2.0),),estimated_confidence=0.2),(30,))
    hi = s.simulate({"v":0.0}, ActionCandidate("h","",effects=(("v",2.0),),estimated_confidence=0.9),(30,))
    slo = lo.at(30).high["v"]-lo.at(30).low["v"]; shi = hi.at(30).high["v"]-hi.at(30).low["v"]
    check("more confident action → narrower band", shi < slo, f"{shi} < {slo}")


def main():
    for fn in (t_horizons_present, t_uncertainty_monotonic, t_determinism,
               t_multiple_simulators, t_confidence_shrinks_uncertainty):
        try: fn()
        except Exception as ex:
            check(fn.__name__, False, f"harness error: {type(ex).__name__}: {ex}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1

def test_simulation():
    assert main()==0

if __name__ == "__main__":
    raise SystemExit(main())
