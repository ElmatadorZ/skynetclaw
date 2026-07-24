"""
test_house_guard.py — OX-HOUSE-GUARD-1 read-side protection
House Mind must surface the highest-quality active mission and never an
error-generated / punctuation-only / zero-information objective — even if those
rows still exist (newer) in the DB.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import runtime_integrity as RI
import house_state as HS


# ── predicate unit tests ──────────────────────────────────────────────────────
def test_is_punctuation_only():
    assert RI.is_punctuation_only("...")
    assert RI.is_punctuation_only(".....")
    assert RI.is_punctuation_only("—  ·· …")
    assert not RI.is_punctuation_only("หุ้น")          # Thai letters = content
    assert not RI.is_punctuation_only("plan v2")
    assert not RI.is_punctuation_only("2026-06-15")    # digits = content


def test_is_displayable_objective():
    assert RI.is_displayable_objective("Build the Q3 report")
    assert not RI.is_displayable_objective("")
    assert not RI.is_displayable_objective("LLM reflection phase failed")
    assert not RI.is_displayable_objective("....")


def test_valid_mission_row():
    assert RI.valid_mission_row("Build report", 0.85, 0)        # confidence carries it
    assert RI.valid_mission_row("Build report", 0.0, 3)         # cognitive content carries it
    assert not RI.valid_mission_row("Build report", 0.0, 0)     # zero-information
    assert not RI.valid_mission_row("LLM reflection phase failed", 0.9, 5)  # error text
    assert not RI.valid_mission_row("...", 0.9, 5)              # punctuation-only


# ── current() guard (the core requirement) ────────────────────────────────────
def _p(tmp_path):
    return str(tmp_path / "hs.db")


def test_garbage_newer_than_valid_selects_valid(tmp_path):
    """A garbage row created AFTER a valid one must not win — current() returns
    the valid (older) mission."""
    p = _p(tmp_path)
    valid = HS.open_state("Build the Q3 revenue report", path=p, bootstrap=False, reuse=False)
    HS.add_known_fact(valid, "Q3 revenue was 12.4M", path=p)     # gives it content
    time.sleep(0.02)
    HS.open_state("LLM reflection phase failed — no learnings extracted",
                  path=p, bootstrap=False, reuse=False)          # newer, error-generated
    cur = HS.current(p)
    assert cur is not None and cur["id"] == valid


def test_valid_newest_is_selected(tmp_path):
    p = _p(tmp_path)
    HS.open_state("old mission", path=p, bootstrap=False, reuse=False)
    time.sleep(0.02)
    newest = HS.open_state("Summarize the AAPL analysis", path=p, bootstrap=False, reuse=False)
    HS.add_belief(newest, "AAPL looks strong", confidence=0.8, path=p)
    cur = HS.current(p)
    assert cur is not None and cur["id"] == newest


def test_all_garbage_yields_blank(tmp_path):
    """Only garbage open rows → House Mind is honestly blank, not garbage."""
    p = _p(tmp_path)
    HS.open_state("...", path=p, bootstrap=False, reuse=False)
    time.sleep(0.01)
    HS.open_state("JSON parse failed", path=p, bootstrap=False, reuse=False)
    time.sleep(0.01)
    HS.open_state("zero info mission", path=p, bootstrap=False, reuse=False)  # 0 conf, no items
    assert HS.current(p) is None


def test_punctuation_and_zero_info_skipped_for_next_valid(tmp_path):
    p = _p(tmp_path)
    good = HS.open_state("Compare SET vs S&P500", path=p, bootstrap=False, reuse=False)
    HS.add_known_fact(good, "SET YTD +3%", path=p)
    time.sleep(0.02)
    HS.open_state("....", path=p, bootstrap=False, reuse=False)               # newer garbage
    time.sleep(0.01)
    HS.open_state("untitled", path=p, bootstrap=False, reuse=False)           # newer zero-info
    cur = HS.current(p)
    assert cur is not None and cur["id"] == good


# ── mission_command active view excludes garbage ──────────────────────────────
def test_mission_command_active_excludes_garbage(tmp_path):
    p = _p(tmp_path)
    valid = HS.open_state("Build the dashboard", path=p, bootstrap=False, reuse=False)
    HS.add_known_fact(valid, "uses Streamlit", path=p)
    HS.open_state("LLM reflection phase failed", path=p, bootstrap=False, reuse=False)
    HS.open_state("...", path=p, bootstrap=False, reuse=False)
    import mission_command as MC
    snap = MC.snapshot(path=p)
    active_objs = [m["objective"] for m in snap["active"] if m.get("kind") == "council"]
    assert "Build the dashboard" in active_objs
    assert not any("reflection phase failed" in o for o in active_objs)
    assert "..." not in active_objs
