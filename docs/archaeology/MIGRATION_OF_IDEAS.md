# Migration of Ideas — Genesis vs Codex, and the Evolution Timeline

> Mission Step 7 (Genesis→Codex relationship) + Step 8 (evolution timeline). Tags:
> SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN. No redesign — only the path that *did* happen
> and the lineage it implies.

## Part A — Can Genesis V1 evolve into the First Principle Codex?

### The two systems' *purpose* (SUPPORTED)
- **Genesis V1 = an ACTION / PRODUCTION system.** Its verbs are *route, compose,
  analyze, render, refine* — it exists to **produce branded artifacts** (`ContentSkill`,
  `FinanceSkill.render_report`, `SalesSkill.playbook`).
- **Codex = an EPISTEMIC / TRUTH system.** Its verbs are *deconstruct, classify-claims,
  axioms* (`skynetclaw_codex.py` endpoints) — it exists to **establish what is true**,
  reinforced by `first_principles.py`, `belief_revision.py`, `theory.py`, `experiment.py`.

### The bridge (LIKELY)
Genesis contained **exactly one epistemic organ: `FactFlagger`** — "detect claims that
require references; mark for human review." That is the *seed* of an epistemic system:
it recognizes that some statements need justification. The Codex is what that seed
becomes when the flagging is (a) enforced, (b) automated, (c) recursive (axioms), and
(d) coupled to belief revision.

### Verdict (LIKELY, not SUPPORTED — no code comment states the lineage)
- Genesis and Codex are **fundamentally different systems** (action vs truth) — Genesis
  does **not** "become" Codex.
- But Genesis **carried the seed** (FactFlagger) from which an epistemic system could
  grow. In the current repo, **both grew**: the action system evolved into the
  `agent_run` loop + skills; the truth system grew *alongside* into Codex + the epistemic
  suite. They now **coexist** and are meant to be coupled — which is exactly the
  "Codex(epistemic) ↔ Genesis(action)" pairing described in the operator's own framing
  and in this session's earlier analysis.
- **UNKNOWN:** whether the current epistemic suite was *derived from* FactFlagger or
  *conceived independently*. No code comment links them; the lineage is inferred by
  responsibility, not provenance.

## Part B — Evolution Timeline (Gen 1 → V3 Vision)

### Generation 1 — Genesis Mind V1 (the artifact) — SUPPORTED
Single-process compound mind for **4 business verticals**. Deterministic core, one
`LLMBridge`. One Evaluator, one Memory, one route, one Resonance loop. Truth = human
flags. **Coupling:** cognition tied to `Domain` enum.
*Change vs before:* baseline.

### Generation 2 — Protocol migrates into prompts + a workflow endpoint — SUPPORTED
Per `compound_mind.py` docstring: the Compound/Cosmic protocol "**lived only in skill
PROMPT TEXT and a separate workflow endpoint**." Cognition moved **out of Python and
into prompt/skill text** — gaining flexibility, losing the deterministic core and the
single-owner discipline.
*Change:* code-cognition → prompt-cognition; determinism weakens; first duplication
(protocol exists twice).

### Generation 3 — SkynetClaw production system — SUPPORTED
General autonomous **agent OS**: `main.agent_run` loop, 14-agent **council** (roles, not
verticals), 50 `BUILTIN_TOOLS`, `skills_auto_router`, persistent SQLite, governance
(GPS-2 + `shadow_gate`), runtime kernel/adapter, and a full **epistemic suite**
(first_principles/belief_revision/theory/experiment/causal/calibration/…).
*Change:* breadth explodes; responsibilities **split/duplicate** (routers, evaluators,
memories); truth becomes **enforced**; determinism largely lost.

### Current — RC-1 frozen under Epic Trust — SUPPORTED
Feature freeze; evidence-driven (`security_regression`, `chaos_test`, `a11y_regression`,
TRUST_SCOREBOARD, KNOWN_RISKS). Cognition stable; discipline re-imposed at the *process*
level (not yet the *architecture* level).
*Change:* growth stops; evidence + regression become the gate.

### V3 Vision — Cognitive OS (design-only) — SUPPORTED (docs) / N/A (implementation)
`docs/v3/*`: kernels (Journal, Reality Boundary, Scheduler, Identity, Constitution,
Epistemic, Supervisor, Contract Registry, Model Gateway) as *projections over one source
of truth*. Explicitly frozen; **not implemented** (marked N/A on the Trust Scoreboard).
*Change (intended):* re-consolidate the scattered owners into kernels — i.e., undo the
Gen-2/Gen-3 duplication. **This is design, not code.**

## Part C — The through-line (LIKELY)
```
Gen1: 1 owner / responsibility, deterministic, human-truth, domain-coupled
   ↓ (cognition leaves code → prompts)
Gen2: protocol duplicated across prompt + endpoint; determinism weakens
   ↓ (breadth explosion)
Gen3: many owners / responsibility; truth enforced; epistemic suite grows from the
      FactFlagger seed; determinism lost
   ↓ (discipline re-imposed at process level)
Now:  frozen, evidence-driven (Epic Trust)
   ↓ (intended re-consolidation — design only)
V3:   kernels = one owner per responsibility again (a *return* to Gen1's single-owner
      discipline, at OS scale)  ← LIKELY reading: V3 is Gen1's discipline re-derived
```
**SPECULATIVE but notable:** V3's core value ("one source of truth, everything is a
projection") is the *same instinct* as V1's "one owner per responsibility" — scaled from
a script to an OS. The evolution may be a spiral, not a line: it drifted away from
single-ownership and the V3 vision is trying to return to it.
