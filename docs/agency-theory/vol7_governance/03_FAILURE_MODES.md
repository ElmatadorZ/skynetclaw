# Agency — Volume VII · 03 — Failure Taxonomy

> Pure philosophy. Questions 6 + 7. Every governance failure localizes to a broken node of
> the governance graph (Vol VII·01); the taxonomy **unifies the security audit's findings** —
> each P0/P1 is a named node-failure here. Recovered from constitutional theory, the
> reference-monitor tradition, and this session's reproduced attacks.

---

## The principle + the node-validation test

`governance = {policy → mediation → verdict → enforcement} + separation + accountability +
requisite variety + legitimacy`. If these are the right nodes, every failure localizes to one,
and each owns a distinct failure. The audit's findings slot in exactly — evidence the
Security Theory is Vol VII specialized (Vol VII·01).

| # | Failure | Broken node | This session's instance |
|---|---|---|---|
| GF1 | **Incomplete mediation** (a path around the monitor) | Mediation (GA3) | the P0: http_request→shim bypass |
| GF2 | **Fail-open** (monitor unavailable → ungoverned) | Mediation completeness (GA3) | governance evaluate→ALLOW; _GOV None |
| GF3 | **Privilege sprawl / ambient authority** | the governed's bounded variety | shim ran any of 97 tools with a token |
| GF4 | **Capture** (governor taken by the governed) | Separation (GA2) | (not observed; the confused deputy is its micro-form) |
| GF5 | **Insufficient variety** (governor can't cover the action space) | Requisite variety (GA5) | weak model + human gate over a rich tool-surface |
| GF6 | **Illegitimacy** (bound with no accepted ground) | Legitimacy (GA6) | — (the open node; tyranny's failure) |
| GF7 | **Ossification** (governance too rigid to adapt) | the secondary/change loop | a static allow-list vs an evolving tool-surface |
| GF8 | **Goodhart** (govern by a gamed proxy) | Policy fidelity | governing "tool name" while the real risk is the operation |

## GF1 · Incomplete mediation — *the constitutive failure*
A single action path that does not cross the monitor voids the bound (GA3). The audit's
reproduced P0 is exactly this: `http_request` reached the executor around the name-based gate.
It **cannot** be produced by a policy error, an enforcement gap, or a variety gap — those can
all be perfect while one path is unmediated. **A governor is only as complete as its least-
mediated boundary** — the governance-layer restatement of the Security Theory's headline (a
per-name gate is worthless while an ungated executor exists). SUPPORTED, reproduced.

## GF2 · Fail-open — *mediation completeness on the error path*
When the monitor is unavailable or errors and the system proceeds anyway, mediation is
incomplete *in time* (GA3 fails on the error branch). The audit found governance evaluate()
defaulting to ALLOW and `_GOV is None` running ungated. **A gate that fails open is not a
gate** — completeness must hold on every branch, including failure. The fix (fail-closed) is
GA3 enforced on the error path. SUPPORTED, reproduced + fixed.

## GF3 · Privilege sprawl / ambient authority — *the governed's variety exceeds its grant*
The governed acquires authority the governor never granted (escalation) — the shim executing
any of 97 tools for a token-holder. Structurally the governed's *effective* action-space grew
past its *authorized* one. The fix (shim allow-list = 16) shrinks the governed's variety back
to the governor's — Ashby (GA5) enforced by construction. SUPPORTED, reproduced + fixed.

## GF4 · Capture — *separation breaks in practice*
The governor comes to serve the governed (regulatory capture; a compromised monitor). Form
preserved, GA2 hollowed. The **confused deputy** is its micro-form: a deputy inside the trust
boundary made to act for a less-privileged client. Not observed at the macro level here, but
the deputy version was the P0's engine. SUPPORTED (as a category); LIKELY-relevant.

## GF5 · Insufficient variety — *the frontier failure (Ashby)*
The governor cannot cover the governed's action space — a weak model + a static allow-list +
a human-on-escalate governing a rich, growing tool-surface. Nothing in the governor is
"broken"; it is simply *out-varied*, so its completeness is only as good as its enumeration,
and the un-enumerated path is the hole (GF1's supply). **This is the governance frontier the
system sits at now** — structure present (GA1–GA4), variety absent (GA5) — and it is the
scalable-oversight problem in situ. SUPPORTED (Vol VII·02 self-diagnosis).

## GF6 · Illegitimacy — *bounds without accepted ground*
A governor that bounds by coercion with no legitimate authority (tyranny) — GA6 fails while
mediation + enforcement hold. Compliance decays or is mere force. Its ground — *why* a bound
is binding — is the open node (Vol VII·04). Not a runtime bug here (the operator is the
legitimate authority), but the deepest structural question. SUPPORTED (as a category) / OPEN
(as a ground).

## GF7 · Ossification & GF8 · Goodhart
- **GF7 (ossification):** governance too rigid to adapt — a static allow-list against an
  evolving tool-surface; the secondary/change loop (Hart) fails, so the policy lags the
  world (the governance twin of Vol VI's distributional shift). LIKELY.
- **GF8 (Goodhart):** governing by a proxy that is gamed — gating the *tool name* while the
  real hazard is the *operation* (execute_script reachable under a different name, or via
  navigate's side effects). The Vol II reward-hacking / Vol VI signal-corruption hazard at the
  governance layer: **the map governed is not the territory of harm.** SUPPORTED (the P0 had
  this flavour — name-based, not effect-based, mediation).

## What the taxonomy establishes
1. **Every audit finding is a named governance-node failure** — GF1 (P0 bypass), GF2 (fail-
   open), GF3 (sprawl), GF5 (weak governor). The Security Theory is Vol VII's failure
   taxonomy restricted to authority. SUPPORTED — the concrete payoff of the capstone.
2. **The constitutive failures are mediation-side** — GF1/GF2 (completeness) void governance
   outright; capture/illegitimacy corrupt it; variety/ossification bound it. Severity tracks
   depth: an unmediated path (GF1) is worse than a rigid policy (GF7). SUPPORTED.
3. **The system's live failure is GF5 (variety), not GF1** — the P0 (GF1) is fixed; what
   remains is the governor being out-varied by the governed (the frontier). Naming which
   failure is live is the auditor's discipline. SUPPORTED.

## Falsifiers
The unification fails if an audit finding maps to *no* governance node. GF1-as-constitutive
fails if governance survives a permanent unmediated path. The Security-as-special-case (GF1–
GF3 = escalation) fails if a capability escalation is exhibited that is not a mediation /
variety / separation failure.
