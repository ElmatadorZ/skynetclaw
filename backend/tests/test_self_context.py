"""
test_self_context.py — proprioception mining (Vol VI Learning bridge)
=====================================================================
Locks the runtime learning bridge: the system mines its OWN recorded outcomes
(warrant_log overclaims + task-similar agent_runs failures) into lessons that
change the next run — and stays SILENT when nothing relevant was learned (the F2
anti-noise discipline).

    python backend/tests/test_self_context.py
"""
from __future__ import annotations
import sys, os, json, sqlite3, tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import self_context as sc

RESULTS = {}


def _mk_db(rows):
    """rows: list of (status, task, summary)."""
    p = tempfile.mktemp(suffix=".db")
    con = sqlite3.connect(p); c = con.cursor()
    c.execute("CREATE TABLE agent_runs(id INTEGER PRIMARY KEY, status TEXT, task TEXT, summary TEXT, ended_at REAL)")
    import time as _t
    for i, (st, task, summ) in enumerate(rows):
        c.execute("INSERT INTO agent_runs(status,task,summary,ended_at) VALUES(?,?,?,?)",
                  (st, task, summ, _t.time() + i))
    con.commit(); con.close()
    return p


def _mk_warrant(records):
    p = tempfile.mktemp(suffix=".jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return p


def t_warrant_lessons():
    print("== T1: mines the system's own overclaim history (CEE -> proprioception) ==")
    log = _mk_warrant([
        {"ts": 1, "run_id": "a", "task": "explore", "verdict": "OK", "n_overclaims": 0, "overclaims": []},
        {"ts": 2, "run_id": "b", "task": "explore", "verdict": "OVERCLAIM", "n_overclaims": 1,
         "overclaims": [{"path": "example.txt", "type": "fabricated_file_reference"}]},
        {"ts": 3, "run_id": "c", "task": "scan", "verdict": "OVERCLAIM", "n_overclaims": 1,
         "overclaims": [{"path": "ghost.md", "type": "fabricated_file_reference"}]},
    ])
    lesson = sc.mine_warrant_lessons(log, recent=60)
    clean = sc.mine_warrant_lessons(_mk_warrant([{"ts": 1, "run_id": "x", "task": "y", "verdict": "OK", "n_overclaims": 0, "overclaims": []}]), recent=60)
    checks = {
        "surfaces overclaim lesson": bool(lesson) and "did NOT exist" in lesson,
        "names the fabricated path (credit)": lesson and "example.txt" in lesson,
        "SILENT when no overclaims (F2)": clean is None,
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T1"] = all(checks.values()); assert RESULTS["T1"]


def t_task_relevant_run_lessons():
    print("== T2: run lessons are TASK-RELEVANT (credit assignment by similarity) ==")
    db = _mk_db([
        ("failed", "scrape the cloudflare protected pricing page", "browser blocked"),
        ("failed", "write a poem about the ocean", "model refused"),
        ("TASK_COMPLETE", "list files", "done"),
    ])
    # current task resembles the scrape failure, not the poem
    lessons = sc.mine_run_lessons(db, "scrape the cloudflare pricing table from the site", recent=40)
    joined = " ".join(lessons)
    checks = {
        "surfaces the relevant (scrape) failure": "cloudflare" in joined or "pricing" in joined,
        "does NOT surface the irrelevant (poem) failure": "poem" not in joined and "ocean" not in joined,
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = all(checks.values()); assert RESULTS["T2"]


def t_silent_when_nothing_learned():
    print("== T3: build_self_context is SILENT when clean (F2 anti-noise) ==")
    db = _mk_db([("TASK_COMPLETE", "unrelated done task", "ok")])
    warrant = _mk_warrant([{"ts": 1, "run_id": "x", "task": "y", "verdict": "OK", "n_overclaims": 0, "overclaims": []}])
    out = sc.build_self_context(db, "a totally novel task with no history", warrant_log_path=warrant)
    empty_db = sc.build_self_context(_mk_db([]), "anything", warrant_log_path=warrant)
    checks = {
        "silent on clean history": out == "",
        "silent on empty db": empty_db == "",
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T3"] = all(checks.values()); assert RESULTS["T3"]


def t_composes_when_learned():
    print("== T4: composes a block when there IS a relevant lesson ==")
    db = _mk_db([("failed", "scrape cloudflare pricing", "blocked")])
    warrant = _mk_warrant([{"ts": 2, "run_id": "b", "task": "explore", "verdict": "OVERCLAIM",
                            "n_overclaims": 1, "overclaims": [{"path": "example.txt"}]}])
    out = sc.build_self_context(db, "scrape the cloudflare pricing page", warrant_log_path=warrant)
    checks = {
        "block present": "PROPRIOCEPTION" in out or "LESSONS FROM YOUR OWN HISTORY" in out,
        "includes warrant lesson": "did NOT exist" in out,
        "includes task-relevant lesson": "cloudflare" in out or "pricing" in out,
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T4"] = all(checks.values()); assert RESULTS["T4"]


def main():
    t_warrant_lessons(); t_task_relevant_run_lessons(); t_silent_when_nothing_learned(); t_composes_when_learned()
    print("\n== SUMMARY ==")
    ok = all(RESULTS.get(k) for k in ("T1", "T2", "T3", "T4"))
    for k in ("T1", "T2", "T3", "T4"):
        print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL PROPRIOCEPTION TESTS PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
