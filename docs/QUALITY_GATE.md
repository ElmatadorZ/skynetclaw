# Quality Gate

> The standard every change must clear before merge. Turns SkynetClaw from "well
> documented" into "has a release standard." Evidence-driven: each gate has an
> objective pass criterion and a **verification command/method** — not an opinion.

## Pipeline
```
change → Build → Lint → Test → Security → Performance → Accessibility
       → Visual Debt → UX → Regression → DecisionLog/ADR → Merge
```
A change **stops** at the first failing gate.

## Gates
| Gate | Pass criterion | How to verify (this repo) |
|---|---|---|
| **Build** | no import/compile error | `python -m py_compile backend/main.py`; `node -e` parse of `index.html` inline scripts |
| **Lint** | no syntax error; no obvious dead code in the diff | `py_compile` + script parse (above); manual diff read |
| **Test** | 100% of existing tests pass | `python backend/security_regression_test.py --http` (10/10) + `python backend/chaos_test.py` (reliability regressions) |
| **Security** | no Critical/High open | web-layer C1–C3 closed & regression-guarded; no new unauth RCE / secret exposure / path escape |
| **Performance** | key read APIs within SLA | probe: `/api/health` `/api/models` < 50ms; `/api/system/graph` cached < 50ms (see P1) |
| **Accessibility** | WCAG 2.1 AA: keyboard focus · ARIA · names · `lang` · landmarks · no contrast < 4.5:1 | `python backend/a11y_regression_test.py` (22/22) + browser contrast sweep (0/300) |
| **Visual Debt** | no **High (S2)** visual debt open | [`ui-debt/README.md`](../ui-debt/README.md) summary shows no open S2 |
| **UX** | no High-severity usability issue; each screen ≤ ~7 default heterogeneous choices | [UX_HEURISTICS](design/UX_HEURISTICS.md) Hick check; [decision-map](design/decision-map.md) |
| **Regression** | prior fixes still hold | re-run security + a11y evals after every UI/security change |
| **DecisionLog / ADR** | any kernel/architecture/scope decision recorded | `docs/v3/DecisionLog.md`; new ADRs for backend/AI-behavior changes |

## SLA reference (performance gate)
| Endpoint | SLA | Current |
|---|--:|--:|
| `/api/health` | < 50 ms | ~11 ms ✅ |
| `/api/models` | < 50 ms | ~10 ms ✅ |
| `/api/connections`, `/api/settings` | < 50 ms | ~11 ms ✅ |
| `/api/system/graph` (cached) | < 50 ms | ~15 ms ✅ |
| `/api/agent/run` (first token) | best-effort (model-bound) | n/a — depends on runtime |

## Severity policy (blocks merge)
- **Security** Critical/High → block. **Visual/UX** S1/S2 on a primary screen → block.
- S3/S4 → may merge with a tracked `ui-debt` entry.

## Evidence-driven rule
Every change after RC-1 follows:
```
Evidence → Hypothesis → Fix → Measurement → Regression → DecisionLog
```
No change is justified by "it feels better" — only by a measured before/after or a
recorded decision. This applies to Backend, UI, **and** AI behavior.

## Honesty clause
A gate is **N/A** (not PASS) when the capability is design-only and not in the build
(e.g. the V3 Journal / Reality Boundary kernels are `docs/v3` designs, not shipped code).
Never mark an unimplemented thing PASS.
