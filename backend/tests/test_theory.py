"""
test_theory.py — OX-THEORY-1 Theory Formation Protocol
  A — pattern corroborated across >=2 domains → theory candidate
  B — pattern in a single domain → not a theory
  C — multi-domain but low confidence → rejected
Plus supporting-domains, source diversity, metrics. Read-only.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import theory as TH


def _causal(pairs):
    """pairs: list of (gap_type, factor, confidence, support)."""
    out = {}
    for gap, factor, conf, sup in pairs:
        out.setdefault(gap, []).append(
            {"factor": factor, "confidence": conf, "supporting_evidence": sup})
    return out


def _find(ts, pattern):
    return next((t for t in ts if t["pattern"] == pattern), None)


def test_A_generalizes_across_domains():
    causal = _causal([("pdf_generation", "uses:github", 0.86, 8),
                      ("api_integration", "uses:github", 0.82, 7)])
    ts = TH.form(causal=causal, principles=[], decisions=[])
    gh = _find(ts, "github")
    assert gh is not None and gh["status"] == "candidate"
    assert set(gh["supporting_domains"]) == {"pdf_generation", "api_integration"}
    assert gh["confidence"] >= 0.70 and gh["evidence"] == 15
    assert "across domains" in gh["theory"]


def test_B_single_domain_not_theory():
    causal = _causal([("pdf_generation", "uses:github", 0.90, 10)])
    ts = TH.form(causal=causal, principles=[], decisions=[])
    assert _find(ts, "github") is None        # only one domain → not a theory


def test_C_low_confidence_rejected():
    causal = _causal([("pdf_generation", "uses:github", 0.60, 8),
                      ("api_integration", "uses:github", 0.62, 8)])
    ts = TH.form(causal=causal, principles=[], decisions=[])
    assert _find(ts, "github") is None        # generalizes but mean conf < 0.70


def test_source_diversity_from_principles_and_decisions():
    causal = _causal([("pdf", "uses:documentation", 0.8, 6),
                      ("api", "uses:documentation", 0.8, 6)])
    principles = [{"pattern": "documentation", "confidence": 0.85}]
    decisions = [{"pattern": "documentation", "confidence": 0.81}]
    ts = TH.form(causal=causal, principles=principles, decisions=decisions)
    doc = _find(ts, "documentation")
    assert doc is not None
    assert set(doc["sources"]) == {"causal", "first_principles", "decision"}


def test_metrics_and_brief():
    causal = _causal([("pdf", "uses:github", 0.86, 8), ("api", "uses:github", 0.84, 7)])
    ts = TH.form(causal=causal, principles=[], decisions=[])
    m = TH.metrics(ts)
    assert m["theory_count"] == 1 and m["max_domains"] == 2
    assert m["avg_confidence"] is not None
    assert "THEORIES" in TH.render_brief(ts)
