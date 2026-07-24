# Agency — Volume IV · 01 — Necessary Conditions, the Minimal Primitive & the Graph

> Pure philosophy. Objectives 2 (necessary conditions) + 3 (the minimal primitive — *the
> most important objective*, where the mission's own formula is attacked) + 7 (planning
> graph). This file carries the volume's risk: it tries to *break* `Plan = Commitment +
> Temporal Structure + Dependency` and reports what it finds.

---

## Objective 2 · Necessary conditions — what makes something a *plan*?

Removal-tests, distinguishing plan from wish / checklist / forecast / recipe / policy /
algorithm.

| Candidate | Necessary? | Test |
|---|---|---|
| **A goal** | **YES (SUPPORTED)** | no end → a structure toward nothing; that is an algorithm or a dance, not a plan |
| **Commitment** | **YES (SUPPORTED)** | no commitment → a *forecast* (what will happen) or a *wish*, not a plan (what I will make happen). The Vol III status is the seed. |
| **Dependency** (precondition structure) | **YES (SUPPORTED)** | no dependency → a *checklist / schedule* (unordered or merely time-stamped items). This is the discriminator the boundary matrix found doing the most work. |
| **Irreversibility / resource** (actions consume and foreclose) | **YES (SUPPORTED — the finding)** | no consumption/foreclosure → the "plan" is over a free, replayable field, which is *inquiry-like search*, not action-planning. Argued below. |
| **Temporal order** | **NO — DERIVED (FALSIFIED as primitive)** | ordering is *induced* by dependency + resource, not independently required; a bare temporal order with no dependency is a *schedule*, not a plan. Argued below. |
| **Revision** | NO (for the plan to *exist*); YES for closed-loop planning | a fixed, un-revisable script is still a plan (open-loop); revision is needed to *function robustly*, not to *be* a plan |
| **Optimality** | **NO** | a *bad* plan is still a plan (same result as Vols I–III: optimality is a norm, not a condition) |

## Objective 3 · The minimal primitive — attacking the mission's formula

**The hypothesis under test:** `Plan = Commitment + Temporal Structure + Dependency`
(sufficient?). The mission demanded: if not enough, name the new primitive with reasons.
The recovery returns **two corrections** — a demotion and an addition.

### Correction 1 (demotion) — Temporal Structure is *not primitive*; it is *induced*
In a plan, why is action A before action B? In the overwhelming majority of cases,
*because B depends on A's effect* (dependency) or *because A and B compete for one
resource* (mutex). Strip dependency and resource-conflict, and the remaining "temporal
order" is arbitrary — which is exactly a **schedule/calendar** (Objective 4), *not* a
plan. Therefore:

> **Temporal ordering in a plan is the induced partial order of Dependency + Resource
> constraints, not an independent primitive.** (SUPPORTED.)

Residual temporal *metric* structure — durations, deadlines, rates — is real but folds
into **Resource**: *time is the universal consumable*. A deadline is time-as-scarce; a
duration is time-as-spent. So metric-time is Resource viewed as the master clock. What is
left of "Temporal Structure" as an independent primitive is **nothing** — it is the
shadow that Dependency and Resource cast. The mission listed the shadow and omitted one
of the two bodies casting it. **The claim "Temporal Structure is a primitive of Plan" is
FALSIFIED** (demoted to derived).

### Correction 2 (addition) — a fourth primitive: **Irreversibility / Resource**
Is `Commitment + Dependency` (+ their induced temporal order) sufficient? **No.** A
structure of committed, dependency-ordered steps over a *free, replayable, non-consuming*
field is not yet a *plan of action* — it is a **search/derivation** (which is what
*inquiry* is). What a plan of action additionally requires is that its field be
**consuming and irreversible**: each action spends finite resources and *unmakes* prior
states (the "delete-effect"), so that a wrong step can render the goal **permanently
unreachable**. Reasons this is *irreducible* to Commitment + Dependency:

1. **It has its own failure modes** (file 03). *Resource collapse* (demand exceeds finite
   means) and the *local-optimum / corner-painting trap* (an irreversible step forecloses
   the goal) are failures that **cannot be generated** by missing/circular dependency or
   by weak commitment. A primitive is real iff it has failures the others cannot produce;
   Irreversibility passes this test. (SUPPORTED — the decisive argument.)
2. **It is a distinct *relation***. Dependency is *positive/enabling* (B needs A). Resource
   consumption is *negative/excluding* (A and B cannot both run; doing A destroys the
   pre-A world). Exclusion is not positive dependency re-labelled; it is its logical
   complement. Lumping both under one word "Dependency" hides precisely the structure that
   matters. (SUPPORTED.)
3. **It is the direction-of-fit signature made structural** (the deep reason, LIKELY→
   SUPPORTED). To *know* the world is to *add* a representation — monotone, non-rival,
   the world untouched. To *act* on the world is to *unmake* its prior state — non-monotone,
   rival, the world spent. Irreversibility/consumption is what world→mind *is*, expressed
   at the level of a multi-step field. It could not appear in Part I because Part I never
   touched the world.

**The recovered minimal primitive (SUPPORTED):**

> **Plan = Commitment ⊕ Dependency ⊕ Irreversibility(Resource)**, with **Temporal
> Structure = the induced partial order** of the latter two. The mission's three terms
> become three *different* terms: one kept (Commitment), one kept (Dependency), one
> **demoted** (Temporal → derived), one **added** (Irreversibility/Resource).

Tagging honestly: that `Commitment + Temporal + Dependency` is *sufficient* — **FALSIFIED**
(misses Irreversibility, mis-lists Temporal). That `Commitment + Dependency +
Irreversibility` is sufficient — **SUPPORTED** (no counterexample survived file 02; each
term has its own failure mode in file 03). Whether even this is complete for *creative* /
*open-world* plans — **UNKNOWN** (file 04, open problems).

### Why this is the valuable result, not a defeat
The mission asked to try to *break* the symmetry and prized a divergence-locating finding
over a confirmation. **Irreversibility is exactly that divergence.** Inquiry's field is
(idealizing) *ergodic* — the truth stays approachable from anywhere, observations
accumulate, you can cross-check and revise toward a fixed target. Planning's field is
*non-ergodic* — it has **absorbing/foreclosing states** (resource exhaustion, missed
irreversible windows, death) from which the goal is unreachable. **This is where Knowing
and Acting genuinely part**, and file 05 shows the parting is itself *predicted* by
direction of fit — so the theory did not merely survive, it forecast its own seam.

## Objective 7 · The planning graph — necessary vs reducible edges

```
        GOAL
          │  (a)  necessary — a plan serves a goal (Obj 2)
          ▼
     COMMITMENT      ── Vol III status, the seed
          │  (b)  necessary — the plan IS the elaboration of the commitment
          ▼
        PLAN  =  Commitment ⊕ Dependency ⊕ Irreversibility   (Temporal = induced)
          │  (c)  necessary-for-mattering, NOT for being (a plan can sit unexecuted)
          ▼
     EXECUTION
          │  (d)  necessary — action meets the world (shared with Vol I loop)
          ▼
     OBSERVATION     ── the shared sensor (hinge doc)
          │  (e)  necessary for CLOSED-loop; reducible for open-loop (a fixed script)
          ▼
      REVISION  ───(f)──▶ back to PLAN / COMMITMENT   (replanning)
