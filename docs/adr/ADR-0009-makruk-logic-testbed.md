# ADR-0009 — Makruk (Thai Chess) as a Live Logic Testbed

- **Status:** Accepted
- **Date:** 2026-07-17
- **Relates to:** ADR-0008 (Cognitive Logic Engine), Capability-first Architecture (ADR-0007)

## Context

SkynetClaw needs a *concrete, adversarial, self-scoring* arena to develop and stress
the platform's reasoning. Abstract benchmarks (the Logic Engine's CSP suite, ADR-0008)
prove exact reasoning on static problems; they do not exercise **sequential decision
making under an opponent** — search, look-ahead, evaluation, and recovering from a bad
position. The operator asked for a playable Thai Chess (หมากรุกไทย / Makruk) feature,
reachable from a UI button, where SkynetClaw plays a human "to test and develop logic
through play, and improve until it closes every gap."

Makruk is a good fit: a *finite, fully-observable, deterministic* game. Correctness is
decidable (a move is legal or it is not; a position is mate or it is not). That makes it
a clean logic testbed — the same philosophy as the calculator/`safe_math` and the Logic
Engine: **offload exact reasoning to a deterministic engine; never fake it with prose.**

Makruk differs from international chess and the rules must be exact:
- 8×8 board; **King (Khun) d1 / Counselor (Met) e1** for White, **rotationally**
  symmetric for Black (Khun e8 / Met d8) — the kings do *not* start on the same
  file. (Confirmed against the gameindy game's own board rendering; verified via
  `test_initial_setup_counts_and_kings`.)
- **Met** moves 1 square diagonally (a weak counselor, not a queen).
- **Khon** (bishop) moves 1 diagonal **or 1 straight forward** (silver-general shape).
- **Ma** (knight) and **Ruea** (rook) as in chess.
- **Bia** (pawn) starts on the **3rd/6th rank**, pushes one, captures diagonally, and
  **promotes to a Met-mover on the 6th/3rd rank** (no two-square move, no en passant).
- Stalemate is a **draw**.

## Decision

Build Makruk as an **isolated package** (`backend/makruk/`), with **zero coupling to
`main.py`** (the God-Object decomposition discipline, C3), plus a thin `mount(app)` HTTP
surface and a self-contained play page.

### Architecture (single-responsibility modules)

| Module | Responsibility |
|---|---|
| `makruk/board.py` | 8×8 board, pieces, the exact Makruk initial setup, (de)serialization. No move logic. |
| `makruk/rules.py` | Move generation per piece, attack detection, legality (no self-check), check / checkmate / stalemate. The "logic." |
| `makruk/game.py` | Stateful game: apply move by algebraic squares, terminal detection, JSON state for the API/UI. |
| `makruk/ai.py` | The opponent: **negamax + alpha-beta** over the exact rules, Makruk-tuned evaluation, node-budgeted, **deterministic**, returns the principal variation + score + a human reason. |
| `makruk_api.py` | `mount(app)` → REST (`/api/makruk/*`) + serves `/makruk`. In-memory game sessions. |
| `makruk.html` | Self-contained play page: click-to-move board, legal-move highlighting, difficulty, hints, and a live view of the engine's reasoning (why it chose the move, its plan, eval, nodes). |

### Data flow

```
human click ──▶ /api/makruk/move ──▶ game.push_algebraic ──▶ rules.legal_moves (validate)
                                                            └─▶ state JSON ──▶ board re-render
UI auto ──────▶ /api/makruk/ai-move ─▶ ai.best_move (negamax/αβ) ─▶ push ─▶ state + {reason,pv,score}
UI 💡 hint ───▶ /api/makruk/hint ────▶ ai.best_move (no mutation) ─▶ {reason,pv,score}
```

### Why negamax now (not learning yet)

The operator's end-goal is a *self-improving* player. The **right first move is a correct,
deterministic, explainable baseline** — an engine whose every move is provably legal and
whose evaluation/search are transparent knobs. That baseline is the substrate a learning
loop (self-play, eval-tuning, opening/endgame knowledge) plugs into later. Shipping a
black-box learner first would violate the platform's evidence-first, explainable ethos and
leave nothing to measure improvement *against*. Learning is deferred by design, not skipped.

## Consequences

**Positive**
- A live, adversarial, self-scoring arena for reasoning; correctness is decidable.
- Fully isolated — no `main.py` growth; deletable without touching the core.
- Deterministic + explainable end-to-end (every AI move ships its reason, plan, score, node count).
- Reuses the platform pattern (offload exact reasoning to an engine) proven by `safe_math` and the Logic Engine.

**Costs / limits (honest)**
- Search is node-budgeted (SkynetClaw is CPU-bound) — expert depth may truncate; it stays
  responsive rather than always searching to full depth.
- **Makruk counting rules** (the board/piece-counting draw conditions for bare endgames) are
  **not yet implemented** — only stalemate-as-draw and checkmate. Flagged for a follow-up.
- No learning loop yet (see above) — the evaluation is hand-tuned, not trained.

## Verification (Article XI — evidence-first)

- `tests/test_makruk.py` — setup, per-piece movement (Met/Khon/Ma/Ruea/Bia), promotion to
  Met-mover, check / checkmate / stalemate, pin legality, and AI (legal move, **mate-in-1**,
  **wins free material**, **determinism**). All model-free and deterministic.
- Two intentionally hand-built terminal positions (a two-rook mate; a knight+king stalemate)
  confirm mate/stalemate detection; one flawed stalemate position I wrote was **correctly
  rejected by the engine** (my white king blocked its own rook's attack) — the engine caught
  my error, which is exactly its job.

## Follow-ups

1. Makruk counting rules (bare-king / piece-count draw conditions).
2. A learning loop: self-play, evaluation tuning, opening/endgame tables — measured against
   this deterministic baseline.
3. Wire `best_move` as an agent tool (the calculator pattern) so the reasoning core can be
   invoked by the model directly, behind the kernel PRE_ACT hook.
