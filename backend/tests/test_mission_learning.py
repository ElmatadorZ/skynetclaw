"""
test_mission_learning.py — ADR-0016: a mission outcome must revise belief
========================================================================
The First Evidence Review's Q2 found that the mission whose hypothesis `rg-1`
graded `correct` taught the House nothing. It produced a Validated Episode and
stopped.

`revise_from_outcome()` locates the House State by DIRECTIVE TEXT and never needed
a session id. But `evaluate()` fetched the directive *through* council_sessions,
and a mission has no session row — so the entire revision step was a silent no-op
for every mission ever graded. No error, no log line, nothing.

Deliberately unchanged: `on_outcome()` stays session-gated. A mission has no
council deliberation and therefore no dissent to resolve; skipping it there is
correct rather than a second instance of the same bug.

    python -m pytest tests/test_mission_learning.py -q
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import institutional_db as _db  # noqa: E402
import outcome_tracker as ot  # noqa: E402

DAY = 86400.0


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "inst.db"
    _db.init_once(str(p))
    return str(p)


def _stake(db, pid, statement, session=None, metric="mission_artifacts",
           identity=None):
    """identity= records the ADR-0016 canonical key in the payload, exactly as
    reality_grading.record_mission_hypothesis() does at stake time."""
    import json as _json
    payload = _json.dumps({"mission_identity": identity} if identity else {})
    with _db.connect(db) as c:
        c.execute(
            "INSERT INTO predictions (id, session_id, agent, statement, "
            " predicted_outcome, invalidation, confidence, made_at, due_7, due_30, "
            " due_90, due_180, status, metric, participants) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?, '[]')",
            (pid, session, "mission_operative", statement, payload,
             "if the artifact is gone", 0.8, time.time() - 8 * DAY,
             time.time() - DAY, time.time() + 30 * DAY, time.time() + 90 * DAY,
             time.time() + 180 * DAY, metric))
        c.commit()


def _belief(db, directive, content, conf=1.0):
    """A House State the revision can find by directive text."""
    import house_state as hs
    sid = hs.open_state(directive, path=db)
    hs.add_belief(sid, content, confidence=conf, agent="Council", path=db)
    return sid


def _reality_rows(db):
    with _db.connect(db) as c:
        return c.execute("SELECT COUNT(*) FROM belief_changes "
                         "WHERE LOWER(agent) LIKE 'reality%'").fetchone()[0]


# ── the defect ───────────────────────────────────────────────────────────────
def test_a_mission_with_no_session_still_revises_belief(db):
    """The whole point of ADR-0016."""
    directive = "MISSION 0001 - ADR-0014 Compliance Audit"
    _belief(db, directive, "the audit will find no violations", conf=1.0)
    _stake(db, "pr_mission",
           f"Mission hypothesis: outcome COMPLETE will hold — {directive}",
           session=None, identity=directive)

    assert _reality_rows(db) == 0, "precondition"
    out = ot.evaluate("pr_mission", "7", "incorrect", path=db)

    assert out["result"] == "incorrect"
    assert _reality_rows(db) == 1, (
        "a graded mission outcome must reach the House Mind — it carried its own "
        "directive all along")
    assert out.get("belief_change")


def test_a_session_backed_prediction_still_prefers_the_session_directive(db):
    """The fuller text wins when it exists; the fallback must not displace it."""
    directive = "strategic decision: which feature next"
    _belief(db, directive, "backport security will be chosen")
    with _db.connect(db) as c:
        c.execute("INSERT INTO council_sessions (id, ts, directive, participants, "
                  "verdict, confidence, created_at) VALUES(?,?,?,?,?,?,?)",
                  ("cs_1", time.time() - 8 * DAY, directive, "[]", "PROCEED", 0.8,
                   time.time() - 8 * DAY))
        c.commit()
    _stake(db, "pr_council", "an unrelated statement", session="cs_1",
           metric="strategic judgement")

    ot.evaluate("pr_council", "7", "incorrect", path=db)
    assert _reality_rows(db) == 1


def test_no_matching_belief_is_not_an_error(db):
    """Nothing to revise is a valid outcome, not a failure."""
    _stake(db, "pr_orphan", "Mission hypothesis: something nobody believed",
           session=None)
    out = ot.evaluate("pr_orphan", "7", "correct", path=db)
    assert out["result"] == "correct"
    assert out.get("belief_change") is None
    assert _reality_rows(db) == 0


def test_a_correct_mission_reinforces_rather_than_halving(db):
    directive = "MISSION 0002 - index rebuild"
    _belief(db, directive, "the rebuild is safe", conf=0.5)
    _stake(db, "pr_ok", f"Mission hypothesis: outcome COMPLETE will hold — {directive}",
           identity=directive)

    ot.evaluate("pr_ok", "7", "correct", path=db)
    with _db.connect(db) as c:
        row = c.execute("SELECT prev_confidence, new_confidence FROM belief_changes "
                        "WHERE LOWER(agent) LIKE 'reality%'").fetchone()
    assert row is not None
    assert row["new_confidence"] >= row["prev_confidence"], \
        "a confirmed mission must not lower the belief it confirmed"


# ── what must NOT change ─────────────────────────────────────────────────────
def test_dissent_resolution_stays_session_gated(db):
    """A mission has no council deliberation, so it has no dissent to resolve.
    Widening on_outcome() to sessionless claims would resolve dissents that were
    never about this work."""
    _stake(db, "pr_m", "Mission hypothesis: outcome COMPLETE will hold — M3")
    out = ot.evaluate("pr_m", "7", "correct", path=db)
    assert out.get("minority") is None, \
        "a sessionless claim must not touch anyone's dissent record"
