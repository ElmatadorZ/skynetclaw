# Architectural Invariants — the DNA that survived every generation

> The final question: **which architectural beliefs stayed invariant across G1 → now?**
> An invariant is a belief *expressed in every observed generation*, even when its
> mechanism changed completely. Tags: SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN.
> Basis: G1 (source) + G3/now (repo) directly; G2/G4 corroborating where noted.

## The invariants (strongest first)

### INV-1 — Cognition is a staged loop that ends in reflection · SUPPORTED
Every generation shapes thinking as **Plan → Produce → Judge → Revise/Reflect**, not a
single generation step. G1 ran Plan→Compose→Evaluate→Refine; now runs
comprehend→plan→execute→reflect. The *stages* and *owners* changed; the **belief that
cognition is a pipeline with a self-review stage did not.**
> Caveat (LIKELY): in both generations the reflect/ground stage is partly *aspirational*
> (V1 named a "Ground" stage it never ran; now "reflect" fires but its effect on later
> runs is unproven — see UNKNOWNS U-9). The **belief** is invariant; its **fulfilment** is
> not.

### INV-2 — One general model is insufficient; cognition must be divided into specialists · SUPPORTED
G1 split work into domain agents/skills; now splits into a many-role council + skills.
The **belief in division of cognitive labor** is invariant (the *axis* of division
changed: business-domain → cognitive-role).

### INV-3 — A dispatch layer selects the specialist · SUPPORTED
Both generations insert a **router between task and specialist**. Invariant as a belief;
its ownership fragmented from one router to many (see RESPONSIBILITY_EVOLUTION_GRAPH R1).

### INV-4 — The product is the scaffolding *around* the model, never the model itself · SUPPORTED
G1 wrapped a bounded `LLMBridge` in deterministic scaffolding; now wraps stochastic model
calls in loop + tools + memory + governance. Even as the model's role grew, **the system
is always the harness, not the model.** The value proposition — *engineered cognition
around a language model* — never changed.

### INV-5 — Certain claims cannot be trusted and need a dedicated truth mechanism · SUPPORTED
G1 had a claim-flagger; now has an enforced anti-hallucination gate + an epistemic suite.
The **mechanism inverted** (advisory→enforced, human→machine) but the **belief that truth
needs its own organ** is invariant. This is the healthiest surviving gene.

### INV-6 — The organism has a deliberate voice / identity, not a neutral one · SUPPORTED
G1 carried named brand voices; now carries an authored persona (identity/soul prose) +
brand skills. The structured owner died; the **belief that the system must speak with a
crafted identity** persisted. (Its loss of the *structured* voice is exactly what caused
the live "Money Atlas" failure — the belief survived, the capability did not.)

### INV-7 — Reasoning must be inspectable, not a black box · LIKELY
G1 exposed interpretable outputs + explicit critique scores; now exposes process logs,
telemetry, and a trust scoreboard. The **belief in observability of the organism's own
thinking** appears invariant. (LIKELY — inferred from consistent presence, not a single
statement.)

### INV-8 — The organism speaks the operator's language natively (Thai-first) · SUPPORTED
G1 wrote prompts, guardrails, and outputs in Thai/English blend; now the UI, prompts, and
outputs are Thai-first. Invariant.

### INV-9 — The organism self-limits on risk (guardrails) · LIKELY
G1 injected risk-disclosure ("not investment advice"); now enforces permissions + immutable
rules. The **belief that the system must restrain itself on dangerous actions/claims** is
invariant; enforcement strengthened.

## What is NOT invariant (for contrast, SUPPORTED)
- **Determinism** of the core (I-1) — died.
- **Single ownership** per responsibility — fragmented.
- **Closed/offline/timeless world** (I-3) — opened.
- **Truth-as-external** (I-2) — internalized.
- **Structured Voice mechanism** — removed (INV-6's *belief* survived, its *engine* did not).

## The DNA sentence (LIKELY — the distilled invariant)
> **"Intelligence is a staged, self-reviewing pipeline of divided, dispatched specialists
> — a crafted, inspectable, operator-native harness *around* a language model — that
> keeps a dedicated organ for truth and restrains itself on risk."**

Every generation is a variation on that sentence. The variables that changed — *where
trust lives, where truth lives, whether the world is real, how many owners each job has,
and whether the organism can sense itself* — are the axes of its evolution. The sentence
is the **DNA**; the axes are the **mutations**.

## Honesty ledger
- INV-1..6, 8 = **SUPPORTED** (present in both directly-observed generations).
- INV-7, 9 = **LIKELY** (inferred from consistent presence, no single decisive statement).
- The DNA sentence = **LIKELY** (a synthesis, not a quotation).
- Whether these invariants are *intentional* design principles or *emergent* survivors =
  **UNKNOWN** (no principles document from G1/G2 recovered; the current one is G-freeze's
  Epic Trust, which post-dates the invariants).
