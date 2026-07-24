"""
council_intelligence_api.py — PART 9 API + PART 8 backend for THE HOUSE
=======================================================================
FastAPI router exposing the Institutional Memory to the Council Intelligence
Dashboard. Mount with:  register(app)  (added in main.py).

Endpoints (all under /api/council):
  /memory/recent · /memory/recall · /memory/{id} · /memory/stats
  /reputation · /reputation/best-worst
  /outcomes/summary · /outcomes/recent · /outcomes/due/{horizon} · /outcomes/{pid}/evaluate
  /archive/recent
  /constitution
  /learning            (consensus + confidence trends, successes/failures)
  /dashboard           (serves council_intelligence.html)

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import council_memory as _mem
import agent_reputation as _rep
import outcome_tracker as _out
import deliberation_archive as _arc
import house_constitution as _con
import scheduler as _sched
import governance_engine as _gov
import house_state as _hstate

router = APIRouter(prefix="/api/council", tags=["council-intelligence"])


@router.get("/memory/recent")
def memory_recent(limit: int = 20):
    return {"sessions": _mem.recent(limit=limit)}


@router.get("/memory/stats")
def memory_stats():
    return _mem.stats()


@router.get("/memory/recall")
def memory_recall(q: str, limit: int = 5):
    return {"query": q, "matches": _mem.recall(q, limit=limit)}


@router.get("/memory/{session_id}")
def memory_get(session_id: str):
    s = _mem.get_session(session_id)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    return s


@router.get("/reputation")
def reputation(limit: int = 20):
    return {"leaderboard": _rep.leaderboard(limit=limit)}


@router.get("/reputation/best-worst")
def reputation_best_worst():
    return _rep.best_and_worst()


@router.get("/outcomes/summary")
def outcomes_summary():
    return _out.review_summary()


@router.get("/outcomes/recent")
def outcomes_recent(limit: int = 20):
    return {"outcomes": _out.recent_outcomes(limit=limit)}


@router.get("/outcomes/due/{horizon}")
def outcomes_due(horizon: str):
    try:
        return {"horizon": horizon, "due": _out.due_reviews(horizon)}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


class EvalReq(BaseModel):
    horizon: str
    result: str


@router.post("/outcomes/{pid}/evaluate")
def outcomes_evaluate(pid: str, req: EvalReq):
    try:
        res = _out.evaluate(pid, req.horizon, req.result)
        # Phase 6: reality just graded a prediction (and may have revised a belief)
        # — surface any new lessons / behavior changes / repeat failures on the bus.
        try:
            import learning_engine as _le, house_sync as _hsync
            _le.diff_and_emit(_hsync.publish)
        except Exception:
            pass
        return res
    except (ValueError, KeyError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/archive/recent")
def archive_recent(limit: int = 20):
    return {"archive": _arc.recent(limit=limit)}


@router.get("/constitution")
def constitution():
    return {"version": _con.VERSION, "rules": _con.RULES, "text": _con.load_constitution()}


@router.get("/learning")
def learning():
    """Institutional learning: consensus & confidence trends, successes, failures."""
    sessions = _mem.recent(limit=50)
    confs = [s["confidence"] for s in sessions if s.get("confidence") is not None]
    trend = _trend(confs)
    bw = _rep.best_and_worst()
    recent_out = _out.recent_outcomes(limit=20)
    successes = [o for o in recent_out if o["status"] == "correct"][:5]
    failures = [o for o in recent_out if o["status"] == "incorrect"][:5]
    dissent_rate = (sum(1 for s in sessions if "unanimous" not in (s.get("dissent_summary") or "")) /
                    len(sessions)) if sessions else 0.0
    return {
        "confidence_trend": trend,
        "avg_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
        "consensus_dissent_rate": round(dissent_rate, 4),
        "best_agents": bw["best"],
        "worst_agents": bw["worst"],
        "recent_successes": successes,
        "recent_failures": failures,
        "n_sessions": len(sessions),
    }


def _trend(values: List[float]) -> str:
    if len(values) < 2:
        return "flat"
    # values are recent-first; compare newer half vs older half
    mid = len(values) // 2
    newer = sum(values[:mid]) / max(mid, 1)
    older = sum(values[mid:]) / max(len(values) - mid, 1)
    if newer > older + 0.05:
        return "rising"
    if newer < older - 0.05:
        return "falling"
    return "flat"


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    html = Path(__file__).parent / "council_intelligence.html"
    if html.exists():
        return HTMLResponse(html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Council Intelligence Dashboard</h1><p>council_intelligence.html missing</p>")


@router.get("/reputation/{agent}/scorecard")
def reputation_scorecard(agent: str):
    return _rep.scorecard(agent)


@router.get("/scheduler/status")
def scheduler_status():
    return {"stats": _sched.stats(), "pending": _sched.pending()[:50]}


@router.post("/scheduler/tick")
def scheduler_tick():
    """Run any due jobs now (Outcome Clock, reputation decay). Cron/admin hook."""
    return _sched.tick()


@router.get("/governance/stats")
def governance_stats():
    return _gov.stats()


@router.get("/governance/{session_id}")
def governance_record(session_id: str):
    rec = _gov.governance_record(session_id)
    if not rec:
        return JSONResponse({"error": "no governance record"}, status_code=404)
    return rec


@router.get("/minorities")
def minorities(vindicated: bool = False, limit: int = 50):
    return {"minorities": _gov.minorities(only_vindicated=vindicated, limit=limit)}


@router.get("/minorities/scoreboard")
def minority_scoreboard():
    return {"scoreboard": _gov.minority_scoreboard()}


@router.get("/state/current")
def state_current():
    st = _hstate.current()
    return st or {"error": "no active House state", "items": {}}


@router.get("/state/{state_id}")
def state_get(state_id: str):
    st = _hstate.read_state(state_id)
    if not st:
        return JSONResponse({"error": "not found"}, status_code=404)
    return st


@router.get("/state/{state_id}/answer")
def state_answer(state_id: str):
    """The House answers: what we know / don't know / believe / why / what changed our mind."""
    return _hstate.answer(state_id)


