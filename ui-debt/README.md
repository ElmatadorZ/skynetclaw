# UI Debt Register

> Product debt, tracked like technical debt. Every known UI/UX defect gets an ID,
> severity, location, fix, and status. Sourced from the QA + Design Review sprints,
> grounded in the real code/DOM (`index.html`). **Screenshots are intentionally not
> fabricated** — each entry gives an exact location + repro; capture live during the
> [Real User Validation](../docs/design/REAL_USER_VALIDATION.md) session.
>
> Severity: **S1** blocker · **S2** major · **S3** minor · **S4** polish.
> Status: 🔴 open · 🟡 in-progress · ✅ fixed.

## Summary
| ID | Title | Sev | Status |
|---|---|:--:|:--:|
| UI-0001 | No visible keyboard focus | S2 | ✅ |
| UI-0002 | Raw exception text shown to users | S2 | 🟡 |
| UI-0003 | iframe blank-white loading dead-end | S3 | ✅ |
| UI-0004 | Zero ARIA / no screen-reader semantics | S2 | ✅ |
| UI-0005 | Modals: no focus-trap / Esc-to-close | S3 | ✅ |
| UI-0006 | Type-scale chaos (12 font-sizes) | S2 | ✅ |
| UI-0007 | Radius inconsistency (9 values, 2 tokens) | S3 | ✅ |
| UI-0008 | Chat toolbar overload (10 buttons) | S2 | ✅ |
| UI-0009 | Skills/Connections over-density | S2 | ✅ |
| UI-0010 | Low-contrast `--text3` on body text | S2 | ✅ |
| UI-0011 | Status conveyed by colour alone | S3 | 🟡 |
| UI-0012 | In-house vocabulary, no glossary | S2 | ✅ |
| UI-0013 | Hardcoded `localhost:8766` | S4 | 🔴 |
| UI-0014 | No command palette / keyboard-first nav | S3 | 🔴 |
| UI-0015 | Inputs rely on placeholder as label | S3 | 🔴 |
| UI-0016 | Over-saturated danger red | S4 | 🔴 |
| UI-0017 | Empty-state wording inconsistent | S4 | 🔴 |

## Sprint status — Zero High Visual Debt = ✅ PASS
Closed to date: **UI-0006, UI-0007, UI-0008, UI-0010, UI-0012** (Zero-Visual-Debt sprint) +
**UI-0009** (Decision-Load Reduction) — all verified live (DOM/contrast/decision-load
measured, code parses, no code-origin console errors).
- **No open High-severity (S2) visual debt remains → "Zero High Visual Debt" PASS.**
- All remaining open items are **S3/S4**: UI-0011 status shape, UI-0013 hardcoded host,
  UI-0014 command palette, UI-0015 input labels, UI-0016 red, UI-0017 empty-state wording,
  plus the S4 follow-ups noted on UI-0006/0008/0012.
- **Next:** verify Reliability items → declare RC-1 ([RC1_CHECKLIST](../docs/RC1_CHECKLIST.md))
  → freeze → [Real User Validation](../docs/design/REAL_USER_VALIDATION.md).

---

### UI-0001 — No visible keyboard focus ✅
- **Problem:** `outline:none` across inputs/buttons removed all keyboard focus indication.
- **Impact:** keyboard/screen-reader users cannot see where they are. WCAG 2.4.7 fail.
- **Location:** global CSS (`outline:none` rules).
- **Fix:** global `:focus-visible` accent ring (keyboard-only). **Done — `6c47133`.**
- **Status:** ✅

### UI-0002 — Raw exception text shown to users 🟡
- **Problem:** `${e.message}` / `${esc(e.message)}` rendered directly in the UI.
- **Impact:** exposes internals, unactionable, unfriendly. Heuristic #9.
- **Location:** `index.html` (connections, tools, search, memory + others).
- **Fix:** `friendlyError()` → message + reason + recovery + `#log-id`, detail to console. 4 sites done (`6c47133`); **remaining sites open.**
- **Status:** 🟡 (sweep the rest)

### UI-0003 — iframe blank-white loading dead-end ✅
- **Problem:** Council/Intel iframes showed blank white while loading; no state if backend down.
- **Impact:** looks broken; user can't tell loading from failure.
- **Fix:** overlay loading veil (layout-safe, no reparenting), clears on load. **Done — `6c47133`.**
- **Status:** ✅

### UI-0004 — Zero ARIA / no screen-reader semantics ✅
- **Problem:** `aria-*` count was 0 across 4200 lines.
- **Impact:** unusable with a screen reader. WCAG 4.1.2.
- **Fix:** nav tablist, icon-button labels, live region, dialog roles (`6c47133`) **+ full
  WCAG 2.1 AA audit**: contrast **0 fails/300 elts**, 9 controls named, `lang=th`, sr-only
  `<h1>`, `role=main`, target-size. Locked by `a11y_regression_test.py` (22/22). See
  [ACCESSIBILITY_AUDIT](../docs/ACCESSIBILITY_AUDIT.md).
- **Residual:** placeholder-only inputs (UI-0015, S3) + automated axe CI (Future Work).
- **Status:** ✅

### UI-0005 — Modals: no focus-trap / Esc-to-close ✅
- **Fix:** generic `.modal-bg` handler — role=dialog, focus first field, Tab trap, Esc closes. **Done — `6c47133`.**
- **Status:** ✅

