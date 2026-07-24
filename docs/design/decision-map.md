# Decision Map (UI-0009)

> The fix for UI-0009 was **decision-load reduction**, not button-hiding. We did **not**
> remove any control — all functionality is preserved. We changed the *information
> hierarchy* so each screen asks **one question** by default and moves authoring to a
> contextual layer. Numbers below are **measured in-browser** (default state, forms
> hidden vs. forms open), not estimated.

## Principle applied
> *One screen → one question. One Primary Action, ≤3 Secondary, everything else
> contextual or advanced. Preserve capability; change hierarchy.*

## Skills
**Question the screen must answer:** *"Which skill do I want on?"*
| | Before | After |
|---|---|---|
| Always-visible authoring controls | **13** (skill form 7 + tool form 6, both open at all times) | **0** (contextual) |
| Competing decision *types* at first glance | ~10 (toggle, edit, New-skill, Import, Clear, name, desc, prompt, delete, apply, save, New-tool, tool fields…) | **3** (scan+toggle a skill · New · Import) |
| Interactive elements in default view (empty list) | 16 | **3** |
**Reason:** the two create/edit forms were *always open*, forcing "how do I author a
skill?" onto a user who only wanted to *turn one on*. Forms are now revealed **only** by
**+ New** or by clicking a row to edit (each opens, focuses the first field, and offers
✕ ปิด; Save/Delete auto-close). The primary decision is now a single binary toggle per row.

## Connections
**Question the screen must answer:** *"Which runtime am I using — and add one if needed?"*
| | Before | After |
|---|---|---|
| Always-visible add-form controls | **9** (add-endpoint + add-integration, both open) | **0** (contextual) |
| Interactive elements in default view (empty) | 13 | **4** |
| Hick decision-time proxy `log2(n+1)` | **3.81** | **2.32** |
**Reason:** two multi-field add-forms sat open beneath the lists. They are now revealed
by a **➕ Add** toggle in each section header (focuses the first field); **Add Connection /
Add Integration auto-close** on success. Reading *what exists* no longer competes with
*creating new*.

## Chat (already addressed — UI-0008)
**Question:** *"What do I want to send?"* — the 5 mode buttons became one segmented
control; the message input + Send is the single Primary Action.

## What we did NOT do
- Did **not** delete or merge any control.
- Did **not** hide the primary action of any screen.
- Did **not** convert homogeneous list rows into accordions (a scan-list is *recognition*,
  not a Hick decision — collapsing it would add clicks, not remove decisions).

## Progressive levels (see [progressive-disclosure.md](progressive-disclosure.md))
- **Beginner/Power:** the list + one primary action (toggle / activate).
- **Expert (contextual):** authoring forms, delete, apply — revealed on intent.
