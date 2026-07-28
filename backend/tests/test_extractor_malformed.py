"""
test_extractor_malformed.py — a corrupt claim must never reach the clock
=========================================================================
Two rows in the live predictions table could not be judged by anyone:

    statement  : {'prob': 0.55, 'outcome': 'SkynetClaw จะเพิ่มความน่าเชื่อถือ...'}
    invalidation: s": 7, "invalidation": "ผู้ใช้ไม่เลือก backport security",

Neither was a coincidence.

`_txt()` renders a dict with json.dumps, and `_find_invalidation` then sliced a
raw character window out of that JSON — `t[start-8 : end+40]` — which lands
mid-token. Separately, `_claim_statement` did `", ".join(map(str, v))` over a
list of scenario dicts, so a Python repr became the claim.

The damage was not cosmetic. A corrupt claim looks falsifiable, sits on the clock
as `pending` forever, and because `on_outcome()` waits for its session to be
fully graded, it blocks every dissent recorded beside it. That is how nine
dissents went unresolved.

These tests use the exact shapes observed in production.

    python -m pytest tests/test_extractor_malformed.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import extractor as ex  # noqa: E402


# ── the invalidation parser ──────────────────────────────────────────────────
def test_reads_invalidation_from_json_structurally():
    """The field, not a window cut out of the serialised form."""
    blob = json.dumps({"horizon_days": 7,
                       "invalidation": "ผู้ใช้ไม่เลือก backport security",
                       "confidence": 0.8}, ensure_ascii=False)
    got = ex._find_invalidation(blob)
    assert got == "ผู้ใช้ไม่เลือก backport security"
    assert '"' not in got and ":" not in got


def test_never_returns_the_production_debris():
    """The exact corrupt value recorded on 2026-07-12 must not recur."""
    blob = json.dumps({"days": 7,
                       "invalidation": "ผู้ใช้ไม่เลือก backport security",
                       "next": "something else"}, ensure_ascii=False)
    got = ex._find_invalidation(blob)
    assert not got.startswith('s"')
    assert '"invalidation"' not in got
    assert "next" not in got, "must not run on into the following field"


def test_finds_invalidation_nested_in_a_scenario_list():
    blob = json.dumps({"prediction": [
        {"prob": 0.55, "outcome": "cost rises",
         "invalidation": "if GPU cost falls below baseline"}]}, ensure_ascii=False)
    assert ex._find_invalidation(blob) == "if GPU cost falls below baseline"


def test_plain_prose_invalidation_still_works():
    txt = "We expect throughput to hold. Invalidation: if p99 latency doubles."
    got = ex._find_invalidation(txt)
    assert "p99" in got and "latency" in got


def test_absent_invalidation_returns_empty_not_debris():
    assert ex._find_invalidation('{"forecast": "things improve"}') == ""
    assert ex._find_invalidation("") == ""


# ── the claim parser ─────────────────────────────────────────────────────────
def test_scenario_list_of_dicts_yields_readable_text_not_a_repr():
    block = {"scenario": [{"prob": 0.55, "outcome": "SkynetClaw gains reliability"},
                          {"prob": 0.45, "outcome": "no measurable change"}]}
    got = ex._claim_statement("forecaster", block)
    assert "SkynetClaw gains reliability" in got
    assert "prob" not in got and "{" not in got and "'" not in got


def test_structured_block_with_nothing_readable_is_skipped():
    """Better to extract nothing than to stake an object as a claim."""
    block = {"scenario": [{"prob": 0.55, "weight": 3}]}
    assert ex._claim_statement("forecaster", block) == ""


def test_plain_string_scenario_is_unchanged():
    block = {"scenario": "GPU cost rises while system efficiency improves"}
    assert ex._claim_statement("forecaster", block) == \
        "GPU cost rises while system efficiency improves"


# ── the gate ─────────────────────────────────────────────────────────────────
def test_gate_rejects_a_serialised_statement():
    bad = {"statement": "{'prob': 0.55, 'outcome': 'SkynetClaw จะเพิ่ม'}",
           "invalidation": "if the user declines the backport"}
    assert "serialised object" in ex._rejects(bad)


def test_gate_rejects_a_json_fragment_invalidation():
    bad = {"statement": "SkynetClaw will choose the full backport",
           "invalidation": 's": 7, "invalidation": "ผู้ใช้ไม่เลือก backport",'}
    assert "serialised data" in ex._rejects(bad)


def test_gate_rejects_an_empty_invalidation():
    assert "invalidation too short" in ex._rejects(
        {"statement": "throughput will improve materially", "invalidation": ""})


def test_gate_passes_a_sound_prediction():
    good = {"statement": "SkynetClaw will choose the full security backport",
            "invalidation": "if the operator declines the backport"}
    assert ex._rejects(good) == ""


def test_a_malformed_verdict_stakes_nothing(monkeypatch):
    """End to end: the corrupt shape that reached production is now refused."""
    staked = []
    monkeypatch.setattr(ex._out, "record_prediction",
                        lambda **kw: staked.append(kw) or "pr_x")
    monkeypatch.setattr(ex._out, "has_pending", lambda *a, **k: False)
    monkeypatch.setattr(ex, "extract_predictions", lambda v: [{
        "statement": "{'prob': 0.4, 'outcome': 'Insufficient information'}",
        "originating_agent": "Forecaster", "participants": ["Forecaster"],
        "invalidation": 's": 1, "invalidation": "User does not respond",',
        "metric": "", "direction": "flat", "horizon_primary": "7",
        "confidence": 0.4, "evidence_source": "unsourced",
    }])

    pids = ex.record_from_verdict({}, session_id="cs_test")
    assert pids == [] and staked == [], "a corrupt claim must never reach the clock"
