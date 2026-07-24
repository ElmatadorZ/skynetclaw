"""
test_intent.py — OX-INTENT-1 Unified Intent Protocol (model-free)
Validations:
  A — "continue previous report": one intent object, consumed by Artifact
      Registry + Tool Intelligence + Knowledge Seeking; no duplicate classification.
  B — "use recent task data": single intent, artifact lookup only, no planning.
  C — "integrate stripe api": intent indicates knowledge acquisition, shared.
Plus: resume is owned solely by the Artifact Registry; the artifact/knowledge
overlap is suppressed; Execution Recall enriches without redefining.
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import intent as INTENT
import artifact_registry as AR
import tool_intelligence as TI
import knowledge_seeking as KS

_TOOLS = ["list_files", "find_files", "read_file", "grep_search", "write_file",
          "web_search", "http_request", "search_obsidian", "read_obsidian_note",
          "shell_command", "recall_archive", "query_learning", "ask_user_options"]


def _ws(tmp_path, missions):
    (tmp_path / "_MISSION_LEDGER.json").write_text(
        json.dumps({"version": 1, "missions": missions}, ensure_ascii=False), encoding="utf-8")
    return str(tmp_path)


def _mk(tmp_path, name, body="# generated\n"):
    (tmp_path / name).write_text(body, encoding="utf-8")


def test_A_continue_previous_report(tmp_path):
    """A — one intent; all three consumers read it; resume owned by Registry."""
    _mk(tmp_path, "q3_report.md")
    ws = _ws(tmp_path, [{"id": "m1", "ts": time.time(), "task": "quarterly report",
                         "files": ["q3_report.md"]}])
    it = INTENT.interpret("continue previous report", available_tools=_TOOLS, workspace=ws)
    # interpreted ONCE → canonical fields
    assert it["intent"] == "resume_artifact"
    assert it["requires_artifact"] is True
    assert it["requires_knowledge_search"] is False
    assert it["requires_clarification"] is False
    assert it["target"] == "q3_report"
    assert it["confidence"] >= 0.9
    # the resolved artifact is carried so consumers never recompute
    assert it["artifact"] and it["artifact"]["artifact"]["artifact_path"].endswith("q3_report.md")

    # CONSUMER: Artifact Registry renders from the intent (no re-classification)
    ar_brief = AR.render_brief_from_intent(it)
    assert "RESUME this artifact" in ar_brief and "q3_report.md" in ar_brief
    # CONSUMER: Tool Intelligence consumes intent, no resume block
    ti_brief = TI.render_brief("continue previous report", _TOOLS, intent=it)
    assert "RESUME AVAILABLE" not in ti_brief
    # CONSUMER: Knowledge Seeking suppresses the artifact overlap (no re-routing)
    plan = it["knowledge_plan"]
    assert all(g.get("source") != "artifacts" for g in plan.get("knowable", []) + plan.get("unknown", []))


def test_B_use_recent_task_data(tmp_path):
    """B — single intent, artifact lookup only, no planning / knowledge search."""
    _mk(tmp_path, "fresh.csv")
    ws = _ws(tmp_path, [{"id": "m2", "ts": time.time(), "task": "export data",
                         "files": ["fresh.csv"]}])
    it = INTENT.interpret("use recent task data", available_tools=_TOOLS, workspace=ws)
    assert it["intent"] == "use_recent_artifact"
    assert it["requires_artifact"] is True
    assert it["requires_knowledge_search"] is False
    assert it["artifact"]["artifact"]["artifact_path"].endswith("fresh.csv")


def test_C_integrate_stripe_api(tmp_path):
    """C — intent indicates knowledge acquisition, shared across consumers."""
    ws = _ws(tmp_path, [])
    it = INTENT.interpret("integrate stripe api", available_tools=_TOOLS, workspace=ws)
    assert it["intent"] == "acquire_knowledge"
    assert it["requires_knowledge_search"] is True
    assert it["requires_artifact"] is False
    # shared plan present for the Knowledge Seeking consumer
    assert it["knowledge_plan"] and it["knowledge_plan"]["knowable"]
    ks_brief = KS.render_brief(it["knowledge_plan"])
    assert "KNOWLEDGE SEEKING" in ks_brief


def test_enrich_does_not_redefine(tmp_path):
    """Execution Recall MAY enrich but MUST NOT redefine the intent."""
    ws = _ws(tmp_path, [])
    it = INTENT.interpret("integrate stripe api", available_tools=_TOOLS, workspace=ws)
    before = it["intent"]
    INTENT.enrich(it, {"unknown_tools": ["frobnicate"], "prior_dead_ends": [{}], "similar_count": 2})
    assert it["intent"] == before                      # canonical decision unchanged
    assert it["recall"]["unknown_tools"] == ["frobnicate"]
    assert it["recall"]["similar_count"] == 2


def test_single_interpretation_no_duplicate_classification(tmp_path, monkeypatch):
    """The detectors are each invoked at most once per interpret() call."""
    _mk(tmp_path, "r.md")
    ws = _ws(tmp_path, [{"id": "m1", "ts": time.time(), "task": "report", "files": ["r.md"]}])
    calls = {"classify": 0, "references": 0, "plan": 0}
    import tool_intelligence, artifact_registry, knowledge_seeking
    orig_c, orig_r, orig_p = (tool_intelligence.classify_task,
                              artifact_registry.references_artifact, knowledge_seeking.plan)
    monkeypatch.setattr(tool_intelligence, "classify_task",
                        lambda *a, **k: (calls.__setitem__("classify", calls["classify"] + 1), orig_c(*a, **k))[1])
    monkeypatch.setattr(artifact_registry, "references_artifact",
                        lambda *a, **k: (calls.__setitem__("references", calls["references"] + 1), orig_r(*a, **k))[1])
    monkeypatch.setattr(knowledge_seeking, "plan",
                        lambda *a, **k: (calls.__setitem__("plan", calls["plan"] + 1), orig_p(*a, **k))[1])
    INTENT.interpret("continue previous report", available_tools=_TOOLS, workspace=ws)
    assert calls == {"classify": 1, "references": 1, "plan": 1}
