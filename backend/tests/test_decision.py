"""
test_decision.py — OX-DECISION-1 Decision Framework Protocol
  A — principle + strategy agree → high confidence
  B — belief drift present → confidence reduced + risk surfaced
  C — blind spot present → uncertainty surfaced + confidence reduced
Plus scoring weights, classification, no-support rejection, schema.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import decision as DEC


def _princ(pattern, category="Knowledge Principle", conf=0.85):
    return [{"pattern": pattern, "category": category, "confidence": conf,
             "principle": f"{pattern} works"}]


def _strat(gap, order):
    return {gap: {"recommended_order": order, "confidence": 0.9}}


def _find(ds, pattern):
    return next((d for d in ds if d["pattern"] == pattern), None)


def test_A_principle_and_strategy_high_confidence():
    ds = DEC.decide(principles=_princ("documentation"),
                    strategies=_strat("api", ["documentation"]),
                    drifts=[], blind_spots=[])
    d = _find(ds, "documentation")
    assert d is not None
    assert d["recommendation"] == "Documentation First"
    # 0.4 + 0.3 + 0.2 + 0.1 = 1.0
    assert d["confidence"] == 1.0
    assert d["supporting_principles"] and not d["known_risks"] and not d["blind_spots"]


def test_schema_fields():
    d = _find(DEC.decide(principles=_princ("github"), strategies=_strat("pdf", ["github"]),
                         drifts=[], blind_spots=[]), "github")
    for k in ("recommendation", "confidence", "supporting_principles",
              "known_risks", "blind_spots", "reasoning", "category"):
        assert k in d


def test_B_belief_drift_reduces_confidence_and_surfaces_risk():
    base = _find(DEC.decide(principles=_princ("documentation"),
                            strategies=_strat("api", ["documentation"]),
                            drifts=[], blind_spots=[]), "documentation")
    drifted = _find(DEC.decide(principles=_princ("documentation"),
                               strategies=_strat("api", ["documentation"]),
                               drifts=[{"belief": "documentation first", "pattern": "documentation",
                                        "severity": "high"}],
                               blind_spots=[]), "documentation")
    assert drifted["confidence"] < base["confidence"]      # 0.8 < 1.0
    assert drifted["known_risks"]                          # risk surfaced
    assert drifted["confidence"] == 0.8


def test_C_blind_spot_surfaces_uncertainty():
    d = _find(DEC.decide(principles=_princ("obsidian"),
                         strategies=_strat("notes", ["obsidian"]),
                         drifts=[],
                         blind_spots=[{"target": "obsidian", "severity": "medium",
                                       "type": "underexplored_source"}]), "obsidian")
    assert d["blind_spots"] == ["obsidian"]                # uncertainty surfaced
    assert d["confidence"] == 0.9                          # forfeits the +0.1


def test_classification_from_principle():
    d = _find(DEC.decide(principles=_princ("existing_code", category="Strategy Principle"),
                         strategies={}, drifts=[], blind_spots=[]), "existing_code")
    assert d["category"] == "Strategy Decision"


def test_no_positive_support_not_recommended():
    # a pattern with only a drift (no principle, no strategy) → no recommendation
    ds = DEC.decide(principles=[], strategies={},
                    drifts=[{"belief": "github", "pattern": "github", "severity": "high"}],
                    blind_spots=[])
    assert _find(ds, "github") is None


def test_metrics_and_brief():
    ds = DEC.decide(principles=_princ("documentation"), strategies=_strat("api", ["documentation"]),
                    drifts=[], blind_spots=[])
    m = DEC.metrics(ds)
    assert m["decision_count"] == 1 and m["avg_confidence"] == 1.0
    assert "DECISIONS" in DEC.render_brief(ds) and "Documentation First" in DEC.render_brief(ds)
