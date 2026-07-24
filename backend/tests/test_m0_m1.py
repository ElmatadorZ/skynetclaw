"""M0/M1 tests — schema v2, scheduler, extractor, reputation decay/consistency."""
import time, json, pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import institutional_db as idb
import scheduler as sched
import extractor as ex
import outcome_tracker as out
import agent_reputation as rep
import council_memory as mem


# ── M0: schema v2 ──────────────────────────────────────────────────────────
def test_schema_v2_tables_and_columns(db):
    with idb.connect(db) as c:
        tabs = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        pcols = {r["name"] for r in c.execute("PRAGMA table_info(predictions)")}
        rcols = {r["name"] for r in c.execute("PRAGMA table_info(agent_reputation)")}
    for t in ("reputation_history", "constitution_audits", "system_maps", "scheduled_jobs"):
        assert t in tabs
    assert {"extracted_from", "horizon_primary", "metric", "direction"} <= pcols
    assert "consistency" in rcols
    assert idb.current_version(db) == 5

def test_ensure_schema_idempotent(db):
    idb.ensure_schema(db); idb.ensure_schema(db)   # must not raise on re-add columns
    assert idb.current_version(db) == 5


# ── M0: scheduler ──────────────────────────────────────────────────────────
def test_scheduler_enqueue_due_and_tick(db):
    fired = []
    sched.register_handler("t_ping", lambda p: fired.append(p))
    sched.enqueue("t_ping", run_at=time.time()-5, payload={"n": 1}, path=db)
    sched.enqueue("t_ping", run_at=time.time()+9999, path=db)  # not due
    assert len(sched.due_jobs(path=db)) == 1
    r = sched.tick(path=db)
    assert r["ran"] == 1 and fired == [{"n": 1}]

def test_scheduler_recurring_reschedules(db):
    sched.register_handler("t_beat", lambda p: {"reschedule_in": 100})
    sched.enqueue("t_beat", run_at=time.time()-5, job_id="beat1", path=db)
    sched.tick(path=db)
    pend = [j for j in sched.pending(path=db) if j["id"] == "beat1"]
    assert pend and pend[0]["status"] == "pending"   # rescheduled, not done

def test_scheduler_unknown_handler_skipped(db):
    sched.enqueue("t_nohandler", run_at=time.time()-5, path=db)
    r = sched.tick(path=db)
    assert r["skipped_no_handler"] >= 1

def test_catch_up_is_tick(db):
    assert "ran" in sched.catch_up(path=db)


# ── M1: extractor ──────────────────────────────────────────────────────────
def test_extractor_pulls_falsifiable():
    v = {"forecaster": {"scenario": "BTC rallies into Q3", "confidence": 0.6},
         "skeptic": {"reason": "invalidation below 58k"},
         "aggregate_recommendation": "Phase in."}
    ps = ex.extract_predictions(v)
    assert len(ps) == 1
    p = ps[0]
    assert p["direction"] == "up" and p["metric"] == "BTC" and p["invalidation"]

def test_extractor_rejects_unfalsifiable():
    v = {"forecaster": {"scenario": "things look good"},
         "aggregate_recommendation": "be optimistic"}
    assert ex.extract_predictions(v) == []   # Constitution R4

def test_extractor_records_linked_to_session(db):
    v = {"forecaster": {"scenario": "gold breaks higher", "confidence": 0.5},
         "skeptic": {"reason": "wrong if below 2300"},
         "aggregate_recommendation": "Accumulate."}
    sid = mem.from_verdict("Gold Q3?", v, path=db)
    ids = ex.record_from_verdict(v, session_id=sid, path=db)
    assert ids
    p = out.get_prediction(ids[0], db)
    assert p["extracted_from"] == sid and p["metric"].lower() == "gold"


# ── M1: reputation decay + consistency + scorecard ─────────────────────────
def test_decay_regresses_toward_neutral(db):
    rep.ensure_agent("Atlas", db)
    for _ in range(6): rep.apply_outcome("Atlas", "correct", confidence=0.7, path=db)
    high = rep.get("Atlas", db)["score"]
    assert high > 500.0  # earned skill lifts above the 500 neutral
    rep.apply_decay("Atlas", now=time.time() + 365*86400, half_life_days=90, path=db)
    low = rep.get("Atlas", db)["score"]
    assert 500.0 <= low < high   # idle skill fades toward neutral, never inflates

def test_consistency_steady_vs_erratic(db):
    t = time.time() - 200*out.DAY
    for i in range(3):
        pid = out.record_prediction(f"A{i}", agent="Atlas", made_at=t, path=db)
        out.evaluate(pid, "180", "correct", path=db)
    for i, r in enumerate(["correct", "incorrect", "correct", "incorrect"]):
        pid = out.record_prediction(f"S{i}", agent="Skeptic", made_at=t, path=db)
        out.evaluate(pid, "180", r, path=db)
    assert rep.get("Atlas", db)["consistency"] == 1.0
    assert rep.get("Skeptic", db)["consistency"] == 0.0

def test_reputation_history_logged(db):
    rep.ensure_agent("Scout", db)
    rep.apply_outcome("Scout", "correct", path=db)
    rep.apply_decay("Scout", now=time.time()+10*86400, path=db)
    events = [h["event"] for h in rep.history("Scout", path=db)]
    assert "outcome" in events and "decay" in events

def test_scorecard_shape(db):
    rep.ensure_agent("Atlas", db)
    rep.apply_outcome("Atlas", "correct", path=db)
    sc = rep.scorecard("Atlas", db)
    assert sc["agent"] == "Atlas" and "reputation" in sc and "trend" in sc

def test_decay_all_covers_house(db):
    rep.seed_house(db)
    assert rep.decay_all(path=db) == 14


# ── M1: API endpoints ──────────────────────────────────────────────────────
def _client(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import council_intelligence_api as api
    app = FastAPI(); api.register(app)
    return TestClient(app)

def test_api_scorecard_and_scheduler(db):
    rep.seed_house(db); rep.apply_outcome("Atlas", "correct", path=db)
    c = _client(db)
    sc = c.get("/api/council/reputation/Atlas/scorecard")
    assert sc.status_code == 200 and sc.json()["agent"] == "Atlas"
    st = c.get("/api/council/scheduler/status")
    assert st.status_code == 200 and "stats" in st.json()
    tk = c.post("/api/council/scheduler/tick")
    assert tk.status_code == 200 and "ran" in tk.json()
