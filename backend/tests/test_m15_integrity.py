"""M1.5 Loop Integrity — explicit regression tests for the four critical findings.
Each test asserts a success criterion the hostile audit demanded."""
import time, json, pathlib, sys, sqlite3, os
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import institutional_db as idb
import agent_reputation as rep
import outcome_tracker as out
import extractor as ex
import council_memory as mem


# ════════════ C1 — PREDICTION ATTRIBUTION INTEGRITY ════════════
def test_c1_attribution_not_hardcoded_forecaster():
    # a forecast from ATLAS must be attributed to Atlas, not Forecaster
    v = {"atlas": {"scenario": "liquidity tightening; DXY higher into year-end", "confidence": 0.6},
         "skeptic": {"reason": "invalidation if DXY falls below 100"},
         "aggregate_recommendation": "defensive"}
    ps = ex.extract_predictions(v)
    assert ps, "should extract a falsifiable claim"
    assert ps[0]["originating_agent"] == "Atlas"   # NOT hard-coded Forecaster

def test_c1_prediction_has_full_attribution():
    v = {"forecaster": {"scenario": "BTC rallies, source [1]", "confidence": 0.7},
         "skeptic": {"reason": "invalidation below 58k"},
         "analyst": {"known": ["per source [1] BTC 64000"]},
         "aggregate_recommendation": "phase in"}
    p = ex.extract_predictions(v)[0]
    assert p["originating_agent"]                      # originating agent
    assert isinstance(p["participants"], list) and p["participants"]   # participating agents
    assert "confidence" in p                           # confidence
    assert p["evidence_source"]                        # evidence source
    # skeptic supplied the invalidation → must be a participant
    assert "Skeptic" in p["participants"]

def test_c1_outcome_distributes_to_all_attributed_agents(db):
    v = {"forecaster": {"scenario": "gold breaks higher", "confidence": 0.6},
         "skeptic": {"reason": "wrong if below 2300"},
         "aggregate_recommendation": "accumulate"}
    sid = mem.from_verdict("Gold path?", v, path=db)
    pids = ex.record_from_verdict(v, session_id=sid, path=db)
    res = out.evaluate(pids[0], "180", "correct", path=db)
    assert set(res["attributed_to"]) >= {"Forecaster", "Skeptic"}
    assert rep.get("Forecaster", db)["wins"] == 1
    assert rep.get("Skeptic", db)["wins"] == 1          # co-signer also graded


# ════════════ C2 — HISTORICAL RECALL INTEGRITY ════════════
def _seed_validated_and_disproven(db):
    v = {"forecaster": {"scenario": "risk-on works", "confidence": 0.8},
         "skeptic": {"reason": "invalidation below 58k"}, "aggregate_recommendation": "go"}
    sg = mem.from_verdict("Should the House go risk-on into Q3 markets?", v, path=db)
    pg = out.record_prediction("up", agent="Forecaster", session_id=sg,
                               made_at=time.time()-200*out.DAY, path=db)
    out.evaluate(pg, "180", "correct", path=db)
    sb = mem.from_verdict("Should the House go risk-on into Q3 markets aggressively now?", v, path=db)
    pb = out.record_prediction("up big", agent="Forecaster", session_id=sb,
                               made_at=time.time()-200*out.DAY, path=db)
    out.evaluate(pb, "180", "incorrect", path=db)
    return sg, sb

def test_c2_disproven_never_ranks_top(db):
    sg, sb = _seed_validated_and_disproven(db)
    res = mem.recall("go risk-on into Q3 markets", path=db)
    assert res[0]["id"] == sg              # validated outranks
    assert res[0]["warning"] is False

def test_c2_disproven_carries_warning_label(db):
    sg, sb = _seed_validated_and_disproven(db)
    res = mem.recall("go risk-on into Q3 markets", path=db)
    disproven = [r for r in res if r["id"] == sb]
    assert disproven and disproven[0]["label"] == "DISPROVEN" and disproven[0]["warning"] is True

