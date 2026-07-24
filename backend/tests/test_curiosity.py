"""
test_curiosity.py — OX-CURIOSITY-1 Gap Discovery Protocol (read-only)
  A — no OAuth episodes      → blind spot (high)
  B — one Obsidian acquisition → underexplored source (medium)
  C — hypothesis support=2   → weak evidence (flagged)
  D — capability evidence=20 → NOT flagged
Plus severity rules, single-source dependency, strengths, metrics.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import curiosity as CU


def _rec(gap, knowledge, sources, ok=True):
    return {"gap_type": gap, "knowledge_gap": knowledge, "task": knowledge,
            "sources_checked": sources, "sources_successful": sources if ok else [],
            "knowledge_found": ok}


def _find(insights, target, type_=None):
    return next((i for i in insights if i["target"] == target
                 and (type_ is None or i["type"] == type_)), None)


def test_severity_rules():
    assert CU.severity(0) == "high"
    assert CU.severity(1) == "medium" and CU.severity(2) == "medium"
    assert CU.severity(3) == "low" and CU.severity(4) == "low"
    assert CU.severity(5) is None and CU.severity(20) is None


def test_A_no_oauth_is_blind_spot():
    recs = [_rec("pdf_generation", "generate a pdf", ["documentation"])]
    ins = CU.scan(records=recs, capabilities=[], hypotheses=[], domains=["oauth", "pdf"])
    oauth = _find(ins, "oauth")
    assert oauth and oauth["type"] == "blind_spot"
    assert oauth["severity"] == "high" and oauth["evidence_count"] == 0
    # pdf IS present in the episode → not a blind spot
    assert _find(ins, "pdf", "blind_spot") is None


def test_B_one_obsidian_is_underexplored_source():
    recs = [_rec("notes", "read a note", ["obsidian"])] + \
           [_rec("x", "y", ["documentation"]) for _ in range(6)]
    ins = CU.scan(records=recs, capabilities=[], hypotheses=[], domains=[])
    ob = _find(ins, "obsidian", "underexplored_source")
    assert ob and ob["severity"] == "medium" and ob["evidence_count"] == 1


def test_C_weak_hypothesis_flagged():
    hyps = [{"factor": "uses:github", "supporting_evidence": 2, "discriminating": True,
             "hypothesis": "github helps"}]
    ins = CU.scan(records=[], capabilities=[], hypotheses=hyps, domains=[])
    wh = _find(ins, "uses:github", "weak_hypothesis")
    assert wh and wh["severity"] == "medium" and wh["evidence_count"] == 2


def test_D_strong_capability_not_flagged():
    caps = [{"name": "HTML Report Builder", "evidence_count": 20, "polarity": "capability"}]
    ins = CU.scan(records=[], capabilities=caps, hypotheses=[], domains=[])
    assert _find(ins, "HTML Report Builder") is None        # evidence 20 → not flagged
    # and it shows up as a STRENGTH instead
    assert any(s["target"] == "HTML Report Builder" for s in CU.strengths(records=[], capabilities=caps))


def test_weak_capability_flagged():
    caps = [{"name": "Shaky", "evidence_count": 2, "polarity": "capability"}]
    ins = CU.scan(records=[], capabilities=caps, hypotheses=[], domains=[])
    sc = _find(ins, "Shaky", "weak_capability")
    assert sc and sc["severity"] == "medium"


def test_single_source_dependency():
    recs = [_rec("pdf", "make pdf", ["github"], ok=True) for _ in range(4)]
    ins = CU.scan(records=recs, capabilities=[], hypotheses=[], domains=[])
    dep = _find(ins, "pdf", "single_source_dependency")
    assert dep and "github" in dep["reason"]


def test_metrics_and_brief():
    recs = [_rec("x", "y", ["documentation"]) for _ in range(6)]
    m = CU.metrics(records=recs, capabilities=[], hypotheses=[], domains=["oauth"])
    assert m["total_insights"] >= 1
    assert "oauth" in m["blind_spots"]
    brief = CU.render_brief(records=recs, capabilities=[], hypotheses=[], domains=["oauth"])
    assert "CURIOSITY" in brief and "oauth" in brief
