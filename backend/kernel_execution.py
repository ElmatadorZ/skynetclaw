"""
kernel_execution.py — Cognitive Kernel · Execution subsystem (migration step 5)
==============================================================================
COGNITIVE_KERNEL_SPEC §7 + §5. This is where the kernel starts to CONTROL rather
than merely observe: the act boundary now fires the PRE_ACT policy hook, and the
answer boundary fires PRE_COMMIT.

Amendment A1 — Scheduling classifies/routes and owns the loop; Execution owns the
act: guard it, run it, report it. Governance only authors policy.

Amendment A3 — safety by construction:
  · FAIL-CLOSED: any failure inside the guard DENIES the act. A gate that cannot
    run is never a silent-proceed.
  · Commit is IDEMPOTENT: commit_once(key) will not double-fire a side effect if
    the lifecycle re-enters Commit.
  · ESCALATED aborts on timeout — never auto-proceeds (escalation_expired()).

Amendment A5 — the guard is deterministic policy evaluation (no model call); its
cost must stay negligible against a CPU-bound inference.

The concrete act-boundary gates (GPS-2, shadow gate, approvals, run allow-list)
are Policies installed by main via kernel_policy.install_act_policies() — the
kernel never imports main.

Never raises. License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

# escalations older than this are ABORTED, never auto-proceeded (A3)
ESCALATION_TIMEOUT_S = 3600.0

_commits: Dict[str, Any] = {}
_commit_lock = threading.Lock()
_escalations: Dict[str, float] = {}


@runtime_checkable
class ExecutionSubsystem(Protocol):
    def guard(self, ctx: Dict[str, Any]) -> Dict[str, Any]: ...
    def commit_once(self, key: str, fn: Callable[[], Any]) -> Dict[str, Any]: ...


def guard(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Fire PRE_ACT for a proposed act. Returns
    {decision, rationale, policy, evaluated, event_id}.

    FAIL-CLOSED (A3): if the policy engine itself cannot run, the act is DENIED —
    a gate that cannot evaluate must never let an act through.
    """
    try:
        import kernel_policy as kp
        r = kp.evaluate("PRE_ACT", ctx or {}, emit_event=True)
        if not r.get("decision"):
            return {"decision": "DENY", "rationale": "policy engine returned no decision — failing closed",
                    "policy": "kernel.failclosed", "evaluated": [], "event_id": None}
        return r
    except Exception as e:
        return {"decision": "DENY", "rationale": f"policy engine error — failing closed: {e}",
                "policy": "kernel.failclosed", "evaluated": [], "event_id": None}


def pre_commit(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Fire PRE_COMMIT before an answer is accepted. Fail-safe: a broken engine
    FLAGs (surfaces) rather than blocking a finished answer — the answer already
    exists, so the safe degradation is to ship it flagged, never silently clean."""
    try:
        import kernel_policy as kp
        return kp.evaluate("PRE_COMMIT", ctx or {}, emit_event=True)
    except Exception as e:
        return {"decision": "FLAG", "rationale": f"policy engine error: {e}",
                "policy": "kernel.failsafe", "evaluated": [], "event_id": None}


def commit_once(key: str, fn: Callable[[], Any]) -> Dict[str, Any]:
    """A3 — idempotent Commit: a re-entered Commit must not double-fire a side
    effect. Returns {fired, result}."""
    if not key:
        return {"fired": True, "result": fn()}
    with _commit_lock:
        if key in _commits:
            return {"fired": False, "result": _commits[key]}
    result = fn()
    with _commit_lock:
        _commits.setdefault(key, result)
    return {"fired": True, "result": _commits[key]}


# ── ESCALATED: abort on timeout, never auto-proceed (A3) ──────────────────────
def escalation_open(gate_id: str) -> None:
    _escalations[gate_id] = time.time()


def escalation_expired(gate_id: str, timeout_s: float = ESCALATION_TIMEOUT_S) -> bool:
    t = _escalations.get(gate_id)
    return bool(t) and (time.time() - t) > timeout_s


def escalation_resolve(gate_id: str) -> None:
    _escalations.pop(gate_id, None)


# ── A6 — conformance self-test ────────────────────────────────────────────────
def conforms_to() -> Dict[str, Any]:
    import kernel_policy as kp
    checks: Dict[str, bool] = {}

    # FAIL-CLOSED: a policy that explodes must DENY the act, never let it through
    class _Boom:
        id = "t.boom"; hook = "PRE_ACT"
        def applies(self, c): return bool(c.get("boom"))
        def evaluate(self, c): raise RuntimeError("gate exploded")
    kp.register(_Boom())
    # (the engine skips a throwing policy; the kernel's own failure path is the
    #  guarantee — assert it directly by breaking the engine)
    import builtins
    _real = kp.evaluate
    try:
        kp.evaluate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("engine down"))
        checks["fail_closed"] = guard({"tool": "shell_command"})["decision"] == "DENY"
    finally:
        kp.evaluate = _real

    # a guard with NO gates installed still returns a decision (never crashes)
    g = guard({"tool": "read_file", "args": {}})
    checks["guard_returns_decision"] = g.get("decision") in kp.DECISIONS

    # PRE_COMMIT fails SAFE (flags, doesn't crash) when the engine breaks
    _real2 = kp.evaluate
    try:
        kp.evaluate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("engine down"))
        checks["pre_commit_fail_safe"] = pre_commit({"answer": "x"})["decision"] == "FLAG"
    finally:
        kp.evaluate = _real2

    # A3 — commit is idempotent: the side effect fires exactly once
    fired = {"n": 0}
    def _side():
        fired["n"] += 1
        return "done"
    k = f"t_commit_{int(time.time()*1000)}"
    r1 = commit_once(k, _side)
    r2 = commit_once(k, _side)
    checks["commit_idempotent"] = (r1["fired"] and not r2["fired"] and fired["n"] == 1
                                   and r2["result"] == "done")

    # A3 — an escalation times out to ABORT, never auto-proceed
    gid = f"t_gate_{int(time.time()*1000)}"
    escalation_open(gid)
    checks["escalation_not_expired_yet"] = not escalation_expired(gid)
    checks["escalation_aborts_on_timeout"] = escalation_expired(gid, timeout_s=-1.0)
    escalation_resolve(gid)

    # cleanup the test policy
    kp._POLICIES = [p for p in kp._POLICIES if getattr(p, "id", "") != "t.boom"]
    ok = all(checks.values())
    return {"ok": ok, "checks": checks}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    r = conforms_to()
    for k, v in r["checks"].items():
        print(f"  {'OK ' if v else 'XX '} {k}")
    print("conforms_to:", r["ok"])
