"""
test_mission_identity.py — OX-H1 Identity Separation (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mission_identity as MI


# the exact augmented_task shape the executor builds (main.py:5643)
def _augmented(directive):
    sys_prefix = ("## 🎯 WORKFLOW CONTEXT (Phase 1 + 2 already executed)\n\n"
                  "### YOU UNDERSTAND THE TASK AS:\n  build a thing\n\n"
                  "### YOUR PLAN:\n  1) do it\n")
    return (f"{sys_prefix}\n\n"
            "═══════════════════════════════════════════════\n"
            "USER REQUEST:\n"
            "═══════════════════════════════════════════════\n"
            f"{directive}")


def test_explicit_directive_wins():
    assert MI.extract_directive(_augmented("x"), "Build Stock Dashboard") == "Build Stock Dashboard"
    print("  OK  an explicit directive is used verbatim")


def test_extracts_clean_request_from_prompt():
    aug = _augmented("Build Stock Dashboard")
    d = MI.extract_directive(aug)
    assert d == "Build Stock Dashboard", repr(d)
    assert "WORKFLOW CONTEXT" not in d and "YOU UNDERSTAND" not in d
    print("  OK  clean directive recovered from an assembled WORKFLOW CONTEXT prompt")


def test_plain_directive_passthrough():
    assert MI.extract_directive("Build Stock Dashboard") == "Build Stock Dashboard"
    assert MI.looks_like_prompt("Build Stock Dashboard") is False
    print("  OK  a plain directive passes through untouched")


def test_prompt_is_detected():
    aug = _augmented("Build X")
    assert MI.looks_like_prompt(aug) is True
    print("  OK  execution prompts are detected by their sigils")


def test_clean_identity_never_leaks_prompt():
    # a prompt with NO user-request marker must never yield the WORKFLOW block
    bad = "## 🎯 WORKFLOW CONTEXT (Phase 1 + 2 already executed)\n### YOU UNDERSTAND THE TASK AS: foo"
    out = MI.clean_identity(bad)
    assert "WORKFLOW CONTEXT" not in out and "YOU UNDERSTAND" not in out
    print("  OK  clean_identity never lets a WORKFLOW CONTEXT block become identity")


def test_title():
    assert MI.mission_title("Build Stock Dashboard\nwith live prices") == "Build Stock Dashboard"
    assert MI.mission_title("## Build X") == "Build X"
    print("  OK  mission_title yields a short canonical first line")


def test_no_state_no_model():
    import mission_identity as mod, inspect
    src = inspect.getsource(mod)
    assert "sqlite3" not in src and "httpx" not in src and "CREATE TABLE" not in src
    print("  OK  stateless, deterministic — no DB, no model, no persistence")


def main():
    print("=" * 56 + "\nOX-H1 MISSION IDENTITY\n" + "=" * 56)
    test_explicit_directive_wins()
    test_extracts_clean_request_from_prompt()
    test_plain_directive_passthrough()
    test_prompt_is_detected()
    test_clean_identity_never_leaks_prompt()
    test_title()
    test_no_state_no_model()
    print("\n  ALL MISSION-IDENTITY TESTS PASS — prompt text never becomes mission identity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
