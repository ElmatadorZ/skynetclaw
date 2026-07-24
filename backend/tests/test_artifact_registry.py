"""
test_artifact_registry.py — OX-ARTIFACT-1 Artifact Awareness (read-side, real files)
Validations:
  A — create test_report.md → the registry contains it.
  B — "use recent task data" → returns the latest ARTIFACT, not the latest question.
  C — "continue previous report" → returns the report ARTIFACT, not the prompt.
  D — delete the artifact → artifact_exists()=False and the system reports missing.
The registry is a projection over the existing mission ledger — these tests build
a real _MISSION_LEDGER.json + real files in a tmp workspace (no second store).
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import artifact_registry as AR


def _ws(tmp_path, missions):
    (tmp_path / "_MISSION_LEDGER.json").write_text(
        json.dumps({"version": 1, "missions": missions}, ensure_ascii=False),
        encoding="utf-8")
    return str(tmp_path)


def _mk(tmp_path, name, body="# generated\n"):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_classify_types():
    assert AR.classify("out/test_report.md") == "report"
    assert AR.classify("notes/idea.md") == "markdown"
    assert AR.classify("x/sales_dashboard.html") == "dashboard"
    assert AR.classify("x/page.html") == "html"
    assert AR.classify("a/brief.pdf") == "pdf"
    assert AR.classify("a/data.csv") == "csv"
    assert AR.classify("a/blob.json") == "json"


def test_A_registry_contains_created_file(tmp_path):
    """Validation A — create test_report.md; registry contains it."""
    _mk(tmp_path, "test_report.md")
    ws = _ws(tmp_path, [{"id": "m1", "ts": time.time(), "task": "write the report",
                         "status": "COMPLETE", "files": ["test_report.md"]}])
    reg = AR.registry(ws)
    assert len(reg) == 1
    r = reg[0]
    assert r["mission_id"] == "m1"
    assert Path(r["artifact_path"]).name == "test_report.md"
    assert r["artifact_type"] == "report"
    assert r["exists"] is True and r["size"] > 0
    assert AR.artifact_exists("test_report.md", ws) is True


def test_B_recent_data_returns_artifact_not_question(tmp_path):
    """Validation B — 'use recent task data' returns the latest artifact."""
    _mk(tmp_path, "old.csv")
    time.sleep(0.01)
    newest = _mk(tmp_path, "fresh_data.csv")
    ws = _ws(tmp_path, [
        {"id": "m1", "ts": 1000.0, "task": "first question",  "files": ["old.csv"]},
        {"id": "m2", "ts": 2000.0, "task": "second question", "files": ["fresh_data.csv"]},
    ])
    assert AR.references_artifact("use recent task data") is True
    res = AR.resolve_resume("use recent task data", ws)
    assert res and res["artifact"]["artifact_path"].endswith("fresh_data.csv")
    # it is an ARTIFACT record (has a path/type/size), never a mission question
    assert "artifact_type" in res["artifact"] and "question" not in res["artifact"]
    assert AR.latest_artifact(ws)["artifact_path"].endswith("fresh_data.csv")


def test_C_continue_previous_report_returns_report_artifact(tmp_path):
    """Validation C — 'continue previous report' returns the report artifact."""
    _mk(tmp_path, "q3_report.md")
    _mk(tmp_path, "side_notes.md")
    _mk(tmp_path, "dash.html")
    ws = _ws(tmp_path, [
        {"id": "m1", "ts": 1000.0, "task": "quarterly report", "files": ["q3_report.md"]},
        {"id": "m2", "ts": 1500.0, "task": "scratch notes",     "files": ["side_notes.md"]},
        {"id": "m3", "ts": 2000.0, "task": "build dashboard",   "files": ["dash.html"]},
    ])
    res = AR.resolve_resume("continue previous report", ws)
    assert res is not None
    assert res["artifact"]["artifact_type"] == "report"
    assert res["artifact"]["artifact_path"].endswith("q3_report.md")
    assert res["recommend_resume"] is True
    brief = AR.render_brief("continue previous report", ws)
    assert "RESUME this artifact" in brief and "q3_report.md" in brief
    assert "Do NOT search house_state.question" in brief


def test_D_deleted_artifact_reports_missing(tmp_path):
    """Validation D — delete the artifact; artifact_exists()=False, system reports missing."""
    p = _mk(tmp_path, "gone_report.md")
    ws = _ws(tmp_path, [{"id": "m1", "ts": time.time(), "task": "report",
                         "files": ["gone_report.md"]}])
    assert AR.artifact_exists("gone_report.md", ws) is True
    p.unlink()                                   # delete the artifact
    assert AR.artifact_exists("gone_report.md", ws) is False
    res = AR.resolve_resume("continue previous report", ws)
    assert res["exists"] is False and res["recommend_resume"] is False
    assert "MISSING" in res["reason"].upper()
    brief = AR.render_brief("continue previous report", ws)
    assert "MISSING" in brief.upper()


def test_mission_artifacts_and_completion_truth(tmp_path):
    _mk(tmp_path, "a.md"); _mk(tmp_path, "b.pdf")
    ws = _ws(tmp_path, [{"id": "mX", "ts": time.time(), "task": "t",
                         "files": ["a.md", "b.pdf"]}])
    arts = AR.mission_artifacts("mX", ws)
    assert {a["artifact_type"] for a in arts} == {"markdown", "pdf"}
    # CAPABILITY 5 — completion truth
    ok = AR.verify_delivery([str(tmp_path / "a.md")], ws, expected=True)
    assert ok["delivered"] is True and ok["existing"]
    bad = AR.verify_delivery([str(tmp_path / "never.md")], ws, expected=True)
    assert bad["delivered"] is False and bad["missing"]


def test_no_false_resume_when_no_artifacts(tmp_path):
    ws = _ws(tmp_path, [{"id": "m1", "ts": 1.0, "task": "just a question", "files": []}])
    assert AR.resolve_resume("continue previous report", ws) is None
    assert AR.render_brief("continue previous report", ws) == ""
    # an unrelated request does not trigger artifact routing
    assert AR.references_artifact("what is the capital of France") is False
