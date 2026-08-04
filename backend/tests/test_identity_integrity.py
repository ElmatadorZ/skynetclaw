"""
test_identity_integrity.py — ADR-0016: one canonical name per unit of work
==========================================================================
The identity twin of P1. P1 forbids two writers of one file; this forbids two ways
of naming one mission. Same defect, different clothes, same consequence: something
that should have joined silently did not.

Measured before the fix: 0 of 8 predictions matched any stored key — not one, not
even as a substring. Five different truncation lengths (80/160/200/300/1000) were
in play for the same conceptual thing, and 9 live House-State keys exceed 160
characters, so `reality_grading`'s slice was already lossy.

The guard checks DATA, not source, and that choice is the point: a source scan
cannot tell a key from a caption, and nine modules legitimately build truncated
previews for logs and UI.

    python -m pytest tests/test_identity_integrity.py -q
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import house_state as hs  # noqa: E402
import identity_integrity as ii  # noqa: E402
import institutional_db as _db  # noqa: E402

DAY = 86400.0


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "inst.db"
    _db.init_once(str(p))
    return str(p)


def _stake(db, pid, identity=None, agent="mission_operative"):
    payload = {} if identity is None else {"mission_identity": identity}
    with _db.connect(db) as c:
        c.execute(
            "INSERT INTO predictions (id, agent, statement, predicted_outcome, "
            " invalidation, confidence, made_at, status, metric, participants) "
            "VALUES(?,?,?,?,?,?,?, 'pending', 'mission_artifacts', '[]')",
            (pid, agent, "Mission hypothesis: …", json.dumps(payload),
             "if the artifact is gone", 0.8, time.time()))
        c.commit()


# ── the invariant ────────────────────────────────────────────────────────────
def test_a_claim_naming_a_real_state_passes(db):
    hs.open_state("MISSION 0001 - audit", path=db)
    _stake(db, "pr_ok", identity="MISSION 0001 - audit")
    r = ii.verify(db)
    assert r["ok"] and not r["violations"]


def test_a_claim_naming_a_state_that_does_not_exist_fails(db):
    hs.open_state("MISSION 0001 - audit", path=db)
    _stake(db, "pr_bad", identity="MISSION 0001 - aud")     # truncated by one char
    r = ii.verify(db)
    assert not r["ok"]
    assert r["violations"][0]["prediction"] == "pr_bad"
    assert "does not exist" in r["violations"][0]["problem"]


def test_truncation_is_caught(db):
    """The concrete hazard: 9 live House-State keys exceed the 160-char slice."""
    long_key = "MISSION 0002 - " + ("x" * 300)
    hs.open_state(long_key, path=db)
    _stake(db, "pr_trunc", identity=long_key[:160])
    assert not ii.verify(db)["ok"], "a truncated identity must not pass"


# ── deliberate absences are not violations ───────────────────────────────────
def test_an_empty_identity_is_not_a_violation(db):
    """clean_identity() returns "" for a prompt or an error string — and in that
    case open_state() was never called either. The two ends fail together, which is
    what makes this the right key rather than a coincidence."""
    _stake(db, "pr_rejected", identity="")
    r = ii.verify(db)
    assert r["ok"]
    assert not r["violations"]


def test_pre_adr_rows_are_reported_as_legacy_not_as_violations(db):
    """They are evidence of the defect. Counting them as violations would make the
    guard permanently red and therefore useless."""
    _stake(db, "pr_old", identity=None)
    r = ii.verify(db)
    assert r["ok"]
    assert r["legacy"] == ["pr_old"]


def test_session_backed_claims_are_out_of_scope(db):
    """A council claim joins on session_id, an FK. It does not need a name, and
    holding it to one would be ceremony."""
    _stake(db, "pr_council", identity=None, agent="Forecaster")
    r = ii.verify(db)
    assert r["checked"] == 0, "only identity-bearing agents are held to this"
    assert r["ok"]


# ── the end-to-end property ADR-0016 exists for ──────────────────────────────
def test_the_staked_identity_is_the_one_open_state_uses(db):
    """The whole principle in one assertion: the name the mission is filed under
    and the name its claim is staked under must be produced by the same function."""
    import mission_identity as mid
    task = "MISSION 0003 - verify the migration is reversible"
    ident = mid.clean_identity(task, "")
    hs.open_state(ident, path=db)
    _stake(db, "pr_e2e", identity=ident)
    assert ii.verify(db)["ok"]


# ── the real staking path, not a hand-built payload ──────────────────────────
def test_record_mission_hypothesis_stakes_the_canonical_identity_whole(db, tmp_path):
    """Every test above builds the payload by hand, so none of them exercises the
    code that actually stakes a claim. Re-truncating the identity in
    reality_grading passed all of them — this is the test that catches it."""
    import json as _json

    import mission_identity as mid
    import reality_grading as rg

    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "report.md").write_text("done", encoding="utf-8")

    long_task = "MISSION 0004 - " + ("verify the reversible migration " * 12)
    entry = {"id": "led_1", "status": "COMPLETE", "task": long_task,
             "files": ["report.md"]}

    pid = rg.record_mission_hypothesis(str(ws), entry, path=db)
    assert pid, "a COMPLETE mission with artifacts must stake a claim"

    with _db.connect(db) as c:
        row = c.execute("SELECT predicted_outcome FROM predictions WHERE id=?",
                        (pid,)).fetchone()
    ident = _json.loads(row["predicted_outcome"]).get("mission_identity")

    expected = mid.clean_identity(long_task, "")
    assert ident == expected, "the staked identity must come from clean_identity()"
    assert len(ident) > 160, (
        "the identity must be stored WHOLE — 9 live House-State keys exceed 160 "
        "characters, so a slice here silently unfiles the mission")
