# ADR-0013 — Cognitive Constitutional Architecture

> *A system endures not because its implementation remains unchanged, but because its
> identity, semantics, and governance evolve deliberately under explicit constitutional
> constraints.*

- **Status:** Proposed — finalized for the amendment **ceremony** (an agent may propose;
  only the operator ratifies — Constitution Kernel §4, Article 7)
- **Date:** 2026-07-19 · **Blast radius:** Foundational (the constitutional identity of SkynetClaw)
- **Constitution:** stages Articles in [Constitution.md](../v3/kernels/Constitution.md) §9, pending ceremony
- **Supersedes (in title/scope):** the "Resource Subordination" draft — now **Chapter 2** herein
- **Renumber:** the earlier State Consolidation proposal → **ADR-0014**
- **Related:** ADR-0002 (CVL), 0003 (Cognitive Kernel), 0007 (Capability-first), 0008 (Logic Engine),
  0010 (Self-Improvement / frozen anchor), 0011 (DIF), 0012 (DIC)

## Context

This ADR is the crystallization of a long design dialogue. It began as *"the architecture
must not depend on a specific model,"* generalized to *"a model is one replaceable resource,"*
deepened to *"what is permanent is not components but semantics,"* and resolved to its final
form: **the thing that endures is not any layer, but the disciplined, evidence-anchored
process by which the system's identity, meaning, and governance evolve.** SkynetClaw is not
an application built around a model. It is a **Cognitive Operating System** whose constitution
outlives every model, framework, language, and verification method beneath it.

## Decision

### The crown — two axes, not one root
The top of the architecture is **not a single node**. It is a duality: what the system *is*,
and what governs how the system *changes*.

