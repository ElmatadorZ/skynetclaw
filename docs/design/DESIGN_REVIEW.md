# Design Review Sprint — Phases B / F / H + Cognitive Flow / Density / Delight

> Polish-only review of the 7 screens, grounded in measured DOM data (interactive-element
> counts, type/radius scales) — not impressions. Companion: [design-system](design-system.md),
> [UX_HEURISTICS](UX_HEURISTICS.md), [UI Debt Register](../../ui-debt/README.md).
>
> **Measured density (interactive elements / buttons per page):** chat 18/14 ·
> connections 44/13 (23 inputs) · skills **61/32** · obs 20/14 · tools 6/4 ·
> council & intel 0 (iframe). Globally: **12 font-sizes, 9 radii** in use.

## Phase B — Visual Hierarchy (Before → After → Reason)

### Chat (primary screen — users live here)
- **First seen:** a 10-button toolbar (Auto/Chat/Code/Files/Shell + Exec/Run Task/Internet/skill badge) competing with the message area.
- **Before:** 10 equally-weighted toolbar buttons; mode + actions + status all on one row.
- **After:** *Mode* (Auto/Chat/Code/Files/Shell) collapses into one segmented control or a single "Mode ▾"; *Run Task / Exec / Internet* move to a right-aligned secondary cluster; skill badge stays. One visual primary = the message input + Send.
- **Reason:** the input is the job; the toolbar should recede. 10→~4 visible controls cuts attention competition. *(Progressive disclosure, no features removed — just grouped.)* → [UI-0008](../../ui-debt/README.md)

### Skills (densest — 61 interactive / 32 buttons)
- **First seen:** a wall of skill cards each with multiple buttons.
- **Before:** every card fully expanded with all actions visible.
- **After:** collapse cards to title + on/off; reveal edit/delete/triggers on hover/expand; a single top bar for bulk actions (Import OS, search/filter).
- **Reason:** 32 buttons = no focal point. Progressive disclosure restores scanability. → [UI-0009]

### Connections (44 interactive, 23 inputs)
- **Before:** endpoints + integrations + add-forms all open at once.
- **After:** the add-form is a disclosure ("+ Add endpoint") that expands on demand; list first.
- **Reason:** reading what exists shouldn't compete with creating new. → [UI-0009]

### Tools (6 interactive — too little)
- **Before:** sparse list, lots of empty space, low information scent.
- **After:** add category grouping + count badges + a one-line description per tool (info already available from `/api/tools/builtin`). *(No new data — surface what exists.)*
- **Reason:** density too low = wasted screen, low scanability.

### Obsidian / Council / Intel
- Obsidian: editor + chat + graph compete; default to one, reveal others on demand.
- Council/Intel: iframes — now have a loading veil; the only hierarchy fix is a thin breadcrumb ("Intel ▸ Node Map") so users know where they are inside the embedded view.

**Progressive-disclosure candidates (system-wide):** chat mode switch, chat secondary
actions, connection add-forms, skill card actions, obsidian secondary panels.

## Phase F — Navigation Cost
| Path | Clicks today | Can it be shorter? |
|---|--:|---|
| Switch top-level page | 1 (nav tab) | ✅ already minimal; add **Ctrl+K palette** for keyboard-first jump ([UI-0014]) |
| Switch model | 1 (model pill) | ✅ good |
| New endpoint | tab → expand-less form → 4+ fields → save (~6) | reduce by collapsing form + tab-order + Enter-to-save |
| Open a skill's triggers | card already expanded (scroll) | after disclosure: 1 (expand) — clearer |
| Get into Council/Intel | 1 (tab) + iframe load | veil added; unchanged otherwise |

- **Mouse travel / eye movement:** chat toolbar spreads primary+secondary across the full
  width → eyes ping-pong. Grouping (Phase B) shortens travel.
- **Context switching:** Council/Intel are iframes = a full document context switch; keep,
  but the breadcrumb reduces disorientation.
