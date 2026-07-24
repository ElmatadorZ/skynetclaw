"""
test_completion_evidence.py — OX-1.6 Evidence-Based Completion (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import completion_evidence as CE


def test_extract_only_checkable_artifacts():
    arts = CE.extract_artifacts("write the price into gold.json and update /repo/report.md")
    assert "gold.json" in arts and "/repo/report.md" in arts
    # pure prose with no artifact → nothing checkable
    assert CE.extract_artifacts("explain the result clearly to the user") == []
    print("  OK  extracts concrete artifacts; ignores pure prose")


def test_uncheckable_is_accepted():
    v = CE.verify("answer the user's question accurately", {}, [], [])
    assert v["proven"] is True and v["uncheckable"] is True
    print("  OK  pure-text DONE_WHEN is UNCHECKABLE → accepted (never gate text answers)")


def test_proven_when_artifact_exists():
    snap = {"exists": ["/repo/gold.json"], "absent": [], "absent_tools": []}
    v = CE.verify("create gold.json with the live price", snap, [], [])
    assert v["proven"] is True and v["missing"] == []
    # also proven via files_touched
    v2 = CE.verify("create gold.json", {}, ["/work/gold.json"], [])
    assert v2["proven"] is True
    # also proven via a successful write tool result
    v3 = CE.verify("create gold.json", {}, [], [("write_file", "Written: /work/gold.json (42 chars)")])
    assert v3["proven"] is True
    print("  OK  PROVEN via world EXISTS / files_touched / successful tool result")


def test_unproven_when_no_evidence():
    v = CE.verify("create report.md summarizing findings", {}, [], [])
    assert v["proven"] is False and v["disproven"] is False
    assert "report.md" in v["missing"]
    print("  OK  named-but-unevidenced artifact → UNPROVEN (weak, not disproven)")


def test_disproven_when_verified_absent():
    snap = {"exists": [], "absent": ["/repo/report.md"], "absent_tools": []}
    v = CE.verify("produce /repo/report.md", snap, [], [])
    assert v["proven"] is False and v["disproven"] is True
    assert "/repo/report.md" in v["disproven_hits"]
    print("  OK  artifact verified ABSENT → DISPROVEN (strong disproof)")


def test_rejection_block():
    v = CE.verify("create report.md", {}, [], [])
    b = CE.render_rejection(v, 1, 2)
    assert "COMPLETION REJECTED (1/2)" in b and "report.md" in b and "without proof" in b
    print("  OK  rejection block names the missing proof and demands real evidence")


def test_no_state_no_model():
    import completion_evidence as mod, inspect
    src = inspect.getsource(mod)
    assert "sqlite3" not in src and "CREATE TABLE" not in src and "httpx" not in src
    assert "import house_state" not in src and "import agent_reputation" not in src
    print("  OK  stateless, deterministic — no DB, no model call, no foreign state")


def main():
    print("=" * 56 + "\nOX-1.6 EVIDENCE-BASED COMPLETION\n" + "=" * 56)
    test_extract_only_checkable_artifacts()
    test_uncheckable_is_accepted()
    test_proven_when_artifact_exists()
    test_unproven_when_no_evidence()
    test_disproven_when_verified_absent()
    test_rejection_block()
    test_no_state_no_model()
    print("\n  ALL COMPLETION-EVIDENCE TESTS PASS — prove completion, don't assert it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
