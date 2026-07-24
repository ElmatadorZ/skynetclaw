"""
test_house_frame.py — OX-1.7 Cognitive House Mind validation (model-free)
Runs against a temp house_state DB (no model, no network).
"""
from __future__ import annotations
import sys, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import house_state as HS
import house_cognition as HC


def _fresh_db():
    fd, p = tempfile.mkstemp(suffix=".db"); os.close(fd); os.unlink(p)
    return p


def test_empty_frame_is_blank_not_invented():
    p = _fresh_db()
    fr = HC.frame(path=p)
    assert fr["current_question"] == "" and fr["current_belief"] == {}
    assert fr["current_conflict"] == "" and fr["current_risk"] == ""
    assert fr["confidence"] == 0.0
    print("  OK  no state → every cognitive field blank (honest 'unknown', nothing invented)")


def test_frame_reprojects_real_state_verbatim():
    p = _fresh_db()
    sid = HS.open_state("Will gold rise next week?", bootstrap=False, path=p)
    HS.add_belief(sid, "Gold likely rises on rate-cut expectations", confidence=0.66, path=p)
    HS.add_contradiction(sid, "Skeptic: a strong dollar caps any rally", path=p)
    HS.add_blind_spot(sid, "No data on central-bank net purchases this month", path=p)
    HS.add_unknown_fact(sid, "Next CPI print is unknown", path=p)

    fr = HC.frame(path=p)
    assert fr["current_question"] == "Will gold rise next week?"
    assert fr["current_belief"]["belief"].startswith("Gold likely rises")
    assert abs(fr["current_belief"]["confidence"] - 0.66) < 1e-6
    # conflict comes from a REAL contradiction (verbatim)
    assert "strong dollar" in fr["current_conflict"]
    # risk prefers a REAL blind spot
    assert "central-bank net purchases" in fr["current_risk"]
    assert fr["confidence_level"] in ("high", "medium", "low", "critical")
    print("  OK  frame reprojects question/belief/conflict/risk verbatim from house_state")


def test_risk_falls_back_to_open_unknown():
    p = _fresh_db()
    sid = HS.open_state("What is the deploy status?", bootstrap=False, path=p)
    HS.add_unknown_fact(sid, "CI pipeline result not yet observed", path=p)
    fr = HC.frame(path=p)
    # no blind spot → risk falls back to the top open unknown (still REAL)
    assert "CI pipeline" in fr["current_risk"]
    assert fr["current_conflict"] == ""   # no contradiction → blank, not invented
    print("  OK  risk falls back to a real open unknown; no conflict invented")


def test_top_belief_is_highest_confidence():
    p = _fresh_db()
    sid = HS.open_state("Best model to use?", bootstrap=False, path=p)
    HS.add_belief(sid, "Use the small model", confidence=0.4, path=p)
    HS.add_belief(sid, "Use the large model", confidence=0.8, path=p)
    fr = HC.frame(path=p)
    assert fr["current_belief"]["belief"] == "Use the large model"
    print("  OK  current belief = the highest-confidence belief")


def test_render_block_and_empty():
    p = _fresh_db()
    assert HC.frame_render(path=p) == ""   # empty state → empty block
    sid = HS.open_state("Ship it?", bootstrap=False, path=p)
    HS.add_belief(sid, "Yes, tests pass", confidence=0.72, path=p)
    HS.add_contradiction(sid, "One flaky test remains", path=p)
    block = HC.frame_render(path=p)
    assert "CURRENT MIND" in block and "Question:" in block and "Belief:" in block and "Conflict:" in block
    print("  OK  CURRENT MIND block renders real fields; empty when nothing known")


def test_frame_diff_emits_only_on_change():
    p = _fresh_db()
    HC.reset()
    events = []
    pub = lambda t, payload, source="": events.append((t, payload))
    sid = HS.open_state("Decision pending?", bootstrap=False, path=p)
    HS.add_belief(sid, "Lean yes", confidence=0.55, path=p)
    n1 = HC.frame_diff_and_emit(pub, path=p)
    assert len(n1) == 1 and n1[0][0] == "house_frame"
    # no change → no event
    n2 = HC.frame_diff_and_emit(pub, path=p)
    assert n2 == []
    # a real change → one event
    HS.add_contradiction(sid, "But the budget is tight", path=p)
    n3 = HC.frame_diff_and_emit(pub, path=p)
    assert len(n3) == 1
    print("  OK  house_frame emits only on a genuine cognitive change (concurrent-safe)")


def test_owns_no_new_state():
    import house_cognition as mod, inspect
    src = inspect.getsource(mod)
    assert "CREATE TABLE" not in src and "INSERT INTO" not in src, "projection must own no state"
    print("  OK  cognitive frame is a pure projection — owns no new state")


def main():
    print("=" * 56 + "\nOX-1.7 COGNITIVE HOUSE MIND\n" + "=" * 56)
    test_empty_frame_is_blank_not_invented()
    test_frame_reprojects_real_state_verbatim()
    test_risk_falls_back_to_open_unknown()
    test_top_belief_is_highest_confidence()
    test_render_block_and_empty()
    test_frame_diff_emits_only_on_change()
    test_owns_no_new_state()
    print("\n  ALL COGNITIVE-HOUSE-MIND TESTS PASS — explain the reasoning state, don't dump it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
