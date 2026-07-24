"""
test_world_model.py — OX-1.1 World Model validation (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import world_model as W


def test_observe_from_real_results():
    wm = W.WorldModel()
    # a real read_file success → file verified EXISTS
    wm.observe_tool("read_file", {"path": "/repo/a.py"}, "print('hi')\n...")
    assert wm.exists("/repo/a.py")
    # a real read_file miss → verified ABSENT
    wm.observe_tool("read_file", {"path": "/repo/missing.py"}, "[File not found: /repo/missing.py]")
    assert wm.absent("/repo/missing.py")
    # write creates → EXISTS
    wm.observe_tool("write_file", {"path": "/repo/new.json"}, "Written: /repo/new.json (12 chars)")
    assert wm.exists("/repo/new.json")
    # delete → ABSENT
    wm.observe_tool("delete_file", {"path": "/repo/new.json"}, "Deleted: /repo/new.json")
    assert wm.absent("/repo/new.json")
    # unknown tool → tool ABSENT
    wm.observe_tool("frobnicate", {}, "[Unknown tool: frobnicate]")
    assert "frobnicate" in [t[5:] for t in wm.absent_tools()]
    print("  OK  observations derived only from real tool results")


def test_no_downgrade():
    wm = W.WorldModel()
    wm.observe("/x", W.EXISTS)
    wm.observe("/x", W.UNVERIFIED)        # must NOT downgrade a verified fact
    assert wm.exists("/x")
    print("  OK  verified facts are never downgraded to unverified")


def test_gate_blocks_known_absent():
    wm = W.WorldModel()
    wm.observe_tool("read_file", {"path": "/repo/missing.py"}, "[File not found: /repo/missing.py]")
    ok, reason = wm.gate("read_file", {"path": "/repo/missing.py"})
    assert ok is False and "ABSENT" in reason
    ok2, _ = wm.gate("read_file", {"path": "/repo/unknown.py"})   # unverified → allowed (must verify)
    assert ok2 is True
    print("  OK  pre-action gate blocks re-reading a known-absent path; allows unverified")


def test_render_block():
    wm = W.WorldModel()
    wm.observe("/repo/a.py", W.EXISTS)
    wm.observe("/repo/missing.py", W.ABSENT)
    block = wm.render()
    assert "VERIFIED WORLD" in block and "/repo/a.py" in block and "/repo/missing.py" in block
    # empty world → empty block (no fabrication / no noise)
    assert W.WorldModel().render() == ""
    print("  OK  VERIFIED WORLD prompt block reflects real state; empty when nothing verified")


def main():
    print("=" * 56 + "\nOX-1.1 WORLD MODEL\n" + "=" * 56)
    test_observe_from_real_results()
    test_no_downgrade()
    test_gate_blocks_known_absent()
    test_render_block()
    print("\n  ALL WORLD-MODEL TESTS PASS — verify before acting")
    return 0


if __name__ == "__main__":
    sys.exit(main())
