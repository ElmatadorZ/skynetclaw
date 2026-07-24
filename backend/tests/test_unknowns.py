"""
test_unknowns.py — OX-UNKNOWNS-1 Strategic Unknown Mapping
  A — well-calibrated / strong evidence → Known Known
  B — surfaced gap / open question / contradicted belief → Known Unknown
  C — zero-evidence blind spot / overconfident surprise → Unknown Unknown
Plus dedup and metrics. Read-only.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import unknowns as UN


def _items(bucket):
    return [b["item"] for b in bucket]


def test_A_known_knowns():
    st = UN.analyze(
        curiosity_insights=[], strengths=[{"target": "HTML Report Builder", "evidence_count": 20}],
        agenda=[], calibration=[{"subject": "Web First", "status": "calibrated", "error": 0.05}],
        drifts=[])
    kk = _items(st["known_knowns"])
    assert "Web First" in kk and "HTML Report Builder" in kk
    assert st["known_unknowns"] == [] and st["unknown_unknowns"] == []


def test_B_known_unknowns():
    st = UN.analyze(
        curiosity_insights=[{"target": "obsidian", "severity": "medium", "evidence_count": 1,
                             "type": "underexplored_source", "reason": "rarely used"}],
        strengths=[],
        agenda=[{"topic": "Is github causal?", "priority_score": 0.7}],
        calibration=[{"subject": "Docs First", "status": "underconfident", "error": 0.25}],
        drifts=[{"belief": "Github First", "severity": "high"}])
    ku = _items(st["known_unknowns"])
    assert "obsidian" in ku                       # underexplored = known thin spot
    assert "Is github causal?" in ku              # open question
    assert "Docs First" in ku                     # underconfidence = known uncertainty
    assert "Github First" in ku                   # contradicted belief
    assert st["unknown_unknowns"] == []


def test_C_unknown_unknowns():
    st = UN.analyze(
        curiosity_insights=[{"target": "oauth", "severity": "high", "evidence_count": 0,
                             "type": "blind_spot", "reason": "No acquisition episodes found"}],
        strengths=[],
        agenda=[],
        calibration=[{"subject": "Github First", "status": "overconfident", "error": 0.42}],
        drifts=[])
    uu = _items(st["unknown_unknowns"])
    assert "oauth" in uu                          # zero-evidence blind spot
    assert "Github First" in uu                   # confidently wrong = a surprise
    assert st["known_knowns"] == []


def test_dedup_within_bucket():
    st = UN.analyze(
        curiosity_insights=[{"target": "obsidian", "severity": "medium", "evidence_count": 1}],
        strengths=[],
        agenda=[{"topic": "obsidian", "priority_score": 0.5}],   # same item label
        calibration=[], drifts=[])
    assert _items(st["known_unknowns"]).count("obsidian") == 1   # deduped


def test_metrics():
    st = UN.analyze(
        curiosity_insights=[{"target": "oauth", "severity": "high", "evidence_count": 0}],
        strengths=[{"target": "HTML", "evidence_count": 10}],
        agenda=[{"topic": "q1", "priority_score": 0.6}],
        calibration=[], drifts=[])
    m = UN.metrics(st)
    assert m["known_knowns"] == 1 and m["known_unknowns"] == 1 and m["unknown_unknowns"] == 1
    assert m["total"] == 3 and m["known_ratio"] == round(1/3, 3)
    assert "UNKNOWN UNKNOWNS" in UN.render_brief(st)
