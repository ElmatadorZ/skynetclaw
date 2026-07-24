# Unknowns — what the evidence does NOT establish

> Mission Step 9 honesty: everything here is explicitly **UNKNOWN** or lower-confidence,
> so no conclusion in the other archaeology docs is overstated. If new evidence
> (intermediate commits, older files, author notes) appears, these can be resolved.

## Provenance / lineage (UNKNOWN)
- **U-1** Whether the current epistemic suite (`first_principles/belief_revision/theory/
  experiment/…`) was *derived from* `FactFlagger` or conceived independently. No code
  comment links them. Lineage is inferred by responsibility only. **UNKNOWN.**
- **U-2** Whether `compound_mind.py`'s "L3/L6" concept descends from V1's `CompoundMind`
  or is a new abstraction that merely reused the name. The docstring implies re-wiring an
  existing protocol but does not cite V1. **LIKELY-reuse, provenance UNKNOWN.**
- **U-3** The intermediate "Generation 2" (protocol living in skill prompt text + a
  workflow endpoint) is asserted by one docstring; the *actual* Gen-2 code is not in view.
  Its shape is **UNKNOWN** beyond that sentence.

## Missing artifacts (UNKNOWN)
- **U-4** Are there V1.x versions between `genesis_mind_compound.py` and the current repo?
  Not provided. The timeline's Gen-1→Gen-2 transition is **inferred, not observed.**
- **U-5** Whether "Alternative Slowbar" (a V1 seed brand) survives anywhere in the current
  system. Grep found brand text in `prompts/*` and skills but did not confirm this
  specific brand. **UNKNOWN.**

## Responsibility internals (LIKELY, needs deeper read)
- **U-6** The *degree of overlap* among the ≥6 evaluators (Skeptic/Auditor/shadow_gate/
  calibration/decision/completion_evidence) — whether they truly duplicate or partition
  cleanly. This audit read their *names/roles*, not their full logic. **LIKELY overlap,
  extent UNKNOWN.**
- **U-7** Same for the ≥8 memory stores: how much data is genuinely redundant vs
  legitimately partitioned by access pattern. **UNKNOWN without a data-flow trace.**
- **U-8** Whether the routers truly conflict or operate at disjoint layers (skill vs
  runtime vs tool vs source). Layer-disjoint routing is *not* duplication. **UNKNOWN
  without a call-graph.**

## Behavior claims (LIKELY, not proven here)
- **U-9** Whether the current loop actually *reflects* (writes lessons that change later
  runs) or merely *names* a reflect phase — i.e., whether V1's "aspirational stage"
  anti-pattern recurs. This archaeology did not execute the loop. **LIKELY-recurs (given
  the Reality-Awareness grounding gap found earlier), but UNPROVEN here.**
- **U-10** Whether the "deterministic core" loss is *by design* (accepted trade-off) or
  *by drift* (unintended). No decision record found either way. **UNKNOWN.**

## Scope not examined (UNKNOWN)
- **U-11** `agent_council.py` internal deliberation/voting logic vs V1's single-agent
  route — read at the roster level only.
- **U-12** The `workflow/` engine's relationship to `agentic_workflow.py` (two planning
  surfaces) — not disambiguated.

> Rule: any statement in the sibling docs that depends on U-1…U-12 is tagged LIKELY or
> SPECULATIVE there, never SUPPORTED.
