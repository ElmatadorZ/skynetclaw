"""
test_warrant_check.py — CEE runtime overclaim detector (C1 made live)
=====================================================================
Locks the first CEE build slice: the fabricated-file-reference detector that
turns Warrant-theory C1 (no belief presented beyond its warrant) into a runtime
check, plus its durable append-only log.

    python backend/tests/test_warrant_check.py
"""
from __future__ import annotations
import sys, os, json, tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import warrant_check as wc

RESULTS = {}


def t_catches_fabrication():
    print("== T1: catches fabricated file references (the example.txt failure) ==")
    cases_flag = [
        "File content retrieved successfully from C:\\repo\\example.txt.",
        "The Obsidian note content retrieved from example_note.md has been observed.",
        "ผมอ่านไฟล์ secret_data.csv แล้วพบว่ามีราคาทอง",
    ]
    ok = all(len(wc.detect_overclaims(t)) >= 1 for t in cases_flag)
    for t in cases_flag:
        print(f"  {'OK ' if wc.detect_overclaims(t) else 'FAIL'} flags: {t[:55]}")
    RESULTS["T1"] = ok; assert ok


def t_no_false_positives():
    print("== T2: no false positives (write-intent / real file / clean) ==")
    ws = tempfile.mkdtemp()
    open(os.path.join(ws, "report.md"), "w").write("hi")
    cases_clean = [
        ("ผมจะเขียนไฟล์ ok.txt ที่มีคำว่า DONE", ws),        # write intent
        ("I will write results to output.csv", ws),          # write intent
        ("อ่าน report.md พบว่ามีเนื้อหา hi", ws),             # real file
        ("ราคาทองวันนี้ 52000 บาท", None),                   # no file at all
    ]
    ok = all(len(wc.detect_overclaims(t, w)) == 0 for t, w in cases_clean)
    for t, w in cases_clean:
        print(f"  {'OK ' if not wc.detect_overclaims(t, w) else 'FAIL'} clean: {t[:45]}")
    RESULTS["T2"] = ok; assert ok


def t_persist_and_recent():
    print("== T3: durable log — persist + recent + overclaim record ==")
    log = tempfile.mktemp(suffix=".jsonl")
    oc = wc.detect_overclaims("retrieved from D:\\nope\\ghost.txt", None)
    wc.persist("run_a", "analyze failures", oc, log_path=log)
    wc.persist("run_b", "write hello", [], log_path=log)
    rows = wc.recent(limit=10, log_path=log)
    checks = {
        "two records persisted": len(rows) == 2,
        "violation recorded as OVERCLAIM": rows[0]["verdict"] == "OVERCLAIM" and rows[0]["n_overclaims"] >= 1,
        "clean recorded as OK": rows[1]["verdict"] == "OK",
        "record carries the path": any("ghost.txt" in o.get("path", "") for o in rows[0]["overclaims"]),
        "records are append-only immutable json": all("ts" in r and "run_id" in r for r in rows),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    try: os.remove(log)
    except Exception: pass
    RESULTS["T3"] = all(checks.values()); assert RESULTS["T3"]


def main():
    t_catches_fabrication(); t_no_false_positives(); t_persist_and_recent()
    print("\n== SUMMARY ==")
    allok = all(RESULTS.get(k) for k in ("T1", "T2", "T3"))
    for k in ("T1", "T2", "T3"):
        print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL WARRANT-CHECK TESTS PASS" if allok else "FAILURES PRESENT"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
