"""
test_calibration.py — OX-CONFIDENCE-1 Confidence Calibration Protocol
  A — predicted 0.90, observed 0.50 → overconfident
  B — predicted 0.60, observed 0.85 → underconfident
  C — predicted 0.80, observed 0.78 → calibrated
Plus error/quality bands, insufficient-evidence ignore, aggregation, metrics.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import calibration as CAL


def test_A_overconfident():
    r = CAL.assess("Github First", 0.90, 0.50, recent_n=10)
    assert r["status"] == "overconfident" and r["error"] == 0.4
    assert r["quality"] == "poor"


def test_B_underconfident():
    r = CAL.assess("Docs First", 0.60, 0.85, recent_n=10)
    assert r["status"] == "underconfident" and r["error"] == 0.25
    assert r["quality"] == "moderate"


def test_C_calibrated():
    r = CAL.assess("Web First", 0.80, 0.78, recent_n=10)
    assert r["status"] == "calibrated" and r["quality"] == "calibrated"
    assert r["error"] == 0.02


def test_quality_bands():
    assert CAL.assess("x", 0.9, 0.5, 5)["quality"] == "poor"        # error 0.40
    assert CAL.assess("x", 0.9, 0.7, 5)["quality"] == "moderate"    # error 0.20
    assert CAL.assess("x", 0.9, 0.80, 5)["quality"] == "calibrated"  # error 0.10


def test_boundary_status_is_calibrated_within_tol():
    # error exactly 0.15 → calibrated (not over/under)
    r = CAL.assess("x", 0.80, 0.65, recent_n=10)
    assert r["error"] == 0.15 and r["status"] == "calibrated"


def test_insufficient_evidence_ignored():
    assert CAL.assess("x", 0.9, None, recent_n=0) is None
    assert CAL.assess("x", 0.9, 0.5, recent_n=2) is None      # < MIN_OBS


def test_calibrate_with_injected_subjects():
    subs = [
        {"subject": "Github First", "predicted_confidence": 0.90, "observed_success": 0.50, "recent_n": 10},
        {"subject": "Docs First", "predicted_confidence": 0.60, "observed_success": 0.85, "recent_n": 10},
        {"subject": "Web First", "predicted_confidence": 0.80, "observed_success": 0.78, "recent_n": 10},
        {"subject": "Thin", "predicted_confidence": 0.95, "observed_success": 0.10, "recent_n": 1},  # ignored
    ]
    recs = CAL.calibrate(subjects=subs)
    assert len(recs) == 3                                 # thin one dropped
    by = {r["subject"]: r["status"] for r in recs}
    assert by["Github First"] == "overconfident"
    assert by["Docs First"] == "underconfident"
    assert by["Web First"] == "calibrated"


def test_metrics_and_brief():
    subs = [
        {"subject": "Github First", "predicted_confidence": 0.90, "observed_success": 0.50, "recent_n": 10},
        {"subject": "Web First", "predicted_confidence": 0.80, "observed_success": 0.78, "recent_n": 10},
    ]
    recs = CAL.calibrate(subjects=subs)
    m = CAL.metrics(recs)
    assert m["subjects_assessed"] == 2
    assert m["by_status"].get("overconfident") == 1
    assert "Github First" in m["overconfident"]
    assert m["mean_error"] is not None
    assert "CALIBRATION" in CAL.render_brief(recs)
