"""
test_execution_fastpath.py — OX-EXECUTION-RECOVERY-1
Unit tests for the execution-recovery wiring + the benchmark's pure logic.
(The live agent run is exercised by benchmark_execution.run_suite, which needs a
running server; here we test the deterministic pieces + the config fix.)
"""
from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import benchmark_execution as B

_ROOT = Path(__file__).resolve().parent.parent


def test_targets_match_mission():
    assert B.TARGETS["A_create"]["min_rate"] == 1.0
    assert B.TARGETS["B_read"]["min_rate"] == 1.0
    assert B.TARGETS["C_modify"]["min_rate"] == 1.0
    assert B.TARGETS["D_search"]["min_rate"] == 1.0
    assert B.TARGETS["E_consecutive"]["min_rate"] == 0.90
    assert B.TARGETS["F_latency"]["max_latency_s"] == 15.0


def test_build_tasks_shape(tmp_path):
    tasks = B.build_tasks(str(tmp_path))
    ids = [t["id"] for t in tasks]
    assert ids == ["A_create", "B_read", "C_modify", "D_search"]
    assert all("task" in t and "verify" in t for t in tasks)


def test_evaluate_all_pass():
    sc = B.evaluate({
        "A_create": {"rate": 1.0}, "B_read": {"rate": 1.0}, "C_modify": {"rate": 1.0},
        "D_search": {"rate": 1.0}, "E_consecutive": {"rate": 0.95}, "F_latency": {"latency": 8.2},
    })
    assert sc["_overall_pass"] is True
    assert sc["F_latency"]["pass"] and sc["E_consecutive"]["pass"]


def test_evaluate_latency_fail():
    sc = B.evaluate({
        "A_create": {"rate": 1.0}, "B_read": {"rate": 1.0}, "C_modify": {"rate": 1.0},
        "D_search": {"rate": 1.0}, "E_consecutive": {"rate": 1.0}, "F_latency": {"latency": 55.0},
    })
    assert sc["_overall_pass"] is False          # 55s > 15s target
    assert sc["F_latency"]["pass"] is False


def test_evaluate_consecutive_below_threshold():
    sc = B.evaluate({
        "A_create": {"rate": 1.0}, "B_read": {"rate": 1.0}, "C_modify": {"rate": 1.0},
        "D_search": {"rate": 1.0}, "E_consecutive": {"rate": 0.80}, "F_latency": {"latency": 9.0},
    })
    assert sc["E_consecutive"]["pass"] is False   # 80% < 90%
    assert sc["_overall_pass"] is False


def test_exec_model_configured():
    """The execution path must be routed to a fast model (config fix).

    settings.json is per-install and git-ignored, so on a clean checkout it does
    not exist yet. Fall back to the shipped template: the assertion is about the
    contract (exec_model is configured), not about the operator's own file.
    """
    cfg = _ROOT / "settings.json"
    if not cfg.exists():
        cfg = _ROOT / "settings.example.json"
    if not cfg.exists():
        import pytest
        pytest.skip("no settings.json or settings.example.json — nothing to check")
    s = json.loads(cfg.read_text(encoding="utf-8"))
    assert s.get("exec_model"), f"exec_model must be set in {cfg.name} for the execution path"


def test_agent_payload_disables_thinking():
    """The agent payload must set think=false on the local execution path."""
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    assert 'payload["think"] = False' in src
    assert "exec_model" in src and "_exec_is_cloud" in src
