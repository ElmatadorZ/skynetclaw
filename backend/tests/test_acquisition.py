"""
test_acquisition.py — OX-ACQUISITION-1 Knowledge Acquisition Protocol
  A — unknown PDF generation  → Documentation in the acquisition plan
  B — missing API knowledge   → Documentation + GitHub attempted
  C — known task              → no acquisition gap created
  D — failed acquisition      → clarification allowed
  E — successful acquisition  → validates, execution proceeds (no clarify)
Plus schema, source hierarchy ordering, records, and metrics.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import acquisition as AQ

_TOOLS = ["list_files", "find_files", "read_file", "grep_search", "write_file",
          "web_search", "http_request", "search_obsidian", "read_obsidian_note",
          "shell_command", "recall_archive", "query_learning", "ask_user_options"]
# Portable: the repository root, whatever machine this runs on.
_WS = str(Path(__file__).resolve().parents[2])


def _gaps(task):
    return AQ.detect_gaps(task, available_tools=_TOOLS, workspace=_WS, vault="C:/repo/vault")


def test_gap_schema_and_hierarchy():
    assert AQ.SOURCE_HIERARCHY[0] == "existing_code"
    assert AQ.SOURCE_HIERARCHY[-1] == "acquisition_attempt"
    g = _gaps("figure out how to generate a PDF document")
    assert g, "explicit learning need should produce a KNOWABLE gap"
    gap = g[0]
    for k in ("gap_id", "task", "knowledge_needed", "source_candidates", "status"):
        assert k in gap
    assert gap["status"] == "pending"


def test_A_unknown_pdf_generation_searches_documentation():
    g = _gaps("figure out how to generate a PDF document")
    plan = AQ.plan_acquisition(g[0])
    assert "documentation" in plan["source_priority"]
    assert plan["acquisition_goal"].startswith("Acquire:")
    assert plan["validation_method"] and plan["success_criteria"]


def test_B_missing_api_knowledge_documentation_and_github():
    g = _gaps("integrate the Stripe API into checkout")
    assert g
    order = AQ.attempt_order(g[0])
    assert "documentation" in order and "github" in order
    # hierarchy ordering: documentation (6) precedes github (7)
    assert order.index("documentation") < order.index("github")


def test_C_known_task_no_acquisition():
    g = _gaps(f"list the files in {_WS} and read main.py")
    assert g == []                       # KNOWN — nothing to acquire


def test_D_failed_acquisition_allows_clarification(tmp_path):
    g = _gaps("integrate the Stripe API")[0]
    # before any attempt: must search first (sources exist) → no clarify
    assert AQ.should_clarify(g, record=None) is False
    rec = AQ.record(g, sources_checked=["documentation", "github"],
                    sources_successful=[], knowledge_found=False,
                    execution_used=False, path=tmp_path / "a.json")
    assert AQ.should_clarify(g, rec) is True          # searched, found nothing → ask allowed
    assert AQ.validate(rec) is False


def test_E_successful_acquisition_proceeds(tmp_path):
    g = _gaps("integrate the Stripe API")[0]
    rec = AQ.record(g, sources_checked=["documentation"],
                    sources_successful=["documentation"], knowledge_found=True,
                    execution_used=True, path=tmp_path / "a.json")
    assert AQ.validate(rec) is True                   # evidence + source + execution-ref
    assert AQ.should_clarify(g, rec) is False          # acquired → no clarification


def test_no_reachable_source_asks_immediately():
    # a gap whose only candidates aren't searchable → clarify is the only move
    fake_gap = {"gap_id": "g", "knowledge_needed": "operator preference",
                "source_candidates": [], "gap_type": "preference"}
    assert AQ.should_clarify(fake_gap, record=None) is True


def test_map_tools_to_sources():
    s = AQ.map_tools_to_sources(["grep_search", "web_search", "http_request", "write_file"])
    assert "existing_code" in s and "web_search" in s and "documentation" in s
    assert "write_file" not in str(s)                 # write_file is not a search source


def test_metrics(tmp_path):
    p = tmp_path / "a.json"
    ga = _gaps("integrate the Stripe API")[0]
    AQ.record(ga, ["documentation"], ["documentation"], knowledge_found=True, execution_used=True, path=p)
    AQ.record(ga, ["github", "web_search"], [], knowledge_found=False, path=p)
    AQ.record(ga, [], [], knowledge_found=False, path=p)          # no attempt
    m = AQ.metrics(path=p)
    assert m["total_gaps"] == 3
    assert m["acquisition_attempt_rate"] == round(2/3, 3)        # 2 of 3 searched
    assert m["acquisition_success_rate"] == 0.5                  # 1 of 2 attempts found
    assert m["top_successful_sources"][0]["source"] == "documentation"
