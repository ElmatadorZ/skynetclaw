"""
test_recovery.py — OX-1.2 Recovery Engine validation (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import recovery as R


def test_classify_real_failures():
    cases = {
        "[File not found: /x/y.py]": R.FILE_NOT_FOUND,
        "❌ run_python TIMEOUT after 3s (max 300).": R.TIMEOUT,
        "[Tool error: http_request] ConnectError: All connection attempts failed": R.NETWORK,
        "[exit 7]\nSTDERR: boom": R.NONZERO_EXIT,
        "Traceback (most recent call last):\n  File ...\nSyntaxError: bad": R.CODE_ERROR,
        "[Unknown tool: frobnicate]": R.UNKNOWN_TOOL,
        "some odd failure": R.GENERIC,
    }
    for result, expect in cases.items():
        got = R.classify("x", result)
        assert got == expect, f"{result!r} → {got} (expected {expect})"
    print("  OK  classifier maps every real failure string to the right class")


def test_strategies_are_alternates():
    # file_not_found must suggest LOCATING, not re-reading
    s = R.strategies(R.FILE_NOT_FOUND)
    assert any("grep_search" in x or "find_files" in x or "list_files" in x for x in s)
    # timeout must suggest scope/timeout change
    assert any("scope" in x or "timeout" in x for x in R.strategies(R.TIMEOUT))
    # every class returns at least one concrete option
    for c in (R.FILE_NOT_FOUND, R.TIMEOUT, R.NETWORK, R.NONZERO_EXIT, R.CODE_ERROR, R.UNKNOWN_TOOL, R.GENERIC):
        assert R.strategies(c), c
    print("  OK  each failure class yields concrete ALTERNATE strategies")


def test_render_block():
    b = R.render("read_file", {"path": "/x"}, "[File not found: /x]")
    assert "RECOVERY OPTIONS" in b and "read_file" in b and "file_not_found" in b and "Do NOT repeat" in b
    print("  OK  RECOVERY OPTIONS block produced for a failed call")


def main():
    print("=" * 56 + "\nOX-1.2 RECOVERY ENGINE\n" + "=" * 56)
    test_classify_real_failures()
    test_strategies_are_alternates()
    test_render_block()
    print("\n  ALL RECOVERY TESTS PASS — recover with alternates, not retries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
