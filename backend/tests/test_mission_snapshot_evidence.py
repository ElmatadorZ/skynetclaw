"""
test_mission_snapshot_evidence.py — the warrant-loss-under-compression bug
==========================================================================
Reproduces the real failure: an exploration run observed test_*.py files via
list_files/find_files, then — after the 16k-ceiling forced a context compression
— reported "no tests found / UNKNOWN" about files it had actually seen, because
the snapshot kept only the first 160 chars of each tool result (dropping names
past it) and skipped find_files output entirely (it begins with "[").

Locks: (1) listing/search facts preserve observed child NAMES, (2) compression
is idempotent — a second compress accumulates the first snapshot's facts.

    python backend/tests/test_mission_snapshot_evidence.py
"""
from __future__ import annotations
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mission_snapshot as ms

RESULTS = {}

# a real list_files result: the test_*.py names sit PAST char 160 (after the
# __pycache__ dir + conftest.py), exactly where _first_fact used to cut.
LIST_TESTS = (
    '[{"name": "__pycache__", "type": "dir", "size": 0, "modified": "2026-07-03 23:45"}, '
    '{"name": "conftest.py", "type": "file", "size": 402, "modified": "2026-06-13 22:32"}, '
    '{"name": "test_acquisition.py", "type": "file", "size": 4707, "modified": "2026-06-22 21:54"}, '
    '{"name": "test_artifact_factory.py", "type": "file", "size": 3211, "modified": "2026-06-22 21:54"}]'
)
# a real find_files result: a JSON array of path strings (begins with "[")
FIND_TESTS = (
    '["C:\\\\repo\\\\skynetclaw\\\\.pytest_cache", '
    '"C:\\\\repo\\\\skynetclaw\\\\_archive\\\\root\\\\test_import.py", '
    '"C:\\\\repo\\\\skynetclaw\\\\backend\\\\tests\\\\test_golden_behaviors.py"]'
)


def _cur_with(*tool_msgs):
    cur = [{"role": "system", "content": "PREAMBLE"},
           {"role": "user", "content": "explore the workspace and list which projects have tests"}]
    for i, (nm, res) in enumerate(tool_msgs):
        cur.append({"role": "assistant", "content": f"calling {nm}"})
        cur.append({"role": "tool", "name": nm, "content": res})
    return cur


def t_listing_names_survive():
    print("== T1: listing/search facts preserve observed test filenames ==")
    cur = _cur_with(("list_files", LIST_TESTS), ("find_files", FIND_TESTS),
                    ("list_files", '[{"name":"main.py","type":"file"}]'))
    new_cur, snap, dropped = ms.compress(cur, keep_recent=1)
    snap_text = "\n".join(m["content"] for m in new_cur if m["role"] == "system")
    checks = {
        "test_acquisition.py survived (was past char 160)": "test_acquisition.py" in snap_text,
        "test_artifact_factory.py survived": "test_artifact_factory.py" in snap_text,
        "find_files test_import.py survived (was skipped by '[')": "test_import.py" in snap_text,
        "find_files test_golden_behaviors.py survived": "test_golden_behaviors.py" in snap_text,
        "noise dropped (no 'modified' timestamps)": "2026-06-22" not in snap_text,
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T1"] = all(checks.values()); assert RESULTS["T1"]


def t_compression_idempotent():
    print("== T2: second compression accumulates the first snapshot's facts ==")
    # round 1: the list_files tool must fall in the compressed MIDDLE (older than
    # the recent tail), so the round-1 snapshot actually captures its facts.
    cur = _cur_with(("list_files", LIST_TESTS))
    cur.append({"role": "assistant", "content": "done exploring backend/tests"})
    new_cur1, snap1, _ = ms.compress(cur, keep_recent=1)
    assert any("test_acquisition.py" in m["content"] for m in new_cur1 if m["role"] == "system"), \
        "round-1 snapshot should have captured the listing"
    # simulate more work after the first snapshot, then compress again — the prior
    # snapshot now sits in the middle and its facts must be carried forward.
    new_cur1.append({"role": "assistant", "content": "calling find_files"})
    new_cur1.append({"role": "tool", "name": "find_files", "content": FIND_TESTS})
    new_cur1.append({"role": "assistant", "content": "done searching"})
    new_cur2, snap2, _ = ms.compress(new_cur1, keep_recent=1)
    snap_text2 = "\n".join(m["content"] for m in new_cur2 if m["role"] == "system")
    checks = {
        "round-1 evidence carried forward (test_acquisition.py)": "test_acquisition.py" in snap_text2,
        "round-2 evidence present (test_import.py)": "test_import.py" in snap_text2,
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = all(checks.values()); assert RESULTS["T2"]


def main():
    t_listing_names_survive(); t_compression_idempotent()
    print("\n== SUMMARY ==")
    ok = all(RESULTS.get(k) for k in ("T1", "T2"))
    for k in ("T1", "T2"):
        print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL EVIDENCE-PRESERVATION TESTS PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
