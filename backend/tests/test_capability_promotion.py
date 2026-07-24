"""
test_capability_promotion.py — OX-CAPABILITY-1 Capability Promotion (model-free)
Validations:
  A — repeated report lessons → capability creation.
  B — repeated failure lessons → warning capability creation.
  C — a new task recalls relevant capabilities before planning.
Plus: the promotion rules (confidence/evidence/stability gates), schema,
registry persistence, and "capabilities preferred over raw lessons".
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import capability_promotion as CP

# lessons shaped like lesson_synthesis output
_LESSONS = [
    {"id": "L_html", "lesson": "HTML artifacts are reliably delivered (12/14 exist).",
     "confidence": 0.86, "evidence_count": 14, "source": ["artifact_history"],
     "category": "artifact", "polarity": "success", "context": {"artifact_type": "html"}},
    {"id": "L_wf", "lesson": '"write_file" is reliable for report tasks (12/14).',
     "confidence": 0.86, "evidence_count": 14, "source": ["tool_history"],
     "category": "tool", "polarity": "success", "context": {"tool": "write_file", "task_type": "report"}},
    {"id": "L_rf", "lesson": '"read_file" is reliable for report tasks (10/11).',
     "confidence": 0.9, "evidence_count": 11, "source": ["tool_history"],
     "category": "tool", "polarity": "success", "context": {"tool": "read_file", "task_type": "report"}},
    {"id": "L_ws", "lesson": '"web_search" is reliable for research tasks (8/9).',
     "confidence": 0.89, "evidence_count": 9, "source": ["tool_history"],
     "category": "knowledge", "polarity": "success", "context": {"tool": "web_search", "task_type": "research"}},
    {"id": "L_pdf", "lesson": "PDF export is unstable — 8/10 produced no artifact.",
     "confidence": 0.8, "evidence_count": 10, "source": ["artifact_history"],
     "category": "artifact", "polarity": "failure", "context": {"artifact_type": "pdf"}},
    {"id": "L_pdftool", "lesson": '"pdf_export" repeatedly fails (8/10).',
     "confidence": 0.8, "evidence_count": 10, "source": ["tool_history"],
     "category": "tool", "polarity": "failure", "context": {"tool": "pdf_export", "task_type": "report"}},
    # under-evidenced lesson — must NOT promote
    {"id": "L_weak", "lesson": "csv artifacts ok (3/3).", "confidence": 1.0,
     "evidence_count": 3, "source": ["artifact_history"], "category": "artifact",
     "polarity": "success", "context": {"artifact_type": "csv"}},
]


def test_A_report_capability_created():
    """A — repeated report/HTML success lessons → 'HTML Report Builder' capability."""
    caps = CP.promote(_LESSONS)
    html = next((c for c in caps if c["name"] == "HTML REPORT Builder"), None) \
        or next((c for c in caps if "HTML" in c["name"] and c["polarity"] == "capability"), None)
    assert html is not None
    assert html["type"] == "reporting" and html["polarity"] == "capability"
    # schema
    for k in ("name", "confidence", "evidence_count", "derived_from", "recommended_tools"):
        assert k in html
    assert html["evidence_count"] == 14 and html["confidence"] >= 0.85
    # recommended tools were pulled from the report-domain tool lessons
    assert "write_file" in html["recommended_tools"] and "read_file" in html["recommended_tools"]
    assert "L_html" in html["derived_from"]


def test_B_warning_capability_created():
    """B — repeated PDF failure → warning capabilities."""
    caps = CP.promote(_LESSONS)
    warns = [c for c in caps if c["polarity"] == "warning"]
    assert any("PDF" in c["name"] and "UNSTABLE" in c["name"] for c in warns)
    assert any("pdf_export" in c["name"] for c in warns)
    pdf = next(c for c in warns if "UNSTABLE" in c["name"])
    assert pdf["evidence_count"] == 10 and pdf["confidence"] >= 0.7


def test_promotion_gates():
    """Under-evidenced / unstable lessons do not promote."""
    caps = CP.promote(_LESSONS)
    # csv (n=3) is below EVIDENCE_THRESH -> no capability
    assert not any("CSV" in c["name"] for c in caps)
    # web_search n=9 (>=5 but <10 stable bar) is NOT stable on first sight -> held
    assert not any(c["name"] == "Knowledge Acquisition" for c in caps)
    # ...but if it was promoted before (prior), stability is satisfied
    caps2 = CP.promote(_LESSONS, prior_names={"Knowledge Acquisition"})
    assert any(c["name"] == "Knowledge Acquisition" for c in caps2)


def test_C_recall_prefers_relevant_capabilities():
    """C — a new report task recalls the report capability before planning."""
    caps = CP.promote(_LESSONS)
    surfaced = CP.recall("create a new HTML report for Q3", capabilities=caps, limit=4)
    assert surfaced
    assert any("HTML" in c["name"] for c in surfaced)
    brief = CP.render_brief(surfaced)
    assert "CAPABILITIES" in brief and "PREFER these over raw lessons" in brief


def test_registry_persist_and_load(tmp_path):
    p = tmp_path / "capabilities.json"
    caps = CP.refresh(lessons=_LESSONS, path=p)
    assert p.exists() and caps
    loaded = CP.load(p)
    assert len(loaded) == len(caps)


def test_stability_via_prior_snapshot(tmp_path):
    """Stability over time: a capability promoted once stays promoted next refresh
    even if its evidence is below the first-sight bar."""
    p = tmp_path / "capabilities.json"
    moderate = [{"id": "L_x", "lesson": "research missions usually complete (6/7).",
                 "confidence": 0.85, "evidence_count": 7, "source": ["mission_history"],
                 "category": "execution", "polarity": "success", "context": {"task_type": "research"}}]
    first = CP.refresh(lessons=moderate, path=p)
    assert not first                       # n=7 < STABLE_EVIDENCE, never seen -> held
    # seed the registry as if it had been promoted, then refresh again
    p.write_text('{"version":1,"capabilities":[{"name":"Research Execution"}]}', encoding="utf-8")
    second = CP.refresh(lessons=moderate, path=p)
    assert any(c["name"] == "Research Execution" for c in second)


def test_recall_empty_is_safe():
    assert CP.recall("anything", capabilities=[]) == []
    assert CP.render_brief([]) == ""
