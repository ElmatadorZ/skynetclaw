# UX Heuristic Evaluation — Nielsen's 10 (evidence-based)

> Scores the **current** SkynetClaw UI against Nielsen's 10 usability heuristics, each
> with concrete evidence from the code/DOM — not feeling. Re-run after each polish
> sprint. Baseline date: this sprint (after commit `6c47133`).

| # | Heuristic | Score | Evidence (for / against) |
|---|---|:--:|---|
| 1 | **Visibility of system status** | **8/10** | ✅ loading spinners, `showToast` + `aria-live`, agent step/process panel, connection dot. ❌ no global "working…" during long agent runs beyond the panel; `/api/health` status now fast (cached). |
| 2 | **Match with the real world** | **5/10** | ❌ heavy in-house jargon (House, Council, Governor, Continental Division, Concierge, Atlas, Mission) with **no glossary/tooltips** → new users must learn vocabulary ([UI-0012](../../ui-debt/README.md)). ✅ chat/search/connections use familiar words. |
| 3 | **User control & freedom** | **7/10** | ✅ Esc closes modals, focus-trap, Cancel buttons, clearChat. ❌ no global undo; no "back" within iframe views; no command palette to escape a wrong page fast. |
| 4 | **Consistency & standards** | **5/10** | ❌ measured drift: **12 font-sizes, 9 radii** (only 2 tokenised), mixed Thai/English/emoji voice, empty-state wording varies ([UI-0006/0007/0017](../../ui-debt/README.md)). ✅ shared CSS vars for color, consistent nav. |
| 5 | **Error prevention** | **7/10** | ✅ disabled buttons during work, confirm on destructive (delete connection guarded), input types. ❌ free-text paths without validation; no inline form validation on connection add (23 inputs). |
| 6 | **Recognition over recall** | **6/10** | ✅ visible nav tabs, model pills, skill badge. ❌ many inputs rely on **placeholder as label** (vanishes on type) ([UI-0015](../../ui-debt/README.md)); jargon demands recall (#2). |
| 7 | **Flexibility & efficiency** | **6/10** | ✅ keyboard send (Enter / Shift+Enter / Ctrl+Enter), model pills = 1 click. ❌ **no command palette / global search** ([UI-0014](../../ui-debt/README.md)); power actions buried in a 10-button toolbar. |
| 8 | **Aesthetic & minimalist design** | **5/10** | ❌ density hotspots: chat toolbar **10 buttons**, skills page **61 interactive / 32 buttons** competing for attention ([UI-0008/0009](../../ui-debt/README.md)); low-contrast `--text3` overused. ✅ clean dark palette, good whitespace in chat. |
| 9 | **Help users recover from errors** | **7/10** | ✅ `friendlyError()` now gives what/why/recover + `#log-id` (no stack) at 4 sites. ❌ remaining `e.message` sites elsewhere; iframe failure recovery is implicit (browser error page). |
| 10 | **Help & documentation** | **3/10** | ❌ no in-app help, no onboarding/first-run, no glossary, no shortcut cheatsheet. ✅ inline hints ("Enter ส่ง · Shift+Enter ขึ้นบรรทัด"). |

**Weighted average ≈ 5.9 / 10** — "usable, not yet polished." The two anchors dragging
the score are **Consistency (#4)** and **Help/Match-real-world (#10/#2: vocabulary)** —
both addressable by the [design-system](design-system.md) + a glossary, with **no new
features**.

## Top 5 heuristic-driven fixes (no features)
1. **#4 Consistency** — adopt the 6-step type scale + 4-step radius tokens; replace raw values. ([UI-0006/0007])
2. **#2/#10 Vocabulary** — ship a glossary + tooltips on House/Council/Mission/etc. ([UI-0012])
3. **#8 Minimalism** — progressive-disclose the chat toolbar (10→ primary + overflow) and skills cards. ([UI-0008/0009])
4. **#6 Recognition** — give placeholder-only inputs real labels. ([UI-0015])
5. **#7 Efficiency** — a Ctrl+K command palette over the *existing* pages/actions (navigation only, not a feature). ([UI-0014])

## Hick's Law — decision time per screen
Decision time grows with the number of visible choices: **T ≈ b · log₂(n + 1)**
(b normalised to 1 → relative units). `n` = interactive elements visible at first glance.
Measured in-browser; "after" reflects the UI-0008/UI-0009 disclosure work.

| Screen | n (before) | T before | n (after) | T after | Note |
|---|--:|--:|--:|--:|---|
| Chat | 18 | 4.25 | ~13 | 3.81 | modes → 1 segmented control (UI-0008) |
| **Skills** | 61¹ | 5.95 | 48¹ / **16→3 (forms)** | 5.61 / **2.00** | authoring forms now contextual (UI-0009) |
| **Connections** | 44¹ | 5.49 | 35¹ / **13→4 (forms)** | 5.17 / **2.32** | add-forms now contextual (UI-0009) |
| Tools | 6 | 2.81 | 6 | 2.81 | already low |
| Obsidian | 20 | 4.39 | 20 | 4.39 | target: default to one panel |

¹ counts include homogeneous **list rows**, which are a *scan* (recognition), not a Hick
choice among heterogeneous alternatives — so these overstate true decision time. The
honest, load-bearing number is the **forms** column: Skills 16→3 and Connections 13→4
visible controls in the default view, because that is where *competing, heterogeneous*
decisions lived. Removing them is what drops "which do I press first?" cognitive load.

**Rule going forward:** any screen whose default-view heterogeneous `n` exceeds ~7
(T > 3) must move authoring/secondary controls to a contextual layer
([progressive-disclosure.md](progressive-disclosure.md)).

> Re-score after each sprint; the goal is every heuristic ≥ 7 before
> [Real User Validation](REAL_USER_VALIDATION.md).
