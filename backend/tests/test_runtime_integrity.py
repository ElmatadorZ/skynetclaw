"""
test_runtime_integrity.py — OX-STABILITY-1 Runtime Integrity Protocol
Phase 1 — orphan run recovery (Validation A)
Phase 2 — mission-identity sanitization (Validation B)
Phase 3 — house_state lifecycle / truthful active count (Validation C)
Phase 4 — learning input integrity (Validation D)
"""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import runtime_integrity as RI
import mission_identity as MI


# ── PHASE 2 — error/identity boundary ─────────────────────────────────────────
def test_is_error_text():
    assert RI.is_error_text("LLM reflection phase failed — no learnings extracted")
    assert RI.is_error_text("JSON parse failed")
    assert RI.is_error_text("tool execution failed")
    assert RI.is_error_text('Traceback (most recent call last):\n  File "x.py", line 3')
    assert not RI.is_error_text("Summarize AAPL/TSLA/MSFT and export a PDF")
    assert not RI.is_error_text("delete the old report")


def test_B_error_strings_never_become_identities():
    """Validation B — injected error strings do not become mission objectives."""
    for bad in ("LLM reflection phase failed",
                "JSON parse failed",
                "tool execution failed — no learnings extracted",
                "อะไรคือปะญหาของการ  LLM reflection phase failed — no learnings extracted"):
        assert MI.clean_identity(bad) == "", f"leaked: {bad!r}"
    # a real directive still passes through untouched
    assert MI.clean_identity("Summarize the Q3 report") == "Summarize the Q3 report"


def test_clean_outputs_drops_error_lessons():
    items = ["LLM reflection phase failed — no learnings extracted",
             "Prefer CoinGecko fallback for gold price", ""]
    assert RI.clean_outputs(items) == ["Prefer CoinGecko fallback for gold price"]


def test_reflect_failure_emits_no_lesson():
    """The source fix: a failed reflection contributes NO lesson (error stays in
    the diagnostic channel only)."""
    import agentic_workflow as AW
    r = AW.Reflection(what_worked=[], what_failed=["reflection_phase_error: model returned no valid JSON"],
                      lessons=[], genome_proposals=[], improvement_targets=[], raw_response="")
    assert r.lessons == []
    assert all(not RI.is_error_text(x) for x in r.lessons)


# ── PHASE 4 — learning input integrity (Validation D) ─────────────────────────
def test_valid_for_learning():
    assert RI.valid_for_learning({"status": "TASK_COMPLETE", "task": "build report"})
    assert RI.valid_for_learning({"status": "failed", "task": "scrape site"})   # real failure = valid
    assert not RI.valid_for_learning({"status": "running", "task": "x"})        # orphan
    assert not RI.valid_for_learning({"status": "interrupted", "task": "x"})    # reconciled orphan
    assert not RI.valid_for_learning({"status": "cancelled", "task": "x"})
    # error-generated mission, even if 'complete', is corrupt history
    assert not RI.valid_for_learning({"status": "TASK_COMPLETE",
                                      "task": "LLM reflection phase failed"})


def test_D_corrupted_history_ignored_by_filters():
    """Validation D — inject corrupted history; filters drop it."""
    runs = [
        {"status": "TASK_COMPLETE", "task": "good run"},
        {"status": "running", "task": "orphan"},
        {"status": "interrupted", "task": "reconciled orphan"},
        {"status": "TASK_COMPLETE", "task": "tool execution failed"},   # error-generated
    ]
    valid = RI.filter_valid_runs(runs)
    assert len(valid) == 1 and valid[0]["task"] == "good run"
    missions = [{"task": "real mission", "files": ["a.md"]},
                {"task": "LLM reflection phase failed", "files": []}]
    vm = RI.filter_valid_missions(missions)
    assert len(vm) == 1 and vm[0]["task"] == "real mission"


def test_lesson_synthesis_ignores_corrupted_runs():
    import lesson_synthesis as LS
    runs = [{"task": "scrape", "status": "running", "summary": ""} for _ in range(4)]
    # 4 orphaned 'running' runs must NOT produce a recovery lesson
    lessons = LS.synthesize(tool_mem={"tools": {}}, missions=[], artifacts=[], runs=runs)
    assert lessons == []


# ── PHASE 1 — orphan run recovery (Validation A) ──────────────────────────────
def _db(tmp_path):
    import openclaw_port_tier2 as OCP
    return OCP.AgentRunsDB(tmp_path / "runs.db")


def test_A_normal_completion_not_clobbered(tmp_path):
    db = _db(tmp_path)
    db.start_run("r1", "task", "m")
    db.end_run("r1", "TASK_COMPLETE")
    # catch-all must NOT overwrite a real terminal status
    changed = db.end_run_if_open("r1", "interrupted")
    assert changed is False
    assert db.get("r1")["status"] == "TASK_COMPLETE"


def test_A_disconnect_path_closes_run(tmp_path):
    db = _db(tmp_path)
    db.start_run("r2", "task", "m")
    # simulate client-disconnect / GeneratorExit: only the finally catch-all runs
    changed = db.end_run_if_open("r2", "interrupted")
    assert changed is True
    assert db.get("r2")["status"] == "interrupted"


def test_A_startup_reconciles_orphans(tmp_path):
    db = _db(tmp_path)
    db.start_run("done", "t", "m"); db.end_run("done", "TASK_COMPLETE")
    db.start_run("orphan1", "t", "m")
    db.start_run("orphan2", "t", "m")
    # reconcile everything still 'running' (max_age=-1 → cutoff in the future)
    n = db.reconcile_stale_runs(max_age_seconds=-1)
    assert n == 2
    assert db.get("orphan1")["status"] == "interrupted"
    assert db.get("orphan2")["status"] == "interrupted"
    assert db.get("done")["status"] == "TASK_COMPLETE"     # terminal untouched
    # no 'running' rows remain
    assert all(r["status"] != "running" for r in db.recent(limit=10))


# ── PHASE 3 — house_state lifecycle (Validation C) ────────────────────────────
def test_C_active_count_reflects_reality(tmp_path):
    import house_state as HS
    p = str(tmp_path / "hs.db")
    ids = [HS.open_state(f"mission {i}", path=p, bootstrap=False, reuse=False) for i in range(100)]
    assert HS.active_count(p) == 100
    # complete 90, fail 10
    for sid in ids[:90]:
        HS.close_state(sid, path=p, status="completed")
    for sid in ids[90:]:
        HS.close_state(sid, path=p, status="failed")
    assert HS.active_count(p) == 0
    counts = HS.lifecycle_counts(p)
    assert counts.get("completed") == 90 and counts.get("failed") == 10


def test_C_archive_stale_ages_out_open(tmp_path):
    import house_state as HS
    p = str(tmp_path / "hs2.db")
    HS.open_state("stale mission", path=p, bootstrap=False)
    assert HS.active_count(p) == 1
    n = HS.archive_stale(max_age_seconds=-1, path=p)   # cutoff in the future → archive all open
    assert n == 1
    assert HS.active_count(p) == 0