```

**Edge verdicts:**
- **(a) Goal→Commitment, (b) Commitment→Plan — NECESSARY (the identity spine).** These
  two edges *are* what a plan is: an elaborated commitment toward a goal. Remove either
  and there is no plan. This spine is the mirror of Warrant→Inquiry: **Planning extends
  Commitment as Inquiry extends Warrant** — the symmetry's true home (file 05). SUPPORTED.
- **(c) Plan→Execution — NECESSARY for the plan to *matter*, REDUCIBLE for it to *exist*.**
  A plan on paper is a plan (belief-unasserted analogy). The Plan/Execution boundary is
  real (Objective 4). SUPPORTED.
- **(d) Execution→Observation — NECESSARY** (else ballistic/blind). Shared node. SUPPORTED.
- **(e) Observation→Revision, (f) Revision→Plan — NECESSARY for robust closed-loop
  planning; REDUCIBLE to the degenerate open-loop case** (a fixed script, "no plan
  survives contact," Clausewitz — open-loop plans are brittle but are plans). The revision
  loop is where planning becomes *most* inquiry-like (adaptive, feedback-gated). LIKELY.

**Minimal necessary subgraph = Goal→Commitment→Plan.** Everything below is the plan's
*life-cycle* (needed to function robustly) but not its *identity* — exactly as a belief's
identity does not require its assertion, only its warrant. This parallel is not decorative;
it is discharged in file 05.

## Falsifiers
The demotion of Temporal is refuted by a genuine plan whose ordering is *not* induced by
any dependency or resource constraint yet is essential (arbitrary-but-required order). The
addition of Irreversibility is refuted by (i) showing resource-collapse and corner-painting
reduce to dependency/commitment failures after all, or (ii) exhibiting a paradigm plan over
a provably free, replayable, non-consuming field. The identity-spine claim is refuted by a
plan that serves no commitment (a plan one is not at all committed to — a mere hypothetical,
which is a *plan-schema*, not a held plan).
