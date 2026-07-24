"""
test_reinforcement.py — OX-REINFORCEMENT-1 Capability Reinforcement (model-free)
  A — positive attribution → weight increases.
  B — negative attribution → weight decreases.
  C — neutral attribution  → no significant change.
  D — repeated reinforcement → capability ordering changes.
Plus bounded/gradual updates, demoted→warning, and recall ordering.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import reinforcement as R


def _report(caps):
    """caps: {name: (lift, evidence, recommendation)}"""
    return {"capabilities": {n: {"lift": l, "recalled_in": e, "recommendation": rec}
                             for n, (l, e, rec) in caps.items()}}


def test_A_positive_lift_increases_weight():
    w = R.reinforce(_report({"HTML": (0.45, 12, "reinforce")}), prior={})
    assert w["HTML"]["weight"] > R.W_BASE
    assert w["HTML"]["status"] == "reinforced"


def test_B_negative_lift_decreases_weight():
    w = R.reinforce(_report({"PDF": (-0.545, 10, "demote")}), prior={})
    assert w["PDF"]["weight"] < R.W_BASE
    assert w["PDF"]["status"] == "demoted"


def test_C_neutral_lift_no_significant_change():
    w = R.reinforce(_report({"Mid": (0.03, 8, "neutral")}), prior={})
    assert w["Mid"]["weight"] == R.W_BASE and w["Mid"]["status"] == "observed"
    # insufficient evidence is also observe-only, even with a big lift
    w2 = R.reinforce(_report({"Rare": (0.9, 1, "insufficient_evidence")}), prior={})
    assert w2["Rare"]["weight"] == R.W_BASE and w2["Rare"]["status"] == "observed"


def test_updates_are_gradual_and_bounded():
    # one mission can't move a weight more than MAX_STEP
    w = R.reinforce(_report({"X": (1.0, 50, "reinforce")}), prior={})
    assert w["X"]["weight"] - R.W_BASE <= R.MAX_STEP + 1e-9
    # repeated huge positive lift converges but never exceeds the cap
    weights = {}
    for _ in range(50):
        weights = R.reinforce(_report({"X": (1.0, 50, "reinforce")}), prior=weights)
    assert weights["X"]["weight"] <= R.W_MAX
    # repeated huge negative lift never drops below the floor
    weights = {}
    for _ in range(50):
        weights = R.reinforce(_report({"Y": (-1.0, 50, "demote")}), prior=weights)
    assert weights["Y"]["weight"] >= R.W_MIN


def test_D_repeated_reinforcement_changes_ordering():
    caps = [{"name": "A", "polarity": "capability"}, {"name": "B", "polarity": "capability"}]
    # initially equal weights → order preserved-ish; reinforce B repeatedly
    weights = {}
    for _ in range(5):
        weights = R.reinforce(_report({"B": (0.5, 12, "reinforce")}), prior=weights)
    ordered = R.apply_to_recall(caps, weights=weights)
    assert ordered[0]["name"] == "B"               # B rose above A
    assert weights["B"]["weight"] > R.W_BASE


def test_demoted_capability_becomes_warning():
    weights = {}
    for _ in range(8):
        weights = R.reinforce(_report({"Bad": (-0.6, 12, "demote")}), prior=weights)
    caps = [{"name": "Bad", "polarity": "capability"}, {"name": "Good", "polarity": "capability"}]
    ordered = R.apply_to_recall(caps, weights=weights)
    bad = next(c for c in ordered if c["name"] == "Bad")
    assert bad["polarity"] == "warning" and bad.get("demoted") is True
    assert ordered[0]["name"] == "Good"            # demoted sinks below positive caps


def test_persist_and_status(tmp_path):
    p = tmp_path / "capability_weights.json"
    rep = _report({"HTML": (0.45, 12, "reinforce"), "PDF": (-0.5, 10, "demote")})
    # gradual: a few missions of consistent evidence cross the trust/avoid bands
    weights = {}
    for _ in range(4):
        weights = R.reinforce(rep, prior=weights, path=p, persist=True)
    loaded = R.load(p)
    assert "HTML" in loaded and "PDF" in loaded
    assert loaded["HTML"]["weight"] >= R.REINFORCE_AT and loaded["PDF"]["weight"] <= R.DEMOTE_AT
    s = R.status(loaded)
    assert any(w["capability"] == "HTML" for w in s["trusted"])
    assert any(w["capability"] == "PDF" for w in s["avoid"])
    assert "HTML" in R.summary(loaded)
