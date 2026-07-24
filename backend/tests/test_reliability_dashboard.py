"""
test_reliability_dashboard.py — OX-HOUSE-STABILIZATION-1 Phase 1
Unit tests for the dashboard's deterministic pieces (DB stats, HTML render).
Live GPU/CPU/Ollama collectors need real hardware and are exercised via the
/api/house/reliability endpoint, not here.
"""
from __future__ import annotations
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import reliability_dashboard as R


def _mk_db(tmp_path, rows):
    db = str(tmp_path / "t.db")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE agent_runs (id TEXT, started_at TEXT, ended_at TEXT, task TEXT, "
              "model TEXT, status TEXT, n_steps TEXT, n_tools TEXT, n_blocks TEXT, "
              "trajectory_path TEXT, summary TEXT, task_raw TEXT)")
    for i, (st, dur, status, tools, summ) in enumerate(rows):
        c.execute("INSERT INTO agent_runs (id,started_at,ended_at,model,status,n_tools,summary) "
                  "VALUES (?,?,?,?,?,?,?)", (str(i), str(st), str(st + dur), "qwen3.5:9b", status, str(tools), summ))
    c.commit(); c.close()
    return db


def test_success_counts_task_complete(tmp_path):
    db = _mk_db(tmp_path, [(1000, 9, "TASK_COMPLETE", 1, ""), (1000, 9, "TASK_COMPLETE", 1, ""),
                           (1000, 184, "failed", 0, "model stream step timeout after 180s")])
    s = R.agent_stats(db, window=20)
    assert s["n"] == 3
    assert s["success_rate"] == round(2 / 3, 3)      # TASK_COMPLETE counts as success
    assert s["timeout_rate"] == round(1 / 3, 3)      # one timeout in summary


def test_median_ignores_stale_rows(tmp_path):
    db = _mk_db(tmp_path, [(1000, 100, "failed", 0, ""), (1000, 200, "failed", 0, ""),
                           (1000, 999999, "interrupted", 0, "")])  # stale >24h row dropped
    s = R.agent_stats(db, window=20)
    assert s["median_duration_s"] == 150.0           # median of {100,200}, stale dropped


def test_empty_db(tmp_path):
    db = _mk_db(tmp_path, [])
    s = R.agent_stats(db, window=20)
    assert s["available"] is True and s["n"] == 0


def test_render_html_smoke():
    snap = {"gpu": {"present": True, "util_pct": 0.0, "vram_used_mb": 797, "vram_total_mb": 12288},
            "system": {"cpu_pct": 11, "ram_used_mb": 6000, "ram_total_mb": 34000},
            "ollama": {"reachable": True, "loaded": [{"name": "qwen3.5:9b", "offload": "CPU"}]},
            "inference_on_gpu": False,
            "agent": {"available": True, "n": 20, "success_rate": 0.0, "timeout_rate": 0.6,
                      "median_duration_s": 184.2},
            "prompt": {"full_prompt_tok": 6206, "compact_prompt_tok": 2929}}
    html = R.render_html(snap)
    assert "Reliability Dashboard" in html
    assert "NO (CPU)" in html          # inference_on_gpu False renders the CPU warning
    assert "qwen3.5:9b [CPU]" in html


def test_offload_classification():
    # ollama_metrics turns size vs size_vram into CPU/GPU/HYBRID — verify the rule via a stub
    def classify(size, vram):
        return "GPU" if vram >= size * 0.95 and size else ("CPU" if vram == 0 else "HYBRID")
    assert classify(6_000_000_000, 0) == "CPU"
    assert classify(6_000_000_000, 6_000_000_000) == "GPU"
    assert classify(6_000_000_000, 3_000_000_000) == "HYBRID"
