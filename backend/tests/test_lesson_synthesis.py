"""
test_lesson_synthesis.py — OX-LEARNING-1 Lesson Synthesis Engine (model-free)
Validations:
  A — repeated successful evidence → success lesson is created.
  B — repeated failure evidence → failure lesson is created.
  C — a new task surfaces relevant lessons before planning.
Plus: the learning-model gates (multiple obs, consistent outcome), registry
persistence, and lesson schema.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import lesson_synthesis as LS

# tool memory shaped like tool_intelligence.load_memory()
_TOOL_MEM = {"tools": {
    "write_file": {"uses": 14, "successes": 12, "total_time": 6.0,
                   "task_types": {"report": {"uses": 14, "successes": 12, "total_time": 6.0}}},
    "pdf_export": {"uses": 10, "successes": 2, "total_time": 9.0,
                   "task_types": {"report": {"uses": 10, "successes": 2, "total_time": 9.0}}},
    "rare_tool":  {"uses": 1, "successes": 1, "total_time": 0.1, "task_types": {}},
}}

# artifact records shaped like artifact_registry.registry()
_ARTIFACTS = (
    [{"artifact_type": "html", "exists": True,  "mission_id": f"h{i}"} for i in range(12)]
    + [{"artifact_type": "html", "exists": False, "mission_id": "h12"}, {"artifact_type": "html", "exists": False, "mission_id": "h13"}]
    + [{"artifact_type": "pdf", "exists": False, "mission_id": f"p{i}"} for i in range(8)]
    + [{"artifact_type": "pdf", "exists": True,  "mission_id": f"p{i}"} for i in range(2)]
)


def _syn(**kw):
    base = dict(tool_mem=_TOOL_MEM, missions=[], artifacts=_ARTIFACTS, runs=[])
    base.update(kw)
    return LS.synthesize(**base)


def test_A_success_lesson_created():
    """A — write_file 12/14 + html 12/14 → success lessons."""
    lessons = _syn()
    wins = [l for l in lessons if l["polarity"] == "success"]
    assert any('"write_file" is reliable' in l["lesson"] for l in wins)
    assert any("HTML artifacts are reliably delivered" in l["lesson"] for l in wins)
    wf = next(l for l in wins if '"write_file"' in l["lesson"])
    # schema
    for k in ("lesson", "confidence", "evidence_count", "source", "category"):
        assert k in wf
    assert wf["evidence_count"] == 14
    assert 0.8 <= wf["confidence"] <= 0.9          # 12/14
    assert "tool_history" in wf["source"] and wf["category"] == "tool"


def test_B_failure_lesson_created():
    """B — pdf_export 8/10 fail + pdf artifacts 8/10 missing → failure lessons."""
    lessons = _syn()
    fails = [l for l in lessons if l["polarity"] == "failure"]
    assert any("PDF export is unstable" in l["lesson"] for l in fails)
    assert any('"pdf_export" repeatedly fails' in l["lesson"] for l in fails)
    pe = next(l for l in fails if "PDF export is unstable" in l["lesson"])
    assert pe["evidence_count"] == 10
    assert pe["confidence"] >= 0.7                 # failure confidence = 8/10
    assert pe["category"] == "artifact"


def test_learning_model_gates():
    """Multiple observations required: a 1/1 tool yields no lesson."""
    lessons = _syn()
    assert not any("rare_tool" in l["lesson"] for l in lessons)
    # inconsistent outcome (50/50) yields no lesson
    mem = {"tools": {"flaky": {"uses": 10, "successes": 5, "total_time": 1.0, "task_types": {}}}}
    assert not any("flaky" in l["lesson"] for l in LS.synthesize(
        tool_mem=mem, missions=[], artifacts=[], runs=[]))


def test_mission_and_recovery_patterns():
    missions = [{"task": "generate a sales report", "status": "COMPLETE"} for _ in range(4)]
    runs = [{"task": "scrape the site", "status": "PROBLEM", "summary": ""} for _ in range(3)]
    lessons = LS.synthesize(tool_mem={"tools": {}}, missions=missions, artifacts=[], runs=runs)
    assert any(l["category"] == "execution" and l["polarity"] == "success" for l in lessons)
    assert any(l["category"] == "recovery" for l in lessons)


def test_C_recall_surfaces_relevant_lessons():
    """C — a new report task surfaces the report-relevant lessons first."""
    lessons = _syn()
    surfaced = LS.recall("create a new HTML report for Q3", lessons=lessons, limit=5)
    assert surfaced, "lessons should surface before planning"
    joined = " ".join(l["lesson"] for l in surfaced)
    assert "write_file" in joined or "HTML" in joined
    brief = LS.render_brief(surfaced)
    assert "LESSONS" in brief and "BEFORE planning" in brief


def test_registry_persist_and_load(tmp_path):
    """The Lesson Registry is stored separately from raw events."""
    p = tmp_path / "lessons.json"
    lessons = LS.refresh(workspace=None, runs=[], path=p,
                         tool_mem=_TOOL_MEM, missions=[], artifacts=_ARTIFACTS)
    assert p.exists() and lessons
    loaded = LS.load(p)
    assert len(loaded) == len(lessons)
    assert all("lesson" in l and "confidence" in l for l in loaded)


def test_recall_empty_is_safe():
    assert LS.recall("anything", lessons=[]) == []
    assert LS.render_brief([]) == ""