| | Axis | Definition | If it changes |
|---|---|---|---|
| **Identity** | Existential | the DNA that makes the system *itself* ("architecture governs through explicit semantics and replaceable capability providers") | the system **dies** (becomes a different system) |
| **Highest-order Constraint** | Governance | the rule that governs change to everything below (the Constitution's amend rule) | **widest blast radius** — it re-governs all future change |

Nothing is *immutable*. Even the Highest-order Constraint can change (a Constitution v2) — it
is simply the change with the **highest blast radius**, therefore the highest cost and the
last resort. There is no sacred untouchable node; there is a hierarchy of change-cost.

### The layered stack (build order)
```
        IDENTITY  ✕  HIGHEST-ORDER CONSTRAINT     (the crown — existential ✕ governance)
              │
              ▼   Telos (purpose)
              ▼   Core Semantics             — define identity; change only by ceremony (maximally stable)
              ▼   Architectural Contracts     — FORMAL / machine-checkable, never prose (prose rots)
              ▼   Capability Model
              ▼   Capability Providers         — models, tools, memory, datastores, simulators,
              │                                  humans, future AI — all REPLACEABLE
              ▼   Conformance Evidence          — test | formal verification | model checking |
              │                                  runtime monitoring | shadow deploy | human audit
              ▼   Operational Semantics         — evolutionary (RVL→CVL→DIC lived here)
              ▼   Implementation                — most volatile
```

### The cycle — a Living Constitution, not a tree
The stack above is only *build order*. **Survival is a cycle:** what is below must feed back
up to evolve what is above — deliberately, under ceremony.
```
   Implementation → Conformance Evidence → Governance Review → Constitutional Amendment → Core Semantics
        ▲                                                                                      │
        └──────────────────────────────────────────────────────────────────────────────────┘
```
Evidence does not terminate at evidence; it is the fuel that, *through ceremony*, updates
meaning. This is what makes a Cognitive OS alive rather than static.

### The anti-circularity anchor (the guard that makes the cycle safe)
A feedback loop from evidence to semantics is exactly where **circular self-improvement**
fails — a system that "improves" only at satisfying its own drifting standard, with no anchor
to reality (ADR-0010). Therefore:

> **The upward path (Evidence → Governance → Semantics) MUST pass through an external,
> held-out anchor the loop cannot edit** — a frozen ground-truth suite + a neutral judge
> (ADR-0010's pattern). Self-generated evidence may never, by itself, satisfy the burden of
> proof for changing identity or core semantics. Otherwise the Living Constitution
> degenerates into a constitution that ratifies its own drift.

## Chapter 1 — The Semantic Constitution
1. **Core Semantics define the identity** of the system and change only by constitutional
   amendment (maximally stable, not immutable).
2. **Contracts formalize semantics** — machine-checkable specifications, not prose.
3. **Capability Contracts describe how semantics may be fulfilled** (`native | emulate |
   degrade | refuse`), never boolean feature-flags.
4. **Providers implement capabilities and are replaceable.**
5. **Conformance Evidence verifies** that implementations satisfy contracts — of any kind
   (test, formal proof, monitoring, audit); evidence is *proof*, never the contract itself.
6. **Operational semantics may evolve** (extend, not replace) without violating core semantics;
   a *breaking* change is a versioned, ceremony-gated event.
7. **Constitutional amendments govern changes to core semantics** — explicit, reviewable,
   versioned, and (per the anchor) externally evidenced.

## Chapter 2 — Resource Subordination (a corollary)
The architecture governs; resources participate. A **resource** (model, tool, external
datastore, simulator, human reviewer, future AI) is an external, swappable **Capability
Provider** invoked through a Contract, replaceable without changing the architecture. The
architecture declares *capabilities required* — never a provider name or API. Reasoning,
Validation (CVL), Memory, and Policy belong to the architecture; a provider only supplies
capabilities. The architecture owns every final decision for **decidable** problems (the
provider is a Candidate Generator); **generative** tasks are *governed*, not decided.

Persistence is a **capability** (SQLite → Postgres → S3 → event store are interchangeable
providers). The institutional *source of truth* is not the database technology but the
**truth semantic** (single, append-only, ordered) — architecture, protected by §7, not a
swappable resource.

## Design order (reason in this order; never skip layers)
```
Mission → Intent → Policy → Cognitive Contract → Capability Requirements
       → Capability Orchestration → Resource Allocation → Execution
       → Validation → Learning → Evolution
```

## Evidence (measured across this review)
- Cognitive core imports **no** model client (`grep -rE "openai|ollama|anthropic|httpx"
  logic/ decision_intelligence/ capabilities/ cognitive_validation.py` → empty). The
  model-independence invariant already holds.
- Five capability-provider silos already exist (`capability_skill_registry`, `llm_adapter` +
  `model_manager`, `builtin_tools`, DIC `registry`) → rule-of-three for a unified Capability
  Contract is **met**; no unified abstraction exists yet (`class *Resource` → empty).
- "Validation" *operational* semantics evolved across ADR-0001→0002→0004→0005→0006, while its
  *core* semantic ("verify cognition before acting") held — evidence that meaning is layered.
- A conformance-evidence + frozen-anchor pattern already exists (`test_golden_behaviors.py`,
  ADR-0010's held-out anchor) — the Living-Constitution guard is not aspirational.
- **Unknown (stated):** ROI of converging the five silos is unproven until attempted;
  "human-as-provider" has no formal implementation today (only `ask_user_options`).

## Verification (executable constitution)
- **CI tripwire #1:** cognitive core imports no provider client (empty grep — holds today).
- **CI tripwire #2:** no module outside the truth-store owner writes `skynerclaw.db` / the journal.
- **Rule:** a Contract with an unmet clause resolves to `degrade`/`refuse` — never a silent wrong answer.
- **Rule:** an amendment to identity/core semantics requires **externally-anchored** evidence.

## Burden of proof (the closing constraint)
> This ADR defines the constitutional identity of SkynetClaw. Future changes should
> **challenge its implementation before challenging its principles.** Amendments to these
> principles require **evidence — externally anchored, from real operational conditions —
> that the current constitution can no longer preserve the system's identity.**

Consequently: code problem → fix code; contract problem → fix contract; semantics problem →
produce anchored evidence; identity/principle change → prove the current constitution can no
longer hold the system's identity. Changing the top of the architecture is the **last
resort**, never the first move.

## When to stop (fixed point)
A fixed point is not "nothing left to think" but "**nothing that should be thought before
acting**" — the point where the marginal value of discussion falls below the marginal value
of friction with reality. This ADR marks it.

## Migration (ratify → pay the real debt)
1. **Ratify** this ADR as the constitutional criterion (operator ceremony).
2. **ADR-0014 — State Consolidation:** retire the 6-DB / 27-JSON drift toward "one truth" —
   the place where the *explicit-semantics* identity is violated in code today.
3. **Judge every later change against this ADR.**
4. **Challenge it only with anchored, real-operational evidence — never prediction.**

## Follow-ups
- **ADR-0014** — State Consolidation & Single-Truth.
- **ADR-0015** — Capability-Contract spine (the five silos converge; reuse the
  `capability_skill_registry` resolve→bind pattern). Done-criterion: a conformance-evidence suite.
