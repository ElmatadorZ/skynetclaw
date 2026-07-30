"""
test_epistemic_dossier.py — the receipt must be honest, especially when thin
============================================================================
The dossier's value is entirely in what it refuses to do: it must not report a
belief as tested when nothing tested it, must not call confidence earned when no
prediction was ever graded, must not hide an unresolved dissent, and must not
turn "no data" into a flattering zero.

Every test drives a temporary database, so the assertions hold regardless of
what the live House happens to contain today.

    python -m pytest tests/test_epistemic_dossier.py -q
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import epistemic_dossier as ed  # noqa: E402


# ── a purpose-built House record ─────────────────────────────────────────────
@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "t.db"
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE state_items(id TEXT, state_id TEXT, kind TEXT, content TEXT,
            confidence REAL, agent TEXT, evidence TEXT, status TEXT,
            superseded INT DEFAULT 0, ts REAL);
        CREATE TABLE minority_positions(id TEXT, session_id TEXT, agent TEXT,
            position TEXT, reason TEXT, stance TEXT, ts REAL, resolved INT DEFAULT 0,
            proven_correct INT, resolved_at REAL, vindication_applied INT DEFAULT 0);
        CREATE TABLE predictions(id TEXT, session_id TEXT, agent TEXT, statement TEXT,
            predicted_outcome TEXT, invalidation TEXT, confidence REAL, made_at REAL,
            due_7 REAL, status TEXT, evaluated_at REAL);
        CREATE TABLE belief_changes(id TEXT, state_id TEXT, item_id TEXT, previous TEXT,
            new TEXT, prev_confidence REAL, new_confidence REAL, reason TEXT,
            evidence TEXT, agent TEXT, ts REAL);
        CREATE TABLE agent_reputation(agent TEXT, score REAL, wins INT, losses INT,
            draws INT, n_predictions INT, n_correct INT, accuracy_rate REAL,
            forecast_quality REAL, evidence_quality REAL, critique_quality REAL,
            updated_at REAL, consistency REAL, alpha REAL, beta REAL,
            last_outcome_at REAL, brier_sum REAL, brier_n INT, calibration REAL);
    """)
    c.commit()
    c.close()
    monkeypatch.setattr(ed, "_DB", p)
    return p


def _sql(db, sql, *a):
    c = sqlite3.connect(db)
    c.execute(sql, a)
    c.commit()
    c.close()


def _belief(db, content, conf=0.9, agent="Analyst", kind="belief", superseded=0):
    _sql(db, "INSERT INTO state_items VALUES(?,?,?,?,?,?,?,?,?,?)",
         "si_1", "hs_1", kind, content, conf, agent, "some evidence", "active",
         superseded, 1_780_000_000.0)


def _agent(db, name, n_pred=0, correct=0, alpha=1.0, beta=1.0, brier_n=0):
    _sql(db, "INSERT INTO agent_reputation VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
         name, 500.0, 0, 0, 0, n_pred, correct,
         (correct / n_pred) if n_pred else None,
         None, None, None, 0.0, None, alpha, beta, None, 0.0, brier_n, 0.5)


# ── the central claim: unearned confidence is named as unearned ──────────────
def test_confidence_without_a_graded_prediction_is_unearned(db):
    _belief(db, "the migration will hold under load", conf=0.95)
    _agent(db, "Analyst", n_pred=0)

    d = ed.dossier("migration load")
    assert d["trust_basis"] == "UNEARNED"
    assert d["stated_confidence"] == 0.95, "the stated figure is still reported"
    assert d["graded_predictions_behind_it"] == 0
    assert "unearned" in d["honest_summary"].lower()
    assert "assertion, not a measurement" in d["honest_summary"]


def test_confidence_becomes_earned_once_predictions_are_graded(db):
    _belief(db, "the migration will hold under load", conf=0.95)
    _agent(db, "Analyst", n_pred=4, correct=3)

    d = ed.dossier("migration load")
    assert d["trust_basis"] == "EARNED"
    assert d["graded_predictions_behind_it"] == 4


def test_agent_at_the_neutral_prior_is_flagged_as_a_placeholder(db):
    _belief(db, "vault path is stable", agent="Skeptic")
    _agent(db, "Skeptic", n_pred=0, alpha=1.0, beta=1.0)

    rec = ed.dossier("vault path")["track_record_of_the_asserters"]["Skeptic"]
    assert rec["at_neutral_prior"] is True
    assert rec["n_graded"] == 0
    assert "neutral prior" in rec["note"]


