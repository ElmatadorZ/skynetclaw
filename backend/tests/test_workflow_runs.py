"""
test_workflow_runs.py — OX-WORKFLOW-1 Workflow Persistence Protocol
Every dispatch leaves a durable record and always reaches a terminal status.
  A — dispatch + COMPREHEND failure → workflow row exists
  B — dispatch + PLAN failure       → workflow row exists
  C — dispatch + channel disconnect → workflow row closed (interrupted)
  D — dispatch + EXECUTE success    → workflow linked to house_state + agent_run
  E — no workflow remains active after restart (reconciliation)
Plus correlation, idempotent terminal, and telemetry metrics.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import workflow_runs as WF


def _db(tmp_path):
    return WF.WorkflowRunsDB(tmp_path / "wf.db")


def test_schema_and_start(tmp_path):
    db = _db(tmp_path)
    db.start("CD-1", "build a report")
    r = db.get("CD-1")
    assert r and r["status"] == "created" and r["phase"] == "dispatch"
    assert r["directive"] == "build a report" and r["created_at"] > 0


def test_A_comprehend_failure_leaves_row(tmp_path):
    db = _db(tmp_path)
    db.start("CD-A", "delete all object")
    db.set_phase("CD-A", "comprehend")
    db.complete_if_open("CD-A", "failed", "comprehend stalled")   # the attempt gap, now closed
    r = db.get("CD-A")
    assert r is not None                       # NO dispatch disappears
    assert r["status"] == "failed" and r["phase"] == "comprehend"
    assert "comprehend" in r["termination_reason"]


def test_B_plan_failure_leaves_row(tmp_path):
    db = _db(tmp_path)
    db.start("CD-B", "x"); db.set_phase("CD-B", "comprehend"); db.set_phase("CD-B", "plan")
    db.complete_if_open("CD-B", "failed", "plan invalid")
    r = db.get("CD-B")
    assert r and r["status"] == "failed" and r["phase"] == "plan"


def test_C_disconnect_closes_workflow(tmp_path):
    db = _db(tmp_path)
    db.start("CD-C", "x"); db.set_phase("CD-C", "council")
    # simulate the relay finally on client disconnect
    closed = db.complete_if_open("CD-C", "interrupted", "stream ended before terminal status")
    assert closed is True
    assert db.get("CD-C")["status"] == "interrupted"
    # idempotent — a real terminal status is never clobbered
    assert db.complete_if_open("CD-C", "interrupted") is False


def test_D_execute_success_links_state_and_run(tmp_path):
    db = _db(tmp_path)
    db.start("CD-D", "summarize AAPL")
    for ph in ("comprehend", "plan", "council"):
        db.set_phase("CD-D", ph)
    db.link("CD-D", house_state_id="hs_abc")        # from house_mind event
    db.set_phase("CD-D", "execute")
    db.link("CD-D", agent_run_id="run_xyz")          # from agent_start event
    db.complete("CD-D", "completed")
    r = db.get("CD-D")
    assert r["status"] == "completed" and r["phase"] == "complete"
    assert r["house_state_id"] == "hs_abc" and r["agent_run_id"] == "run_xyz"   # full correlation
    # link uses COALESCE — first non-null id is never overwritten
    db.link("CD-D", house_state_id="hs_OTHER")
    assert db.get("CD-D")["house_state_id"] == "hs_abc"


def test_E_no_active_after_restart(tmp_path):
    db = _db(tmp_path)
    db.start("done", "t"); db.complete("done", "completed")
    db.start("orphan1", "t"); db.set_phase("orphan1", "comprehend")
    db.start("orphan2", "t"); db.set_phase("orphan2", "execute")
    n = db.reconcile_stale(max_age_seconds=-1)        # cutoff in the future → all active
    assert n == 2
    assert db.get("orphan1")["status"] == "interrupted"
    assert db.get("orphan2")["status"] == "interrupted"
    assert db.get("done")["status"] == "completed"    # terminal untouched
    assert all(r["status"] not in WF.ACTIVE_STATUSES for r in db.recent(100))


def test_metrics(tmp_path):
    db = _db(tmp_path)
    db.start("c1", "t"); db.complete("c1", "completed")
    db.start("c2", "t"); db.complete("c2", "completed")
    db.start("f1", "t"); db.set_phase("f1", "comprehend"); db.complete("f1", "failed", "stall")
    db.start("i1", "t"); db.set_phase("i1", "plan"); db.complete("i1", "interrupted")
    m = db.metrics()
    assert m["total"] == 4
    assert m["completion_rate"] == 0.5            # 2/4
    assert m["abandonment_rate"] == 0.5           # failed + interrupted
    assert m["by_status"]["completed"] == 2
    # phase-failure distribution: where the non-completed ones died
    assert m["phase_failure_distribution"].get("comprehend") == 1
    assert m["phase_failure_distribution"].get("plan") == 1
    assert "avg_phase_reached" in m
