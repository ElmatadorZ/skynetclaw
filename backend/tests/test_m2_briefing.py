"""M2 — Deliberation Briefing Engine: the Council consumes synthesized briefings,
never raw memories. Tests synthesis, no-raw-sessions, repeated errors, trends, blind
spots, empty history, and the council injection."""
import time, pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import deliberation_briefing as dbrief
import recall_quality as rq
import outcome_tracker as ot
from council_memory import CouncilSession, save_session

DAY = 86400.0
SECTIONS = ("executive_summary", "relevant_historical_cases", "validated_lessons",
            "failed_lessons", "common_patterns", "repeated_errors", "confidence_trends",
            "agent_performance_trends", "recommended_focus_areas", "known_blind_spots")


def _sess(directive, verdict, ts, conf=0.85, participants=None, path=None):
    s = CouncilSession(directive=directive, verdict=verdict, confidence=conf, ts=ts,
                       participants=participants or ["Atlas", "Skeptic"])
    save_session(s, path=path)
    return s.id

def _pred(sid, statement, status, made, metric="BTC", direction="up", inval="below 58k", path=None):
    p = ot.record_prediction(statement, agent="Forecaster", session_id=sid, made_at=made,
                             metric=metric, direction=direction, invalidation=inval,
                             participants=["Forecaster", "Skeptic"], path=path)
    ot.evaluate(p, "180", status, path=path)


def _seed_overconfident_failures(db_path, n=3):
    now = time.time()
    for i in range(n):
        s = _sess(f"go all-in leverage risk-on BTC rally cycle {i}", "YES max leverage BTC moons",
                  now-(40+i)*DAY, conf=0.9, path=db_path)
        _pred(s, f"BTC rallies hard {i}", "incorrect", now-200*DAY, metric="BTC", direction="up", path=db_path)


# ── structure + the no-raw-sessions rule ───────────────────────────────────
def test_all_ten_sections_present(db):
    _seed_overconfident_failures(db)
    b = db_build(db, "all-in leverage risk-on BTC")
    for s in SECTIONS:
        assert s in b, f"missing section {s}"

def db_build(db, q):
    return dbrief.build_brief(q, path=db)

def test_cases_are_refs_not_raw_sessions(db):
    _seed_overconfident_failures(db)
    b = db_build(db, "all-in leverage risk-on BTC")
    for c in b["relevant_historical_cases"]:
        # synthesized reference shape ONLY — never the raw session record
        assert set(c.keys()) == {"ref", "validity", "warning", "gist", "accuracy", "why_relevant"}
        assert "contributions" not in c and "model" not in c and "evidence_summary" not in c


# ── synthesis content ───────────────────────────────────────────────────────
def test_repeated_error_detected(db):
    _seed_overconfident_failures(db, n=3)
    b = db_build(db, "all-in leverage risk-on BTC")
    assert b["repeated_errors"]
    assert b["repeated_errors"][0]["occurrences"] >= 2
    assert "btc" in b["repeated_errors"][0]["error"].lower()

def test_failed_lessons_have_reason(db):
    _seed_overconfident_failures(db)
    b = db_build(db, "all-in leverage risk-on BTC")
    assert b["failed_lessons"] and b["failed_lessons"][0]["why_failed"]

def test_validated_lesson_extracted(db):
    now = time.time()
    s = _sess("hedge tail risk partial allocation discipline", "Phase in keep a hedge",
              now-20*DAY, conf=0.6, path=db)
    _pred(s, "hedged book survives", "correct", now-200*DAY, metric="gold", inval="below 2300", path=db)
    b = db_build(db, "hedge tail risk partial allocation")
    assert b["validated_lessons"] and "hedge" in b["validated_lessons"][0]["lesson"].lower()

def test_overconfidence_trend_detected(db):
    _seed_overconfident_failures(db)
    b = db_build(db, "all-in leverage risk-on BTC")
    ct = b["confidence_trends"]
    assert ct["calibration_gap"] > 0.15 and "OVERCONFIDENT" in ct["note"]

def test_blind_spots_flag_untested(db):
    now = time.time()
    _sess("novel untested structured product idea zzz", "try it", now-10*DAY, path=db)
    b = db_build(db, "novel untested structured product idea zzz")
    assert any("UNTESTED" in s or "untested" in s for s in b["known_blind_spots"])

def test_focus_areas_warn_against_repeated_error(db):
    _seed_overconfident_failures(db)
    b = db_build(db, "all-in leverage risk-on BTC")
    assert any("repeat" in f.lower() for f in b["recommended_focus_areas"])

def test_agent_performance_trends(db):
    _seed_overconfident_failures(db)
    b = db_build(db, "all-in leverage risk-on BTC")
    # Forecaster + Skeptic were attributed the failed predictions → should appear with low skill
    names = {a["agent"] for a in b["agent_performance_trends"]}
    assert names  # at least one rated agent surfaced


# ── empty history: never invent a past ──────────────────────────────────────
def test_empty_history_does_not_invent(db):
    b = db_build(db, "completely unprecedented question xyzzy plugh")
    assert b["n_cases"] == 0
    assert "no history" in b["executive_summary"].lower() or "no prior" in b["executive_summary"].lower()
    assert b["validated_lessons"] == [] and b["failed_lessons"] == []


# ── council injection format ────────────────────────────────────────────────
def test_format_for_council_surfaces_warnings(db):
    _seed_overconfident_failures(db)
    b = db_build(db, "all-in leverage risk-on BTC")
    text = dbrief.format_brief_for_council(b)
    assert "HISTORICAL BRIEF" in text
    assert "Repeated Error" in text or "predicted btc" in text.lower()
    assert "do not repeat disproven" in text.lower()

def test_format_empty_history(db):
    b = db_build(db, "nothing here at all qwerty")
    text = dbrief.format_brief_for_council(b)
    assert "HISTORICAL BRIEF" in text and ("no prior" in text.lower() or "no history" in text.lower())
