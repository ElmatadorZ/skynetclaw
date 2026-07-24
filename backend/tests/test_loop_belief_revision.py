"""CLOSING THE LOOP — ผิด/ถูก → เรียนรู้ → เปลี่ยนความเชื่อ.
A graded prediction outcome must revise the House Mind's shared belief: reality
(not another verdict) changes the House's mind. Covers house_state.revise_from_outcome
and its wiring through outcome_tracker.evaluate."""
import time, pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import house_state as hs
import council_memory as cm
import outcome_tracker as ot


_DIRECTIVE = "Should the House go risk-on into Q3 markets?"


def _seed_state_with_belief(db, conf=0.8):
    sid = hs.open_state(_DIRECTIVE, bootstrap=False, path=db)
    hs.add_belief(sid, "Go risk-on into Q3", confidence=conf, agent="Council",
                  reason="council verdict", path=db)
    return sid


# ── revise_from_outcome directly ───────────────────────────────────────────────
def test_disproven_outcome_lowers_belief_and_logs_change(db):
    sid = _seed_state_with_belief(db, conf=0.8)
    ch = hs.revise_from_outcome(_DIRECTIVE, "incorrect", horizon="30", path=db)
    assert ch and ch["state_id"] == sid
    assert ch["new_confidence"] < 0.8                 # belief weakened
    assert ch["confidence_impact"] < 0               # "changed our mind", downward
    a = hs.answer(sid, db)
    assert a["what_we_believe"][0]["confidence"] < 0.8
    # reality is recorded as what changed the House's mind
    assert any(c["agent"] == "Reality (outcome)" for c in a["what_changed_our_mind"])
    assert a["contradictions"]                        # a contradiction was logged


def test_confirmed_outcome_reinforces_belief(db):
    sid = _seed_state_with_belief(db, conf=0.5)
    ch = hs.revise_from_outcome(_DIRECTIVE, "correct", horizon="90", path=db)
    assert ch and ch["new_confidence"] > 0.5          # belief strengthened
    assert ch["confidence_impact"] > 0
    assert "CONFIRMED" in ch["reason"]


def test_partial_outcome_small_downward_revision(db):
    sid = _seed_state_with_belief(db, conf=0.6)
    ch = hs.revise_from_outcome(_DIRECTIVE, "partial", horizon="30", path=db)
    assert ch and ch["new_confidence"] < 0.6
    assert "PARTIALLY" in ch["reason"]


def test_no_matching_state_returns_none(db):
    _seed_state_with_belief(db)
    assert hs.revise_from_outcome("totally unrelated quantum widget directive",
                                  "incorrect", path=db) is None


def test_outcome_without_standing_belief_records_fact(db):
    sid = hs.open_state(_DIRECTIVE, bootstrap=False, path=db)   # no belief set
    ch = hs.revise_from_outcome(_DIRECTIVE, "incorrect", horizon="30", path=db)
    assert ch is None                                  # nothing to revise
    a = hs.answer(sid, db)
    assert any("graded incorrect" in f for f in a["what_we_know"])


# ── the wiring: evaluate() drives the belief revision ──────────────────────────
def test_evaluate_revises_house_belief_end_to_end(db):
    # a real persisted deliberation + its House State + a prediction
    sid = cm.from_verdict(_DIRECTIVE, {
        "analyst": {"known": ["BTC 64000"], "data_gaps": ["Fed dot plot"]},
        "forecaster": {"scenario": "BTC will rally into Q3", "invalidation": "below 58k"},
        "aggregate_recommendation": "Go risk-on into Q3.",
    }, path=db)
    state_id = _seed_state_with_belief(db, conf=0.8)
    pid = ot.record_prediction("BTC will rally into Q3", agent="Forecaster",
                               session_id=sid, invalidation="below 58k",
                               confidence=0.8, path=db)
    res = ot.evaluate(pid, "30", "incorrect", path=db)

    # learning happened (reputation) AND the House changed its mind (belief)
    assert res["reputation"]                           # เรียนรู้
    assert res["belief_change"] is not None            # เปลี่ยนความเชื่อ
    assert res["belief_change"]["confidence_impact"] < 0
    a = hs.answer(state_id, db)
    assert a["what_we_believe"][0]["confidence"] < 0.8
    assert any(c["agent"] == "Reality (outcome)" for c in a["what_changed_our_mind"])
