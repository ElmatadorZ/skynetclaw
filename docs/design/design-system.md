# SkynetClaw Design System (Phase G)

> Polish baseline — **describes the tokens that exist today and the consolidated scale
> every screen should converge on.** No new visual language; this codifies and tidies
> what is already in `index.html`. Measured from the live DOM (see
> [DESIGN_REVIEW](DESIGN_REVIEW.md) for the evidence).

## 0. Why this exists
The app already has a coherent dark "future-noir" look, but the *scales* have drifted:
**12 distinct font-sizes** and **9 distinct border-radii** are in use while `:root`
only tokenises two radii. This file defines the target scale and the rule: **use the
token, never a raw value.**

## 1. Color
### Surfaces (from `:root`, keep)
| Token | Value | Use |
|---|---|---|
| `--bg` | `#07090f` | app background |
| `--bg2` | `#0d1018` | panels |
| `--bg3` | `#111722` | cards / inputs |
| `--bg4` | `#17202e` | raised input / hover |
| `--border` | `#1b2740` | hairline |
| `--border2` | `#223050` | interactive border |

### Text (contrast-checked)
| Token | Value | Contrast on `--bg` | Allowed use |
|---|---|---|---|
| `--text` | `#cdd8ea` | ~12:1 ✅ | body, headings |
| `--text2` | `#6a84a8` | ~4.6:1 ✅ | secondary text |
| `--text3` | `#3d5068` | **~2.4:1 ❌** | **decorative only** — never on text the user must read (see [UI-0010](../../ui-debt/README.md)) |

### Accent & status
| Token | Value | Use |
|---|---|---|
| `--accent` | `#6c5ff0` | primary action, focus, selection |
| `--accent2` | `#9b8fff` | focus ring, active tab |
| status / success | `#3fb950` (adopt) | online, success |
| status / warning | `#d29922` (adopt) | degraded, caution |
| status / danger | **soften `--red #ff1a2e` → `#f0566b`** | errors (current red is over-saturated, see [UI-0016](../../ui-debt/README.md)) |

**Rule:** status is **never colour-only** — always colour **+ icon/shape + text label**
(`● online`, `▲ offline`). Required for color-blind users.

## 2. Typography scale (IMPLEMENTED — `:root` tokens)
Consolidated from **12 distinct sizes → 7** (literal scale = 4 steps; zero sub-11px text).
Tokens now in `:root`:
| Token | Size | Use |
|---|---|---|
| `--fs-xs` | 11px | meta, captions, badges (was the 8.5/9/10/10.5px sprawl) |
| `--fs-sm` | 12px | secondary text, list rows |
| `--fs-base` | 14px | body, chat, inputs (app default) |
| `--fs-title` | 15px | section / modal titles |
Residual `13 / 13.5 / 17px` come from a few **em/%-derived** elements (computed, readable)
— tracked as S4 in [UI-0006](../../ui-debt/README.md). Font family: system stack +
`Consolas, monospace` for code/editor. **Rule:** no literal `font-size` below 11px.

## 3. Spacing scale (4-pt base)
Use only: **4 · 8 · 12 · 16 · 24 · 32**. Tokenise as `--sp-1 … --sp-6`. No 5/6/7/9/11/14px
ad-hoc padding (currently common). Touch targets ≥ 32px tall.

## 4. Radius (IMPLEMENTED — consolidated 9 → 3 + full)
Literal radii reduced to the `:root` tokens (4,5,7,9,12px strays normalised away):
| Token | Value | Use |
|---|---|---|
| `--radius-sm` | 6px | inputs, small buttons, pills, badges |
| `--radius` | 10px | cards, list rows, panels, modals |
| `--radius-full` | 50% | avatars, status dots |
Chat bubble's `16px 16px 16px 4px` is the one documented exception. (Computed 7/9px seen on
round dots are `50%` resolving to px — not debt.) See [UI-0007](../../ui-debt/README.md).

## 5. Elevation / border
Flat-first (matches the dark aesthetic). Three levels only:
- **0** — page background, no border.
- **1** — `1px solid var(--border)`, panels.
- **2** — `1px solid var(--border2)` + `box-shadow:0 8px 32px rgba(0,0,0,.4)`, modals/popovers + `backdrop-filter:blur(6px)` (already used on modal-bg).
No other shadows.

## 6. Buttons (4 variants — formalise)
| Variant | Look | Use | Max per view |
|---|---|---|---|
| **primary** | accent fill | the ONE main action | 1 |
| **secondary** | bordered, transparent | supporting actions | few |
| **ghost** | text only, hover bg | tertiary / toolbar | many |
| **icon** | square ghost, must carry `aria-label` | compact actions | many |
States required for all: `:hover`, `:active` (translateY 1px), `:disabled` (opacity .5),
`:focus-visible` (accent2 outline). All four now exist globally (see commit `6c47133`).
**Rule:** only one **primary** per screen. (Chat toolbar currently has ~10 equally-weighted
buttons — see [UI-0008](../../ui-debt/README.md).)

## 7. Iconography & vocabulary
- Emoji icons are the current system — acceptable, but every icon-only control **must**
  have a text label or `aria-label` (now auto-applied from `title`).
- **Glossary required** (see [UI-0012](../../ui-debt/README.md)): House, Council, Governor,
  Continental Division, Mission, Concierge, Atlas, Skill, Runtime — define once, expose as
  tooltips on first encounter. Domain words must not require recall.

## 8. Component rules
### Panels
1px `--border`, `--radius`, header row with title + a single refresh/affordance.
### Empty state (every list/page)
Icon + one-line *what's here* + a CTA. One voice (pick Thai-primary), not mixed.
### Loading
Inline `.spin` + label ("กำลังโหลด…"); skeletons for lists >3 rows; never blank.
### Error
`friendlyError()` only — message + reason + recovery + `#log-id`; never a stack.
### Toast
`showToast()`; bottom-center; auto-dismiss 2.2s; also announced via `aria-live` (done).
### Offline / permission-denied / no-results / first-run
Each list must distinguish these four — today most collapse to a generic empty (debt).

## 9. Animation
- Transitions 120–200ms ease for color/border/transform; 300ms for veils.
- `transform:translateY(1px)` on press; no bounce/overshoot.
- **Honour `prefers-reduced-motion`** (done globally).
- Nothing should appear/disappear instantly or jump.

## 10. The one rule
Every screen uses **these tokens only**. A raw hex, a non-scale font-size, or a stray
radius is design debt — log it in [`ui-debt/`](../../ui-debt/README.md).
