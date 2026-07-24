# ADR-0010 — Self-Improvement Loop (Makruk as the reference implementation)

- **Status:** Accepted
- **Date:** 2026-07-18
- **Relates to:** ADR-0009 (Makruk logic testbed), ADR-0008 (Cognitive Logic Engine),
  ADR-0007 (Capability-first Architecture), Epic Trust (evidence-first governance)

## Context

The operator asked to make the Makruk engine *self-improve*, and to *connect that
to how SkynetClaw develops its own logic*. Earlier we were explicit (and honest):
as first built, Makruk was a **measurement instrument**, not a learning loop —
playing more games did not make anything better, because the engine's skill was a
set of **hand-tuned constant weights**.

The trap to avoid is **circular self-improvement**: a system that "gets better" only
at beating its own past self, with no anchor to objective reality. Self-play Elo
going up is not evidence of real capability if the yardstick is also drifting.

## Decision

Turn the engine's evaluation into **learnable parameters** and add a self-play loop
that improves them under a **frozen, held-out anchor** — and treat this loop as the
**reference pattern** the platform reuses to develop other cognitive capabilities.

### The loop (in `makruk/learn.py`)

```
champion ── perturb one weight ─▶ candidate
    ▲                                │  play self-play games (both colours, seeded openings)
    │                                ▼  judged by a NEUTRAL fixed material referee
    │   promote ONLY if candidate:   │
    │     (a) beats champion head-to-head (dense material signal), AND
    └─────(b) does NOT regress on a FROZEN ANCHOR suite (fixed positions,
              known answers: mate + win-material) ── the non-circular floor
```

Four honesty safeguards make a gain **evidence, not a vibe**:
1. **Frozen anchor** — a fixed suite of positions with known-correct play. A candidate
   must still solve them; this is external ground truth the loop cannot move.
2. **Neutral judge** — self-play games are scored by the *fixed default* material
   values, never the candidate's own weights, so a candidate can't "win" by inflating
   what it values.
3. **Determinism** — seeded RNG; a run is fully reproducible.
4. **Ledger** — every generation (what changed, match result, anchor before/after,
   promote?) is written to `training_ledger.json` as an auditable trail.

The champion persists to `weights.json`, which the engine loads at startup
(`ai.ACTIVE_WEIGHTS`) — so improvement **ships into the deployed engine**. It never
overwrites the shipped weights unless the champion holds the frozen anchor.

### Wiring to the running system

- `GET /api/makruk/weights` — the engine's current weights, and how they differ from
  the defaults (is it tuned, and by how much).
- `POST /api/makruk/reload-weights` — hot-reload a freshly trained `weights.json`
  without a restart.
- CLI: `python -m makruk.learn --generations N`.

## How this develops SkynetClaw's logic (the connection)

This is deliberately built as a **template**, not a one-off chess hack:

- **Same shape, reusable:** *parameterise a capability → self-play / self-measure →
  gate against a frozen held-out anchor → promote → persist*. Any capability with (i)
  tunable parameters and (ii) a decidable objective can adopt it — the CVL/Assurance
  scorers, planning heuristics, retrieval ranking. Makruk is the proving ground
  because correctness there is *decidable* (a move is legal or not; a position is mate
  or not), so we can trust the loop before pointing it at fuzzier capabilities.
- **The engine is a reasoning tool the agent can call** (the calculator/logic-engine
  pattern). A stronger engine = a stronger verified-reasoning tool in SkynetClaw's kit.
- **Evidence-first, by construction:** improvement is only ever claimed with a ledger +
  a held-out anchor — the same discipline Epic Trust demands of every change.

## Consequences

**Positive** — the engine genuinely improves and the gain is auditable; a reusable,
honest self-improvement pattern exists; no circular self-deception (held-out anchor +
neutral judge).

**Costs / limits (honest)**
- Self-play on CPU is **slow**; meaningful gains need an **offline** run (minutes–hours),
  not real-time. The loop is designed for background/offline use.
- Shallow, short games give a weak signal in balanced openings; the signal is strong
  where material imbalance appears (verified: good weights beat broken ones by +14).
- Only the **evaluation** is learned so far — not search heuristics, not an opening or
  endgame book, not a learned value network. Those are future extensions.
- This tunes the **engine**, a deterministic subsystem — it does **not** train the LLM
  agent's weights. The connection to the agent is via the *pattern* and the *tool*, not
  gradient updates to the model.

## Verification (Article XI)

`tests/test_makruk.py`: weights drive the eval; the frozen anchor is solved by defaults;
perturbation is deterministic and single-coordinate; weights save/load round-trip; **the
learning signal is real** (good weights beat broken ones head-to-head); tuning is
deterministic and **never ships an anchor regression**. Full suite green.

## Follow-ups

1. A proper **Elo ladder** vs frozen reference opponents (absolute strength over time).
2. Bigger labeled position suite (Texel-style) for a faster, denser eval signal.
3. Extend learning beyond evaluation: search-order heuristics, endgame knowledge.
4. Apply the template to a second capability (e.g., an Assurance scorer) to prove reuse.
