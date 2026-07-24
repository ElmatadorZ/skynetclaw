"""
test_first_principles.py — OX-FIRST-PRINCIPLE-1 First Principle Extraction
  A — MetaLearning + Causal support the same pattern → principle candidate
  B — single source only → reject
  C — support < 5 → reject
Plus classification, 2-system rule across pairs, and risk principles.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import first_principles as FP


def _ml(gap, order, conf, ev):
    return {gap: {"recommended_order": order, "confidence": conf, "evidence_count": ev}}


def _ca(gap, factor, conf, support):
    return {gap: [{"factor": factor, "confidence": conf, "supporting_evidence": support,
                   "hypothesis": f"{factor} helps"}]}


def _find(ps, pattern):
    return next((p for p in ps if p["pattern"] == pattern), None)


def test_A_metalearning_plus_causal_candidate():
    ps = FP.extract(strategies=_ml("pdf", ["github", "documentation"], 0.90, 6),
                    hypotheses=_ca("pdf", "uses:github", 0.85, 6),
                    reinforced=[])
    gh = _find(ps, "github")
    assert gh is not None
    assert set(gh["sources"]) == {"MetaLearning", "Causal"}
    assert gh["supporting_evidence"] >= 5 and gh["confidence"] >= 0.70
    assert gh["status"] == "candidate"
    # github leads the strategy order → Strategy Principle
    assert gh["category"] == "Strategy Principle"
    assert "Executable examples" in gh["principle"]


def test_B_single_source_rejected():
    ps = FP.extract(strategies=_ml("pdf", ["github"], 0.95, 10),
                    hypotheses={}, reinforced=[])
    assert _find(ps, "github") is None        # only MetaLearning → 1 system → reject


def test_C_insufficient_support_rejected():
    ps = FP.extract(strategies=_ml("pdf", ["github"], 0.90, 2),
                    hypotheses=_ca("pdf", "uses:github", 0.90, 2),
                    reinforced=[])
    # 2 systems but combined support 4 < 5 → reject
    assert _find(ps, "github") is None


def test_low_confidence_rejected():
    ps = FP.extract(strategies=_ml("pdf", ["github"], 0.60, 6),
                    hypotheses=_ca("pdf", "uses:github", 0.62, 6),
                    reinforced=[])
    assert _find(ps, "github") is None        # mean conf 0.61 < 0.70


def test_causal_plus_reinforcement_pair():
    # documentation supported by Causal + a reinforced capability (http_request→documentation)
    ps = FP.extract(strategies={},
                    hypotheses=_ca("api", "uses:documentation", 0.8, 5),
                    reinforced=[{"name": "Researcher", "recommended_tools": ["http_request"],
                                 "confidence": 0.85, "evidence_count": 6}])
    doc = _find(ps, "documentation")
    assert doc is not None and set(doc["sources"]) == {"Causal", "Reinforcement"}
    assert doc["category"] == "Knowledge Principle"


def test_risk_principle_from_drift():
    drifts = [{"belief": "Github First", "source": "metalearning",
               "contradiction": 0.45, "recent_n": 8, "severity": "high"}]
    rps = FP.extract_risk(drifts=drifts)
    assert rps and rps[0]["category"] == "Risk Principle"
    assert set(rps[0]["sources"]) == {"BeliefRevision", "MetaLearning"}
    assert rps[0]["confidence"] >= 0.70 and rps[0]["supporting_evidence"] == 8


def test_metrics_and_brief():
    ps = FP.extract(strategies=_ml("pdf", ["github", "documentation"], 0.90, 6),
                    hypotheses=_ca("pdf", "uses:github", 0.85, 6), reinforced=[])
    m = FP.metrics(ps)
    assert m["principle_count"] >= 1 and m["avg_confidence"] is not None
    assert "FIRST PRINCIPLES" in FP.render_brief(ps)
