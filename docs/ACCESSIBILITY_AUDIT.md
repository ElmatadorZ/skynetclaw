# Accessibility Audit — WCAG 2.1 AA

> Evidence-based audit of `index.html`, measured in a real browser (getComputedStyle /
> contrast math / DOM introspection), not opinion. Every fix is locked by
> [`backend/a11y_regression_test.py`](../backend/a11y_regression_test.py) (22 assertions).
> Scope: the automatable + measurable AA criteria. Date: 2026-07-01.

## Method
- Live preview of the SPA; `preview_eval` computed contrast ratios (WCAG 1.4.3 formula),
  accessible-name resolution, target sizes, landmarks, `lang`, duplicate ids.
- **Contrast** swept across the 5 primary pages (chat / skills / tools / connections /
  obsidian) — **300 visible text elements** measured.
- Each finding → fix → **re-measured** → static regression assertion.

## Findings & fixes (measured before → after)
| WCAG | Finding | Before | After | Fix |
|---|---|---|---|---|
| 1.4.3 Contrast | `--text3` (#647e9f) on card surfaces (bg3/bg4) | **3.9–4.3:1** (≈90 elements) | **≥4.5:1** | lift `--text3`→#7590b0 |
| 1.4.3 Contrast | `--text2` (#6a84a8) on bg4 | 4.27:1 | ≥4.5:1 | lift `--text2`→#7a91b3 |
| 1.4.3 Contrast | seg mode buttons used dim text3 | 4.3:1 | ≥4.5:1 | `.seg .tb-btn`→`--text2` |
| 1.4.3 Contrast | `.proc-title` used `--accent` | 4.3:1 | ≥4.5:1 | →`--accent2` |
| 4.1.2 Name | 8 controls with no accessible name | unnamed | named | aria-label map (model-sel, upload-input, nc-preset, nc-type, pkg-mgr, obs-model-sel, agent-max-steps, intg-svc, conn-sel) |
| 3.1.1 Lang | page `lang="en"` on Thai UI | en | **th** | `<html lang="th">` |
| 2.4.6 Headings | no `<h1>` | 0 | 1 | sr-only `<h1>` |
| 1.3.1 Landmark | no `main` | 0 | 1 | `role="main"` on active page |
| 2.5.8 Target | proc-close 20×23px | <24 | ≥24 | min 24×24 |

**Final measurement:** contrast failures **0 / 300 checked** across all pages · unnamed
controls **0** · `lang=th` · h1 **1** · main landmarks **1** · target sizes OK ·
0 console errors.

## Already in place (prior a11y layer, commit `6c47133`)
Visible `:focus-visible` ring (2.4.7) · ARIA tablist nav + `role=dialog` modals with
focus-trap + Esc (2.1.1/2.1.2/4.1.2) · icon-button labels · `aria-live` status region
(4.1.3) · `prefers-reduced-motion` (2.3.3) · friendly errors (3.3.1).

## Verdict
The **automatable / measurable WCAG 2.1 AA criteria PASS with evidence.**
Accessibility on the [Trust Scoreboard](TRUST_SCOREBOARD.md) moves **PARTIAL → PASS**.

## Honest scope (not claimed)
- Human-judgment AA criteria (meaningful sequence quality, sensory-characteristic
  wording, error-suggestion helpfulness, cognitive walkthrough) are **not** machine-
  verified here — best covered by [Real User Validation](design/REAL_USER_VALIDATION.md)
  with screen-reader + keyboard-only users.
- A fully **automated axe-core / Playwright** a11y run in CI is **Future Work**
  ([KNOWN_RISKS](KNOWN_RISKS.md)); today's guard is the static regression + this
  reproducible eval.
- Placeholder-only inputs (UI-0015, S3) still rely on placeholder as the name — an AA
  *name exists*, but a persistent visible label is the recommended improvement (deferred).

## Reproduce
Preview the SPA, run the contrast/name sweeps from this doc's method, and
`python backend/a11y_regression_test.py` (22/22).