- **Keyboard-first gap:** only chat/search have shortcuts. A **command palette over existing
  pages/actions** (no new capability) would make the whole app keyboard-navigable. → [UI-0014]

## Phase H — Professional Finish (principles, not appearance)
Why Linear / Raycast / VS Code / GitHub Desktop / JetBrains *feel* premium, and what to apply:
| Principle they share | SkynetClaw today | Apply (polish only) |
|---|---|---|
| **One type scale, one spacing grid** | 12 font-sizes, 9 radii | converge to the [design-system](design-system.md) scales |
| **One primary action per view** | chat: ~10 equal buttons | single primary + grouped secondary |
| **Keyboard-first (palette)** | mostly mouse | Ctrl+K over existing nav/actions |
| **Restraint / minimalism** | dense skills/connections | progressive disclosure |
| **Quiet, consistent color; status = color+icon+text** | some color-only status, harsh red | soften red, add shape+label |
| **Predictable feedback on every action** | good (toast/stream) — keep | extend to remaining `e.message` sites |
| **Calm motion** | mixed; now respects reduce-motion | standardise 120–200ms |
**What makes premium feel premium:** *nothing competes*, *everything is consistent*, *every
action confirms itself*, *the keyboard can do anything*. None require new features.

## Cognitive Flow Audit (Attention → Decision → Action → Feedback)
| Screen | Attention | Decision | Action | Feedback | Verdict |
|---|---|---|---|---|---|
| Chat | ⚠ jumps (10-btn toolbar) | ✅ clear (type) | ✅ Send/Enter | ✅ stream+toast | **Fix attention** |
| Skills | ❌ no focal point (32 btns) | ⚠ effortful | ✅ | ✅ toast | **Fix attention+decision** |
| Connections | ⚠ form+list compete | ⚠ which field? | ✅ | ✅ | **Fix attention** |
| Tools | ✅ calm | ✅ | ✅ | ⚠ thin | OK (add scent) |
| Obsidian | ⚠ 3 panels | ⚠ | ✅ | ✅ | Fix attention |
| Council/Intel | ✅ (single iframe) | ✅ | n/a | ✅ veil | OK |
**Rule applied:** where *attention jumps* or *decision takes effort*, the screen failed —
all trace back to **too many equally-weighted controls** → fixed by hierarchy + disclosure.

## Information Density Audit
| Screen | Signal | Noise | Density | Scanability | Note |
|---|--:|--:|--:|--:|---|
| Chat | 8 | 6 | 7 | 6 | toolbar is noise on a content screen |
| Skills | 6 | 9 | 9 | 4 | **over-dense**, 61 elements |
| Connections | 7 | 7 | 8 | 5 | forms inflate density |
| Tools | 5 | 2 | 3 | 7 | **under-dense**, low scent |
| Obsidian | 7 | 6 | 7 | 6 | 3 competing panels |
| Council/Intel | 7 | 2 | 5 | 8 | clean (embedded) |
Targets: Skills/Connections **down** via disclosure; Tools **up** via grouping+descriptions.

## Delight Review (micro-interactions that earn "this feels good")
Low-effort, high-delight (all polish, no features):
- **Press feedback** — `translateY(1px)` on buttons (added) → tactile.
- **Focus ring** — crisp accent2 ring on keyboard nav (added).
- **Veil → content fade** on iframe load (added) → no jarring swap.
- **Model pill select** — add a subtle scale/checkmark on the active pill.
- **Copy** — code blocks should get a hover "Copy" with a 1s "Copied ✓" swap.
- **Toast** — slide-up + fade (currently fade only) → softer arrival.
- **Command palette** (if added) — the single biggest "premium" delight for power users.
- **Empty states** — a friendly one-liner + CTA turns dead ends into invitations.

> Everything above is achievable under "polish only." The deepest truth (the user's own
> point): these are *hypotheses*. The next gate is **[Real User Validation](REAL_USER_VALIDATION.md)** —
> if real users trip exactly where this audit predicts (toolbar overload, jargon, skills
> density), that convergence is the strongest evidence we're near production.
