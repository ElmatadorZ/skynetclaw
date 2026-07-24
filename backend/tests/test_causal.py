"""
test_causal.py — OX-CAUSAL-1 Causal Discovery Protocol
  A — github in successes, absent in failures → causal candidate
  B — random correlation (factor in both equally) → rejected
  C — support < 5 → insufficient evidence (not promoted)
Plus: present-everywhere is not causal, observation projection, recall, metrics.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import causal as CA


def _rec(gap, sources, ok, comp=0.8):
    """Acquisition-record shape that observations() projects."""
    return {"gap_type": gap, "sources_checked": sources,
            "sources_successful": sources if ok else [],
            "knowledge_found": ok, "execution_used": True, "compliance_score": comp}


def _find(hyps, factor):
    return next((h for h in hyps if h["factor"] == factor), None)


def test_observation_projection():
    o = CA.observations([_rec("pdf", ["github"], True)])[0]
    for k in ("gap_type", "strategy", "sources_used", "compliance", "outcome"):
        assert k in o
    assert o["strategy"] == "github_first" and o["outcome"] == "success"


def test_A_github_causal_candidate():
    # 6 successes WITH github, 6 failures WITHOUT github (use web_search instead)
    recs = [_rec("pdf_generation", ["github", "documentation"], True) for _ in range(6)] \
         + [_rec("pdf_generation", ["web_search"], False) for _ in range(6)]
    h = _find(CA.discover(recs, gap_type="pdf_generation"), "uses:github")
    assert h is not None
    assert h["promotion_candidate"] is True
    assert h["supporting_evidence"] >= 5 and h["contradicting_evidence"] == 0
    assert h["confidence"] >= 0.70
    assert "github" in h["hypothesis"] and "because" in h["hypothesis"]


def test_B_random_correlation_rejected():
    # github present in HALF the successes and HALF the failures → not discriminating
    recs = []
    for i in range(10):
        recs.append(_rec("api", ["github"] if i % 2 == 0 else ["web_search"], True))
        recs.append(_rec("api", ["github"] if i % 2 == 0 else ["web_search"], False))
    h = _find(CA.discover(recs, gap_type="api"), "uses:github")
    assert h is not None
    assert h["promotion_candidate"] is False        # ~0.5 confidence, not discriminating
    assert h["confidence"] < 0.70


def test_C_insufficient_support():
    # github only wins 3 times (< MIN_SUPPORT) though never fails
    recs = [_rec("rare", ["github"], True) for _ in range(3)] \
         + [_rec("rare", ["web_search"], False) for _ in range(3)]
    h = _find(CA.discover(recs, gap_type="rare"), "uses:github")
    assert h["supporting_evidence"] == 3
    assert h["promotion_candidate"] is False         # support < 5


def test_present_everywhere_not_causal():
    # github used in EVERY observation (success and fail) → no contrast → not causal
    recs = [_rec("x", ["github"], True) for _ in range(6)] \
         + [_rec("x", ["github"], False) for _ in range(6)]
    h = _find(CA.discover(recs, gap_type="x"), "uses:github")
    assert h["discriminating"] is False and h["promotion_candidate"] is False


def test_refresh_persists_only_promoted(tmp_path):
    p = tmp_path / "c.json"
    recs = [_rec("pdf_generation", ["github"], True) for _ in range(6)] \
         + [_rec("pdf_generation", ["web_search"], False) for _ in range(6)]
    promoted = CA.refresh(records=recs, path=p)
    assert "pdf_generation" in promoted
    assert any(h["factor"] == "uses:github" for h in promoted["pdf_generation"])
    # recall brief surfaces the reason
    brief = CA.render_brief("pdf_generation", path=p)
    assert "CAUSAL INSIGHT" in brief and "github" in brief


def test_metrics(tmp_path):
    p = tmp_path / "c.json"
    recs = [_rec("pdf_generation", ["github"], True) for _ in range(6)] \
         + [_rec("pdf_generation", ["web_search"], False) for _ in range(6)]
    CA.refresh(records=recs, path=p)
    m = CA.metrics(records=recs, path=p)
    assert m["promoted_count"] >= 1 and m["gap_types_covered"] == 1
    assert m["avg_confidence"] is not None
