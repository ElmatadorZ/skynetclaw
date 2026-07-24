# Cognitive Primitives — the Instruction Set of SkynetClaw

**Version:** 0.1 (DRAFT — design only) · **Date:** 2026-07-13 · **Owner:** ElmatadorZ
**Under:** ADR-0007 (Capability-first). **Root of:** the Capability Dependency Graph
and every Capability. Nothing composes below this level.

A **Primitive** is the smallest, recomposable cognitive operation — the ISA of the
Cognitive OS. Capabilities are *compositions* of primitives (a CPU builds every
program from a fixed instruction set; SkynetClaw builds every capability from these).

---

## 1. Why primitives are the true base unit

- **Composability:** "Decision Making" is not atomic — it is `Compare + Estimate +
  Rank + Constraint-check + Risk-score + Verify`. Naming the atoms lets capabilities be
  *defined*, not just described.
- **Reuse:** `Rank` serves Decision, Risk, Forecast, Search — write it once, assure it
  once, reuse everywhere.
- **Trust propagates from here:** a primitive's *determinism class* (below) is the
  origin of every capability's trustworthiness. You cannot reason about the trust of
  "Decision" without knowing the trust of its primitives.

---

## 2. The two-axis model (refinement of the layer stack)

The layer stack `Primitive → Capability → Service → Engine → Tool → Validator` is
really **two orthogonal axes**:

```
COMPOSITION (what it is made of):   Primitive ──▶ Capability
REALIZATION (how it runs):          <node> ──▶ [Service] ──▶ Engine ──▶ Tool ──▶ Validator
```

- A **Primitive** is realized by (usually) one `Engine + Tool + Validator` — the
  Service layer collapses (it is atomic). E.g. `Calculate` = Engine `safe_math` → Tool
  `calculator` → Validator `arithmetic`.
- A **Capability** is realized by *orchestrating its primitives'* realizations, plus —
  only if the Promotion Rule (ADR-0007) is met — its own Service/Engine.

This makes the model rigorous: composition says *what*, realization says *how*, and any
node on either axis obeys the layer-collapse and promotion rules.

---

## 3. Determinism class — where trust comes from

Every primitive is tagged with how it produces its output. **This tag is the seed of
the whole assurance model** (CVL v3 / confidence × severity):

| Class | Meaning | May it BLOCK? | Confidence |
|---|---|---|---|
| **D — Deterministic** | pure computation, reproducible | yes (gates) | 1.0 |
| **P — Probabilistic** | statistical/estimative, bounded | flag, not block | measured |
| **M — Model** | LLM-backed judgment | advisory only | low, calibrated |

**Propagation law:** a composed node is **at best as trustworthy as its least
deterministic primitive.** A capability containing any `M` primitive is `M`-class
(advisory) unless the `M` result is downstream-verified by a `D` primitive. This law
flows up the Capability Dependency Graph and is what stops a confident-but-ungrounded
capability from ever gaining blocking authority.

---

## 4. The primitive catalog (the instruction set)

Signature notation: `in → out`. `evidence?` = does it emit assurance evidence (feeds
CVL/CAE). `realized-by` names a current or planned Engine.

### 4.1 Numeric & symbolic
| Primitive | Signature | Class | evidence? | Realized-by |
|---|---|---|---|---|
| **Calculate** | expression → value | D | yes | `safe_math` |
| **Estimate** | partial-data → value + range | P | yes | (planned) |
| **Normalize** | values + scale → scaled values | D | no | (planned) |
| **Aggregate** | set → summary statistic | D | yes | (planned) |
| **Score** | item + rubric → number | D/P | yes | (planned) |

### 4.2 Relational & ordering
| Primitive | Signature | Class | evidence? | Realized-by |
|---|---|---|---|---|
| **Compare** | a, b → ordering / delta | D | yes | (planned) |
| **Rank** | items + key → ordered list | D | yes | (planned) |
| **Filter** | set + predicate → subset | D | no | `grep`-class |
| **Classify** | item → label + confidence | M/P | yes | model |
| **Detect** | signal + pattern → hit + span | D/P | yes | `secret_leak`-class |

### 4.3 Inferential & predictive
| Primitive | Signature | Class | evidence? | Realized-by |
|---|---|---|---|---|
| **Infer** | premises → conclusion | M/P | yes | model / logic engine |
| **Predict** | history → future + distribution | P | yes | (planned) |
| **Verify** | claim + ground-truth → bool + evidence | D | **yes (core)** | CVL validators |

### 4.4 Memory, knowledge & expression
| Primitive | Signature | Class | evidence? | Realized-by |
|---|---|---|---|---|
| **Recall** | query → stored records | D (over store) | yes | `kernel_memory` |
| **Retrieve** | query → external docs | P | yes | `web_search` |
| **Summarize** | text → shorter text | M | no | model |
| **Explain** | state → human rationale | M | no | model / CVL Explain |

*(The catalog is open — new primitives are added here first, never invented inside a
capability. A capability that needs an unlisted operation reveals a missing
primitive.)*

---

## 5. Invariants

1. **No capability computes below the primitive line.** If a capability needs a new
   atomic operation, add a Primitive here first (the "missing-instruction" signal).
2. **A primitive declares its determinism class**, and the class is verified by the
   primitive's own Validator (a `D` primitive claiming determinism must be reproducible
   under test).
3. **Trust flows up, never manufactured down** (§3 propagation law).
4. **Primitives are the unit of reuse and of assurance** — assure the atom once, inherit
   it everywhere it composes.
