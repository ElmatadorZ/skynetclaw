"""M3 — Governance Engine: the Constitution governs, it does not advise.
Tests the 5 required records, binding enforcement, waivers, minority tracking,
vindication, and the governance audit trail."""
import time, pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import governance_engine as ge
import council_memory as cm
import outcome_tracker as ot
import agent_reputation as rep

DAY = 86400.0

_CLEAN = {
    "analyst": {"known": ["BTC 64000 per source [1]"], "unknown": ["Fed path"]},
    "forecaster": {"scenario": "BTC rallies", "early_warning_1": "invalidation below 58k", "confidence": 0.6},
    "skeptic": {"verdict": "FRAGILE", "reason": "liquidity thin"},
    "aggregate_recommendation": "Phase in, hedge.",
}


# ── the five required records ───────────────────────────────────────────────
def test_extract_five_records():
    r = ge.extract_records(_CLEAN)
    assert set(r) == {"majority_position", "minority_positions", "evidence_record",
                      "confidence_record", "uncertainty_record"}
    assert r["majority_position"]
    assert r["minority_positions"] and r["minority_positions"][0]["agent"] == "Skeptic"
    assert r["evidence_record"] and r["uncertainty_record"]
    assert "Forecaster" in r["confidence_record"]


# ── binding enforcement ─────────────────────────────────────────────────────
def test_clean_passes():
    e = ge.enforce(_CLEAN)
    assert e["decision"] == ge.PASS and e["governance_score"] == 1.0

def test_forecast_without_invalidation_rejected():
    v = {"forecaster": {"scenario": "BTC will moon, unstoppable"},
         "analyst": {"known": ["data [1]"]}, "aggregate_recommendation": "buy"}
    e = ge.enforce(v)
    assert e["decision"] == ge.REJECTED and any(x["rule"] == "R4" for x in e["rejects"])

def test_claim_without_evidence_rejected():
    v = {"forecaster": {"scenario": "x", "early_warning_1": "invalidation below 1"},
         "aggregate_recommendation": "do the thing"}
    e = ge.enforce(v)
    assert e["decision"] == ge.REJECTED and any(x["rule"] == "R1" for x in e["rejects"])

def test_minority_omitted_rejected():
    # dissent language present, but a malformed verdict yields no extractable minority
    v = {"analyst": {"known": ["d [1]"], "unknown": ["x"]},
         "forecaster": {"scenario": "x", "early_warning_1": "invalidation below 1"},
         "executor": {"note": "the team disagree strongly but it's omitted"},
         "aggregate_recommendation": "go"}
    # force the omission: strip the extracted minority to simulate a record that dropped it
    recs = ge.extract_records(v)
    recs["minority_positions"] = []
    e = ge.enforce(v, records=recs)
    assert any(x["rule"] == "R5" for x in e["violations"])

def test_uncertainty_not_stated_flagged():
    v = {"analyst": {"known": ["d [1]"]},
         "aggregate_recommendation": "go"}   # no forecast, no uncertainty
    e = ge.enforce(v)
    assert e["decision"] == ge.FLAGGED and any(x["rule"] == "R3" and x["severity"] == ge.FLAG
                                               for x in e["flags"])

def test_waiver_lifts_rejection():
    v = {"forecaster": {"scenario": "BTC will moon"}, "analyst": {"known": ["d [1]"]},
         "aggregate_recommendation": "buy"}
    e = ge.enforce(v, waivers=["R4"])
    assert e["decision"] != ge.REJECTED
    assert any(w["rule"] == "R4" for w in e["waivers"])


# ── persistence: governance audit trail ─────────────────────────────────────
def test_govern_persists_record_and_minority(db):
    sid = cm.from_verdict("risk-on Q3?", _CLEAN, path=db)
    rec = ge.govern(sid, _CLEAN, path=db)
    assert rec["decision"] == ge.PASS
    g = ge.governance_record(sid, path=db)
    assert g["decision"] == ge.PASS and g["governance_score"] == 1.0
    assert len(g["minority_positions"]) == 1 and g["minority_positions"][0]["agent"] == "Skeptic"

def test_rejected_is_blocked_in_audit(db):
    v = {"forecaster": {"scenario": "BTC will moon"}, "aggregate_recommendation": "buy"}
    sid = cm.from_verdict("reckless", v, path=db)
    ge.govern(sid, v, path=db)
    g = ge.governance_record(sid, path=db)
    assert g["decision"] == ge.REJECTED and g["blocked"] == 1


# ── minority tracking + vindication (the House learns when dissent was right) ─
def test_vindication_rewards_right_dissent(db):
    sid = cm.from_verdict("go all-in?", _CLEAN, path=db)
    ge.govern(sid, _CLEAN, path=db)
    rep.ensure_agent("Skeptic", db)
    before = rep.get("Skeptic", db)["score"]
    p = ot.record_prediction("majority call", agent="Forecaster", session_id=sid,
                             made_at=time.time()-200*DAY, path=db)
    res = ot.evaluate(p, "180", "incorrect", path=db)   # majority WRONG
    assert res["minority"]["vindicated"] == ["Skeptic"]
    assert rep.get("Skeptic", db)["score"] > before     # rewarded

def test_wrong_dissent_not_punished(db):
    sid = cm.from_verdict("careful call", _CLEAN, path=db)
    ge.govern(sid, _CLEAN, path=db)
    rep.ensure_agent("Skeptic", db)
    before = rep.get("Skeptic", db)["score"]
    p = ot.record_prediction("majority call", agent="Forecaster", session_id=sid,
                             made_at=time.time()-200*DAY, path=db)
    ot.evaluate(p, "180", "correct", path=db)           # majority RIGHT → dissent was wrong
    m = ge.minorities(session_id=sid, path=db)[0]
    assert m["resolved"] == 1 and m["proven_correct"] == 0
    assert rep.get("Skeptic", db)["score"] == before    # NOT punished

def test_vindication_waits_for_full_grading(db):
    sid = cm.from_verdict("multi", _CLEAN, path=db)
    ge.govern(sid, _CLEAN, path=db)
    p1 = ot.record_prediction("a", agent="Forecaster", session_id=sid, made_at=time.time()-200*DAY, path=db)
    p2 = ot.record_prediction("b", agent="Forecaster", session_id=sid, made_at=time.time()-200*DAY, path=db)
    r1 = ot.evaluate(p1, "180", "incorrect", path=db)
    assert r1["minority"]["resolved"] == 0              # still pending p2
    r2 = ot.evaluate(p2, "180", "incorrect", path=db)
    assert r2["minority"]["vindicated"] == ["Skeptic"]

def test_minority_scoreboard(db):
    for i in range(2):
        sid = cm.from_verdict(f"call {i}", _CLEAN, path=db)
        ge.govern(sid, _CLEAN, path=db)
        p = ot.record_prediction("x", agent="Forecaster", session_id=sid, made_at=time.time()-200*DAY, path=db)
        ot.evaluate(p, "180", "incorrect", path=db)     # Skeptic vindicated both times
    sb = ge.minority_scoreboard(db)
    sk = [x for x in sb if x["agent"] == "Skeptic"][0]
    assert sk["n_vindicated"] == 2 and sk["vindication_rate"] == 1.0

def test_governance_stats(db):
    sid = cm.from_verdict("s", _CLEAN, path=db)
    ge.govern(sid, _CLEAN, path=db)
    st = ge.stats(db)
    assert "by_decision" in st and st["minorities"] >= 1
