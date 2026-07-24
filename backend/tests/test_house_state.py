"""HOUSE STATE ENGINE — the House Mind. Tests the shared cognitive state, belief
evolution, and the five questions the House must be able to answer."""
import time, pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import house_state as hs


def _blueprint_state(db):
    sid = hs.open_state("Where are the Agent Blueprints?", bootstrap=False, path=db)
    hs.add_known_fact(sid, "Skills exist", agent="Analyst", path=db)
    hs.add_known_fact(sid, "Obsidian exists", agent="Scout", path=db)
    hs.add_unknown_fact(sid, "Blueprint location", agent="Scout", path=db)
    hs.add_hypothesis(sid, "Blueprints stored in Obsidian", confidence=0.68, agent="Scout", path=db)
    hs.add_contradiction(sid, "No blueprint files detected", agent="Auditor", path=db)
    hs.add_minority(sid, "Blueprints may not exist", agent="Skeptic", path=db)
    return sid


# ── the five questions the House must answer ────────────────────────────────
def test_house_answers_five_questions(db):
    sid = _blueprint_state(db)
    hs.add_belief(sid, "Blueprints are in Obsidian", confidence=0.6, agent="Atlas",
                  reason="vault structure", evidence="obsidian_search", path=db)
    a = hs.answer(sid, db)
    assert a["what_we_know"] == ["Skills exist", "Obsidian exists"]
    assert "Blueprint location" in a["what_we_dont_know"]
    assert a["what_we_believe"] and a["what_we_believe"][0]["confidence"] == 0.6
    assert a["why_we_believe"]               # evidence / reasons present
    assert a["contradictions"] and a["minority_view"]

def test_what_changed_our_mind(db):
    sid = _blueprint_state(db)
    hs.add_belief(sid, "Blueprints NOT in Obsidian", confidence=0.40, agent="Scout", reason="guess", path=db)
    hs.update_belief(sid, "Blueprints ARE in Obsidian", confidence=0.70, agent="Atlas",
                     reason="Vault structure discovered", evidence="obsidian_search result", path=db)
    a = hs.answer(sid, db)
    chg = a["what_changed_our_mind"][0]
    assert chg["agent"] == "Atlas"
    assert chg["confidence_impact"] == 0.3
    assert chg["reason"] == "Vault structure discovered"
    assert chg["evidence"] == "obsidian_search result"


# ── belief evolution mechanics ──────────────────────────────────────────────
def test_belief_supersedes_previous(db):
    sid = hs.open_state("q", bootstrap=False, path=db)
    hs.add_belief(sid, "A", confidence=0.3, agent="X", path=db)
    hs.add_belief(sid, "B", confidence=0.5, agent="Y", path=db)
    st = hs.read_state(sid, db)
    beliefs = st["items"]["belief"]
    assert len(beliefs) == 1 and beliefs[0]["content"] == "B"   # only current belief is active

def test_confidence_impact_can_be_negative(db):
    sid = hs.open_state("q", bootstrap=False, path=db)
    hs.add_belief(sid, "A", confidence=0.8, agent="X", path=db)
    ch = hs.update_belief(sid, "A revised down", confidence=0.4, agent="Skeptic",
                          reason="counter-evidence", path=db)
    assert ch["confidence_impact"] == -0.4


# ── confidence recompute (contradictions + unknowns reduce it) ──────────────
def test_contradictions_lower_confidence(db):
    sid = hs.open_state("q", bootstrap=False, path=db)
    hs.add_belief(sid, "B", confidence=0.9, agent="X", path=db)
    before = hs.read_state(sid, db)["confidence"]
    hs.add_contradiction(sid, "but X conflicts", agent="Skeptic", path=db)
    after = hs.read_state(sid, db)["confidence"]
    assert after < before


# ── state reuse: same question accumulates one mind ─────────────────────────
def test_open_state_reuses_same_question(db):
    a = hs.open_state("how to handle the risk-on call", bootstrap=False, path=db)
    b = hs.open_state("how to handle the risk-on call", bootstrap=False, path=db)
    assert a == b   # one living state, not a reset

def test_distinct_questions_get_distinct_states(db):
    a = hs.open_state("question about gold prices", bootstrap=False, path=db)
    b = hs.open_state("entirely different topic quantum widgets", bootstrap=False, path=db)
    assert a != b


# ── update from a council verdict (the House State Update step) ─────────────
def test_update_from_verdict_folds_into_mind(db):
    sid = hs.open_state("risk-on Q3?", bootstrap=False, path=db)
    v = {"analyst": {"known": ["BTC 64000"], "data_gaps": ["Fed path"]},
         "forecaster": {"scenario": "rally likely", "confidence": 0.6},
         "skeptic": {"verdict": "FRAGILE", "reason": "thin liquidity"},
         "governance": {"governance_score": 0.71},
         "aggregate_recommendation": "Phase in, hedge."}
    hs.update_from_verdict(sid, v, path=db)
    a = hs.answer(sid, db)
    assert "BTC 64000" in a["what_we_know"]
    assert "Fed path" in a["what_we_dont_know"]
    assert a["what_we_believe"][0]["belief"].startswith("Phase in")
    assert a["contradictions"] and a["minority_view"]
    assert a["hypotheses"]


# ── self-knowledge (fixes "the council doesn't know itself") ────────────────
def test_self_facts_bootstrapped(db):
    sid = hs.open_state("how many agents does the council have?", path=db)  # self-referential
    a = hs.answer(sid, db)
    assert any("14 members" in f or "council of 14" in f for f in a["what_we_know"])


# ── consciousness rule: the readable shared block ───────────────────────────
def test_format_for_council_block(db):
    sid = _blueprint_state(db)
    hs.add_belief(sid, "Blueprints in Obsidian", confidence=0.6, agent="Atlas", path=db)
    text = hs.format_state_for_council(hs.read_state(sid, db))
    assert "THE HOUSE MIND" in text and "Known facts" in text
    assert "read before you deliberate" in text and "ONE mind" in text

def test_current_returns_latest(db):
    s1 = hs.open_state("first topic alpha", bootstrap=False, path=db)
    time.sleep(0.01)
    s2 = hs.open_state("second topic bravo", bootstrap=False, path=db)
    hs.add_known_fact(s2, "fact", path=db)
    assert hs.current(db)["id"] == s2
