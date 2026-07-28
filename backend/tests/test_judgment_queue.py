"""
test_judgment_queue.py — the loop must actually close, and say who is blocking it
=================================================================================
The vindication machinery (`governance_engine.on_outcome`) was written, wired,
and had never run once across nine recorded dissents. The cause was not a broken
judge: `auto_judge` correctly abstains on a claim no judge recognises, the claim
stays `pending`, and `on_outcome` refuses to resolve a session's dissents until
that session is fully graded. One unanswerable claim silently blocked every
dissent beside it, and nothing said so.

These tests pin both halves of the repair:

  · the wait is classified honestly — "reality has not answered" is not the same
    state as "nobody asked a human"
  · a human verdict submitted through the queue really does close the loop:
    dissent resolved, minority vindicated, reputation moved

The end-to-end test is the important one. It fails on the pre-fix code path.

    python -m pytest tests/test_judgment_queue.py -q
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import institutional_db as _db  # noqa: E402
import judgment_queue as jq  # noqa: E402

DAY = 86400.0


@pytest.fixture()
def db(tmp_path):
    """A real institutional schema, so the code under test runs unmocked."""
    p = tmp_path / "inst.db"
    _db.init_once(str(p))
    return str(p)


def _session(db, sid, directive="ship the rollout"):
    """predictions.session_id is a real foreign key, so the session must exist."""
    # Plain INSERT, not INSERT OR IGNORE: a fixture that silently swallows its
    # own constraint failure produces tests that fail somewhere far away.
    with _db.connect(db) as c:
        c.execute("INSERT INTO council_sessions (id, ts, directive, participants, "
                  "verdict, confidence, created_at) VALUES(?,?,?,?,?,?,?)",
                  (sid, time.time() - 8 * DAY, directive, "[]", "PROCEED", 0.8,
                   time.time() - 8 * DAY))
        c.commit()


def _stake(db, pid, *, session=None, metric="mission_artifacts",
           invalidation="if the artifact is gone", due_offset=-DAY, agent="Forecaster"):
    if session:
        _session(db, session)
    with _db.connect(db) as c:
        c.execute(
            "INSERT INTO predictions (id, session_id, agent, statement, "
            " predicted_outcome, invalidation, confidence, made_at, due_7, due_30, "
            " due_90, due_180, status, metric, participants) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?, '[]')",
            (pid, session, agent, f"claim {pid}", "holds", invalidation, 0.8,
             time.time() - 8 * DAY, time.time() + due_offset,
             time.time() + 30 * DAY, time.time() + 90 * DAY, time.time() + 180 * DAY,
             metric))
        c.commit()


def _dissent(db, mid, session, agent="Skeptic"):
    with _db.connect(db) as c:
        c.execute("INSERT INTO minority_positions (id, session_id, agent, position, "
                  "reason, stance, ts, resolved, vindication_applied) "
                  "VALUES(?,?,?,?,?,?,?,0,0)",
                  (mid, session, agent, "FRAGILE", "this will not hold", "dissent",
                   time.time() - 8 * DAY))
        c.commit()


# ── classification: the distinction that was missing ─────────────────────────
def test_not_yet_due_is_awaiting_reality_not_awaiting_a_person():
    cl = jq.classify({"status": "pending", "metric": "eval", "invalidation": "x",
                      "due_7": time.time() + DAY})
    assert cl["state"] == "AWAITING_HORIZON"


def test_due_with_no_recognised_metric_is_awaiting_a_human():
    cl = jq.classify({"status": "pending", "metric": "ประสิทธิภาพโดยรวมของ THE HOUSE",
                      "invalidation": "if throughput falls",
                      "due_7": time.time() - 3 * DAY})
    assert cl["state"] == "AWAITING_HUMAN"
    assert cl["overdue_hours"] > 70
    assert "waiting on" in cl["because"] or "operator" in cl["because"]


def test_judged_claim_is_terminal():
    assert jq.classify({"status": "correct"})["state"] == "JUDGED"


def test_json_fragment_invalidation_is_malformed_not_pending():
    """A mis-parsed row must not masquerade as a claim awaiting an answer."""
    cl = jq.classify({"status": "pending", "metric": "",
                      "invalidation": 's": 7, "invalidation": "user declines",',
                      "due_7": time.time() - DAY})
    assert cl["state"] == "MALFORMED"
    assert "mis-parsed" in cl["because"]


def test_missing_invalidation_is_malformed():
    cl = jq.classify({"status": "pending", "metric": "eval", "invalidation": "",
                      "due_7": time.time() - DAY})
    assert cl["state"] == "MALFORMED"
    assert "nothing was committed to as disproof" in cl["because"]


# ── the queue names what is blocked, and on whom ─────────────────────────────
def test_queue_reports_dissents_blocked_on_a_human(db):
    _stake(db, "pr_block", session="cs_1", metric="strategic judgement",
           invalidation="if the rollout fails")
    _dissent(db, "mp_1", "cs_1")
    _dissent(db, "mp_2", "cs_1")

    q = jq.queue(path=db)
    assert q["dissents_blocked_on_a_human"] == 2
    assert "waiting on you" in q["note"]
    top = q["open"][0]
    assert top["state"] == "AWAITING_HUMAN"
    assert top["blocking_dissents"] == 2


def test_queue_does_not_blame_a_human_for_an_unelapsed_horizon(db):
    _stake(db, "pr_future", session="cs_2", metric="strategic judgement",
           due_offset=+5 * DAY)
    _dissent(db, "mp_3", "cs_2")

    q = jq.queue(path=db)
    assert q["dissents_blocked_on_a_human"] == 0
    assert q["note"] is None


# ── the end-to-end proof: a human verdict closes the loop ────────────────────
def test_human_verdict_resolves_the_dissent_and_vindicates_the_minority(db):
    """The whole point. Before this, `on_outcome` had never run in production."""
    _stake(db, "pr_e2e", session="cs_e2e", metric="strategic judgement",
           invalidation="if the rollout fails")
    _dissent(db, "mp_e2e", "cs_e2e", agent="Skeptic")

    with _db.connect(db) as c:
        before = c.execute("SELECT resolved, proven_correct, vindication_applied "
                           "FROM minority_positions WHERE id='mp_e2e'").fetchone()
    assert before["resolved"] == 0, "precondition: the dissent is unresolved"

    # The council was WRONG. Reality says so, via the operator.
    jq.submit("pr_e2e", "incorrect", horizon="7", note="rollout failed", path=db)

    with _db.connect(db) as c:
        after = c.execute("SELECT resolved, proven_correct, vindication_applied "
                          "FROM minority_positions WHERE id='mp_e2e'").fetchone()
        pred = c.execute("SELECT status FROM predictions WHERE id='pr_e2e'").fetchone()

    assert pred["status"] == "incorrect"
    assert after["resolved"] == 1, "the dissent must now be resolved"
    assert after["proven_correct"] == 1, "majority wrong ⇒ the dissenter was right"
    assert after["vindication_applied"] == 1, "the vindication must reach reputation"


def test_a_correct_majority_resolves_without_punishing_the_dissenter(db):
    """House doctrine: a dissenter who turned out wrong is never punished."""
    _stake(db, "pr_ok", session="cs_ok", metric="strategic judgement",
           invalidation="if it fails")
    _dissent(db, "mp_ok", "cs_ok", agent="Skeptic")

    with _db.connect(db) as c:
        rep_before = c.execute("SELECT score FROM agent_reputation WHERE agent='Skeptic'"
                               ).fetchone()
    before_score = rep_before["score"] if rep_before else None

    jq.submit("pr_ok", "correct", horizon="7", path=db)

    with _db.connect(db) as c:
        m = c.execute("SELECT resolved, proven_correct, vindication_applied "
                      "FROM minority_positions WHERE id='mp_ok'").fetchone()
        rep_after = c.execute("SELECT score FROM agent_reputation WHERE agent='Skeptic'"
                              ).fetchone()

    assert m["resolved"] == 1
    assert m["proven_correct"] == 0, "the majority held, so the dissent was not vindicated"
    assert m["vindication_applied"] == 0, "no reward"
    after_score = rep_after["score"] if rep_after else None
    if before_score is not None and after_score is not None:
        assert after_score >= before_score, "a wrong dissent must never be punished"


def test_submit_refuses_a_verdict_it_does_not_understand(db):
    _stake(db, "pr_bad", session="cs_b")
    with pytest.raises(ValueError):
        jq.submit("pr_bad", "probably", path=db)


def test_submit_goes_through_the_ordinary_grading_path(db, monkeypatch):
    """A second write path would be an untested way to change what the House
    believes. The queue must delegate, not reimplement."""
    called = {}

    def _spy(pid, horizon, result, path=None):
        called.update(pid=pid, horizon=horizon, result=result)
        return {}

    monkeypatch.setattr(jq._ot, "evaluate", _spy)
    jq.submit("pr_x", "partial", horizon="30", path=db)
    assert called == {"pid": "pr_x", "horizon": "30", "result": "partial"}
