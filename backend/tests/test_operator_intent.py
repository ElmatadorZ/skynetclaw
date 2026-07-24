"""OPERATOR INTENT ENGINE — recovering probable operator intent from working
context. Verifies the RULE: a short/deictic directive is resolved against context
BEFORE being declared ambiguous, and only escalated to clarification when recovery
confidence is too low."""
import pathlib, sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import operator_intent as oi
from operator_intent import OperatorContext as Ctx


# ── the spec example: "ไหนอะ" + mission "Find Blueprint Files" → 87%, acts ──────
def test_spec_example_recovers_location_at_87():
    ri = oi.recover(Ctx(directive="ไหนอะ", mission="Find Blueprint Files"))
    assert ri.intent_type == oi.LOCATION
    assert ri.confidence == 87                       # the documented target
    assert ri.clarification_need is False            # confident enough to act
    assert "blueprint files" in ri.recovered_intent.lower()
    assert ri.anchor_source == "mission"


# ── the RULE: short directives are NOT immediately ambiguous ────────────────────
def test_short_directive_with_anchor_is_not_flagged_ambiguous():
    ri = oi.recover(Ctx(directive="ดูดิ", mission="Build the dashboard"))
    assert ri.intent_type == oi.DISPLAY
    assert ri.clarification_need is False
    assert "dashboard" in ri.recovered_intent.lower()
    assert ri.confidence >= oi.ACT_CONF


def test_elaborate_marker_with_cohering_mission():
    ri = oi.recover(Ctx(directive="ลองคิดดู", mission="Analyze the gold market"))
    assert ri.intent_type == oi.ELABORATE
    assert "gold market" in ri.recovered_intent.lower()
    assert ri.confidence >= oi.ACT_CONF             # coherence bonus applied


def test_reference_resolves_to_recent_deliberation():
    ri = oi.recover(Ctx(
        directive="อันนี้",
        recent_deliberation=[{"directive": "Should the House go risk-on into Q3?"}]))
    assert ri.intent_type == oi.REFERENCE
    assert ri.anchor_source == "recent_deliberation"
    assert "risk-on" in ri.recovered_intent.lower()


def test_english_deixis_this_one():
    ri = oi.recover(Ctx(directive="show this", mission="Generate the liquidity report"))
    assert ri.intent_type in (oi.DISPLAY, oi.REFERENCE)
    assert ri.anchor                                  # an anchor was resolved


# ── self-contained directives are taken at face value ──────────────────────────
def test_full_directive_passthrough():
    d = "Should the House increase gold allocation before the Fed meeting?"
    ri = oi.recover(Ctx(directive=d))
    assert ri.intent_type == oi.FULL
    assert ri.confidence == 90
    assert ri.clarification_need is False
    assert "self-contained" in ri.assumptions[0]


def test_long_directive_with_deictic_word_is_full():
    d = "Please analyze the Q3 liquidity outlook and recommend a position with invalidation."
    ri = oi.recover(Ctx(directive=d))
    assert ri.intent_type == oi.FULL                 # not ELABORATE — it's a real task


# ── genuine ambiguity: no anchor → clarify (but still return a best guess) ──────
def test_no_anchor_requests_clarification():
    ri = oi.recover(Ctx(directive="อันนี้"))          # nothing in context
    assert ri.intent_type == oi.REFERENCE
    assert ri.clarification_need is True
    assert ri.clarification_question
    assert ri.confidence < oi.ACT_CONF
    assert ri.recovered_intent                        # best-guess intent still present
    assert ri.anchor == ""


def test_empty_directive():
    ri = oi.recover(Ctx(directive="   "))
    assert ri.clarification_need is True
    assert ri.confidence == 0


# ── anchor priority + confidence behaviour ─────────────────────────────────────
def test_recent_deliberation_outranks_mission_as_anchor():
    ri = oi.recover(Ctx(
        directive="ตัวนี้",
        mission="Find Blueprint Files",
        recent_deliberation=[{"directive": "Evaluate the new freight route"}]))
    assert ri.anchor_source == "recent_deliberation"
    assert "freight" in ri.recovered_intent.lower()


def test_confidence_is_bounded():
    ri = oi.recover(Ctx(
        directive="ไหนอะ", mission="Find Blueprint Files",
        recent_deliberation=[{"directive": "Find Blueprint Files location"}],
        house_state={"question": "Where are the Blueprint Files?"},
        recent_conversation=["where did we put them"],
        workspace="blueprints/", active_agent="Scout"))
    assert ri.confidence <= oi.CONF_CAP
    assert ri.clarification_need is False


