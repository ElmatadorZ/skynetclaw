"""
test_compliance.py — OX-COMPLIANCE-1 Capability Compliance Verification
Measure whether recalled capabilities actually shaped execution:
  recommended_tools  vs  actually-used tools  →  FOLLOWED / PARTIAL / IGNORED.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import compliance as C

_REG = [
    {"name": "HTML Report Builder", "polarity": "capability",
     "recommended_tools": ["read_file", "write_file"]},
    {"name": "Research", "polarity": "capability",
     "recommended_tools": ["web_search", "http_request"]},
    {"name": "PDF (UNSTABLE)", "polarity": "warning", "recommended_tools": ["read_file"]},
]


# ── scoring + classification ──────────────────────────────────────────────────
def test_score_followed():
    r = C.score(["read_file", "write_file"], ["read_file", "write_file", "grep_search"])
    assert r["compliance_score"] == 1.0 and r["classification"] == C.FOLLOWED


def test_score_partial():
    r = C.score(["read_file", "write_file"], ["read_file", "list_files"])
    assert r["compliance_score"] == 0.5 and r["classification"] == C.PARTIAL
    assert r["matched_tools"] == ["read_file"]


def test_score_ignored():
    r = C.score(["read_file", "write_file"], ["web_search"])
    assert r["compliance_score"] == 0.0 and r["classification"] == C.IGNORED


def test_score_not_applicable():
    r = C.score([], ["read_file"])
    assert r["compliance_score"] is None and r["classification"] == C.NA


# ── evaluate against the capability registry ──────────────────────────────────
def test_evaluate_uses_recommended_tools():
    r = C.evaluate(["HTML Report Builder"], ["read_file", "write_file"], registry=_REG)
    assert r["classification"] == C.FOLLOWED
    assert set(r["expected_tools"]) == {"read_file", "write_file"}


def test_evaluate_ignores_warning_capabilities():
    # a warning capability contributes no expected tools
    r = C.evaluate(["PDF (UNSTABLE)"], ["read_file"], registry=_REG)
    assert r["classification"] == C.NA and r["compliance_score"] is None


def test_evaluate_union_across_capabilities():
    r = C.evaluate(["HTML Report Builder", "Research"],
                   ["read_file", "write_file", "web_search", "http_request"], registry=_REG)
    assert r["compliance_score"] == 1.0 and r["classification"] == C.FOLLOWED


# ── record + aggregate metrics ────────────────────────────────────────────────
def test_record_and_metrics(tmp_path):
    p = tmp_path / "compliance.json"
    C.record("m1", ["HTML Report Builder"], ["read_file", "write_file"], outcome="success", registry=_REG, path=p)  # FOLLOWED
    C.record("m2", ["HTML Report Builder"], ["read_file"], outcome="success", registry=_REG, path=p)                # PARTIAL
    C.record("m3", ["HTML Report Builder"], ["web_search"], outcome="failure", registry=_REG, path=p)               # IGNORED
    C.record("m4", [], ["read_file"], outcome="success", registry=_REG, path=p)                                     # N/A
    m = C.metrics(path=p)
    assert m["total"] == 4 and m["measurable"] == 3
    assert m["by_classification"][C.FOLLOWED] == 1
    assert m["by_classification"][C.PARTIAL] == 1
    assert m["by_classification"][C.IGNORED] == 1
    assert m["by_classification"][C.NA] == 1
    assert m["followed_rate"] == round(1/3, 3)
    # avg over the 3 measurable: (1.0 + 0.5 + 0.0)/3
    assert m["avg_compliance_score"] == 0.5


def test_per_capability_breakdown(tmp_path):
    p = tmp_path / "compliance.json"
    C.record("m1", ["HTML Report Builder"], ["read_file", "write_file"], registry=_REG, path=p)  # FOLLOWED
    C.record("m2", ["HTML Report Builder"], ["web_search"], registry=_REG, path=p)               # IGNORED
    pc = C.per_capability(path=p)
    assert pc["HTML Report Builder"]["recalled_in"] == 2
    assert pc["HTML Report Builder"]["avg_compliance"] == 0.5
    assert pc["HTML Report Builder"]["followed_rate"] == 0.5


def test_attribution_carries_compliance(tmp_path):
    """Integration: attribution.record stores the compliance signal additively
    without changing the attribution_score computation."""
    import attribution as A
    p = tmp_path / "attribution.json"
    rec = A.record("m1", capabilities=["HTML Report Builder"], outcome="success",
                   compliance_score=1.0, compliance_class="FOLLOWED", path=p)
    assert rec["compliance_score"] == 1.0 and rec["compliance_class"] == "FOLLOWED"
    assert rec["attribution_score"] > 0          # unchanged base computation
