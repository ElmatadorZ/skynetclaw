# Decisions Requiring Evidence

> Open questions surfaced by the archaeology that **must not be answered by opinion**.
> Each names the evidence that would settle it. **No fixes, no redesign** — this only
> states what to measure before any decision. Aligns with Epic Trust ("Evidence >
> Opinion", "no change without proof"). Tags: SUPPORTED/LIKELY/SPECULATIVE/UNKNOWN.

| ID | Decision that is NOT yet justified | Evidence required to justify it |
|---|---|---|
| **DEC-1** | Whether the ≥6 evaluators are genuine duplication (consolidate) or a clean partition (keep) | A responsibility trace: for a fixed task, log which of Skeptic/Auditor/shadow_gate/calibration/decision/completion_evidence fire and on what input — measure overlap. (resolves [U-6]) |
| **DEC-2** | Whether the ≥8 memory stores are redundant | Data-flow map: what each store writes/reads, and % of facts duplicated across stores. (resolves [U-7]) |
| **DEC-3** | Whether the routers conflict or are layer-disjoint | Call-graph: for N tasks, which router decides what; detect two routers deciding the same axis. (resolves [U-8]) |
| **DEC-4** | Whether the "reflect" phase actually changes future behavior | A/B: run a task, force a reflection, re-run a related task; measure if the lesson altered output. (resolves [U-9]) |
| **DEC-5** | Whether losing the "deterministic core" was a decision or drift | Search commit history / DecisionLog for an explicit trade-off record; if none → it is drift. (resolves [U-10]) |
| **DEC-6** | Whether `first_principles`/epistemic suite descends from `FactFlagger` | Provenance: earliest commit of each epistemic module vs FactFlagger; author notes. (resolves [U-1]) |
| **DEC-7** | Whether V3's kernel consolidation is warranted by *measured* duplication cost | Quantify the cost of the current scatter (latency, drift, bug rate) before building kernels — do not build on the archaeology alone. |
| **DEC-8** | Whether any V1 gene should be *deliberately re-introduced* (e.g. single-owner discipline, deterministic gates) | Only after DEC-1..3 quantify the duplication cost; re-introduction must beat the status quo on a measured metric. |

## Standing rule for these decisions
None of DEC-1…DEC-8 may be closed as "done" on the strength of this archaeology. The
archaeology establishes **what happened** (with the tags in the sibling docs); it does
**not** establish **what should change**. Any change still requires:
`Evidence → Hypothesis → Measurement → Regression → DecisionLog` (Epic Trust), and must
be admissible under the freeze (reliability↑ or evidence↑), else deferred Post-RC.

## Cross-references
- Findings: [EVOLUTION_MAP](EVOLUTION_MAP.md), [RESPONSIBILITY_MATRIX](RESPONSIBILITY_MATRIX.md),
  [DUPLICATION_AUDIT](DUPLICATION_AUDIT.md), [COGNITIVE_DNA](COGNITIVE_DNA.md)
- Honesty: [UNKNOWNS](UNKNOWNS.md)
- Governance: `docs/EPIC_TRUST.md`, `docs/v3/DecisionLog.md`
