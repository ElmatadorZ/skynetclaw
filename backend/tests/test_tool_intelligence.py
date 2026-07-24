"""
test_tool_intelligence.py — OX-SKILL-1 Tool Intelligence (model-free)
Covers the three spec validations: registry records usage (A), prior winner is
recommended (B), and 'continue previous' selects artifact recall before planning
(C). Plus registry shape, classification, and cold-start safety.
"""
from __future__ import annotations
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tool_intelligence as TI


def _isolate(tmp_path):
    TI._STORE = tmp_path / "tool_memory.json"
    return TI._STORE


_SCHEMAS = [
    {"function": {"name": "write_file", "description": "Write/overwrite content to a file",
                  "parameters": {"properties": {"path": {}, "content": {}}, "required": ["path", "content"]}}},
    {"function": {"name": "web_search", "description": "Search the web via DuckDuckGo for any query",
                  "parameters": {"properties": {"query": {}, "max_results": {}}, "required": ["query"]}}},
    {"function": {"name": "read_file", "description": "Read a local file",
                  "parameters": {"properties": {"path": {}}, "required": ["path"]}}},
]
_CANDS = [s["function"]["name"] for s in _SCHEMAS]


def test_classify_task():
    assert TI.classify_task("Generate a PDF report") == "report"
    assert TI.classify_task("research the gold price news") == "research"
    assert TI.classify_task("fix the python script") == "code"
    assert TI.classify_task("write an obsidian note") == "obsidian"
    assert TI.classify_task("hello there") == "general"


def test_registry_shape(tmp_path):
    _isolate(tmp_path)
    reg = TI.build_registry(_SCHEMAS)
    wf = next(r for r in reg if r["tool"] == "write_file")
    # the six spec fields are all present
    for f in ("tool", "purpose", "inputs", "outputs", "failure_modes", "success_rate"):
        assert f in wf
    assert "*path" in wf["inputs"]            # required inputs are marked
    assert wf["success_rate"] is None          # nothing learned yet


def test_A_registry_records_usage(tmp_path):
    """Test A — after a report run uses tools, the registry records usage."""
    _isolate(tmp_path)
    tt = TI.classify_task("Generate a market report and save it as a PDF")
    TI.record(tt, "web_search", True, 2.1)
    TI.record(tt, "write_file", True, 0.4)
    TI.record(tt, "write_file", True, 0.5)
    reg = TI.build_registry(_SCHEMAS)
    wf = next(r for r in reg if r["tool"] == "write_file")
    assert wf["uses"] == 2 and wf["success_rate"] == 1.0
    assert TI.success_rate("web_search") == 1.0
    assert TI._STORE.exists() and TI._STORE.stat().st_size > 0


def test_B_prior_tool_is_recommended(tmp_path):
    """Test B — a second report suggests the previously successful tool."""
    _isolate(tmp_path)
    tt = TI.classify_task("Generate a market report and save it as a PDF")
    TI.record(tt, "web_search", True, 2.1)
    TI.record(tt, "write_file", True, 0.4)
    TI.record(tt, "write_file", True, 0.5)
    rec = TI.recommend(TI.classify_task("Generate another sales report"), _CANDS)
    assert rec["prior_solution"]["tool"] == "write_file"
    assert rec["safest"]["tool"] == "write_file"
    assert "SOLVED THIS BEFORE: write_file" in TI.render_brief("Generate another sales report", _CANDS)


def test_resume_detection_removed(tmp_path):
    """OX-INTENT-1 — Tool Intelligence no longer performs resume detection;
    that responsibility moved to the Artifact Registry (single source of truth)."""
    _isolate(tmp_path)
    assert not hasattr(TI, "detect_resume")
    # render_brief no longer emits a resume block
    brief = TI.render_brief("continue previous report", _CANDS)
    assert "RESUME AVAILABLE" not in brief


def test_brief_consumes_intent_task_type(tmp_path):
    """OX-INTENT-1 — render_brief uses intent['task_type'] instead of
    re-classifying the raw text."""
    _isolate(tmp_path)
    tt = TI.classify_task("Generate a report")
    TI.record(tt, "write_file", True, 0.4)
    # an intent that declares the task-type drives the recommendation
    brief = TI.render_brief("anything at all", _CANDS, intent={"task_type": tt})
    assert "SOLVED THIS BEFORE: write_file" in brief


def test_cold_start_brief_is_safe(tmp_path):
    """With no memory, the brief still renders the routing doctrine."""
    _isolate(tmp_path)
    brief = TI.render_brief("do something new", _CANDS)
    assert "ROUTING DOCTRINE" in brief
    assert "No prior tool evidence" in brief
    rec = TI.recommend("general", _CANDS)
    assert rec["prior_solution"] is None and rec["evidence"] == 0
