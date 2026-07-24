# ADR-0007 — Capability-first Architecture

**Status:** Proposed (founding principle) · **Date:** 2026-07-13 · **Blast radius:** Architecture-defining (system-wide)
**Constitution:** Articles III, IV, V, IX, X · **Precedes:** ADR-0006 (CAF) and all future capability ADRs.
**Specs:** [COGNITIVE_PRIMITIVES.md](../specs/COGNITIVE_PRIMITIVES.md), [CAPABILITY_DEPENDENCY_GRAPH.md](../specs/CAPABILITY_DEPENDENCY_GRAPH.md), [MATURITY_MODEL.md](../specs/MATURITY_MODEL.md), [CAPABILITY_MODEL.md](../specs/CAPABILITY_MODEL.md), [CAF](../architecture/CAF_COGNITIVE_ANALYSIS_FRAMEWORK.md)

> **v0.2 amendment (Chief Architect, 2026-07-13):** added the **Primitive** base layer,
> the **two-axis** model, computed maturity, and the **Promotion Rule** (below). The
> capability *tree* is replaced by the **Capability Dependency Graph**.

## Context

SkynetClaw's design vocabulary has been **mechanism-first**: we reason in terms of
tools and engines ("add a calculator tool", "a Structured Reasoning Toolkit"). For a
tool, that is fine. For a **Cognitive Operating System**, it is the wrong primary
noun. A name like "Structured Reasoning Toolkit" describes a *bag of utilities*, not
the *cognitive capabilities* the system possesses. The benchmark review (ADR-0006
context) exposed the cost: the cognitive **data plane** is under-modelled, so we
cannot reason about — or grow — the system's *thinking* as a first-class resource.

An OS's stable nouns are its **resources and the guarantees over them** (processes,
memory, files). A Cognitive OS's primary resource is **cognition**. Therefore the
stable top-level nouns must be **Capabilities** — what the system can think and do —
not the tools that happen to implement them today.

## Decision

**Adopt Capability-first Architecture as a founding principle of SkynetClaw.**

> **Reasoning, Planning, Decision, Forecast, Optimization, Constraint, Verification,
> Memory, Safety … are CAPABILITIES — not tools.** A tool is one mechanism that
> realizes a capability; it is never the unit of design.

The architecture has **two orthogonal axes**, not one linear stack:

```
COMPOSITION (what it is made of):   Primitive ──▶ Capability
REALIZATION (how it runs):          <node> ──▶ [Service] ──▶ Engine ──▶ Tool ──▶ Validator
```

- **Primitive** (COGNITIVE_PRIMITIVES) is the true base unit — the ISA. Capabilities
  *compose* from primitives (Decision = Compare + Estimate + Rank + Verify + …).
  Primitives carry a **determinism class** (D/P/M) that is the origin of all trust and
  propagates up the graph.
- **Capabilities** form a **Capability Dependency Graph**, not a tree
  (CAPABILITY_DEPENDENCY_GRAPH) — one capability is a dependency of many.
- Any node on either axis is *realized* through `[Service] → Engine → Tool → Validator`.

**Layer-collapse rule (anti-over-engineering).** The realization layers are the
*maximal* template. A primitive/simple capability collapses layers: Arithmetic is
`Engine(safe_math) → Tool(calculator) → Validator(arithmetic)` with **no Service**.

**Promotion Rule (complement to layer-collapse).** A layer is *promoted into existence*
only when a concrete condition demands it — never "because we want to split it":

| Promote to… | only when the node has… |
|---|---|
| **Capability** (from Primitive) | composition of ≥2 primitives / a nameable cognitive goal |
| **Service** (from Engine) | multiple implementations · its own lifecycle · routing · state · a separate policy |
| **Engine** (from Tool) | non-trivial algorithm worth isolating + testing |
| **Validator** | any node that makes a checkable claim (always — assurance is mandatory) |

If none of a layer's conditions hold, do not create it. Together, layer-collapse +
promotion keep the architecture from bloating as it grows to 100+ capabilities:
structure appears **only where reality forces it**.

**Computed maturity (MATURITY_MODEL).** `Missing/Emerging/Partial/Present/Trusted` are
**computed** from `Benchmark × Validator × Coverage × Reliability` with hard gates and a
**dependency ceiling** (a capability is only as mature as its weakest dependency) — never
hand-assigned. A capability advances by *earning a score*, and demotes automatically the
night a dependency or metric regresses.

**Corollary — the Capability Model is the system's master registry.** Before any
capability is built, it exists as a node in `docs/specs/CAPABILITY_MODEL.md` with its
family, maturity, five-layer realization, owning kernel hook, and benchmark category.
Growth from 10 → 100 capabilities is *adding taxonomy nodes*, never re-architecting.

## Alternatives

1. **Stay mechanism-first (tools/engines).** Rejected: does not scale in
   comprehensibility; "toolkit" hides the cognitive model; no stable taxonomy to grow
   against.
2. **Capability = Service only (skip Engine/Tool/Validator distinction).** Rejected:
   loses the deterministic-core / governed-surface / assured-output separation that
   makes capabilities testable and safe.
3. **Full 5 layers always.** Rejected: over-engineers trivial capabilities (the
   layer-collapse rule fixes this).

## Consequences

- The design pipeline gains the root layers before code:
  `Review → Capability Model → Cognitive Primitives → Capability Dependency Graph →
  Maturity Model → CAF Spec → Benchmark OS → ADR-0007 → ADR-0006 → Implementation`.
  The three root specs (Primitives, CDG, Maturity) are ratified first so every later
  document references one foundation — the system can reach 100+ capabilities without
  re-architecting.
- Existing components re-read cleanly under the hierarchy (proof it is not academic):
  kernel subsystems = **Services**; `safe_math` = an **Engine**; `calculator` = a
  **Tool**; CVL `arithmetic`/`expression`/`secret_leak` = **Validators**; the kernel
  hooks/audit spine remain the substrate all capabilities plug into.
- CVL/CAE Validators are re-framed as *the assurance layer of every capability*, not a
  separate subsystem — unifying the CVL v2/v3 work with this principle.
- Every future feature ADR must name the Capability it serves and its five-layer
  realization; a "tool" with no owning capability is a smell.

## Verification (design-level)

Traceability: the principle is validated by mapping the *current* system onto the
hierarchy without contradiction (done above). Adoption is the gate that lets ADR-0006
(CAF) and the Capability Model proceed. No code changes under this ADR.
