# Cognitive Kernel Spec — Engineering Council Review

**Reviews:** COGNITIVE_KERNEL_SPEC v0.1 → produces v0.2 amendments
**Date:** 2026-07-13 · **Constitution:** Article IX (Engineering Council), XI (Verification)
**Verdict:** **Accept with amendments.** The architecture is sound and fully
traceable to real components. Eight lenses raised six substantive amendments (A1–A6),
now folded into Spec v0.2. No amendment changes the six pillars — they harden edges
the draft left open.

---

## Ratification decisions (operator, 2026-07-13)

| # | Decision | Effect on spec |
|---|---|---|
| D1 | **Sync control + best-effort events** | §3 service-call rules confirmed; forces A2 (audit durability) |
| D2 | **Per-request cognitive id, grouped by mission** | §4 `correlation_id` = cognitive request id; mission id is a group key |
| D3 | **Code `Policy` objects now; declarative format later** | §5 phase 1 = typed Policy objects on hooks |
| D4 | **Council review first, then migrate** | this document; migration gated on it |

---

## Lens findings

**① Architect — coherence & boundaries.** Pillars map cleanly; CVL as reference
subsystem is correct. *Gap:* the Scheduling↔Governance boundary is fuzzy — who
decides CHAT vs council? → **A1**.

**② Skeptic — what breaks.** The gate path is fail-safe, but there is **no
degradation story for a service that fails mid-lifecycle** (Memory down during
Contextualize; Reflect crashes after a side effect already fired). Silent hang or
partial commit is possible. → **A3** (service-failure degradation + commit
idempotency).

**③ Security — trust boundaries.** Hooks are good, but any subsystem can `publish`
any event, including a spoofed `policy.allow`. Authority over `policy.*` and
`cognitive.*` verdicts must be restricted to their owning service. → **A4**.

**④ Reliability — the audit spine vs best-effort (D1).** Direct contradiction: §4
calls the event log the "black-box recorder," yet D1 makes events best-effort — so
the audit could be *incomplete exactly when it matters*. Resolution: split
**audit-critical** events (policy decisions, commits, escalations → synchronous,
durable) from **observational** events (best-effort). → **A2**.

**⑤ Performance — kernel overhead on a CPU-bound host.** Evaluating every policy at
every hook is fine now (`applies()` predicate exists), but the kernel's own cost
must stay negligible vs the model call. Needs an explicit budget. → **A5**.

**⑥ Maintainer — half-migrated ambiguity.** The strangler-fig plan (§8) has no
"definition of done" per step; a partially-conformed module is indistinguishable
from a finished one. → **A6** (per-subsystem conformance marker + test).

**⑦ Operator/Cost.** Physical envelope is honored (Principle #7). No further action;
A5 covers kernel overhead.

**⑧ Governance/Ethics — the ESCALATED dead-end.** `ESCALATED` has no timeout and no
default. If the human never resolves, the request hangs forever, and an
"escalate-then-proceed" bug could default-allow. Escalation must time out to a
**safe default = abort, never proceed**. → folded into **A3**.

---

## Past-mission walkthrough (Spec §6 state machine)

Replaying four real missions from this session against the state machine — does any
phase go missing?

| Mission (real) | Path through the machine | Verdict |
|---|---|---|
| 16k overflow → councils marked failed | CONTEXTUALIZING should reject an over-budget prompt; old flow overflowed at EXECUTING → STALLED | ✅ Context Service invariant (P#7) catches it *earlier* than the bug did — design is an improvement |
| Agent ignored its own vault (find_files→[]) | EXECUTING → `resolve(path)` with vault exemption | ✅ Execution `resolve` interface covers it |
| CVL wrong-math repair | EXECUTING → VALIDATING(defect) → REPAIRING → VALIDATING → COMMITTING | ✅ exact match to §6 |
| Continental action-bias bypassed council | PERCEIVING → classify; must route CONTEXTUALIZING → DELIBERATING (was skipped) | ✅ confirms classification belongs to Scheduling, deliberation to Governance (→ A1) |

**Result:** no missing phase. The machine models real missions, and in the overflow
case it would have *prevented* the historical bug. One boundary clarification (A1)
surfaced.

---

## Amendments folded into Spec v0.2

- **A1 — Scheduling vs Governance boundary.** Scheduling *classifies and routes*
  (CHAT/mission/deliberation); Governance *deliberates* when routed to DELIBERATING
  and *authors policy*. Classification is never Governance's job.
- **A2 — Two event tiers.** *Audit-critical* (`policy.*`, `mission.commit`,
  `*.escalated`) are synchronous + durably logged; *observational* (`lifecycle.*`,
  `memory.*`, notes) are best-effort. The black-box recorder = the audit-critical
  tier.
- **A3 — Service-failure & escalation safety.** A service failing mid-lifecycle
  degrades to a defined safe state (block/flag, never silent-proceed); Commit is
  idempotent (a re-entered Commit must not double-fire a side effect); `ESCALATED`
  has a timeout whose default is **abort**, never proceed.
- **A4 — Event authority.** Only the Policy service may emit `policy.*` verdicts;
  only the Validation service may emit `cognitive.*` verdicts. The bus tags
  `source`; consumers of authority-events trust only the owning source.
- **A5 — Kernel perf budget.** Kernel orchestration (routing + hooks + eventing)
  must cost < 5% of a request's wall-clock on the CPU-bound host; policies use the
  `applies()` predicate and are indexed by hook.
- **A6 — Conformance marker.** Each migrated subsystem ships a
  `conforms_to(interface)` self-test in `eval_suite`; a module is "migrated" only
  when its conformance case is green. Distinguishes done from half-done.

**Recommendation to the operator:** move ADR-0003 to **Accepted** and begin
migration step 1 (Event envelope, now with the A2 two-tier split). Validators remain
paused until the foundational steps (Event → Context/Memory → Policy-on-hooks) land.
