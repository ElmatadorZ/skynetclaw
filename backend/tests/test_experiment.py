"""
test_experiment.py — OX-EXPERIMENT-1 Experiment Design Protocol
  A — strong strategy + strong drift → HIGH priority experiment
  B — strong strategy + no drift     → MEDIUM priority
  C — weak strategy                  → no experiment
Plus schema (control/test orderings), suggested test, metrics. Read-only.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import experiment as EXP


def _strat(gap, order, conf, ev=14):
    return {gap: {"recommended_order": order, "confidence": conf, "evidence_count": ev}}


def _drift(gap_or_src):
    return [{"belief": f"{gap_or_src}: github→documentation", "pattern": gap_or_src,
             "severity": "high", "recent_n": 8}]


def _find(es, gap):
    return next((e for e in es if e["gap_type"] == gap), None)


def test_A_strong_strategy_strong_drift_high():
    es = EXP.design(strategies=_strat("pdf_generation", ["github", "documentation"], 0.91),
                    hypotheses={"pdf_generation": [{"factor": "uses:github"}]},
                    drifts=_drift("pdf_generation"))
    e = _find(es, "pdf_generation")
    assert e is not None and e["priority"] == "high"
    assert e["hypothesis"] == "github_first_is_better"
    assert e["control_strategy"] == ["github", "documentation"]
    assert e["test_strategy"] == ["documentation", "github"]      # controlled alternative
    assert e["evidence"] == 14 and e["has_drift"] is True
    assert "alternate github_first vs documentation_first" == e["suggested_test"]


def test_B_strong_strategy_no_drift_medium():
    es = EXP.design(strategies=_strat("pdf_generation", ["github", "documentation"], 0.91),
                    hypotheses={}, drifts=[])
    e = _find(es, "pdf_generation")
    assert e is not None and e["priority"] == "medium"
    assert e["has_drift"] is False
    assert "no recent contradiction" in e["reason"]


def test_C_weak_strategy_no_experiment():
    es = EXP.design(strategies=_strat("pdf_generation", ["github", "documentation"], 0.70),
                    hypotheses={}, drifts=[])
    assert _find(es, "pdf_generation") is None        # weak belief → no experiment


def test_single_source_strategy_skipped():
    # cannot form a controlled comparison from a single-source order
    es = EXP.design(strategies=_strat("x", ["github"], 0.95), hypotheses={}, drifts=[])
    assert es == []


def test_priority_ordering_high_before_medium():
    strategies = {}
    strategies.update(_strat("a", ["github", "docs"], 0.90))
    strategies.update(_strat("b", ["web", "github"], 0.90))
    es = EXP.design(strategies=strategies, hypotheses={}, drifts=_drift("a"))
    assert es[0]["gap_type"] == "a" and es[0]["priority"] == "high"
    assert es[1]["priority"] == "medium"


def test_metrics_and_brief():
    es = EXP.design(strategies=_strat("pdf", ["github", "documentation"], 0.91),
                    hypotheses={}, drifts=_drift("pdf"))
    m = EXP.metrics(es)
    assert m["experiment_count"] == 1 and m["by_priority"].get("high") == 1
    assert "github_first_is_better" in m["high_priority"]
    assert "EXPERIMENT CANDIDATES" in EXP.render_brief(es)