# ── standing ─────────────────────────────────────────────────────────────────
def test_no_record_is_reported_as_no_record_not_invented(db):
    d = ed.dossier("something the house has never considered")
    assert d["standing"] == "NO_RECORD"
    assert "nothing on file" in d["honest_summary"]
    assert d["what_the_house_believes"] == []


def test_untested_belief_says_reality_never_checked_it(db):
    _belief(db, "the cache layer reduces latency")
    _agent(db, "Analyst")
    d = ed.dossier("cache latency")
    assert d["standing"] == "UNTESTED"
    assert "never checked" in d["because"]


def test_unresolved_dissent_makes_the_belief_contested(db):
    _belief(db, "local models beat cloud for this workload")
    _agent(db, "Analyst")
    _sql(db, "INSERT INTO minority_positions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         "mp_1", "cs_1", "Skeptic", "FRAGILE",
         "local models may lose on long-context workload", "dissent",
         1_780_000_100.0, 0, None, 0.0, 0)

    d = ed.dossier("local models workload")
    assert d["standing"] == "CONTESTED"
    assert d["who_disagreed"][0]["dissenter"] == "Skeptic"
    assert d["who_disagreed"][0]["resolved"] is False
    assert "never resolved" in d["honest_summary"]
    assert "does not know whether the minority was right" in d["honest_summary"]


def test_refuted_outranks_everything(db):
    _belief(db, "the index rebuild is safe")
    _agent(db, "Analyst")
    _sql(db, "INSERT INTO predictions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         "pr_1", "cs_1", "Analyst", "the index rebuild is safe", "ok",
         "if it corrupts a shard", 0.9, 1_780_000_000.0, 1_780_600_000.0,
         "incorrect", 1_780_700_000.0)

    d = ed.dossier("index rebuild")
    assert d["standing"] == "REFUTED"


def test_reality_driven_revision_is_distinguished_from_more_talk(db):
    _belief(db, "throughput scales linearly")
    _agent(db, "Analyst")
    _sql(db, "INSERT INTO belief_changes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         "bc_1", "hs_1", "si_1", "throughput scales linearly",
         "throughput plateaus past 8 workers", 0.8, 0.4,
         "observed in production", None, "Reality (outcome)", 1_780_500_000.0)

    d = ed.dossier("throughput scales")
    assert d["standing"] == "REVISED_BY_REALITY"
    assert d["how_the_belief_has_moved"][0]["driven_by_reality"] is True


def test_deliberation_revision_is_not_counted_as_reality(db):
    _belief(db, "queue depth is the bottleneck")
    _agent(db, "Analyst")
    _sql(db, "INSERT INTO belief_changes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         "bc_1", "hs_1", "si_1", "queue depth is the bottleneck",
         "lock contention is the bottleneck", 0.7, 0.6, "further debate",
         None, "Council", 1_780_500_000.0)

    d = ed.dossier("queue depth bottleneck")
    assert d["standing"] != "REVISED_BY_REALITY"
    assert d["how_the_belief_has_moved"][0]["driven_by_reality"] is False


# ── falsifiers and unknowns ──────────────────────────────────────────────────
def test_missing_falsifier_is_called_out(db):
    _belief(db, "the retry policy is correct")
    _agent(db, "Analyst")
    d = ed.dossier("retry policy")
    assert "No falsifier is on record" in d["honest_summary"]


def test_falsifier_is_surfaced_with_its_invalidation_condition(db):
    _belief(db, "the retry policy is correct")
    _agent(db, "Analyst")
    _sql(db, "INSERT INTO predictions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         "pr_1", "cs_1", "Analyst", "the retry policy is correct", "holds",
         "if duplicate writes appear", 0.8, 1_780_000_000.0, 1_780_600_000.0,
         "pending", None)

    f = ed.dossier("retry policy")["what_would_prove_it_wrong"][0]
    assert f["would_be_wrong_if"] == "if duplicate writes appear"
    assert f["graded"] is False


def test_recorded_unknowns_are_reported(db):
    _belief(db, "the shard layout is optimal")
    _agent(db, "Analyst")
    _sql(db, "INSERT INTO state_items VALUES(?,?,?,?,?,?,?,?,?,?)",
         "si_u", "hs_1", "unknown_fact",
         "shard layout under 10x write volume is unmeasured", None, "Analyst",
         None, "active", 0, 1_780_000_000.0)

    d = ed.dossier("shard layout")
    assert d["what_it_admits_it_does_not_know"]
    assert "unknown" in d["honest_summary"].lower()


