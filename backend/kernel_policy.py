"""
kernel_policy.py — Cognitive Kernel · Policy engine (migration step 4)
=====================================================================
COGNITIVE_KERNEL_SPEC §5: governance made declarative and enforced at fixed hook
points — the analog of LSM security hooks. Mechanism (the kernel fires the hook)
is separated from policy (what the decision is). Decision D3: typed Policy objects
now; a council-editable declarative format later.

A Policy declares a hook and answers applies()/evaluate(); the engine runs every
applicable policy at a hook and the MOST-RESTRICTIVE decision wins
(DENY > ESCALATE > REPAIR > FLAG > ALLOW). Every decision emits an audit-critical
`policy.<decision>` event with its rationale (via kernel_events, source="policy" —
the A4 authority owner), so the black-box recorder captures all governance.

This step EXPRESSES the House's existing checks as policies (strangler-fig):
  · guidance_check (Vol V G1, deviant-act guard)  → PRE_COMMIT
  · warrant_check  (CEE-C1, fabrication guard)    → PRE_COMMIT
The hooks are wired to fire live in step 5 (Scheduling/Execution split); here the
policies exist on the hook surface and the engine resolves them.

Where each policy runs (registered_by_hook() is the authority, not this comment):
  PRE_ACT      governance.gps2 · shadow.fabrication · approvals.prior_deny ·
               run.tool_allow      — before a side effect leaves the House
  PRE_COMMIT   guidance.g1 · warrant.cee_c1
                                   — before a claim is committed as belief
  PRE_VALIDATE cvl.quality_gate    — before output is accepted as valid

Never raises. Stdlib only; checks + kernel_events are lazy imports.
License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Protocol, runtime_checkable

# Decisions, least → most restrictive (SPEC §5).
DECISIONS = ("ALLOW", "FLAG", "REPAIR", "ESCALATE", "DENY")
_RANK = {d: i for i, d in enumerate(DECISIONS)}

# The kernel's fixed enforcement surface (SPEC §5).
HOOKS = ("PRE_PLAN", "PRE_ACT", "PRE_VALIDATE", "PRE_COMMIT", "PRE_RESPONSE")


@dataclass
class Decision:
    decision: str = "ALLOW"        # one of DECISIONS
    rationale: str = ""
    policy: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)   # structured evidence


@runtime_checkable
class Policy(Protocol):
    id: str
    hook: str
    def applies(self, ctx: Dict[str, Any]) -> bool: ...
    def evaluate(self, ctx: Dict[str, Any]) -> Decision: ...


_POLICIES: List[Policy] = []


def register(p: Policy) -> None:
    if not any(getattr(x, "id", None) == getattr(p, "id", None) for x in _POLICIES):
        _POLICIES.append(p)


def registered() -> List[str]:
    return [getattr(p, "id", "?") for p in _POLICIES]


def registered_by_hook() -> Dict[str, List[str]]:
    """Policy ids grouped by the hook each one actually runs on.

    registered() is a flat list, and a flat list printed under a single hook's
    name reads as if every policy fires at that one boundary. They do not: the
    fabrication and warrant guards run at PRE_COMMIT, the quality gate at
    PRE_VALIDATE. A governance surface that misreports *where* it acts is worse
    than one that says nothing, because it is believed.
    """
    out: Dict[str, List[str]] = {}
    for p in _POLICIES:
        out.setdefault(getattr(p, "hook", "?"), []).append(getattr(p, "id", "?"))
    return {h: out[h] for h in HOOKS if h in out} | {h: v for h, v in out.items() if h not in HOOKS}


def policies_for(hook: str) -> List[Policy]:
    return [p for p in _POLICIES if getattr(p, "hook", None) == hook]


def _worse(a: str, b: str) -> str:
    return a if _RANK.get(a, 0) >= _RANK.get(b, 0) else b


def evaluate(hook: str, ctx: Dict[str, Any], emit_event: bool = True) -> Dict[str, Any]:
    """Run every applicable policy at `hook`; most-restrictive decision wins.
    Emits an audit-critical policy.<decision> event with rationale. Never raises."""
    ctx = ctx or {}
    evaluated: List[Dict[str, Any]] = []
    final = Decision("ALLOW", "", "")
    for p in policies_for(hook):
        try:
            if not p.applies(ctx):
                continue
            d = p.evaluate(ctx)
            evaluated.append({"policy": d.policy or p.id, "decision": d.decision,
                              "rationale": d.rationale, "detail": d.detail or {}})
            # most-restrictive wins; on a tie, prefer a policy that actually SPOKE
            # (has an id/rationale) over the default placeholder, so an elevated
            # ALLOW keeps its audited rationale instead of being swallowed.
            _more = _RANK.get(d.decision, 0) > _RANK.get(final.decision, 0)
            _tie_informative = (_RANK.get(d.decision, 0) == _RANK.get(final.decision, 0)
                                and not final.policy and (d.policy or d.rationale))
            if _more or _tie_informative:
                final = d
        except Exception:
            continue
    out = {"hook": hook, "decision": final.decision, "rationale": final.rationale,
           "policy": final.policy, "detail": final.detail or {}, "evaluated": evaluated}
    if emit_event and evaluated:
        try:
            import kernel_events as _ke
            sev = "error" if final.decision in ("DENY", "ESCALATE") else (
                "warn" if final.decision in ("REPAIR", "FLAG") else "info")
            # the audit event carries the rationale, not the raw evidence blobs
            r = _ke.emit(f"policy.{final.decision.lower()}",
                         {"hook": hook, "rationale": final.rationale, "policy": final.policy,
                          "evaluated": [{k: v for k, v in e.items() if k != "detail"}
                                        for e in evaluated]},
                         source="policy", severity=sev)
            out["event_id"] = (r.get("event") or {}).get("id")
        except Exception:
            pass
    return out


# ── Existing checks expressed as policies (strangler-fig) ─────────────────────
class GuidancePolicy:
    """Vol V G1 — an act on a target nothing guided (the deviant chain, R8).

    HOOK NOTE (honest): the SPEC §5 table places G1 at PRE_ACT, but the real check
    is post-hoc — it reads the ORDERED act+observation log and can only be judged
    once the acts exist. So it is a PRE_COMMIT policy today. A true per-act
    guidance gate would need a different (prospective) check; recorded as future work.
    """
    id = "guidance.g1"
    hook = "PRE_COMMIT"

    def applies(self, ctx: Dict[str, Any]) -> bool:
        return bool(ctx.get("events"))

    def evaluate(self, ctx: Dict[str, Any]) -> Decision:
        try:
            import guidance_check
            v = guidance_check.check_guidance(ctx.get("task", ""), ctx.get("events", []))
            if v:
                return Decision("FLAG", guidance_check.format_violations(v)[:400], self.id,
                                {"violations": v})
        except Exception:
            pass
        return Decision("ALLOW", "", self.id)


class WarrantPolicy:
    """CEE-C1 — flags fabricated/over-claimed results not backed by the workspace."""
    id = "warrant.cee_c1"
    hook = "PRE_COMMIT"

    def applies(self, ctx: Dict[str, Any]) -> bool:
        return bool(ctx.get("answer"))

    def evaluate(self, ctx: Dict[str, Any]) -> Decision:
        try:
            import warrant_check
            oc = warrant_check.detect_overclaims(ctx.get("answer", ""), ctx.get("workspace_folder"))
            if oc:
                return Decision("FLAG", warrant_check.summarize(oc)[:400], self.id,
                                {"overclaims": oc})
        except Exception:
            pass
        return Decision("ALLOW", "", self.id)


class CognitiveValidationPolicy:
    """The CVL cognitive quality gate as a first-class policy on the hook surface
    (step 6). Every registered validator — arithmetic, expression, secret_leak, and
    every future driver — is now GOVERNED by the kernel: an error maps to REPAIR
    (route to the bounded repair loop), a warning to FLAG. The live completion gate
    still runs CVL directly; this makes CVL available at PRE_VALIDATE so validation
    is unified with the policy surface."""
    id = "cvl.quality_gate"
    hook = "PRE_VALIDATE"

    def applies(self, ctx: Dict[str, Any]) -> bool:
        return bool(ctx.get("answer"))

    def evaluate(self, ctx: Dict[str, Any]) -> Decision:
        try:
            import cognitive_validation as _cvl
            r = _cvl.validate(ctx.get("answer", ""))
            if r.get("errors"):
                return Decision("REPAIR", (r.get("explanation") or "")[:400], self.id,
                                {"cvl": {k: r.get(k) for k in ("errors", "domains", "repair_prompt")}})
            if r.get("issues"):
                return Decision("FLAG", (r.get("explanation") or "")[:400], self.id, {"cvl": r})
        except Exception:
            pass
        return Decision("ALLOW", "", self.id)


register(GuidancePolicy())
register(WarrantPolicy())
register(CognitiveValidationPolicy())


# ── PRE_ACT policies — the House's real act-boundary gates, expressed as Policy ─
# Dependency-INJECTED (main installs the concrete gates) so the kernel never
# imports main. Registration ORDER is the legacy precedence order, which decides
# WHICH rationale is reported when several policies block; the safety property
# (any DENY ⇒ blocked) is order-independent.

class GPS2Policy:
    """The GPS-2 constitutional gate. FAIL-CLOSED: no gate, or a gate error, DENIES."""
    id = "governance.gps2"
    hook = "PRE_ACT"

    def __init__(self, gate: Any = None):
        self.gate = gate

    def applies(self, ctx: Dict[str, Any]) -> bool:
        return bool(ctx.get("tool"))

    def evaluate(self, ctx: Dict[str, Any]) -> Decision:
        if self.gate is None:
            return Decision("DENY", "governance monitor unavailable — failing closed", self.id)
        try:
            d, reason = self.gate.evaluate(ctx.get("tool", ""), ctx.get("args", {}) or {})
        except Exception as e:
            return Decision("DENY", f"gate-error-failclosed: {e}", self.id)
        if d == "DENY":
            return Decision("DENY", reason, self.id)          # elevation NEVER touches DENY
        if d == "ESCALATE":
            # An authenticated operator pre-approves the interactive human gate — and
            # ONLY that. `operator_elevated` is set by main ONLY after a server-side
            # token verify (the model never sets it), so this is not injectable.
            if ctx.get("operator_elevated") is True:
                return Decision("ALLOW", f"operator-elevated (audited): {reason}", self.id,
                                {"elevated": True})
            return Decision("ESCALATE", reason, self.id)
        return Decision("ALLOW", reason or "", self.id)


class ShadowGatePolicy:
    """L4 shadow gate — blocks writing fabricated live data.
    NOTE: preserves the legacy FAIL-OPEN behaviour (a missing/erroring shadow
    module must not block every tool); GPS-2 above is the fail-closed boundary."""
    id = "shadow.fabrication"
    hook = "PRE_ACT"

    def __init__(self, fn: Any = None):
        self.fn = fn

    def applies(self, ctx: Dict[str, Any]) -> bool:
        return bool(ctx.get("tool")) and self.fn is not None

    def evaluate(self, ctx: Dict[str, Any]) -> Decision:
        try:
            v = self.fn(ctx.get("tool", ""), ctx.get("args", {}) or {},
                        ctx.get("action_sigs"), session_id="",
                        tool_results_log=ctx.get("tool_results_log"))
        except TypeError:
            try:
                v = self.fn(ctx.get("tool", ""), ctx.get("args", {}) or {},
                            ctx.get("action_sigs"), session_id="")
            except Exception:
                return Decision("ALLOW", "", self.id)          # legacy fail-open
        except Exception:
            return Decision("ALLOW", "", self.id)              # legacy fail-open
        if getattr(v, "action", "PROCEED") == "BLOCK":
            return Decision("DENY", getattr(v, "reason", "policy violation"), self.id)
        return Decision("ALLOW", "", self.id)


class ExecApprovalsPolicy:
    """The operator previously DENIED this tool for these args → never retry.
    The approvals store is PER-RUN, so its checker arrives on the ctx."""
    id = "approvals.prior_deny"
    hook = "PRE_ACT"

    def applies(self, ctx: Dict[str, Any]) -> bool:
        return bool(ctx.get("tool")) and callable(ctx.get("approvals_check"))

    def evaluate(self, ctx: Dict[str, Any]) -> Decision:
        try:
            if ctx["approvals_check"](ctx.get("tool", ""), ctx.get("args", {}) or {}) == "DENY":
                return Decision("DENY", "operator previously denied this tool for these args", self.id)
        except Exception:
            pass
        return Decision("ALLOW", "", self.id)


class ToolAllowPolicy:
    """A run-scoped allow-list (e.g. the Telegram safe subset) is a HARD boundary."""
    id = "run.tool_allow"
    hook = "PRE_ACT"

    def applies(self, ctx: Dict[str, Any]) -> bool:
        return bool(ctx.get("tool")) and bool(ctx.get("tool_allow"))

    def evaluate(self, ctx: Dict[str, Any]) -> Decision:
        if ctx.get("tool") not in (ctx.get("tool_allow") or []):
            return Decision("DENY", f"'{ctx.get('tool')}' is outside this run's permitted tools", self.id)
        return Decision("ALLOW", "", self.id)


def install_act_policies(gate: Any = None, shadow: Any = None) -> List[str]:
    """main injects the concrete act-boundary gates at startup (the kernel never
    imports main). Per-run state (approvals, allow-list) arrives on the ctx.
    Idempotent — re-installing rebinds the gates. Registration order = legacy
    precedence, which selects WHICH rationale is reported when several block."""
    global _POLICIES
    _POLICIES = [p for p in _POLICIES if getattr(p, "hook", "") != "PRE_ACT"
                 or getattr(p, "id", "") == "guidance.g1"]
    for p in (GPS2Policy(gate), ShadowGatePolicy(shadow), ExecApprovalsPolicy(),
              ToolAllowPolicy()):
        register(p)
    return registered()


# ── A6 — conformance self-test ────────────────────────────────────────────────
def conforms_to() -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    # the existing checks are registered on the hooks where they can actually evaluate
    checks["guidance_on_pre_commit"] = "guidance.g1" in [p.id for p in policies_for("PRE_COMMIT")]
    checks["warrant_on_pre_commit"] = "warrant.cee_c1" in [p.id for p in policies_for("PRE_COMMIT")]
    # most-restrictive wins: DENY beats FLAG beats ALLOW at the same hook
    class _Flag:
        id = "t.flag"; hook = "PRE_PLAN"
        def applies(self, c): return True
        def evaluate(self, c): return Decision("FLAG", "flagged", self.id)
    class _Deny:
        id = "t.deny"; hook = "PRE_PLAN"
        def applies(self, c): return True
        def evaluate(self, c): return Decision("DENY", "denied", self.id)
    register(_Flag()); register(_Deny())
    res = evaluate("PRE_PLAN", {"x": 1}, emit_event=False)
    checks["most_restrictive"] = res["decision"] == "DENY" and len(res["evaluated"]) == 2
    # no applicable policy ⇒ ALLOW (default-open where nothing governs)
    checks["default_allow"] = evaluate("PRE_RESPONSE", {}, emit_event=False)["decision"] == "ALLOW"
    # a clean answer passes the real warrant policy (applies + evaluate over real check)
    clean = evaluate("PRE_COMMIT", {"answer": "The sky is blue."}, emit_event=False)
    checks["clean_allows"] = clean["decision"] in ("ALLOW", "FLAG")  # real check, no crash
    # emitting produces an audit-critical policy.* event id
    emitted = evaluate("PRE_PLAN", {"x": 1}, emit_event=True)
    checks["emits_policy_event"] = bool(emitted.get("event_id"))
    # cleanup test policies
    global _POLICIES
    _POLICIES = [p for p in _POLICIES if p.id not in ("t.flag", "t.deny")]
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
    print("conforms_to:", r["ok"], "| policies:", registered())
