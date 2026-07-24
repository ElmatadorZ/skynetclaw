"""
test_reality_context.py — REALITY grounding block
==================================================
The workspace banner told the model WHERE to write but never WHAT was there, so
with files mounted it still asked "which file?". reality_context.build_reality
injects the verified workspace contents + runtime identity so the model answers
from the current world. These tests lock the block's shape (aggregation-only,
bounded, honest).

    python backend/tests/test_reality_context.py
"""
from __future__ import annotations
import sys, os, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import reality_context as rc

RESULTS = {}


def t_lists_workspace():
    print("== T1: lists real workspace contents (incl. nested) ==")
    d = tempfile.mkdtemp()
    open(os.path.join(d, "report.md"), "w").write("hi")
    open(os.path.join(d, "data.csv"), "w").write("a,b\n1,2")
    os.makedirs(os.path.join(d, "sub"), exist_ok=True)
    open(os.path.join(d, "sub", "notes.txt"), "w").write("x" * 5000)
    b = rc.build_reality(d, runtime_label="execution", model="ElmatadorZ")
    checks = {
        "lists top-level file": "report.md" in b and "data.csv" in b,
        "lists nested file": "notes.txt" in b,
        "reports total count": "3 total" in b,
        "carries runtime+model identity": "execution" in b and "ElmatadorZ" in b,
        "labelled verified/observation": "verified current world" in b,
        "has anti-'which file' instruction": "which file" in b,
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T1"] = all(checks.values()); assert RESULTS["T1"]


def t_empty_and_none():
    print("== T2: empty workspace + no workspace ==")
    e = tempfile.mkdtemp()
    be = rc.build_reality(e)
    checks = {
        "empty workspace flagged EMPTY": "EMPTY" in be,
        "no workspace + no runtime -> blank": rc.build_reality(None) == "",
        "runtime-only still renders": "model=X" in rc.build_reality(None, model="X"),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = all(checks.values()); assert RESULTS["T2"]


def t_bounded():
    print("== T3: bounded (never bloats the window) ==")
    d = tempfile.mkdtemp()
    for i in range(120):
        open(os.path.join(d, f"f{i:03d}.txt"), "w").write("x")
    b = rc.build_reality(d, max_files=40)
    checks = {
        "reports true total (120)": "120 total" in b,
        "shows at most max_files": b.count("\n  - ") <= 40,
        "notes the remainder": "and 80 more" in b,
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T3"] = all(checks.values()); assert RESULTS["T3"]


def t_operational_summary():
    print("== T4: operational history summary (grounds 'analyze failures') ==")
    import sqlite3, time
    db = tempfile.mktemp(suffix=".db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE agent_runs(id TEXT, started_at REAL, ended_at REAL, "
                "task TEXT, model TEXT, status TEXT, n_steps INT, n_tools INT, "
                "n_blocks INT, trajectory_path TEXT, summary TEXT, task_raw TEXT)")
    now = time.time()
    rows = [("done", "ok task", "completed fine"),
            ("failed", "recheck", "model stream step timeout after 180s [[EXEC_MEM]]{x}"),
            ("limit", "count 1-3", "agent reached MAX_STEPS without TASK_COMPLETE [[EXEC_MEM]]{y}"),
            ("interrupted", "big job", "stream ended")]
    for i, (st, task, summ) in enumerate(rows):
        con.execute("INSERT INTO agent_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"r{i}", now, now + i, task, "m", "TASK_COMPLETE" if st == "done" else st,
                     1, 0, 0, "", summ, task))
    con.commit(); con.close()
    b = rc.build_operational_summary(db, recent=3)
    checks = {
        "reports run count": "4 agent runs" in b,
        "reports failed/limit counts": "failed=1" in b and "limit=1" in b,
        "lists latest failures": "LATEST FAILURES" in b,
        "strips EXEC_MEM noise from cause": "[[EXEC_MEM]]" not in b,
        "shows a real cause": "180s" in b or "MAX_STEPS" in b,
        "empty db -> blank (no fake)": rc.build_operational_summary(tempfile.mktemp(suffix=".db")) == "",
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    try: os.remove(db)
    except Exception: pass
    RESULTS["T4"] = all(checks.values()); assert RESULTS["T4"], b


def main():
    t_lists_workspace(); t_empty_and_none(); t_bounded(); t_operational_summary()
    print("\n== SUMMARY ==")
    allok = all(RESULTS.get(k) for k in ("T1", "T2", "T3", "T4"))
    for k in ("T1", "T2", "T3", "T4"):
        print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL REALITY-CONTEXT TESTS PASS" if allok else "FAILURES PRESENT"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
