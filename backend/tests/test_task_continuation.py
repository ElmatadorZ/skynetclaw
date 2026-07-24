"""
test_task_continuation.py — ephemeral multi-round working memory
================================================================
Locks the context-handoff logic that lets a task larger than the model window
finish across rounds:
  * should_continue: the round-to-round decision (continue on LIMIT, recover on
    FAILED-with-progress, stop on SUCCESS/BLOCKED/no-progress).
  * TaskMemory: bounded, deduped accumulation; seed carries objective + progress
    + a continue-don't-restart instruction and stays small.

Hermetic:  python backend/tests/test_task_continuation.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import task_continuation as tc

RESULTS = {}


def t_should_continue():
    print("== T1: should_continue round decision ==")
    cases = [
        # (status, tools, had_summary, expected)
        ("SUCCESS", 5, True, False),   # done
        ("LIMIT",   3, True, True),    # ran out of steps -> more to do
        ("LIMIT",   0, False, True),   # LIMIT always continues
        ("FAILED",  2, False, True),   # halted but made progress -> fresh round may recover
        ("FAILED",  0, False, False),  # halted, zero progress -> stop (no spin)
        ("BLOCKED", 9, True, False),   # dead-end -> stop
        ("weird",   1, True, False),   # unknown -> stop (safe)
    ]
    ok = True
    for status, tools, summ, exp in cases:
        got = tc.should_continue(status, tools, summ)
        if got != exp: ok = False
        print(f"  {'OK ' if got==exp else 'FAIL'} {status:8s} tools={tools} summary={summ} -> {got} (exp {exp})")
    RESULTS["T1"] = ok; assert ok


def t_memory_accumulate():
    print("== T2: TaskMemory accumulation, dedup, bounding ==")
    m = tc.TaskMemory("summarize 40 files into report.md", max_findings=5, max_finding_len=50)
    m.absorb("read files 1-10, wrote partial to report.md", tools_used=12)
    m.absorb("read files 1-10, wrote partial to report.md", tools_used=3)  # duplicate summary
    m.absorb("read files 11-20", tools_used=8)
    checks = {
        "round counted": m.round == 3,
        "tools accumulated": m.tools_total == 23,
        "duplicate finding deduped": len(m.findings) == 2,
    }
    # bounding: push past max_findings
    for i in range(10):
        m.absorb(f"processed batch {i}", tools_used=1)
    checks["findings bounded to max"] = len(m.findings) <= 5
    checks["long finding truncated"] = all(len(f) <= 50 for f in m.findings)
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = all(checks.values()); assert RESULTS["T2"]


def t_seed():
    print("== T3: seed_task carries objective + progress + continue instruction ==")
    m = tc.TaskMemory("build a 12-section handbook")
    m.absorb("wrote sections 1-3", tools_used=6)
    seed = m.seed_task()
    checks = {
        "names the objective": "12-section handbook" in seed,
        "shows progress": "sections 1-3" in seed,
        "instructs continue, not restart": "Continue" in seed and "do NOT repeat" in seed,
        "keeps completion protocol": "TASK_COMPLETE" in seed,
        "labels the round": "round 2" in seed,
        "stays compact (< 4000 chars)": len(seed) < 4000,
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T3"] = all(checks.values()); assert RESULTS["T3"], seed[:400]


def main():
    t_should_continue(); t_memory_accumulate(); t_seed()
    print("\n== SUMMARY ==")
    allok = all(RESULTS.get(k) for k in ("T1", "T2", "T3"))
    for k in ("T1", "T2", "T3"):
        print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL TASK-CONTINUATION TESTS PASS" if allok else "FAILURES PRESENT"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
