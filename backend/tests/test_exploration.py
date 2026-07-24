"""
test_exploration.py — OX-EXPLORATION-1 Adaptive Exploration Protocol
  A conf 0.95 → rate 0.05 · B conf 0.80 → 0.15 · C conf 0.60 → 0.30 · D none → 1.00
  E alternative wins repeatedly (>=5) → promotion_candidate
  F alternative wins once → no promotion
Plus candidate generation, selection (epsilon-greedy), and recall reorder.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import exploration as EX


# ── POLICY (A–D) ──────────────────────────────────────────────────────────────
def test_A_high_confidence_rate():
    assert EX.exploration_rate(0.95) == 0.05


def test_B_medium_confidence_rate():
    assert EX.exploration_rate(0.80) == 0.15


def test_C_low_confidence_rate():
    assert EX.exploration_rate(0.60) == 0.30


def test_D_no_strategy_full_exploration():
    assert EX.exploration_rate(None) == 1.00


# ── candidate generation ──────────────────────────────────────────────────────
def test_candidate_generation_bounded_and_deterministic():
    primary, alts = EX.candidates(["github", "documentation", "web_search"])
    assert primary == ["github", "documentation", "web_search"]
    assert len(alts) <= EX.MAX_ALT_CANDIDATES
    assert all(a != primary for a in alts)
    assert ["documentation", "github", "web_search"] in alts   # swap-first-two path
    # determinism: same input → same candidates
    assert EX.candidates(["github", "documentation", "web_search"])[1] == alts


# ── selection (epsilon-greedy, injectable rng) ───────────────────────────────
def test_selection_primary_when_rng_high(tmp_path):
    strat = {"recommended_order": ["github", "documentation"], "confidence": 0.95}
    sel = EX.select("pdf", strategy=strat, rng=lambda: 0.99, path=tmp_path / "e.json")
    assert sel["exploration"] is False and sel["selected_strategy"] == ["github", "documentation"]


def test_selection_explores_when_rng_low(tmp_path):
    strat = {"recommended_order": ["github", "documentation"], "confidence": 0.60}  # rate 0.30
    sel = EX.select("pdf", strategy=strat, rng=lambda: 0.0, path=tmp_path / "e.json")
    assert sel["exploration"] is True and sel["selected_strategy"] != ["github", "documentation"]


def test_no_strategy_selects_empty_exploration(tmp_path):
    sel = EX.select("novel", strategy=None, rng=lambda: 0.5, path=tmp_path / "e.json")
    assert sel["exploration"] is True and sel["selected_strategy"] == []
    assert sel["exploration_rate"] == 1.00


# ── E: alternative wins repeatedly → promotion candidate ─────────────────────
def test_E_alternative_wins_repeatedly_flags_promotion(tmp_path):
    p = tmp_path / "e.json"
    alt = ["documentation", "github"]
    prim = ["github", "documentation"]
    # primary: mostly failing
    for _ in range(6):
        EX.record_outcome("pdf", prim, exploration=False, outcome="failure", path=p)
    # alternative: 5+ wins
    for _ in range(6):
        EX.record_outcome("pdf", alt, exploration=True, outcome="success", path=p)
    res = EX.detect_improvements("pdf", path=p)
    cand = next(r for r in res if r["alternative"] == alt)
    assert cand["promotion_candidate"] is True
    assert cand["alt_success_rate"] > cand["primary_success_rate"]
    assert cand["alt_evidence"] >= 5
    # counter persisted
    prof = EX.lookup_exploration_profile("pdf", path=p)
    assert prof and prof.get("times_improved", 0) >= 1


def test_F_alternative_wins_once_no_promotion(tmp_path):
    p = tmp_path / "e.json"
    for _ in range(6):
        EX.record_outcome("api", ["github"], exploration=False, outcome="failure", path=p)
    EX.record_outcome("api", ["documentation"], exploration=True, outcome="success", path=p)  # once
    res = EX.detect_improvements("api", path=p)
    cand = next(r for r in res if r["alternative"] == ["documentation"])
    assert cand["promotion_candidate"] is False     # evidence < 5
    assert cand["alt_evidence"] == 1


# ── recall reorder + metrics ──────────────────────────────────────────────────
def test_reorder_applies_selected_order():
    assert EX.reorder(["github", "documentation", "web_search"],
                      ["documentation", "github"]) == ["documentation", "github", "web_search"]


def test_metrics(tmp_path):
    p = tmp_path / "e.json"
    EX.record_outcome("pdf", ["documentation", "github"], exploration=True, outcome="success", path=p)
    EX.record_outcome("pdf", ["github", "documentation"], exploration=False, outcome="success", path=p)
    m = EX.metrics(path=p)
    assert m["total_records"] == 2
    assert m["exploration_success_rate"] == 1.0
    assert m["most_discovered_gap_types"][0][0] == "pdf"
