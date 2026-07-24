# Release Candidate 1 — Checklist

> Run against the [Quality Gate](QUALITY_GATE.md). Status is **evidence-based**:
> **PASS** (verified), **PENDING** (not yet verified — no false PASS), **N/A** (design-only,
> not in this build). RC-1 is declared only when no gate blocks and no High debt remains.

## UI
| Item | Status | Evidence |
|---|:--:|---|
| Typography (scale, no sub-11px) | ✅ PASS | 12→7 sizes, 0 sub-readable (UI-0006) |
| Contrast (body text ≥ 4.5:1) | ✅ PASS | `--text3` 2.4→4.76:1 (UI-0010) |
| Radius / token consistency | ✅ PASS | literal radii = 6/10/16/50% (UI-0007) |
| Keyboard (focus visible, Enter/Esc/Ctrl+Enter) | ✅ PASS | `:focus-visible`, modal Esc/trap (UI-0001/0005) |
| Accessibility (WCAG 2.1 AA: contrast/names/lang/landmarks/focus) | ✅ PASS | audit: 0 contrast fails/300 elts, 22/22 regression ([ACCESSIBILITY_AUDIT](ACCESSIBILITY_AUDIT.md)) |

## UX
| Item | Status | Evidence |
|---|:--:|---|
| Toolbar (one primary, grouped) | ✅ PASS | 10→ segmented mode control (UI-0008) |
| Decision load (≤ ~7 default heterogeneous choices) | ✅ PASS | Skills/Connections forms → contextual (UI-0009); Hick measured |
| Navigation (1-click page switch) | ✅ PASS | nav tablist; +Ctrl+K palette = future (UI-0014, S3) |
| Vocabulary (glossary + tooltips) | ✅ PASS | GLOSSARY.md + Council/Intel tooltips (UI-0012) |
| Error UX (human message + log id, no stack) | ✅ PASS | `friendlyError()` verified live (log id `T1SL`) |

## Backend
| Item | Status | Evidence |
|---|:--:|---|
| Security (no Critical/High) | ✅ PASS | C1–C3 closed; regression 10/10 |
| Performance (read APIs < SLA) | ✅ PASS | health/models/graph ~11–15ms (P1) |
| Journal kernel | ⏭️ N/A | design-only (`docs/v3/kernels/Journal.md`), not implemented |
| Reality Boundary kernel | ⏭️ N/A | design-only (`docs/v3/kernels/RealityBoundary.md`), not implemented |
| Governance (GPS-2 tool gate) | ✅ PASS | armed at load (agent-tool layer) — note: web layer now guarded separately |

## Reliability (chaos-tested — see [CHAOS_REPORT](CHAOS_REPORT.md))
| Item | Status | Evidence |
|---|:--:|---|
| Crash recovery | ✅ PASS | chaos EXP-1 (config recovery), EXP-2 (atomic save, no leak), EXP-4 (ACID rollback) |
| Restart | ✅ PASS | live kill+relaunch: healthy, settings intact, DB `wal` |
| Data integrity under concurrency | ✅ PASS | chaos EXP-3 (0 locks) + WAL at startup (EXP-5) |
| Resume (interrupted mission) | ⏭️ N/A | requires the unshipped Journal kernel (design-only) |

## Blocking summary
- **UI:** all PASS. **UX:** all PASS (S3/S4 remain as tracked debt, non-blocking).
- **Security/Perf:** PASS. **Reliability:** **PASS** (chaos-tested) — Resume is **N/A**
  (needs the unshipped Journal), which is *scope*, not a defect.
- **Visual Debt:** no open **S2** (UI-0009 closed) → **Zero High Visual Debt = PASS**.
- **No CRITICAL reliability issue remains** (chaos found 1 bug, CHAOS-001, now fixed +
  regression-guarded).

## RC-1 decision
**RC-1 = PASS.** UI, UX, Security, Performance, Zero-High-Visual-Debt, and Reliability
(crash/restart/integrity) are all green with evidence. The only non-green item —
*Resume of an interrupted mission* — is **N/A by scope** (the Journal kernel is design-
only), not an open defect, so it does **not** block RC-1.
Next: **freeze RC-1** → begin [Real User Validation](design/REAL_USER_VALIDATION.md).

> Honesty over ceremony: nothing is stamped PASS without evidence, and design-only
> capabilities are marked N/A — never PASS.