def test_active_agent_recorded_in_assumptions():
    ri = oi.recover(Ctx(directive="ดูดิ", mission="Build the dashboard", active_agent="Architect"))
    assert any("Architect" in a for a in ri.assumptions)


# ── output contract ────────────────────────────────────────────────────────────
def test_to_dict_shape():
    d = oi.recover(Ctx(directive="ไหนอะ", mission="Find Blueprint Files")).to_dict()
    for k in ("directive", "intent_type", "recovered_intent", "confidence",
              "assumptions", "clarification_need", "clarification_question",
              "anchor", "anchor_source"):
        assert k in d
    assert isinstance(d["assumptions"], list)
    assert isinstance(d["confidence"], int)


def test_format_for_council_renders():
    ri = oi.recover(Ctx(directive="ไหนอะ", mission="Find Blueprint Files"))
    out = oi.format_for_council(ri)
    assert "OPERATOR INTENT" in out and "87%" in out


# ── House-aware convenience: pulls live context without deliberation wiring ─────
def test_from_house_pulls_state_and_recent(db):
    import house_state as hs
    import council_memory as cm
    # seed a recent deliberation + an open House Mind state
    cm.from_verdict("Should the House go risk-on into Q3?", {
        "analyst": {"known": ["BTC 64000"], "data_gaps": ["Fed dot plot"]},
        "skeptic": {"verdict": "REBUILD", "reason": "liquidity thin"},
        "aggregate_recommendation": "Phase in, hedge tail risk.",
    }, model="test", path=db)
    hs.open_state("Where are the Q3 risk levels?", bootstrap=False, path=db)

    ri = oi.from_house("ดูดิ", path=db)
    assert ri.intent_type == oi.DISPLAY
    assert ri.anchor                                  # resolved from live House memory
    assert ri.anchor_source in ("recent_deliberation", "mission", "house_state")


def test_from_house_safe_on_empty_db(db):
    ri = oi.from_house("อันนี้", path=db)
    assert ri.clarification_need is True              # nothing to anchor to yet
    assert ri.recovered_intent


# ── THE FULL LOOP: ask → think → predict → (grade/learn deferred) → change belief ──
# Proves operator_intent's ASK stage is wired into run_council and that one
# deliberation closes the synchronous side of the learning loop. The LLM is
# stubbed; everything else is the real pipeline against a temp DB.
def test_run_council_closes_the_learning_loop(db, monkeypatch):
    import asyncio
    import agent_council as ac
    import institutional_db as idb
    import house_state as hs

    assert ac._OINTENT is True                        # ASK stage is wired in

    canned = {
        "verdict": "CONSISTENT", "confidence": 0.7,
        "known": ["BTC at 64000 per market data"], "data_gaps": ["Fed dot plot"],
        "scenario": "BTC will rally into Q3", "invalidation": "invalidation below 58k",
        "early_warning_1": "liquidity is thin",
        "hook": "Phase in, hedge tail risk.", "runtime_decision": "auto",
    }
    seen_prompts = []

    async def fake_llm(system, user, **kw):
        seen_prompts.append(user)
        return {"ok": True, "json": dict(canned)}

    monkeypatch.setattr(ac, "_llm_call_json", fake_llm)

    verdict = asyncio.run(ac.run_council(
        "Should the House go risk-on into Q3?", context={}, model="test"))

    # ── ถาม: the operator intent was recovered and injected into deliberation ──
    assert any("OPERATOR INTENT" in p for p in seen_prompts)

    # ── คิด: the deliberation was persisted as a council session ──
    with idb.connect(db) as c:
        n_sessions = c.execute("SELECT COUNT(*) n FROM council_sessions").fetchone()["n"]
        n_pred = c.execute("SELECT COUNT(*) n FROM predictions").fetchone()["n"]
    assert n_sessions >= 1

    # ── ทำนาย: a falsifiable prediction was extracted (has an invalidation) ──
    assert n_pred >= 1

    # ── เปลี่ยนความเชื่อ: the House Mind now holds a belief from the verdict ──
    state = hs.current(db)
    assert state is not None
    assert state["items"]["belief"], "House Mind should hold a belief after the verdict"

    assert verdict.aggregate_recommendation
