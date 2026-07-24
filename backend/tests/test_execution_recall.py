"""
test_execution_recall.py — OX-1.5 Execution Memory validation (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import execution_recall as ER
import world_model as W


def test_footer_roundtrip():
    snap = {"exists": ["/a"], "absent": ["/x/y.py"], "absent_tools": ["frobnicate"], "n": 3}
    foot = ER.encode_footer(snap, 0.42, blocked=True, halt="BLOCKED: dead end", final_status="BLOCKED")
    base = "did some work"
    mem = ER.parse_footer(base + foot)
    assert mem["u"] == ["frobnicate"] and mem["a"] == ["/x/y.py"]
    assert mem["b"] is True and mem["s"] == "BLOCKED" and mem["c"] == 0.42
    # a summary with no footer parses to empty (no fabrication)
    assert ER.parse_footer("no footer here") == {}
    print("  OK  footer encodes into / parses out of the existing summary column")


def test_recall_unknown_tools_are_task_independent():
    rows = [
        {"task": "build a telegram bot", "summary": "x" + ER.encode_footer(
            {"absent_tools": ["frobnicate"], "absent": [], "exists": []}, 0.5, False, "", "success")},
    ]
    # a totally unrelated task still recalls the unknown tool (tool set is global)
    rec = ER.recall("compute fibonacci numbers", rows)
    assert rec["unknown_tools"] == ["frobnicate"]
    assert rec["absent_paths_hint"] == [], "absent paths must NOT carry across unrelated tasks"
    print("  OK  unknown tools carry across any task; absent paths do not")


def test_recall_paths_and_deadends_require_similarity():
    foot = ER.encode_footer({"absent_tools": [], "absent": ["/repo/gold.json"], "exists": []},
                            0.1, blocked=True, halt="BLOCKED: no new info", final_status="BLOCKED")
    rows = [{"task": "fetch the live gold price and write gold.json", "summary": "tried" + foot}]
    # a SIMILAR task recalls the absent path hint + the dead-end warning
    rec = ER.recall("write the current gold price into gold.json", rows)
    assert "/repo/gold.json" in rec["absent_paths_hint"]
    assert rec["prior_dead_ends"] and "no new info" in rec["prior_dead_ends"][0]["halt"]
    assert rec["similar_count"] == 1
    print("  OK  absent-path hints + dead-end warnings carry only to similar tasks")


def test_seed_world_only_seeds_tools():
    wm = W.WorldModel()
    rec = {"unknown_tools": ["frobnicate"], "absent_paths_hint": ["/repo/gold.json"], "prior_dead_ends": []}
    n = ER.seed_world(wm, rec)
    assert n == 1
    assert "frobnicate" in [t[5:] for t in wm.absent_tools()], "unknown tool must be seeded"
    # absent path must NOT be hard-seeded (a file may have been created since)
    assert not wm.absent("/repo/gold.json"), "absent path must remain unverified (hint only)"
    print("  OK  seed_world seeds unknown tools only; absent paths stay unverified")


def test_render_block_and_empty():
    rec = {"unknown_tools": ["frobnicate"], "absent_paths_hint": ["/x"],
           "prior_dead_ends": [{"task": "t", "halt": "BLOCKED: dead end"}]}
    b = ER.render(rec)
    assert "EXECUTION MEMORY" in b and "frobnicate" in b and "PRIOR DEAD-END" in b
    # nothing to recall → empty block (no noise, no fabrication)
    assert ER.render({"unknown_tools": [], "absent_paths_hint": [], "prior_dead_ends": []}) == ""
    assert ER.render({}) == ""
    print("  OK  EXECUTION MEMORY block reflects real recall; empty when nothing to carry")


def test_no_state_no_foreign_import():
    import execution_recall as mod, inspect
    src = inspect.getsource(mod)
    assert "import house_state" not in src and "import agent_reputation" not in src
    assert "sqlite3" not in src and "CREATE TABLE" not in src, "must own NO state / no new store"
    print("  OK  read-model owns no state (no DB, no new table, no foreign-state import)")


def main():
    print("=" * 56 + "\nOX-1.5 EXECUTION MEMORY\n" + "=" * 56)
    test_footer_roundtrip()
    test_recall_unknown_tools_are_task_independent()
    test_recall_paths_and_deadends_require_similarity()
    test_seed_world_only_seeds_tools()
    test_render_block_and_empty()
    test_no_state_no_foreign_import()
    print("\n  ALL EXECUTION-MEMORY TESTS PASS — carry knowledge forward, zero new state")
    return 0


if __name__ == "__main__":
    sys.exit(main())
