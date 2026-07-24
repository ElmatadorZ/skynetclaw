# Real User Validation — Test Plan

> The gate after the polish sprints. **Stop AI-reviewing-AI; put the UI in front of real
> people.** This plan turns the [UI Debt Register](../../ui-debt/README.md) predictions into
> falsifiable hypotheses: if real users trip exactly where the audit predicts, that
> convergence is the strongest evidence SkynetClaw is near production. A research
> artifact — no feature, no code.

## 1. Participants (5–10)
Recruit across the personas the product targets:
| Persona | n | Why |
|---|--:|---|
| Beginner (non-technical) | 2 | tests jargon + first-run + recognition |
| Developer | 2 | tests efficiency, keyboard, density tolerance |
| Operator / power user | 2 | tests navigation cost + mission flow |
| Researcher / analyst | 1–2 | tests Obsidian/Intel comprehension |
5 users find ~85% of usability problems (Nielsen); 8–10 raises confidence on jargon.

## 2. Method
- **Moderated think-aloud**, 30–40 min each, screen + audio recorded (with consent).
- Same tasks for all; no hints unless fully stuck (then log it as a failure).
- One observer notes; do not lead. Capture **the exact screen** where they hesitate
  (this is where the register's screenshots get filled in for real).

## 3. Tasks (identical for everyone)
| # | Task | Predicted friction (from audit) |
|---|---|---|
| T1 | Open the app and send your first message | first-run clarity; chat toolbar overload ([UI-0008]) |
| T2 | Switch the AI to a different model | model pill discoverability |
| T3 | Add a new connection/endpoint and activate it | Connections density ([UI-0009]), placeholder labels ([UI-0015]) |
| T4 | Turn a Skill on, then off | Skills density ([UI-0009]) |
| T5 | Open "Council" and say what it is for | vocabulary ([UI-0012]) |
| T6 | Open "Intel" and find the Node Map | iframe orientation; breadcrumb gap |
| T7 | Cause an error (e.g. backend off) and recover | error UX ([UI-0002]) |
| T8 | Do it all with the keyboard only | keyboard-first gap ([UI-0014]); focus visibility ([UI-0001]) |

## 4. Metrics (per task, per user)
- **Success** (unaided / aided / failed)
- **Time on task** (seconds)
- **Clicks** (and mis-clicks)
- **Confusion points** (verbatim hesitation/question)
- **SEQ** — Single Ease Question, 1–7, right after each task

### Vocabulary comprehension check (Heuristic #2)
Ask each user to define, in their words: **House, Council, Governor, Mission, Concierge,
Atlas, Runtime, Skill.** Score 0 (no idea) / 1 (vague) / 2 (correct). A term averaging <1
must get a glossary/tooltip ([UI-0012]).

### System-level
- **SUS** (System Usability Scale, 10 items) at the end → single 0–100 number to track
  across releases.

## 5. Results template (one row per user × task)
```
user, persona, task, success(0/1/aided), time_s, clicks, SEQ(1-7), confusion_notes
```
Plus: SUS score, vocabulary scores, top-3 quotes, top-3 observed blockers.

## 6. Hypothesis ledger (falsifiable — fill after sessions)
| Audit prediction | Confirmed by users? | Evidence |
|---|:--:|---|
| Chat toolbar overwhelms (UI-0008) | ? | |
| Jargon blocks beginners (UI-0012) | ? | |
| Skills/Connections feel dense (UI-0009) | ? | |
| Keyboard-only is hard (UI-0014) | ? | |
| Errors are now recoverable (UI-0002 fix holds) | ? | |
| Focus/keyboard a11y works (UI-0001/0005 fix holds) | ? | |

## 7. Decision rule
- Any task with **<70% success** or **SEQ < 4** → that screen is not production-ready;
  open/raise the matching UI-debt item.
- **SUS ≥ 75** overall + every persona completes T1–T7 unaided → cleared for production
  on usability grounds.
- **Convergence:** where user data matches the audit, fix with confidence; where it
  *diverges*, the users win — update the register, the audit was wrong.

> This is the honest end state: the audit is a set of hypotheses; real users are the
> evidence. Run this, then iterate the register from data — not from another AI review.
