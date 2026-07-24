"""
test_metalearning.py — OX-METALEARNING-1 Learning How To Learn Protocol
  A — PDF generation episodes where github wins → github promoted (leads order)
  B — API integration where documentation wins → documentation promoted
  C — insufficient evidence (<5) → no strategy
  D — successful strategy → reinforcement (strengthened)
  E — failed strategy → demotion
Plus schema, promotion rules, recall bias, and metrics.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import metalearning as ML


def _ep(gap_type, tried, successful, ok=True, exe=True, comp=0.8):
    """Shape of an acquisition record (episodes() projects these)."""
    return {"gap_type": gap_type, "sources_checked": tried, "sources_successful": successful,
            "knowledge_found": ok, "execution_used": exe, "compliance_score": comp}


def test_episode_projection():
    e = ML.episode_from_record(_ep("api", ["documentation"], ["documentation"]))
    for k in ("gap_type", "sources_tried", "sources_successful",
              "acquisition_success", "execution_success", "compliance_score"):
        assert k in e
    assert e["acquisition_success"] is True and e["sources_tried"] == ["documentation"]


def test_A_pdf_generation_github_promoted():
    recs = [_ep("pdf_generation", ["github", "documentation"], ["github"]) for _ in range(6)]
    strat = ML.discover_strategies(ML.episodes(recs))["pdf_generation"]
    assert strat["promoted"] is True
    assert strat["recommended_order"][0] == "github"
    assert strat["confidence"] >= 0.70 and strat["evidence_count"] == 6


def test_B_api_documentation_promoted():
    recs = [_ep("api_integration", ["documentation", "github"], ["documentation"]) for _ in range(8)]
    strat = ML.discover_strategies(ML.episodes(recs))["api_integration"]
    assert strat["promoted"] is True
    assert strat["recommended_order"][0] == "documentation"


def test_C_insufficient_evidence_no_strategy(tmp_path):
    recs = [_ep("rare_gap", ["web_search"], ["web_search"]) for _ in range(3)]  # < MIN_EVIDENCE
    p = tmp_path / "s.json"
    promoted = ML.refresh(records=recs, path=p)
    assert "rare_gap" not in promoted
    assert ML.lookup_strategy("rare_gap", path=p) is None


def test_D_successful_strategy_reinforced(tmp_path):
    p = tmp_path / "s.json"
    # first cycle: borderline confidence
    c1 = [_ep("pdf_generation", ["github"], ["github"], ok=True) for _ in range(5)]
    c1 += [_ep("pdf_generation", ["github"], [], ok=False) for _ in range(2)]   # 5/7 ≈ 0.71
    ML.refresh(records=c1, path=p)
    conf1 = ML.lookup_strategy("pdf_generation", path=p)["confidence"]
    # second cycle: more successes → confidence strengthens, status reinforced
    c2 = c1 + [_ep("pdf_generation", ["github"], ["github"], ok=True) for _ in range(8)]
    allstrat = ML.discover_strategies(ML.episodes(c2), prior=ML.load_strategies(p))
    s = allstrat["pdf_generation"]
    assert s["confidence"] > conf1 and s["status"] == "reinforced" and s["promoted"]


def test_E_failed_strategy_demoted(tmp_path):
    p = tmp_path / "s.json"
    good = [_ep("pdf_generation", ["github"], ["github"], ok=True) for _ in range(6)]
    ML.refresh(records=good, path=p)
    assert ML.lookup_strategy("pdf_generation", path=p)["confidence"] >= 0.70
    # later evidence is mostly failures → confidence falls below the gate → demoted
    bad = good + [_ep("pdf_generation", ["github"], [], ok=False) for _ in range(20)]
    allstrat = ML.discover_strategies(ML.episodes(bad), prior=ML.load_strategies(p))
    s = allstrat["pdf_generation"]
    assert s["confidence"] < 0.70 and s["promoted"] is False and s["status"] == "demoted"
    promoted = ML.refresh(records=bad, path=p)
    assert "pdf_generation" not in promoted        # dropped from the promoted store


def test_recall_bias_order(tmp_path):
    p = tmp_path / "s.json"
    recs = [_ep("api_integration", ["existing_code", "documentation", "github"], ["documentation"]) for _ in range(6)]
    ML.refresh(records=recs, path=p)
    # a fresh gap's candidates get reordered so the proven source leads
    biased = ML.bias_order("api_integration", ["existing_code", "github", "documentation"], path=p)
    assert biased[0] == "documentation"
    # unknown gap_type → unchanged
    assert ML.bias_order("unknown_gap", ["a", "b"], path=p) == ["a", "b"]


def test_metrics(tmp_path):
    p = tmp_path / "s.json"
    recs = ([_ep("pdf_generation", ["github"], ["github"]) for _ in range(6)] +
            [_ep("api_integration", ["documentation"], ["documentation"]) for _ in range(6)])
    ML.refresh(records=recs, path=p)
    m = ML.metrics(path=p, records=recs)
    assert m["strategy_count"] == 2
    assert m["strategy_success_rate"] is not None
    assert m["episodes_total"] == 12
    assert m["most_effective_sources"][0]["source"] in ("github", "documentation")
