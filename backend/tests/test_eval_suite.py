"""
test_eval_suite.py — the scoreboard framework mechanics
=======================================================
Locks: the deterministic tier scores; persist/recent/trend build a usable
time-series; a regression shows as a negative delta.

    python backend/tests/test_eval_suite.py
"""
from __future__ import annotations
import sys, json, tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import eval_suite as es

RESULTS = {}


def t_deterministic_scores():
    print("== T1: deterministic tier runs and scores (no live, no backend needed) ==")
    log = tempfile.mktemp(suffix=".jsonl")
    rec = es.run_suite(include_live=False, log_path=log)
    checks = {
        "produced a score in [0,1]": 0.0 <= rec["score"] <= 1.0,
        "ran the deterministic bridge cases": rec["total"] >= 6,
        "each result has id+status": all("id" in r and "status" in r for r in rec["results"]),
        "no live cases in det-only run": all(r["category"] != "live" for r in rec["results"]),
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k} (score={rec['score']} total={rec['total']})")
    RESULTS["T1"] = all(checks.values()); assert RESULTS["T1"]


def t_timeseries_and_trend():
    print("== T2: persist -> recent -> trend builds a usable time-series ==")
    log = tempfile.mktemp(suffix=".jsonl")
    es._persist({"ts": 1, "score": 0.8, "passed": 8, "total": 10, "skipped": 0, "errors": 0, "failing": ["x"]}, log)
    es._persist({"ts": 2, "score": 1.0, "passed": 10, "total": 10, "skipped": 0, "errors": 0, "failing": []}, log)
    es._persist({"ts": 3, "score": 0.7, "passed": 7, "total": 10, "skipped": 0, "errors": 0, "failing": ["a", "b", "c"]}, log)
    rows = es.recent(10, log)
    tr = es.trend(log)
    checks = {
        "three runs recorded": len(rows) == 3,
        "trend latest is the last score": tr["latest"] == 0.7,
        "trend delta is negative on regression": tr["delta"] == -0.3,
        "trend counts all runs": tr["n"] == 3,
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = all(checks.values()); assert RESULTS["T2"]


def main():
    t_deterministic_scores(); t_timeseries_and_trend()
    print("\n== SUMMARY ==")
    ok = all(RESULTS.get(k) for k in ("T1", "T2"))
    for k in ("T1", "T2"): print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL EVAL-SUITE FRAMEWORK TESTS PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
