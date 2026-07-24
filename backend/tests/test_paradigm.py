"""
test_paradigm.py — OX-PARADIGM-1 Paradigm Evolution Protocol
  A — broad, confident theory, no anomalies → Stable Paradigm
  B — broad, confident theory + anomaly (drift/overconfidence/UU) → Paradigm Shift
  C — narrow/moderate theory, no anomaly → Paradigm Candidate
Plus anomaly sources and metrics. Read-only.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paradigm as PG


def _theory(pattern, domains, conf):
    return {"pattern": pattern, "supporting_domains": domains, "confidence": conf,
            "theory": f"{pattern} generalizes"}


def _in(bucket, pattern):
    return any(r["pattern"] == pattern for r in bucket)


def test_A_stable_paradigm():
    st = PG.evolve(theories=[_theory("github", ["pdf", "api", "web"], 0.88)],
                   drifts=[], calibration=[], unknowns_state={"unknown_unknowns": []})
    assert _in(st["stable_paradigms"], "github")
    assert not st["paradigm_shifts"] and not st["paradigm_candidates"]


def test_B_paradigm_shift_on_drift():
    st = PG.evolve(theories=[_theory("github", ["pdf", "api", "web"], 0.88)],
                   drifts=[{"belief": "github first", "pattern": "github", "severity": "high"}],
                   calibration=[], unknowns_state={"unknown_unknowns": []})
    assert _in(st["paradigm_shifts"], "github")
    shift = next(r for r in st["paradigm_shifts"] if r["pattern"] == "github")
    assert "recent belief drift" in shift["anomalies"]
    assert not st["stable_paradigms"]


def test_B_paradigm_shift_on_overconfidence_or_uu():
    over = PG.evolve(theories=[_theory("github", ["a", "b", "c"], 0.9)],
                     drifts=[], calibration=[{"subject": "github first", "status": "overconfident", "error": 0.4}],
                     unknowns_state={"unknown_unknowns": []})
    assert _in(over["paradigm_shifts"], "github")
    uu = PG.evolve(theories=[_theory("github", ["a", "b", "c"], 0.9)],
                   drifts=[], calibration=[],
                   unknowns_state={"unknown_unknowns": [{"item": "github"}]})
    assert _in(uu["paradigm_shifts"], "github")


def test_C_paradigm_candidate():
    # only 2 domains (< PARADIGM_DOMAINS) → emerging, not yet dominant
    st = PG.evolve(theories=[_theory("documentation", ["pdf", "api"], 0.78)],
                   drifts=[], calibration=[], unknowns_state={"unknown_unknowns": []})
    assert _in(st["paradigm_candidates"], "documentation")
    assert not st["stable_paradigms"] and not st["paradigm_shifts"]


def test_low_confidence_is_candidate_not_paradigm():
    # broad but under-confident → candidate, not stable paradigm
    st = PG.evolve(theories=[_theory("github", ["a", "b", "c", "d"], 0.72)],
                   drifts=[], calibration=[], unknowns_state={"unknown_unknowns": []})
    assert _in(st["paradigm_candidates"], "github") and not st["stable_paradigms"]


def test_metrics_and_brief():
    st = PG.evolve(theories=[_theory("github", ["a", "b", "c"], 0.9),
                             _theory("documentation", ["x", "y"], 0.8)],
                   drifts=[{"belief": "g", "pattern": "github"}],
                   calibration=[], unknowns_state={"unknown_unknowns": []})
    m = PG.metrics(st)
    assert m["paradigm_shifts"] == 1 and m["paradigm_candidates"] == 1
    assert "github" in m["shifting"]
    assert "PARADIGMS" in PG.render_brief(st)
