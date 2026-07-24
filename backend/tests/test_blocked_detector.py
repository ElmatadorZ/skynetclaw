"""
test_blocked_detector.py — OX-1.4 BLOCKED State validation (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from blocked_detector import BlockedDetector


def test_varied_but_empty_streak_grows():
    d = BlockedDetector(k=4)
    # four steps, each takes a DIFFERENT action but learns nothing new
    for i in range(4):
        d.begin_step()
        d.observe_result("grep_search", "no matches found")  # same result text → not novel after first
        d.end_step(world_size=0, acted=True)
    # first step's result WAS novel (seen for the first time) → streak only grew on 2nd..4th
    assert d.streak == 3, f"streak should be 3 (first result was novel), got {d.streak}"
    print(f"  OK  varied-but-empty steps grow the no-info streak ({d.streak})")


def test_new_information_resets_streak():
    d = BlockedDetector(k=4)
    d.begin_step(); d.observe_result("read_file", "AAA"); d.end_step(world_size=0, acted=True)
    d.begin_step(); d.observe_result("read_file", "AAA"); d.end_step(world_size=0, acted=True)  # dup → +1
    assert d.streak == 1
    # a step that GROWS the world model resets the streak (real progress)
    d.begin_step(); d.observe_result("read_file", "AAA"); d.end_step(world_size=1, acted=True)
    assert d.streak == 0, "world growth must reset the streak"
    # a step that returns a NOVEL result also resets
    d.begin_step(); d.observe_result("read_file", "AAA"); d.end_step(world_size=1, acted=True)  # dup, no growth → +1
    assert d.streak == 1
    d.begin_step(); d.observe_result("grep_search", "FOUND IT"); d.end_step(world_size=1, acted=True)
    assert d.streak == 0, "a novel result must reset the streak"
    print("  OK  world growth OR a novel result resets the streak")


def test_no_action_step_does_not_count():
    d = BlockedDetector(k=4)
    for _ in range(6):
        d.begin_step()
        d.end_step(world_size=0, acted=False)   # no tool ran this step
    assert d.streak == 0, "a no-action step is stagnation, not BLOCKED"
    print("  OK  no-action steps never grow the BLOCKED streak (that's stagnation)")


def test_blocked_requires_streak_and_recovery_exhausted():
    d = BlockedDetector(k=3)
    # drive a no-info streak (first result novel, then dups)
    for _ in range(5):
        d.begin_step(); d.observe_result("x", "same"); d.end_step(world_size=0, acted=True)
    assert d.streak >= 3
    # streak alone is NOT enough — recovery must also be exhausted
    assert d.is_blocked(recovery_exhausted=False) is False, "streak alone must not block"
    assert d.is_blocked(recovery_exhausted=True) is True, "streak + exhausted recovery → BLOCKED"
    print("  OK  BLOCKED needs BOTH a no-info streak AND recovery exhausted")


def test_productive_run_never_blocks():
    d = BlockedDetector(k=3)
    # a long run where every step learns something new → never blocked
    for i in range(20):
        d.begin_step(); d.observe_result("read_file", f"unique-{i}"); d.end_step(world_size=i, acted=True)
    assert d.streak == 0
    assert d.is_blocked(recovery_exhausted=True) is False, "a productive run must never be BLOCKED"
    print("  OK  a productive run (info every step) is never falsely BLOCKED")


def test_no_coupling_to_other_owners():
    import blocked_detector as mod, inspect
    src = inspect.getsource(mod)
    assert "import house_state" not in src and "import agent_reputation" not in src, \
        "BLOCKED detector must not couple to belief/reputation owners"
    print("  OK  detector owns only the info-gain streak (no foreign state import)")


def main():
    print("=" * 56 + "\nOX-1.4 BLOCKED STATE\n" + "=" * 56)
    test_varied_but_empty_streak_grows()
    test_new_information_resets_streak()
    test_no_action_step_does_not_count()
    test_blocked_requires_streak_and_recovery_exhausted()
    test_productive_run_never_blocks()
    test_no_coupling_to_other_owners()
    print("\n  ALL BLOCKED-STATE TESTS PASS — detect dead ends, terminate honestly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
