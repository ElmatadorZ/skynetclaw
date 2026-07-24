"""
test_policy_hook_reporting.py — the governance surface must not misreport itself.

The boot log used to print all seven policies under "PRE_ACT hook armed", which
claimed the fabrication and warrant guards fire before a side effect. They fire
before a *commit*. The documentation copied the log, so a wrong log line became a
wrong security model on the wiki.

These guards lock the correction: policies are reported under the hook they
actually run on, and the four act-boundary policies are the ones at PRE_ACT.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

ACT_POLICIES = {"governance.gps2", "shadow.fabrication",
                "approvals.prior_deny", "run.tool_allow"}
COMMIT_POLICIES = {"guidance.g1", "warrant.cee_c1"}
VALIDATE_POLICIES = {"cvl.quality_gate"}


def _by_hook():
    import main  # noqa: F401 — importing main is what installs the act policies
    import kernel_policy as kp
    return kp.registered_by_hook()


def test_every_policy_is_reported_under_its_own_hook():
    import kernel_policy as kp
    by_hook = _by_hook()
    for hook, ids in by_hook.items():
        for pid in ids:
            declared = [getattr(p, "hook", None) for p in kp._POLICIES
                        if getattr(p, "id", None) == pid]
            assert declared == [hook], f"{pid} reported under {hook}, declares {declared}"


def test_act_boundary_holds_exactly_the_four_act_policies():
    assert set(_by_hook().get("PRE_ACT", [])) == ACT_POLICIES


def test_belief_guards_are_not_at_the_act_boundary():
    by_hook = _by_hook()
    assert set(by_hook.get("PRE_COMMIT", [])) == COMMIT_POLICIES
    assert set(by_hook.get("PRE_VALIDATE", [])) == VALIDATE_POLICIES
    assert not (COMMIT_POLICIES | VALIDATE_POLICIES) & set(by_hook.get("PRE_ACT", []))


def test_grouping_loses_no_policy():
    import kernel_policy as kp
    by_hook = _by_hook()
    flat = sorted(kp.registered())
    grouped = sorted(pid for ids in by_hook.values() for pid in ids)
    assert flat == grouped


def test_boot_log_reports_per_hook_not_one_flat_list():
    src = (_ROOT / "main.py").read_text(encoding="utf-8")
    assert "registered_by_hook()" in src
    assert "PRE_ACT hook armed — policies:" not in src   # the claim that was wrong
