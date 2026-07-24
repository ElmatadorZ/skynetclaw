"""
test_belief_revision.py — OX-BELIEF-REVISION-1 Belief Revision Protocol
  A — belief 0.90, recent 0.40 → high drift
  B — belief 0.80, recent 0.60 → medium (gap 0.20; validation-authoritative threshold)
  C — belief 0.75, recent 0.70 → no drift (stable)
  D — unsupported belief (no recent evidence) → ignored
Plus severity table, review classification, and metrics.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import belief_revision as BR


def test_severity_table():
    assert BR.severity(0.50) == "high"
    assert BR.severity(0.41) == "high"
    assert BR.severity(0.30) == "medium"
    assert BR.severity(0.20) == "medium"      # validation B boundary
    assert BR.severity(0.15) == "low"
    assert BR.severity(0.10) == "low"
    assert BR.severity(0.05) is None          # stable


def test_A_high_drift():
    r = BR.assess("Github First", 0.90, 0.40, recent_n=10)
    assert r["status"] == "belief_drift" and r["severity"] == "high"
    assert r["contradiction"] == 0.5


def test_B_medium_drift():
    r = BR.assess("Github First", 0.80, 0.60, recent_n=10)
    assert r["status"] == "belief_drift" and r["severity"] == "medium"
    assert r["contradiction"] == 0.2


def test_C_no_drift_stable():
    r = BR.assess("Github First", 0.75, 0.70, recent_n=10)
    assert r["status"] == "stable" and r["severity"] is None


def test_D_unsupported_belief_ignored():
    assert BR.assess("Github First", 0.90, None, recent_n=0) is None       # no recent evidence
    assert BR.assess("Github First", 0.90, 0.40, recent_n=2) is None       # < MIN_RECENT


def _ep(gap, sources, ok):
    return {"gap_type": gap, "sources_checked": sources,
            "knowledge_found": ok}


def test_review_classifies_strategy_drift():
    strategies = {"pdf_generation": {"recommended_order": ["github"], "confidence": 0.90}}
    # recent evidence: mostly failing now (3/10) → drift
    eps = [_ep("pdf_generation", ["github"], i < 3) for i in range(10)]
    rev = BR.review(strategies=strategies, hypotheses={}, capabilities=[],
                    episodes=eps, attributions=[])
    assert rev["belief_drift"], "strategy belief should drift"
    d = rev["belief_drift"][0]
    assert d["severity"] in ("high", "medium") and d["source"] == "metalearning"


def test_review_capability_strength_and_ignores_unsupported():
    caps = [{"name": "HTML Report Builder", "confidence": 0.90, "polarity": "capability"},
            {"name": "Lonely Cap", "confidence": 0.95, "polarity": "capability"}]
    attrs = [{"recalled_capabilities": ["HTML Report Builder"], "outcome": "success"} for _ in range(8)]
    # "Lonely Cap" has no attribution evidence → ignored entirely
    rev = BR.review(strategies={}, hypotheses={}, capabilities=caps,
                    episodes=[], attributions=attrs)
    names = [a["belief"] for a in rev["stable"] + rev["belief_drift"]]
    assert "HTML Report Builder" in names
    assert "Lonely Cap" not in names               # unsupported → ignored
    assert any(s["belief"] == "HTML Report Builder" for s in rev["strengths"])


def test_metrics_and_brief():
    strategies = {"pdf": {"recommended_order": ["github"], "confidence": 0.90}}
    eps = [_ep("pdf", ["github"], i < 4) for i in range(10)]   # 0.40 recent → high drift
    rev = BR.review(strategies=strategies, hypotheses={}, capabilities=[], episodes=eps, attributions=[])
    m = BR.metrics(rev)
    assert m["drift_count"] >= 1 and m["drift_by_severity"].get("high", 0) >= 1
    assert "DRIFT" in BR.render_brief(rev)
