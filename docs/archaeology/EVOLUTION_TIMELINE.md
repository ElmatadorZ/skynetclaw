# Evolution Timeline (biological, not commit history)

> Generations of the organism, each: **Generation → Mutation → Pressure → Result → New
> capability**. Dates are real (git), but this reads the bursts as *evolutionary eras*,
> not a changelog. Tags: SUPPORTED / LIKELY / UNKNOWN. Evidence = SELECTIVE_PRESSURES.
>
> **Pre-history (UNKNOWN):** Genesis V1 (the pasted artifact) and the *birth* of the
> Council both predate the first commit (2026-06-15) and are **not recoverable from git**.

---

## G-0 — Pre-history · UNKNOWN
The Deterministic Compound (Genesis V1) and an already-running Council. No git evidence.
*Everything below is what git actually witnessed (2026-06-15 → 07-01, ~16 days).*

## G-α — The Nervous System & the Eye · 2026-06-15/16 (41 commits) · SUPPORTED
- **Mutation:** an event bus + wiretaps + house-mind + belief/mission/lesson surfaces bolt
  onto an existing council.
- **Pressure:** **P-OBS** (make deliberation visible) + **P-CONC** (concurrent-mission
  safety, "eliminate shadow state") + early **P-CONS** ("ONE event per fact — single source
  of truth").
- **Result:** the organism can *see itself deliberate* and *persist* beliefs/missions.
- **New capability:** observability + durable institutional memory. *(SUPPORTED)*

## G-β — The Discipline of Doubt · 2026-06-17/18 · SUPPORTED
- **Mutation:** the "Discovery Architecture" arc (OX-1 … OX-1.7): investigate-first,
  World-Model-verify-before-acting, recovery-by-alternates, execution-confidence,
  BLOCKED-detection, evidence-based-completion, execution-memory.
- **Pressure:** **P-GROUND** ("verify before acting") + **P-TRUST** ("prove completion,
  don't assert it").
- **Result:** the loop stops *asserting* and starts *checking*; dead-ends become honest.
- **New capability:** grounded, self-checking execution (the seed of Reality-Awareness). *(SUPPORTED)*

## G-γ — The Cambrian Explosion of Cognition · 2026-06-22/23 (40 commits) · SUPPORTED
- **Mutation:** ~24 **"additive, read-only"** protocols appear in two days — learning,
  capability, telemetry, control, attribution, reinforcement, compliance, acquisition,
  metalearning, exploration, causal, curiosity, belief-revision, first-principle, decision,
  confidence, experiment, theory, research-agenda, unknowns, paradigm, observability.
- **Pressure:** **P-ADD** (the master pressure — one new organ per capability, never touch
  the old) + **P-TRUST** (truth becomes a scientific-method suite).
- **Result:** Truth → Epistemic; Evaluator → many; Memory → many. **This is the burst that
  fragmented ownership** — breadth exploded via non-invasive addition.
- **New capability:** a full epistemic/scientific-method organism — *at the cost of single
  ownership*. *(SUPPORTED — 10 verbatim "additive, read-only" tags)*

## G-δ — The Body & the Hands · 2026-06-24/25 · SUPPORTED
- **Mutation:** execution separated from reasoning; GPU root-caused; Runtime Kernel /
  Discovery-routing / Boot / OS / Workflow-Engine; ElmatadorZ (Qwen-14B) as the live model.
- **Pressure:** **P-PERF** (CPU too slow → real GPU) + **P-GROUND** (route execution to a
  runtime that actually works) + a **P-CONS** attempt ("Workflow Engine as the single
  orchestration layer").
- **Result:** the world becomes **live/hardware-real**; a *runtime* router is born (M-1).
- **New capability:** real execution on real hardware; multi-runtime dispatch. *(SUPPORTED)*

## G-ε — Senses & Skin · 2026-06-26/29 · SUPPORTED
- **Mutation:** skills (web-dashboard-builder), deterministic news **fast-path "out of the
  agent loop"**, shadow_gate truth-fixes, document/image upload + OCR, live Intel node map.
- **Pressure:** **P-PERF/P-TRUST** (the stochastic loop was flaky → bypass it with a
  *deterministic* path for critical output) + **P-GROUND** (read real documents/images; real
  ranked news).
- **Result:** reliable outward perception + a deterministic escape hatch around the unreliable
  model — a partial, local *return* of V1's deterministic instinct.
- **New capability:** ingest real files; produce reliable reports without trusting the loop. *(SUPPORTED)*

## G-ζ — The Mirror & the Law · 2026-06-30/07-01 · SUPPORTED
- **Mutation:** V2/V3 architecture *designs* (kernels), then Epic Trust freeze, RC-1,
  security/chaos/a11y regressions, and this archaeology.
- **Pressure:** **P-CONS** finally rising (V3 = "one owner per responsibility again, at OS
  scale") + a new **governance/evidence** pressure (Epic Trust: "no change without proof").
- **Result:** growth *stops*; the organism turns to **self-examination** (audits,
  archaeology) and **discipline** (freeze, evidence gates). No new organs — only mirrors and
  laws. *(SUPPORTED — docs/tests exist; V3 kernels are design-only, N/A implemented)*

---

## The shape of the evolution (LIKELY)
```
G-α see & remember → G-β doubt & verify → G-γ EXPLODE (additive) → G-δ act on real hardware
    → G-ε perceive the world reliably → G-ζ freeze, examine, legislate
```
- **Explosive breadth first (G-γ), consolidation only last (G-ζ).** The organism grew every
  faculty by *addition* (P-ADD winning), then — once breadth was overwhelming — turned to
  *examination and discipline* (P-CONS / governance rising). SUPPORTED by the date order.
- **Proprioception is the one faculty that never shipped** — it is the only sense that
  required *invasive* growth, which the additive era (G-γ) structurally could not produce
  (see M-8). SUPPORTED (no impl commit).

## Unknowns
- **UNKNOWN:** all of G-0 (V1 + council birth) — external to git.
- **UNKNOWN:** whether G-γ's explosion was a deliberate strategy or emergent momentum
  (no ADR/design-doc from that era recovered; the only stated policy is the per-commit
  "additive, read-only" tag).
