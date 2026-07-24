"""
test_research_agenda.py — OX-RESEARCH-AGENDA-1 Research Agenda Protocol
  A — broad theory + drift + high-priority experiment → top priority
  B — broad theory, calibrated, no drift, only medium experiment → lower priority
  C — pattern with no theory and no experiment → excluded
Plus scoring fields and metrics. Read-only.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import research_agenda as RA


def _theory(pattern, domains, conf=0.85):
    return {"pattern": pattern, "supporting_domains": domains, "confidence": conf,
            "theory": f"{pattern} generalizes"}


def _exp(pattern, priority):
    return {"hypothesis": f"{pattern}_first_is_better", "priority": priority, "gap_type": "g"}


def _drift(pattern, severity="high"):
    return {"belief": f"g: {pattern}→documentation", "pattern": pattern, "severity": severity}


def _find(ag, pattern):
    return next((r for r in ag if r["pattern"] == pattern), None)


def test_A_high_impact_uncertain_testable_is_top():
    ag = RA.form(theories=[_theory("github", ["pdf", "api"])],
                 experiments=[_exp("github", "high")],
                 drifts=[_drift("github", "high")], calibration=[])
    r = _find(ag, "github")
    assert r is not None
    assert r["impact"] == 1.0          # 0.5 + 0.25*2
    assert r["leverage"] == 0.9        # high-priority experiment
    assert r["uncertainty"] == 0.9     # high drift
    assert r["priority_score"] == round(1.0 * 0.9 * 0.9, 4)
    assert r["has_experiment"] and r["has_drift"]


def test_B_stable_calibrated_is_lower():
    a = RA.form(theories=[_theory("github", ["pdf", "api"])], experiments=[_exp("github", "high")],
                drifts=[_drift("github", "high")], calibration=[])
    b = RA.form(theories=[_theory("documentation", ["pdf", "api"])],
                experiments=[_exp("documentation", "medium")],
                drifts=[], calibration=[{"subject": "documentation first", "status": "calibrated", "error": 0.05}])
    ra = _find(a, "github")
    rb = _find(b, "documentation")
    assert rb["uncertainty"] == 0.2 and rb["leverage"] == 0.6   # no drift, medium experiment
    assert rb["priority_score"] < ra["priority_score"]


def test_C_no_theory_no_experiment_excluded():
    # drift alone (no theory, no experiment) → nothing investigable → not on agenda
    ag = RA.form(theories=[], experiments=[], drifts=[_drift("github")], calibration=[])
    assert _find(ag, "github") is None


def test_miscalibration_raises_uncertainty():
    ag = RA.form(theories=[_theory("github", ["pdf", "api"])], experiments=[_exp("github", "medium")],
                 drifts=[],
                 calibration=[{"subject": "github first", "status": "overconfident", "error": 0.45}])
    r = _find(ag, "github")
    assert r["uncertainty"] == 0.45        # calibration error dominates the base


def test_ranking_and_metrics():
    ag = RA.form(theories=[_theory("github", ["pdf", "api"]), _theory("documentation", ["x"])],
                 experiments=[_exp("github", "high"), _exp("documentation", "medium")],
                 drifts=[_drift("github", "high")], calibration=[])
    assert ag[0]["pattern"] == "github"            # highest priority first
    m = RA.metrics(ag)
    assert m["agenda_size"] == 2 and m["top_score"] == ag[0]["priority_score"]
    assert m["with_experiment"] == 2 and m["with_drift"] == 1
    assert "RESEARCH AGENDA" in RA.render_brief(ag)