def test_c2_failed_predictions_reduce_rank(db):
    sg, sb = _seed_validated_and_disproven(db)
    res = {r["id"]: r for r in mem.recall("go risk-on into Q3 markets", path=db)}
    assert res[sb]["rank"] < res[sg]["rank"]   # failed history ranks lower despite similar text

def test_c2_unverified_is_neutral(db):
    v = {"forecaster": {"scenario": "x", "confidence": 0.5}, "skeptic": {"reason": "invalidation below 1"}}
    s = mem.from_verdict("totally novel topic about quantum widgets", v, path=db)
    res = mem.recall("quantum widgets novel", path=db)
    assert res and res[0]["label"] == "unverified" and res[0]["warning"] is False


# ════════════ C3 — REPUTATION INTEGRITY ════════════
def test_c3_score_is_bounded(db):
    rep.ensure_agent("Atlas", db)
    for _ in range(200): rep.apply_outcome("Atlas", "correct", confidence=0.9, path=db)
    assert rep.get("Atlas", db)["score"] <= 1000.0   # no unbounded inflation

def test_c3_one_bad_forecast_not_permanent(db):
    rep.ensure_agent("Scout", db)
    rep.apply_outcome("Scout", "incorrect", confidence=0.9, path=db)
    low = rep.get("Scout", db)["score"]
    for _ in range(12): rep.apply_outcome("Scout", "correct", confidence=0.7, path=db)
    assert rep.get("Scout", db)["score"] > low + 100   # recovers

def test_c3_overconfidence_penalized(db):
    rep.ensure_agent("Loud", db); rep.ensure_agent("Humble", db)
    for _ in range(8):
        rep.apply_outcome("Loud", "incorrect", confidence=0.95, path=db)
        rep.apply_outcome("Humble", "incorrect", confidence=0.3, path=db)
    assert rep.get("Loud", db)["calibration"] < rep.get("Humble", db)["calibration"]

def test_c3_recent_matters_old_fades(db):
    rep.ensure_agent("Idle", db)
    for _ in range(10): rep.apply_outcome("Idle", "correct", confidence=0.6, path=db)
    hi = rep.get("Idle", db)["score"]
    rep.apply_decay("Idle", now=time.time()+365*86400, path=db)
    lo = rep.get("Idle", db)["score"]
    assert 500.0 <= lo < hi   # old proof fades toward neutral

def test_c3_apply_outcome_is_atomic(db):
    # one transaction → reputation + history land together
    rep.ensure_agent("Atlas", db)
    rep.apply_outcome("Atlas", "correct", confidence=0.7, path=db)
    assert rep.get("Atlas", db)["n_predictions"] == 1
    assert len(rep.history("Atlas", path=db)) >= 1

def test_c3_calibration_tracked(db):
    rep.ensure_agent("Cal", db)
    rep.apply_outcome("Cal", "correct", confidence=0.9, path=db)
    assert "calibration" in rep.get("Cal", db)


# ════════════ C4 — PERSISTENCE INTEGRITY ════════════
def test_c4_read_does_not_acquire_write_lock(db):
    pid = out.record_prediction("x", agent="Atlas", path=db)
    w = sqlite3.connect(db, timeout=0.5)
    w.execute("PRAGMA journal_mode=WAL"); w.execute("BEGIN IMMEDIATE")
    w.execute("UPDATE predictions SET status='pending' WHERE id=?", (pid,))
    try:
        assert out.get_prediction(pid, db) is not None   # read succeeds under held write lock
    finally:
        w.rollback(); w.close()

def test_c4_init_once_is_cached(db, monkeypatch):
    idb.init_once(db)
    calls = {"n": 0}
    real = idb.ensure_schema
    monkeypatch.setattr(idb, "ensure_schema", lambda p=None: calls.__setitem__("n", calls["n"]+1))
    for _ in range(10):
        idb.init_once(db)         # already initialised → must NOT call ensure_schema
    assert calls["n"] == 0

def test_c4_schema_v3(db):
    assert idb.current_version(db) == 5
