"""
test_discovery.py — OX-1 Discovery Layer validation (read-only, model-free)
==========================================================================
Proves the House investigates first, plans second, asks last.

    python backend/tests/test_discovery.py
"""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import institutional_db as idb
import house_state as hs
import discovery as D

DB = os.path.join(tempfile.gettempdir(), "discovery_test.db")


@pytest.fixture(autouse=True, scope="module")
def _isolated_house_state():
    # Isolate INSTITUTIONAL_DB to a fresh temp DB for THIS module, at RUN time only.
    # Setting it at IMPORT time mutates a PROCESS-GLOBAL env during pytest collection
    # and leaks into sibling modules (the seed and the query land in different DBs).
    # The certification council traced 4 full-suite failures to exactly this pattern.
    # Restored on teardown so nothing leaks out.
    prev = os.environ.get("INSTITUTIONAL_DB")
    if os.path.exists(DB):
        os.remove(DB)
    os.environ["INSTITUTIONAL_DB"] = DB
    idb._INITIALIZED.discard(DB)      # the fresh file must get its schema re-created
    idb.init_once(DB)
    # seed one real open mission + House Mind state
    sid = hs.open_state("build a stock dashboard")
    hs.update_from_verdict(sid, {
        "analyst": {"known": ["yahoo finance reachable"], "unknown": ["which symbols"]},
        "forecaster": {"scenario": "ship within a week", "confidence": 0.6},
        "skeptic": {"verdict": "FRAGILE", "rebuild_trigger": "if data source dies"},
        "aggregate_recommendation": "Build the dashboard on Yahoo data",
        "governance": {"governance_score": 0.7}})
    yield
    if prev is None:
        os.environ.pop("INSTITUTIONAL_DB", None)
    else:
        os.environ["INSTITUTIONAL_DB"] = prev


def _no_planning(r):
    # a lookup answer must NOT have triggered plan/council/comprehend/clarify
    assert r["category"] in (D.STATE_LOOKUP,), r["category"]
    assert not r.get("needs_clarification"), "lookup must not ask"
    assert r.get("answer"), "lookup must produce an answer from records"


def test1_status():
    D.clear_cache()
    r = D.route("งานค้างมีอะไร")
    print("T1 'งานค้างมีอะไร' →", r["category"], "| order:", r["discovery_order"])
    print("    answer:", r["answer"][:110])
    assert r["category"] == D.STATE_LOOKUP
    assert "mission" in r["discovery_order"]           # Mission Query ran
    assert "mission" in r["evidence"]
    _no_planning(r)
    print("    OK — Mission Query → answer, no plan/council/assumptions")


def test2_recent_thought():
    D.clear_cache()
    r = D.route("ล่าสุดเราคิดอะไรไว้")
    print("T2 'ล่าสุดเราคิดอะไรไว้' →", r["category"], "| order:", r["discovery_order"])
    assert r["category"] == D.STATE_LOOKUP
    assert "house_mind" in r["evidence"] and "timeline" in r["evidence"]   # Timeline + House Mind
    _no_planning(r)
    print("    OK — Timeline + House Mind → answer")


def test3_continue():
    D.clear_cache()
    r = D.route("ต่อ")
    print("T3 'ต่อ' →", r["category"], "(resolved_from", r.get("resolved_from"), ") | order:", r["discovery_order"])
    print("    answer:", r["answer"][:110])
    # Phase B: 'ต่อ' must inspect ACTIVE MISSION FIRST, never start with archive
    assert r["discovery_order"][0] == "mission", "ต่อ must inspect mission first"
    assert "archive" not in r["discovery_order"], "ต่อ must NOT start with archive recall"
    assert r["category"] == D.STATE_LOOKUP and r.get("resolved_from") == D.AMBIGUOUS
    assert "Resuming" in r["answer"]
    print("    OK — active mission first → reclassified → checkpoint answer")


def test4_mission():
    D.clear_cache()
    r = D.route("สร้าง dashboard การตลาดใหม่")
    print("T4 'สร้าง dashboard ใหม่' →", r["category"], "| order:", r["discovery_order"])
    assert r["category"] == D.MISSION
    # discovery STILL ran first to ground comprehension
    assert "mission" in r["evidence"] and "house_mind" in r["evidence"] and "archive" in r["evidence"]
    print("    OK — discovery first, then category=MISSION (caller → comprehend/plan/council)")


def test5_deictic():
    D.clear_cache()
    r = D.route("อันนี้")
    print("T5 'อันนี้' →", r["category"], "(resolved_from", r.get("resolved_from"), ")")
    # context recovery resolves against the active mission (there is one)
    assert r["discovery_order"][0] == "mission"
    assert r["category"] == D.STATE_LOOKUP, "should resolve from owned state, not ask"
    # and prove clarify is the LAST resort: with NO state, it asks
    D.clear_cache()
    _orig = D.query_missions
    D.query_missions = lambda: {"active": [], "paused": [], "completed": [], "failed": [], "counts": {}}
    _origm = D.read_house_mind
    D.read_house_mind = lambda: {"objective": "", "belief": "", "confidence": 0.0, "known": [],
                                 "unknown": [], "risks": [], "hypotheses": [], "next_action": {}, "state_id": ""}
    try:
        r2 = D.route("อันนี้")
        assert r2["category"] == D.AMBIGUOUS and r2["needs_clarification"], "must ask only when discovery fails"
        print("    OK — resolved from state when possible; clarify ONLY when discovery is empty")
    finally:
        D.query_missions = _orig; D.read_house_mind = _origm


def main():
    print("=" * 60 + "\nOX-1 DISCOVERY VALIDATION\n" + "=" * 60)
    test1_status(); test2_recent_thought(); test3_continue(); test4_mission(); test5_deictic()
    print("\n  ALL DISCOVERY TESTS PASS — investigate first, plan second, ask last")
    return 0


if __name__ == "__main__":
    sys.exit(main())