@router.get("/state/{state_id}/changes")
def state_changes(state_id: str, limit: int = 20):
    return {"changes": _hstate.recent_changes(state_id, limit=limit)}


@router.get("/belief-changes")
def belief_changes(limit: int = 30):
    """Recent belief evolutions — what changed the House's mind and why."""
    import institutional_db as _idb, time as _t
    _idb.init_once()
    with _idb.connect() as c:
        rows = c.execute(
            "SELECT bc.id, bc.state_id, bc.previous, bc.new, bc.prev_confidence, "
            "bc.new_confidence, bc.reason, bc.evidence, bc.agent, bc.ts, "
            "hs.question FROM belief_changes bc "
            "LEFT JOIN house_state hs ON bc.state_id=hs.id "
            "ORDER BY bc.ts DESC LIMIT ?", (limit,)).fetchall()
    return {"changes": [dict(r) for r in rows], "total": len(rows)}


@router.get("/recall-quality/sessions")
def recall_quality_sessions(limit: int = 20):
    """Recent council sessions with Recall Quality scores (validity, accuracy, age)."""
    import institutional_db as _idb, time as _t
    import recall_quality as _rq
    sessions = _mem.recent(limit=limit)
    if not sessions:
        return {"sessions": []}
    _idb.init_once()
    with _idb.connect() as c:
        outcomes = _rq.gather_outcomes(c, [s["id"] for s in sessions])
    now = _t.time()
    result = []
    for s in sessions:
        sid = s["id"]
        oc = outcomes.get(sid, {})
        age = (now - (s.get("ts") or now)) / 86400.0
        validity, reason = _rq.assess_validity(
            oc.get("accuracy"), oc.get("n_evaluated", 0), age, None)
        result.append({**s, "validity": validity, "validity_reason": reason,
                       "outcomes": oc, "age_days": round(age, 1)})
    return {"sessions": result}


@router.get("/missions")
def missions_list(limit: int = 20):
    """Active and recently closed missions from house_state."""
    import institutional_db as _idb
    _idb.init_once()
    with _idb.connect() as c:
        active = [dict(r) for r in c.execute(
            "SELECT id, question, confidence, summary, created_at, updated_at "
            "FROM house_state WHERE status='open' ORDER BY updated_at DESC LIMIT ?",
            (limit,)).fetchall()]
        completed = [dict(r) for r in c.execute(
            "SELECT id, question, confidence, summary, created_at, updated_at "
            "FROM house_state WHERE status='closed' ORDER BY updated_at DESC LIMIT ?",
            (limit,)).fetchall()]
    recent_sessions = _mem.recent(limit=10)
    return {"active": active, "completed": completed, "recent_sessions": recent_sessions}


def register(app) -> None:
    """Mount the Council Intelligence API + wire the Outcome Clock (call from main.py)."""
    import institutional_db as _db
    _db.ensure_schema()
    try:
        _rep.seed_house()
    except Exception:
        pass
    # M1: register scheduler handlers + recurring jobs, then catch up on boot
    try:
        _sched.register_handler("outcome_review", _out.outcome_clock_handler)
        _sched.register_handler("reputation_decay", _rep.reputation_decay_handler)
        try:
            import eval_suite as _evs
            _sched.register_handler("nightly_eval", _evs.nightly_eval_handler)
            # first run ~04:00 local tonight (quiet hours), then daily via reschedule
            import datetime as _dt
            _t = _dt.datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)
            if _t <= _dt.datetime.now():
                _t += _dt.timedelta(days=1)
            _sched.enqueue("nightly_eval", run_at=_t.timestamp(), job_id="job_nightly_eval")
        except Exception as _ne:
            print(f"[InstitutionalMemory] nightly eval wire skipped: {_ne}")
        _sched.enqueue("outcome_review", job_id="job_outcome_review_daily")
        _sched.enqueue("reputation_decay", job_id="job_reputation_decay_weekly")
        _sched.catch_up()
        # CONTINUOUS TICK: catch_up only ran at boot, so daily jobs fired only
        # when the operator happened to restart the backend — the Outcome Clock
        # never actually ticked on a live system. A daemon ticker fixes that.
        import threading as _th, time as _tm

        def _tick_loop():
            while True:
                _tm.sleep(600)
                try:
                    _sched.tick()
                except Exception as _te:
                    print(f"[Scheduler] tick failed: {_te}")

        _th.Thread(target=_tick_loop, daemon=True, name="institutional-scheduler-tick").start()
        print("[InstitutionalMemory] scheduler ticking every 10 min (nightly eval ~04:00)")
    except Exception as _se:
        print(f"[InstitutionalMemory] scheduler wire skipped: {_se}")
    app.include_router(router)
