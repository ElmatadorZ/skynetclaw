"""
test_observability.py — OX-OBSERVABILITY-1 read-only aggregator
  - workflow visible (timeline + active workflow_id + reached phase)
  - timeout/failure visible (failed phase + termination reason)
  - state source visible (state_id / updated_at / source)
  - cognitive stack visible (decision/theory/agenda/unknowns/paradigm)
  - graceful degradation when data is missing
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import observability as OB


def test_workflow_visible():
    row = {"workflow_id": "CD-1", "phase": "execute", "status": "active",
           "created_at": 1000.0, "updated_at": 1100.0, "directive": "build a report",
           "house_state_id": "hs_1", "agent_run_id": "run_1", "termination_reason": ""}
    v = OB.build_workflow_view(row)
    assert v["workflow_id"] == "CD-1"                  # B: active workflow_id
    assert v["current_phase"] == "EXECUTE"
    labels = [t["phase"] for t in v["timeline"] if t["reached"]]
    assert labels == ["DISPATCHED", "COMPREHEND", "PLAN", "COUNCIL", "EXECUTE"]   # A
    assert v["timeline"][-1]["reached"] is False        # COMPLETE not reached
    assert v["failed_phase"] is None                    # active, not failed
    assert v["house_state_id"] == "hs_1" and v["agent_run_id"] == "run_1"


def test_timeout_failure_visible():
    row = {"workflow_id": "CD-2", "phase": "comprehend", "status": "interrupted",
           "created_at": 1.0, "updated_at": 2.0,
           "termination_reason": "stream ended before terminal status"}
    v = OB.build_workflow_view(row)
    assert v["status"] == "interrupted"
    assert v["failed_phase"] == "COMPREHEND"            # D: where it died
    assert "stream ended" in v["termination_reason"]    # D: termination reason


def test_state_source_visible():
    st = {"id": "hs_42", "updated_at": 1730000000.0, "session_id": "sess-A",
          "status": "open", "question": "summarize AAPL", "confidence": 0.86}
    v = OB.build_house_state_view(st)
    assert v["state_id"] == "hs_42"                     # C
    assert v["updated_at"] == 1730000000.0
    assert v["source"] == "sess-A"                       # session id as source
    assert v["confidence"] == 0.86


def test_cognitive_stack_visible():
    cs = OB.build_cognitive_stack(
        decisions=[{"recommendation": "Documentation First", "confidence": 0.81}],
        theories=[{"theory": "Examples reduce ambiguity", "confidence": 0.84}],
        agenda=[{"topic": "Is github causal?", "priority_score": 0.7}],
        unknowns_metrics={"known_knowns": 2, "unknown_unknowns": 1},
        paradigm_metrics={"stable_paradigms": 1, "paradigm_shifts": 0},
        generated_at=1234.0)
    assert cs["decision"]["label"] == "Documentation First" and cs["decision"]["confidence"] == 0.81
    assert cs["theory"]["confidence"] == 0.84
    assert cs["research_agenda"]["label"] == "Is github causal?"
    assert cs["unknowns"]["unknown_unknowns"] == 1
    assert cs["paradigm"]["stable_paradigms"] == 1
    assert cs["generated_at"] == 1234.0                  # E: timestamp present


def test_graceful_degradation_on_missing_data():
    # G — every builder tolerates None / empty without raising
    assert OB.build_workflow_view(None)["workflow_id"] is None
    assert OB.build_house_state_view(None)["state_id"] is None
    cs = OB.build_cognitive_stack()
    assert cs["decision"]["label"] is None and cs["theory"]["count"] == 0


def test_snapshot_shape_live():
    # snapshot() must always return the panel sections, even on an empty system
    snap = OB.snapshot()
    for k in ("workflow", "house_state", "cognitive_stack", "generated_at"):
        assert k in snap
    assert "decision" in snap["cognitive_stack"] and "paradigm" in snap["cognitive_stack"]
