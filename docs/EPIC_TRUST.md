# EPIC: Trust  🔒

> **Status: OPEN — the only active epic.** Feature development is **frozen**. From now
> until this epic closes, a change is admissible **only** if it makes the system more
> trustworthy or produces evidence that it is. Everything else is deferred to
> [§6 Post-RC-1 backlog](#6-post-rc-1-backlog).
>
> This is the governance for the RC-1 freeze window. It operationalises the project's
> direction: **evidence-driven, not idea-driven.**

## 1. The one rule (PR admission criterion)
A pull request may merge **iff** it satisfies at least one:
- **(A) Reliability↑** — it makes a real failure less likely, smaller, or recoverable.
- **(B) Evidence↑** — it proves (with a test/measurement) that the system behaves as claimed.

If a PR does **neither**, it does not merge during the freeze — it is logged in the
Post-RC-1 backlog. **No exceptions for "small" features.**

## 2. What counts as Reliability↑ (A)
Security hardening · crash/restart/resume recovery · data-integrity · concurrency
safety · input validation · graceful degradation · atomic writes · timeouts/retries/
circuit-breakers · resource limits · error handling that prevents corruption ·
performance fixes that remove a failure mode (e.g. event-loop blocking).

## 3. What counts as Evidence↑ (B)
A new/expanded **regression test** (`security_regression_test.py`, `chaos_test.py`) ·
a **measured** before/after (latency, contrast, decision-load, lock counts) · a
reproducible **chaos experiment** · an **audit** with file:line evidence · a **gate**
that makes a property checkable (QUALITY_GATE). Evidence must be *runnable or
reproducible*, not narrative.

## 4. Decision table
| Change | Admissible now? | Why |
|---|:--:|---|
| Fix a bug + add a regression test | ✅ A+B | classic trust win |
| Add WAL / atomic write / timeout | ✅ A | removes a failure mode |
| Add a chaos/perf/a11y measurement | ✅ B | evidence |
| Refactor for testability (no behavior change) | ✅ B | enables evidence |
| Reduce visual/decision debt with measured proof | ✅ A/B | UX reliability + evidence |
| Documentation of an audit/decision (ADR, DecisionLog) | ✅ B | durable evidence |
| New agent / skill / tool / page / workflow | ❌ | feature → **defer** |
| Visual restyle without a measured problem | ❌ | taste, not trust |
| Dependency bump "to be current" | ❌ unless it fixes a CVE/failure | otherwise defer |

## 5. PR checklist (paste into every PR)
```
Epic: Trust
[ ] Track: (A) Reliability↑  and/or  (B) Evidence↑   ← at least one required
[ ] What failure does this make less likely / smaller / recoverable?  ______
[ ] Evidence attached (test name / measured before→after / chaos exp / audit ref): ______
[ ] Quality Gate green: build · py_compile/script-parse · security_regression --http (10/10)
      · chaos_test (all pass) · no new S1/S2 UI/UX debt
[ ] Regression: the failure this fixes now has a test that fails without the fix
[ ] DecisionLog/ADR updated if this changes a decision
[ ] If this is a feature → STOP, move to Post-RC-1 backlog
```
Merge blocks on any unchecked mandatory item. See [QUALITY_GATE.md](QUALITY_GATE.md).

## 6. Post-RC-1 backlog (deferred, not rejected)
Anything that fails §1 lands here with a one-line rationale. It is **not** worked on
until the epic closes. (Known deferrable items already tracked elsewhere: UI-0014
command palette, UI-0013 hardcoded host, UI-0015 input labels, UI-0016 red, UI-0017
empty-state wording — all S3/S4 in [ui-debt](../ui-debt/README.md); and the V3 kernels,
which are design-only.)

| Item | Type | Deferred because |
|---|---|---|
| _(add here as they arrive)_ | | |

## 7. Trust ledger — merged under this epic so far
Evidence the epic is already the operating mode (chronological, most recent last):
| Change | Track | Evidence |
|---|:--:|---|
| Security C1–C3 (RCE/exfil/path-escape) | A+B | `security_regression_test.py` 10/10 |
| P1 perf (health/models/graph 2.3s→~11ms) | A+B | measured latency |
| A11y layer (focus/ARIA/modals/errors) | A+B | browser eval, 0 console errors |
| Zero Visual Debt (UI-0006/07/08/10/12) | A/B | measured contrast/sizes/Hick |
| UI-0009 decision-load reduction | A/B | measured default-view controls |
| Chaos suite + CHAOS-001 fix + WAL | A+B | `chaos_test.py` all pass |
| QUALITY_GATE + RC1 checklist | B | release standard w/ criteria |

## 8. Exit criteria (when the freeze lifts)
The epic stays open through **RC-1 freeze → Real User Validation**. It closes when:
1. RC-1 is frozen (tagged) with no CRITICAL open in security/reliability, **and**
2. Real User Validation has run and its evidence is folded into `ui-debt` / DecisionLog.

After that, feature work resumes **under the same Quality Gate** — Trust becomes the
permanent bar, not a phase. Post-freeze, every change still follows:
`Evidence → Hypothesis → Fix → Measurement → Regression → DecisionLog`.

## 9. Enforcement
- A reviewer's first question is always: *"which track, and where's the evidence?"*
- A green Quality Gate is necessary but not sufficient — the change must also *increase
  trust*, not merely *not break it*.
- Design-only capability is never counted as reliability (it ships nothing). Mark N/A.
