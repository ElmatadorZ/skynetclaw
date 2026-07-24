"""
test_control_engine.py — OX-CONTROL-1 Adaptive Control Engine (model-free)
Closes Measure → Decide → Adjust:
  A — regressing  → corrective actions + tightening policy.
  B — improving   → reinforcing actions.
  C — flat        → observe, do not overreact.
Plus insufficient_data, control history, and the bounded adjust surface.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import control_engine as CE


def _sc(verdict, score=0.0, drivers=None, n=12):
    return {"verdict": verdict, "score": score, "drivers": drivers or [], "n_runs": n}


def test_A_regressing_generates_corrective_actions():
    d = CE.decide(_sc("regressing", -0.31, ["completion_rate -0.3", "dead_end_rate +0.2"]))
    assert d["verdict"] == "regressing"
    acts = " ".join(d["recommended_actions"]).lower()
    assert "warning" in acts and "recovery" in acts and "threshold" in acts
    # schema
    for k in ("verdict", "recommended_actions", "reason"):
        assert k in d
    pol = d["policy"]
    assert pol["promotion_conf_delta"] > 0          # raise the bar
    assert pol["capability_recall_order"] == "warnings_first"
    assert pol["lesson_recall_focus"] == "recovery"
    assert pol["hold"] is False
    assert "declining" in d["reason"]


def test_B_improving_reinforces():
    d = CE.decide(_sc("improving", 0.4, ["completion_rate +0.3"]))
    acts = " ".join(d["recommended_actions"]).lower()
    assert "reinforce" in acts and "proven" in acts and "validated" in acts
    pol = d["policy"]
    assert pol["reinforce_proven"] is True
    assert pol["promotion_conf_delta"] <= 0
    assert pol["capability_recall_order"] == "proven_first"


def test_C_flat_recommends_observation():
    d = CE.decide(_sc("flat", 0.01))
    acts = " ".join(d["recommended_actions"]).lower()
    assert "maintain" in acts or "observe" in acts
    assert d["policy"]["hold"] is True
    assert d["policy"]["promotion_conf_delta"] == 0.0
    assert "overreact" in d["reason"]


def test_insufficient_data_holds():
    d = CE.decide(_sc("insufficient_data", 0.0, n=2))
    assert d["policy"]["hold"] is True
    assert CE.render_brief(d) == ""                 # nothing to direct yet


def test_control_history_records(tmp_path):
    p = tmp_path / "control_history.json"
    CE.decide_and_record(_sc("regressing", -0.2), path=p)
    CE.decide_and_record(_sc("improving", 0.2), path=p)
    hist = CE.load_history(p)
    assert len(hist) == 2
    assert hist[0]["verdict"] == "regressing" and hist[1]["verdict"] == "improving"
    # latest policy reflects the most recent decision
    assert CE.latest(p)["verdict"] == "improving"
    assert CE.latest_policy(p)["capability_recall_order"] == "proven_first"


def test_adjust_surface_is_bounded():
    # regressing raises threshold but stays bounded
    reg = CE.decide(_sc("regressing", -0.5))["policy"]
    assert CE.adjusted_promotion_threshold(0.80, reg) == 0.85
    assert CE.adjusted_promotion_threshold(0.92, reg) <= 0.95     # clamp
    # a pathological policy cannot blow past the cap
    assert CE.adjusted_promotion_threshold(0.80, {"promotion_conf_delta": 99}) <= 0.90


def test_reorder_capabilities_priority():
    caps = [{"name": "A", "polarity": "capability"}, {"name": "W", "polarity": "warning"},
            {"name": "B", "polarity": "capability"}]
    warns_first = CE.reorder_capabilities(caps, {"capability_recall_order": "warnings_first"})
    assert warns_first[0]["polarity"] == "warning"
    proven_first = CE.reorder_capabilities(caps, {"capability_recall_order": "proven_first"})
    assert proven_first[0]["polarity"] == "capability"


def test_render_brief_per_verdict():
    assert "REGRESSING" in CE.render_brief(CE.decide(_sc("regressing", -0.2)))
    assert "IMPROVING" in CE.render_brief(CE.decide(_sc("improving", 0.2)))
    assert "FLAT" in CE.render_brief(CE.decide(_sc("flat", 0.0)))
