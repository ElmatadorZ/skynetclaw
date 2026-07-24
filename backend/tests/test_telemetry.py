"""
test_telemetry.py — OX-TELEMETRY-1 Improvement Telemetry (model-free)
Measures whether the House is improving: compares a recent window of runs against
a prior window and reports direction + size of change.
  A — improving runs   → verdict "improving", score > 0.
  B — regressing runs  → verdict "regressing", score < 0.
  C — too few runs     → "insufficient_data".
Plus metric correctness, flat detection, and rendering.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import telemetry as T


def _run(i, status, steps=5, tools=6, blocks=0, summary=""):
    return {"id": f"r{i}", "started_at": 1000 + i, "status": status,
            "n_steps": steps, "n_tools": tools, "n_blocks": blocks, "summary": summary}


def _sc(runs):
    # pass lessons/caps explicitly so the test never touches real registries
    return T.scorecard(runs=runs, lessons=[], caps=[])


def test_C_insufficient_data():
    sc = _sc([_run(0, "TASK_COMPLETE"), _run(1, "limit")])
    assert sc["verdict"] == "insufficient_data"
    assert "insufficient data" in T.render(sc)


def test_metric_correctness():
    runs = [_run(0, "TASK_COMPLETE"), _run(1, "limit", blocks=2),
            _run(2, "TASK_COMPLETE"), _run(3, "blocked")]
    m = T._win_metrics(runs)
    assert m["n"] == 4
    assert m["completion_rate"] == 0.5            # 2/4
    assert m["block_rate"] == 0.25                # 1/4 had n_blocks>0
    assert m["dead_end_rate"] == 0.5              # limit + blocked


def test_A_improving():
    # prior: mostly fail; recent: mostly complete + fewer blocks
    prior = [_run(i, "limit", blocks=2) for i in range(4)]
    recent = [_run(10 + i, "TASK_COMPLETE", blocks=0) for i in range(4)]
    sc = _sc(prior + recent)
    assert sc["verdict"] == "improving"
    assert sc["score"] > 0
    assert sc["deltas"]["completion_rate"] > 0
    assert sc["deltas"]["dead_end_rate"] < 0       # fewer dead-ends = improvement
    assert any("completion_rate" in d for d in sc["drivers"])


def test_B_regressing():
    prior = [_run(i, "TASK_COMPLETE", blocks=0) for i in range(4)]
    recent = [_run(10 + i, "limit", blocks=2) for i in range(4)]
    sc = _sc(prior + recent)
    assert sc["verdict"] == "regressing"
    assert sc["score"] < 0
    assert sc["deltas"]["completion_rate"] < 0


def test_flat():
    runs = [_run(i, "TASK_COMPLETE", blocks=0) for i in range(8)]
    sc = _sc(runs)
    assert sc["verdict"] == "flat"
    assert abs(sc["score"]) < 0.05


def test_exec_confidence_from_footer():
    import json
    def mk(i, status, c):
        return _run(i, status, summary=f"done [[EXEC_MEM]]{json.dumps({'c': c, 'b': False})}")
    prior = [mk(i, "TASK_COMPLETE", 0.4) for i in range(3)]
    recent = [mk(10 + i, "TASK_COMPLETE", 0.9) for i in range(3)]
    sc = _sc(prior + recent)
    assert sc["windows"]["prior"]["exec_confidence"] == 0.4
    assert sc["windows"]["recent"]["exec_confidence"] == 0.9
    assert sc["deltas"]["exec_confidence"] > 0
    assert sc["verdict"] == "improving"


def test_learning_accrual_reported():
    sc = T.scorecard(runs=[_run(i, "TASK_COMPLETE") for i in range(4)],
                     lessons=[{"id": "a"}, {"id": "b"}], caps=[{"name": "X"}])
    assert sc["learning"] == {"lessons": 2, "capabilities": 1}
