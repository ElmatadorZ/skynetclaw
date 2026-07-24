"""
test_attribution.py — OX-ATTRIBUTION-1 Outcome Attribution Engine (model-free)
  A — successful mission using a recalled capability → positive attribution.
  B — successful mission without any recall          → low attribution.
  C — failed mission despite recall                  → negative attribution.
Plus the cross-mission lift model (reinforce/demote), control grouping, persist.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import attribution as A


def test_A_positive_attribution_with_recall():
    s = A.mission_score("success", n_recalled=2)
    assert s > 0.5
    rec = A.record("m1", capabilities=["HTML Report Builder"], outcome="success",
                   path=Path("/nonexistent/skip.json"))  # path write may fail; record dict still returned
    assert rec["outcome"] == "success" and rec["attribution_score"] > 0
    assert rec["recalled_capabilities"] == ["HTML Report Builder"]


def test_B_low_attribution_without_recall():
    s = A.mission_score("success", n_recalled=0)
    assert 0.0 <= s <= 0.1                       # success but nothing recalled → low credit


def test_C_negative_attribution_on_failure_despite_recall():
    s = A.mission_score("failure", n_recalled=2)
    assert s < 0                                  # recall present, failure followed → blame
    assert A.mission_score("failure", n_recalled=0) == 0.0   # no recall → not implicated


def test_record_and_persist(tmp_path):
    p = tmp_path / "attribution.json"
    A.record("m1", capabilities=["Cap"], lessons=["L1"], control_verdict="improving",
             outcome="success", path=p)
    A.record("m2", capabilities=["Cap"], outcome="failure", path=p)
    recs = A.load_records(p)
    assert len(recs) == 2
    assert recs[0]["control_policy"] == "improving"


def test_cross_mission_lift_reinforce_and_demote(tmp_path):
    """The causal-ish signal: GoodCap recalled mostly on successes (positive lift);
    BadCap recalled mostly on failures (negative lift -> demote candidate)."""
    p = tmp_path / "attribution.json"
    # GoodCap: 4/4 success ; BadCap: 0/4 success ; baseline mixes both
    for i in range(4):
        A.record(f"g{i}", capabilities=["GoodCap"], outcome="success", path=p)
    for i in range(4):
        A.record(f"b{i}", capabilities=["BadCap"], outcome="failure", path=p)
    rep = A.attribute(path=p)
    assert rep["n_missions"] == 8
    assert rep["baseline"] == 0.5
    good = rep["capabilities"]["GoodCap"]
    bad = rep["capabilities"]["BadCap"]
    assert good["lift"] > 0 and good["recommendation"] == "reinforce"
    assert bad["lift"] < 0 and bad["recommendation"] == "demote"
    assert any(d["name"] == "BadCap" for d in rep["demote"])
    assert any(d["name"] == "GoodCap" for d in rep["reinforce"])


def test_insufficient_evidence_not_judged(tmp_path):
    p = tmp_path / "attribution.json"
    A.record("m1", capabilities=["Rare"], outcome="success", path=p)
    A.record("m2", lessons=["L"], outcome="failure", path=p)
    rep = A.attribute(path=p)
    assert rep["capabilities"]["Rare"]["recommendation"] == "insufficient_evidence"
    assert rep["demote"] == [] and rep["reinforce"] == []


def test_control_verdict_grouping(tmp_path):
    p = tmp_path / "attribution.json"
    for i in range(3):
        A.record(f"i{i}", capabilities=["C"], control_verdict="improving", outcome="success", path=p)
    A.record("r0", capabilities=["C"], control_verdict="regressing", outcome="failure", path=p)
    rep = A.attribute(path=p)
    assert rep["control"]["improving"]["success_rate"] == 1.0
    assert rep["control"]["regressing"]["success_rate"] == 0.0


def test_summary_answers_questions(tmp_path):
    p = tmp_path / "attribution.json"
    for i in range(4):
        A.record(f"g{i}", capabilities=["GoodCap"], outcome="success", path=p)
    for i in range(4):
        A.record(f"b{i}", capabilities=["BadCap"], outcome="failure", path=p)
    s = A.summary(path=p)
    assert "ATTRIBUTION" in s and "GoodCap" in s and "BadCap" in s