### UI-0006 — Type-scale chaos ✅
- **Problem:** **12 distinct font-sizes** in the live DOM (incl. 8.5px, 10.5px — sub-readable).
- **Impact:** inconsistent rhythm, reads "amateur"; tiny text fails readability. Heuristic #4/#8.
- **Location:** ad-hoc `font-size` across `index.html`.
- **Fix:** `:root` type tokens (`--fs-xs:11 / --fs-sm:12 / --fs-base:14 / --fs-title:15`);
  normalised 8.5/9/10/10.5/12.5/13px → scale. **Measured: 12 → 7 distinct, zero sub-11px text.**
- **Status:** ✅ (S2 closed; residual 13/13.5/17px are em/%-derived & readable → S4 note)

### UI-0007 — Radius inconsistency ✅
- **Problem:** **9 radius values** (4,5,6,7,9,10,12,16,50%) but `:root` defines only `--radius`,`--radius-sm`.
- **Impact:** visually noisy corners; system tokens bypassed.
- **Fix:** token scale `--radius-sm:6 / --radius:10 / --radius-full:50%`; normalised 4/5/7→6, 9/12→10.
  **Measured: literal radii now 6/10/16(bubble)/50% only** (computed 7/9px = round dots resolving `50%`).
- **Status:** ✅

### UI-0008 — Chat toolbar overload 🔴
- **Problem:** chat toolbar has **10 equally-weighted buttons** (modes + Exec + Run Task + Internet + badge).
- **Impact:** no focal point on the primary screen; attention jumps. Heuristic #8; Cognitive-Flow fail.
- **Location:** `index.html` `.chat-toolbar`.
- **Fix:** the 5 mode buttons are now **one segmented control** (`.seg`, role=group) — reads as a
  single control instead of 5 competing buttons; logic unchanged (`setMode` still toggles).
  Secondary-action de-emphasis (Exec/RunTask/Internet) tracked as S4 follow-up.
- **Status:** ✅ (primary overload resolved; secondary-cluster polish → S4)

### UI-0009 — Skills / Connections over-density ✅
- **Problem:** Skills page = **61 interactive / 32 buttons**; Connections = **44 / 23 inputs**.
- **Impact:** lowest scanability; decision effort high ("which do I press first?").
- **Fix:** **decision-load reduction, not button-hiding** — the always-open authoring forms
  became **contextual**: Skills form (13 controls) revealed only by New/edit; Connections
  add-forms (9 controls) revealed by ➕ Add. Existing functions **decorated** (logic
  untouched), forms auto-close on save. **Measured default view: Skills 16→3, Connections
  13→4 controls; Hick 3.81→2.32.** All functionality preserved.
- **Refs:** [decision-map](../docs/design/decision-map.md) · [progressive-disclosure](../docs/design/progressive-disclosure.md)
- **Status:** ✅

### UI-0010 — Low-contrast `--text3` on readable text 🔴
- **Problem:** `--text3 #3d5068` on `--bg #07090f` ≈ **2.4:1** (WCAG AA needs 4.5:1).
- **Impact:** hints/labels using text3 are hard to read. WCAG 1.4.3.
- **Fix:** lifted `--text3` `#3d5068` → `#647e9f`. **Measured contrast 2.4 → 4.76:1 on `--bg`** (passes WCAG AA).
- **Status:** ✅

### UI-0011 — Status conveyed by colour alone 🟡
- **Problem:** connection dot / internet dot use colour only.
- **Impact:** color-blind users can't read status. WCAG 1.4.1.
- **Fix:** colour **+ shape/icon + text** (`● online` / `▲ offline`). Dot got an `aria-label` (`6c47133`); visual shape/label still open.
- **Status:** 🟡

### UI-0012 — In-house vocabulary, no glossary 🔴
- **Problem:** House, Council, Governor, Continental Division, Mission, Concierge, Atlas — no definitions/tooltips.
- **Impact:** new users must learn jargon; Heuristic #2 (match real world) = 5/10.
- **Fix:** [GLOSSARY.md](../docs/design/GLOSSARY.md) defines all terms plainly; `title` tooltips added to
  Council + Intel nav. In-iframe term tooltips (agent names) tracked as S4 follow-up.
- **Status:** ✅ (glossary + primary tooltips; iframe-content tooltips → S4)

### UI-0013 — Hardcoded `localhost:8766` 🔴
- **Problem:** `const API`, iframe `src`, script `src` hardcode the host (4 places).
- **Impact:** breaks if host/port differs; portability.
- **Fix:** derive from current origin / single config constant.
- **Status:** 🔴

### UI-0014 — No command palette / keyboard-first nav 🔴
- **Problem:** navigation is mouse-click only (except chat send).
- **Impact:** slow for power users; Heuristic #7.
- **Fix:** Ctrl+K palette over **existing** pages/actions (navigation, not a new capability).
- **Status:** 🔴

### UI-0015 — Inputs rely on placeholder as label 🔴
- **Problem:** many inputs have only a placeholder (disappears on type); no `<label>`/`aria-label`.
- **Impact:** Heuristic #6; screen-reader + recall cost.
- **Fix:** add `<label>` or `aria-label` to every input.
- **Status:** 🔴

### UI-0016 — Over-saturated danger red 🔴
- **Problem:** `--red #ff1a2e` is harsh on the dark palette.
- **Fix:** soften to ~`#f0566b`; reserve pure red for true blockers.
- **Status:** 🔴

### UI-0017 — Empty-state wording inconsistent 🔴
- **Problem:** empty states mix Thai/English, some have a CTA, some don't.
- **Fix:** one voice + the empty-state rule (icon + what + CTA) from design-system §8.
- **Status:** 🔴

---
## How to use this register
1. New defect → next `UI-XXXX`, fill all fields, add to the summary table.
2. Fix → reference the commit, flip status ✅.
3. Review the table at the start of every polish sprint; nothing ships with an open **S1/S2**
   on a primary screen (Chat, Connections).
