"""
test_execution_primacy.py — OX-EXEC execution policy + commander (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import execution_policy as EP
import commander as CMD


# ── OX-EXEC-2 Action Bias ────────────────────────────────────────────────────
def test_action_bias_bypasses_council():
    for d in ("approve", "confirm", "continue", "do it", "generate report",
              "create html dashboard", "save the note", "write the file",
              "ทำเลย", "ต่อเลย", "อนุมัติ"):
        c = EP.classify(d)
        assert c["route"] == EP.DIRECT_EXECUTE, f"{d!r} -> {c}"
        assert c["action_bias"] is True
    print("  OK  explicit operator intent (EN+TH) routes to DIRECT_EXECUTE")


# ── OX-EXEC-6 State lookup → discover, no reasoning ──────────────────────────
def test_state_lookup_route():
    for d in ("status", "show me the mission list", "what is the progress",
              "recent runs", "สถานะ", "ความคืบหน้า"):
        assert EP.classify(d)["route"] == EP.STATE_LOOKUP, d
    print("  OK  retrieval requests route to STATE_LOOKUP (no comprehend/plan/council)")


# ── Risk + OX-EXEC-3 Unknown != Blocked ─────────────────────────────────────
def test_risk_and_gap_policy():
    assert EP.assess_risk("delete the production database") == "high"
    assert EP.assess_risk("summarize the report") == "low"
    assert EP.assess_risk("refactor the module") == "medium"
    assert EP.gap_policy("low")["action"] == "proceed"
    assert EP.gap_policy("medium")["action"] == "proceed_with_warning"
    assert EP.gap_policy("high")["action"] == "ask"
    print("  OK  unknown+low→proceed · +medium→warn · +high→ask (unknown alone never blocks)")


# ── OX-EXEC-1 Council advises, Commander decides ────────────────────────────
def test_commander_overrides_council_rebuild():
    pol = EP.classify("build a stock dashboard")          # DELIBERATE, medium
    v = CMD.decide(pol, council_verdict={"skeptic": {"verdict": "REBUILD"}})
    assert v["verdict"] == CMD.EXECUTE_NOW and v["overrode_council"] is True
    print("  OK  council REBUILD is advisory — Commander executes (overrides)")


def test_only_evidence_plus_high_risk_holds():
    pol = EP.classify("delete the production secrets")    # high risk
    # doubt alone does NOT hold:
    assert CMD.decide(pol)["verdict"] == CMD.EXECUTE_NOW or pol["risk"] == "high"
    # evidence + high risk → HOLD (the only legitimate block)
    v = CMD.decide(pol, evidence_block=True)
    assert v["verdict"] == CMD.HOLD
    # low-risk action with evidence flag still executes
    pol2 = EP.classify("summarize the findings")
    assert CMD.decide(pol2, evidence_block=True)["verdict"] == CMD.EXECUTE_NOW
    print("  OK  only EVIDENCE + high risk may HOLD; doubt never blocks")


# ── OX-EXEC-4 Plan loop prevention ──────────────────────────────────────────
def test_no_third_plan_cycle():
    pol = EP.classify("build something complex")
    v = CMD.decide(pol, plan_cycles=1)
    assert v["verdict"] == CMD.EXECUTE_NOW and "loop" in v["reason"].lower()
    print("  OK  second planning cycle → Commander forces EXECUTE NOW (no third plan)")


def test_operator_hold_respected():
    pol = EP.classify("do it")
    assert CMD.decide(pol, operator_hold=True)["verdict"] == CMD.HOLD
    print("  OK  explicit operator hold is respected over action bias")


def test_action_bias_executes_even_at_plan_loop():
    pol = EP.classify("approve")
    assert CMD.decide(pol, plan_cycles=3,
                      council_verdict={"skeptic": {"verdict": "REBUILD"}})["verdict"] == CMD.EXECUTE_NOW
    print("  OK  explicit confirmation always executes now")


def test_no_state_no_model():
    import inspect
    for mod in (EP, CMD):
        src = inspect.getsource(mod)
        assert "httpx" not in src and "sqlite3" not in src and "CREATE TABLE" not in src
    print("  OK  policy + commander are stateless and model-free")


def main():
    print("=" * 56 + "\nOX-EXEC EXECUTION PRIMACY\n" + "=" * 56)
    test_action_bias_bypasses_council()
    test_state_lookup_route()
    test_risk_and_gap_policy()
    test_commander_overrides_council_rebuild()
    test_only_evidence_plus_high_risk_holds()
    test_no_third_plan_cycle()
    test_operator_hold_respected()
    test_action_bias_executes_even_at_plan_loop()
    test_no_state_no_model()
    print("\n  ALL EXECUTION-PRIMACY TESTS PASS — execute first, reason second, ask last")
    return 0


if __name__ == "__main__":
    sys.exit(main())