# ── self-audit honesty ───────────────────────────────────────────────────────
def test_self_audit_reports_null_not_zero_for_empty_ratios(db):
    a = ed.self_audit()
    assert a["available"] is True
    # No dissents at all: the resolution rate is undefined, not 0%.
    assert a["dissent_resolution_rate"] is None
    assert a["grading_rate"] is None


def test_self_audit_names_an_unexercised_vindication_loop(db):
    _sql(db, "INSERT INTO minority_positions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         "mp_1", "cs_1", "Skeptic", "FRAGILE", "reason", "dissent",
         1_780_000_000.0, 0, None, 0.0, 0)

    a = ed.self_audit()
    assert a["dissent_resolution_rate"] == 0.0
    assert any("never run" in f for f in a["uncomfortable_findings"])


def test_self_audit_flags_beliefs_that_only_change_by_talking(db):
    _sql(db, "INSERT INTO belief_changes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         "bc_1", "hs_1", "si_1", "a", "b", 0.5, 0.6, "debate", None,
         "Council", 1_780_000_000.0)

    a = ed.self_audit()
    assert a["reality_driven_share"] == 0.0
    assert any("not yet by reality" in f for f in a["uncomfortable_findings"])


def test_self_audit_survives_an_unreadable_database(monkeypatch, tmp_path):
    monkeypatch.setattr(ed, "_DB", tmp_path / "does_not_exist.db")
    a = ed.self_audit()
    assert a["available"] is False and a.get("reason")


# ── the dossier must never fabricate ─────────────────────────────────────────
def test_empty_query_is_refused_rather_than_guessed(db):
    d = ed.dossier("   ")
    assert d["standing"] == "NO_QUERY"


def test_unreadable_database_degrades_honestly(monkeypatch, tmp_path):
    monkeypatch.setattr(ed, "_DB", tmp_path / "nope.db")
    d = ed.dossier("anything at all")
    assert d["standing"] == "UNAVAILABLE"
    assert "cannot reach its own record" in d["honest_summary"]


# ── the instrument must not go quiet on one success (RFC-0001 Q5) ────────────
def test_one_resolved_dissent_does_not_silence_the_finding(db):
    """The First Evidence Review caught this: `if dissents and not resolved`
    meant 1-of-9 reported identically to 9-of-9. A single data point silenced a
    systemic warning."""
    for i in range(9):
        _sql(db, "INSERT INTO minority_positions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
             f"mp_{i}", "cs_1", "Skeptic", "FRAGILE", "r", "dissent",
             1_780_000_000.0, 1 if i == 0 else 0, None, 0.0, 0)

    a = ed.self_audit()
    joined = " ".join(a["uncomfortable_findings"])
    assert "dissent" in joined, "a 1-of-9 gap must still be reported"
    assert "1 of 9" in joined, "the finding must state how far along it is"


def test_a_closed_gap_stops_being_reported(db):
    """Proportional, not permanent: when every dissent is resolved, the finding
    goes away. Otherwise the audit would cry wolf forever."""
    _sql(db, "INSERT INTO minority_positions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         "mp_1", "cs_1", "Skeptic", "FRAGILE", "r", "dissent",
         1_780_000_000.0, 1, 1, 1_780_000_100.0, 1)
    joined = " ".join(ed.self_audit()["uncomfortable_findings"])
    assert "dissent" not in joined


def test_zero_progress_still_says_never(db):
    for i in range(3):
        _sql(db, "INSERT INTO minority_positions VALUES(?,?,?,?,?,?,?,?,?,?,?)",
             f"mp_{i}", "cs_1", "Skeptic", "FRAGILE", "r", "dissent",
             1_780_000_000.0, 0, None, 0.0, 0)
    joined = " ".join(ed.self_audit()["uncomfortable_findings"])
    assert "never run" in joined


def test_one_reality_revision_does_not_silence_the_finding(db):
    for i in range(10):
        _sql(db, "INSERT INTO belief_changes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
             f"bc_{i}", "hs_1", "si_1", "a", "b", 0.5, 0.6, "why", None,
             "Reality (outcome)" if i == 0 else "Council", 1_780_000_000.0)
    joined = " ".join(ed.self_audit()["uncomfortable_findings"])
    assert "deliberation" in joined
    assert "1 of 10" in joined
