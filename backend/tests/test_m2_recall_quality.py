"""M2 Foundation — Recall Quality Layer: every recalled memory must be justified.
Tests all five validity states, the five required scores, and the ranking law."""
import time, pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import recall_quality as rq
import council_memory as cm
import outcome_tracker as ot
from council_memory import CouncilSession, save_session

DAY = 86400.0


def _sess(directive, ts, conf=0.7, path=None):
    s = CouncilSession(directive=directive, confidence=conf, ts=ts)
    save_session(s, path=path)
    return s.id

def _grade(sid, results, made, path=None):
    for i, r in enumerate(results):
        p = ot.record_prediction(f"{sid}-{i}", agent="Forecaster", session_id=sid, made_at=made, path=path)
        ot.evaluate(p, "180", r, path=path)


# ── the five required scores ───────────────────────────────────────────────
def test_every_recalled_memory_has_five_scores(db):
    s = _sess("risk-on Q3 markets liquidity", time.time()-10*DAY, path=db)
    _grade(s, ["correct"], time.time()-200*DAY, path=db)
    r = cm.recall("risk-on Q3 markets", path=db)[0]
    for field in ("similarity", "accuracy_score", "calibration_score", "outcome_status", "validity"):
        assert field in r, f"missing {field}"
    assert isinstance(r["outcome_status"], dict)

def test_justification_explains_recall(db):
    s = _sess("gold hedge inflation", time.time()-10*DAY, path=db)
    _grade(s, ["correct"], time.time()-200*DAY, path=db)
    j = cm.recall("gold hedge inflation", path=db)[0]["justification"]
    for k in ("why_recalled", "why_relevant", "whether_correct", "whether_valid"):
        assert k in j and j[k]


# ── the five validity states ────────────────────────────────────────────────
def test_state_validated(db):
    s = _sess("validated topic alpha bravo", time.time()-10*DAY, path=db)
    _grade(s, ["correct", "correct"], time.time()-200*DAY, path=db)
    assert cm.recall("validated topic alpha bravo", path=db)[0]["validity"] == rq.VALIDATED

def test_state_disproven(db):
    s = _sess("disproven topic charlie delta", time.time()-10*DAY, path=db)
    _grade(s, ["incorrect", "incorrect"], time.time()-200*DAY, path=db)
    r = cm.recall("disproven topic charlie delta", path=db)[0]
    assert r["validity"] == rq.DISPROVEN and r["warning"] is True

def test_state_partially_valid(db):
    s = _sess("mixed topic echo foxtrot", time.time()-10*DAY, path=db)
    _grade(s, ["correct", "incorrect"], time.time()-200*DAY, path=db)
    r = cm.recall("mixed topic echo foxtrot", path=db)[0]
    assert r["validity"] == rq.PARTIALLY_VALID and r["warning"] is True

def test_state_unknown(db):
    _sess("untested topic golf hotel", time.time()-10*DAY, path=db)
    r = cm.recall("untested topic golf hotel", path=db)[0]
    assert r["validity"] == rq.UNKNOWN and r["warning"] is False

def test_state_outdated_by_staleness(db):
    s = _sess("stale topic india juliet", time.time()-700*DAY, path=db)
    _grade(s, ["correct", "correct"], time.time()-900*DAY, path=db)
    r = cm.recall("stale topic india juliet", path=db)[0]
    assert r["validity"] == rq.OUTDATED and "horizon" in r["justification"]["whether_valid"]

def test_state_outdated_by_supersession(db):
    old = _sess("regime shift hedge plan kilo lima", time.time()-300*DAY, path=db)
    _grade(old, ["correct"], time.time()-400*DAY, path=db)
    new = _sess("regime shift hedge plan kilo lima updated", time.time()-5*DAY, path=db)
    _grade(new, ["correct"], time.time()-100*DAY, path=db)
    res = {r["id"]: r for r in cm.recall("regime shift hedge plan kilo lima", path=db)}
    assert res[old]["validity"] == rq.OUTDATED
    assert res[old]["superseded_by"] == new
    assert res[new]["validity"] == rq.VALIDATED


# ── ranking law: correctness beats similarity ───────────────────────────────
def test_disproven_outranked_by_validated_despite_similarity(db):
    # disproven has identical-ish text (higher raw similarity) but must rank below validated
    v = _sess("alpha beta gamma delta epsilon", time.time()-10*DAY, path=db)
    _grade(v, ["correct", "correct"], time.time()-200*DAY, path=db)
    d = _sess("alpha beta gamma delta epsilon zeta", time.time()-9*DAY, path=db)
    _grade(d, ["incorrect", "incorrect"], time.time()-200*DAY, path=db)
    res = cm.recall("alpha beta gamma delta epsilon", path=db)
    assert res[0]["id"] == v and res[0]["warning"] is False
    assert res[0]["rank"] > [x for x in res if x["id"] == d][0]["rank"]

def test_trusted_states_never_below_warned(db):
    val = _sess("mike november oscar", time.time()-10*DAY, path=db)
    _grade(val, ["correct"], time.time()-200*DAY, path=db)
    bad = _sess("mike november oscar papa", time.time()-10*DAY, path=db)
    _grade(bad, ["incorrect"], time.time()-200*DAY, path=db)
    res = cm.recall("mike november oscar", path=db)
    # first warned item index must be after all non-warned
    warned_idx = [i for i, r in enumerate(res) if r["warning"]]
    trusted_idx = [i for i, r in enumerate(res) if not r["warning"]]
    assert not trusted_idx or not warned_idx or max(trusted_idx) < min(warned_idx)


# ── pure-layer unit tests ───────────────────────────────────────────────────
def test_validity_states_enumerated():
    assert set(rq.STATES) == {"VALIDATED", "PARTIALLY_VALID", "OUTDATED", "DISPROVEN", "UNKNOWN"}

def test_assess_validity_pure():
    assert rq.assess_validity(1.0, 3, 10, None)[0] == rq.VALIDATED
    assert rq.assess_validity(0.0, 3, 10, None)[0] == rq.DISPROVEN
    assert rq.assess_validity(0.5, 3, 10, None)[0] == rq.PARTIALLY_VALID
    assert rq.assess_validity(None, 0, 10, None)[0] == rq.UNKNOWN
    assert rq.assess_validity(1.0, 3, 10, "cs_newer")[0] == rq.OUTDATED
    assert rq.assess_validity(1.0, 3, 9999, None)[0] == rq.OUTDATED

def test_disproven_cannot_supersede():
    cands = [{"id": "old", "directive": "x y z topic", "ts": 1},
             {"id": "new", "directive": "x y z topic", "ts": 2}]
    outcomes = {"new": {"n_evaluated": 2, "accuracy": 0.0}}  # newer is disproven
    assert rq.detect_supersession(cands, outcomes) == {}
