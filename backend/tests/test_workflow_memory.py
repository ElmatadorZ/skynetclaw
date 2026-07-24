"""
test_workflow_memory.py — OX-UI-1 Workflow Memory read-model (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import workflow_memory as W


_ROWS = [
    {"id": "r1", "task": "Build Discovery Layer", "status": "running",
     "summary": "working...", "n_steps": 3, "n_tools": 5, "started_at": 100.0,
     "trajectory_path": "/x.jsonl"},
    {"id": "r2", "task": "Fetch gold price", "status": "TASK_COMPLETE",
     "summary": "[done_when: gold.json exists] wrote gold.json [[EXEC_MEM]]{\"u\":[],\"a\":[]}",
     "n_steps": 4, "n_tools": 6, "started_at": 50.0},
    {"id": "r3", "task": "Broken task", "status": "blocked",
     "summary": "BLOCKED: dead end", "started_at": 10.0},
]


def test_active_run_sorts_first_and_is_not_archived():
    out = W.recent(_ROWS, limit=6)
    assert out[0]["id"] == "r1" and out[0]["archived"] is False
    assert out[0]["status"] == "thinking"
    print("  OK  the running mission sorts first and is not archived")


def test_done_when_parsed_and_footer_stripped():
    out = {e["id"]: e for e in W.recent(_ROWS, limit=6)}
    r2 = out["r2"]
    assert r2["done_when"] == "gold.json exists"
    assert "[[EXEC_MEM]]" not in r2["outcome"], "machine footer must be stripped"
    assert r2["status"] == "done" and r2["archived"] is True
    print("  OK  DONE_WHEN parsed; EXEC_MEM footer stripped; status translated")


def test_blocked_status_translated_not_raw():
    r3 = {e["id"]: e for e in W.recent(_ROWS, limit=6)}["r3"]
    assert r3["status"] == "blocked" and r3["archived"] is True
    assert "blocked" in r3["status_label"].lower()
    print("  OK  blocked run shown in operator language, archived")


def test_no_state_owned():
    import workflow_memory as mod, inspect
    src = inspect.getsource(mod)
    assert "CREATE TABLE" not in src and "INSERT INTO" not in src and "sqlite3" not in src
    print("  OK  read-model owns no state (shapes the existing agent_runs ledger)")


def main():
    print("=" * 56 + "\nOX-UI-1 WORKFLOW MEMORY\n" + "=" * 56)
    test_active_run_sorts_first_and_is_not_archived()
    test_done_when_parsed_and_footer_stripped()
    test_blocked_status_translated_not_raw()
    test_no_state_owned()
    print("\n  ALL WORKFLOW-MEMORY TESTS PASS — execution artifacts out of House Mind")
    return 0


if __name__ == "__main__":
    sys.exit(main())
